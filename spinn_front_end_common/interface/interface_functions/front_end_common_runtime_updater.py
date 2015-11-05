from spinnman.messages.sdp.sdp_flag import SDPFlag
from spinnman.messages.sdp.sdp_header import SDPHeader
from spinnman.messages.sdp.sdp_message import SDPMessage
from spinnman.model.cpu_state import CPUState
from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.utilities import constants
import struct


class FrontEndCommonRuntimeUpdater(object):
    """
    FrontEndCommonRuntimeUpdater: function to update the runtime of an
    application running on a spinnaker machine
    """

    def __call__(
            self, placements, txrx, no_sync_changes, app_id,
            executable_targets, graph_mapper):

        if (no_sync_changes + 1) % 2 == 0:
            next_sync_state = CPUState.SYNC0
        else:
            next_sync_state = CPUState.SYNC1

        # check that the right number of processors are in sync0
        processors_ready = txrx.get_core_state_count(app_id, next_sync_state)
        total_processors = executable_targets.total_processors
        all_core_subsets = executable_targets.all_core_subsets

        while processors_ready != total_processors:
            unsuccessful_cores = helpful_functions.get_cores_not_in_state(
                all_core_subsets, next_sync_state, txrx)

            for (x, y, p) in unsuccessful_cores:
                subvertex = placements.get_subvertex_on_processor(x, y, p)
                vertex = graph_mapper.get_vertex_from_subvertex(subvertex)
                steps = vertex.no_machine_time_steps
                data = struct.pack("<II", constants.SDP_RUNTIME_ID_CODE, steps)
                txrx.send_sdp_message(SDPMessage(SDPHeader(
                    flags=SDPFlag.REPLY_NOT_EXPECTED,
                    destination_cpu=p,
                    destination_chip_x=x,
                    destination_port=
                    constants.SDP_RUNNING_COMMAND_DESTINATION_PORT,
                    destination_chip_y=y), data=data))

            processors_ready = txrx.get_core_state_count(
                app_id, next_sync_state)

        no_sync_changes += 1
        return {'no_sync_changes': no_sync_changes}

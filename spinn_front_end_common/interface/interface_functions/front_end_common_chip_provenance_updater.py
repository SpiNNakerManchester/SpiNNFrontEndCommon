from spinnman.messages.sdp.sdp_flag import SDPFlag
from spinnman.messages.sdp.sdp_header import SDPHeader
from spinnman.messages.sdp.sdp_message import SDPMessage
from spinnman.model.cpu_state import CPUState
from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.utilities import constants
import struct


class FrontEndCommonChipProvenanceUpdater(object):
    """ Updates the runtime of an application running on a spinnaker machine
    """

    def __call__(
            self, placements, txrx, app_id, executable_targets, graph_mapper):

        # check that the right number of processors are in sync
        processors_completed = \
            txrx.get_core_state_count(app_id, CPUState.FINISHED)
        total_processors = executable_targets.total_processors
        all_core_subsets = executable_targets.all_core_subsets

        # check that all cores are in the state CPU_STATE_12 which shows that
        # the core has received the message and done provenance updating
        while processors_completed != total_processors:
            unsuccessful_cores = helpful_functions.get_cores_not_in_state(
                all_core_subsets, CPUState.FINISHED, txrx)

            for (x, y, p) in unsuccessful_cores:
                subvertex = placements.get_subvertex_on_processor(x, y, p)
                vertex = graph_mapper.get_vertex_from_subvertex(subvertex)
                infinite_run = 0
                steps = vertex.no_machine_time_steps
                if steps is None:
                    infinite_run = 1
                    steps = 0

                data = struct.pack(
                    "<III",
                    constants.SDP_RUNNING_MESSAGE_CODES.
                    SDP_UPDATE_PROVENCE_REGION_AND_EXIT.value,
                    steps, infinite_run)
                txrx.send_sdp_message(SDPMessage(SDPHeader(
                    flags=SDPFlag.REPLY_NOT_EXPECTED,
                    destination_cpu=p,
                    destination_chip_x=x,
                    destination_port=(
                        constants.SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value),
                    destination_chip_y=y), data=data))

            processors_completed = txrx.get_core_state_count(
                app_id, CPUState.FINISHED)

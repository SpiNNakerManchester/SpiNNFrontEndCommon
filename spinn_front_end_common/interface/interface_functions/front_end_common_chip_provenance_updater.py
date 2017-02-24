from spinn_machine.utilities.progress_bar import ProgressBar

from spinnman.messages.sdp.sdp_flag import SDPFlag
from spinnman.messages.sdp.sdp_header import SDPHeader
from spinnman.messages.sdp.sdp_message import SDPMessage
from spinnman.model.cpu_state import CPUState

from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.abstract_models\
    .abstract_binary_uses_simulation_run import AbstractBinaryUsesSimulationRun

import struct


class FrontEndCommonChipProvenanceUpdater(object):
    """ Forces all cores to generate provenance data, and then exit
    """

    __slots__ = []

    def __call__(
            self, txrx, app_id, placements, graph_mapper=None):

        # Get the placements that are compatible with provenance updating
        matching_placements, _ = helpful_functions.get_placements_by_run_type(
            placements, graph_mapper, AbstractBinaryUsesSimulationRun)
        matching_subsets = helpful_functions.get_placement_core_subsets(
            matching_placements)

        # check that the right number of processors are finished
        processors_completed = txrx.get_core_state_count(
            app_id, CPUState.FINISHED)
        total_processors = len(matching_subsets)
        left_to_do_cores = total_processors - processors_completed

        progress_bar = ProgressBar(
            left_to_do_cores,
            "Forcing error cores to generate provenance data")

        # check that all cores are in the state FINISHED which shows that
        # the core has received the message and done provenance updating
        while processors_completed != total_processors:
            unsuccessful_cores = helpful_functions.get_cores_not_in_state(
                matching_subsets, CPUState.FINISHED, txrx)

            for (x, y, p) in unsuccessful_cores:
                data = struct.pack(
                    "<I", constants.SDP_RUNNING_MESSAGE_CODES.
                    SDP_UPDATE_PROVENCE_REGION_AND_EXIT.value)
                txrx.send_sdp_message(SDPMessage(SDPHeader(
                    flags=SDPFlag.REPLY_NOT_EXPECTED,
                    destination_cpu=p,
                    destination_chip_x=x,
                    destination_port=(
                        constants.SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value),
                    destination_chip_y=y), data=data))

            processors_completed = txrx.get_core_state_count(
                app_id, CPUState.FINISHED)

            left_over_now = total_processors - processors_completed
            to_update = left_to_do_cores - left_over_now
            if to_update != 0:
                progress_bar.update(to_update)
        progress_bar.end()

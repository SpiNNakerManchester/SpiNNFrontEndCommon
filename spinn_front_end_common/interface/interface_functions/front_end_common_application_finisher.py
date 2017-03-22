import struct

from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utilities import exceptions
from spinn_machine.core_subsets import CoreSubsets
from spinn_front_end_common.abstract_models.abstract_requires_stop_command \
    import AbstractRequiresStopCommand

from spinnman.messages.sdp.sdp_flag import SDPFlag
from spinnman.messages.sdp.sdp_header import SDPHeader
from spinnman.messages.sdp.sdp_message import SDPMessage
from spinnman.model.enums.cpu_state import CPUState
from spinn_machine.utilities.progress_bar import ProgressBar


class FrontEndCommonApplicationFinisher(object):

    __slots__ = []

    def __call__(self, app_id, txrx, placements, graph_mapper=None):

        total_processors = 0
        all_core_subsets = CoreSubsets()
        for placement in placements.placements:
            app_vertex = (
                graph_mapper.get_application_vertex(placement.vertex)
                if graph_mapper is not None else None
            )
            if ((app_vertex is not None and
                    isinstance(app_vertex, AbstractRequiresStopCommand)) or
                    isinstance(placement.vertex, AbstractRequiresStopCommand)):
                all_core_subsets.add_processor(
                    placement.x, placement.y, placement.p)
            total_processors += 1

        progress_bar = ProgressBar(
            total_processors,
            "Turning off all the cores within the simulation")

        # check that the right number of processors are finished
        processors_finished = txrx.get_core_state_count(
            app_id, CPUState.FINISHED)
        finished_cores = processors_finished

        while processors_finished != total_processors:

            if processors_finished > finished_cores:
                progress_bar.update(
                    finished_cores - processors_finished)
                finished_cores = processors_finished

            processors_rte = txrx.get_core_state_count(
                app_id, CPUState.RUN_TIME_EXCEPTION)
            processors_watchdogged = txrx.get_core_state_count(
                app_id, CPUState.WATCHDOG)

            if processors_rte > 0 or processors_watchdogged > 0:
                raise exceptions.ExecutableFailedToStopException(
                    "{} of {} processors went into an error state when"
                    " shutting down".format(
                        processors_rte + processors_watchdogged,
                        total_processors))

            successful_cores_finished = txrx.get_cores_in_state(
                all_core_subsets, CPUState.FINISHED)

            for core_subset in all_core_subsets:
                for processor in core_subset.processor_ids:
                    if not successful_cores_finished.is_core(
                            core_subset.x, core_subset.y, processor):
                        byte_data = struct.pack(
                            "<I",
                            constants.SDP_RUNNING_MESSAGE_CODES
                            .SDP_UPDATE_PROVENCE_REGION_AND_EXIT.value)

                        txrx.send_sdp_message(SDPMessage(
                            sdp_header=SDPHeader(
                                flags=SDPFlag.REPLY_NOT_EXPECTED,
                                destination_port=(
                                    constants.SDP_PORTS
                                    .RUNNING_COMMAND_SDP_PORT.value),
                                destination_cpu=processor,
                                destination_chip_x=core_subset.x,
                                destination_chip_y=core_subset.y),
                            data=byte_data))

            processors_finished = txrx.get_core_state_count(
                app_id, CPUState.FINISHED)

        progress_bar.end()

import struct

from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utilities import exceptions

from spinnman.messages.sdp.sdp_flag import SDPFlag
from spinnman.messages.sdp.sdp_header import SDPHeader
from spinnman.messages.sdp.sdp_message import SDPMessage
from spinnman.model.enums.cpu_state import CPUState
from spinn_machine.utilities.progress_bar import ProgressBar


class FrontEndCommonApplicationFinisher(object):

    __slots__ = []

    def __call__(self, app_id, txrx, executable_targets, has_ran):

        if not has_ran:
            raise exceptions.ConfigurationException(
                "The ran token is not set correctly, please fix and try again")

        total_processors = executable_targets.total_processors
        all_core_subsets = executable_targets.all_core_subsets

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

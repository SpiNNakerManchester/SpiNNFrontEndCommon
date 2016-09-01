from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utilities import exceptions

from spinnman.messages.sdp.sdp_flag import SDPFlag
from spinnman.messages.sdp.sdp_header import SDPHeader
from spinnman.messages.sdp.sdp_message import SDPMessage
from spinnman.model.cpu_state import CPUState

from spinn_machine.utilities.progress_bar import ProgressBar

import struct


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

        # check that the right number of processors are in sync0
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
                error_cores = helpful_functions.get_cores_in_state(
                    all_core_subsets,
                    {CPUState.RUN_TIME_EXCEPTION, CPUState.WATCHDOG}, txrx)
                fail_message = helpful_functions.get_core_status_string(
                    error_cores)
                raise exceptions.ExecutableFailedToStopException(
                    "{} of {} processors went into an error state when"
                    " shutting down: {}".format(
                        processors_rte + processors_watchdogged,
                        total_processors, fail_message),
                    helpful_functions.get_core_subsets(error_cores), True)

            successful_cores_finished = set(
                helpful_functions.get_cores_in_state(
                    all_core_subsets, CPUState.FINISHED, txrx))

            all_cores = set(all_core_subsets)
            unsuccessful_cores = all_cores - successful_cores_finished

            for core_subset in unsuccessful_cores:
                for processor in core_subset.processor_ids:
                    byte_data = struct.pack(
                        "<I",
                        constants.SDP_RUNNING_MESSAGE_CODES.SDP_STOP_ID_CODE
                        .value)

                    txrx.send_sdp_message(SDPMessage(
                        sdp_header=SDPHeader(
                            flags=SDPFlag.REPLY_NOT_EXPECTED,
                            destination_port=(
                                constants.SDP_PORTS.RUNNING_COMMAND_SDP_PORT.
                                value),
                            destination_cpu=processor,
                            destination_chip_x=core_subset.x,
                            destination_chip_y=core_subset.y), data=byte_data))

            processors_finished = txrx.get_core_state_count(
                app_id, CPUState.FINISHED)

        progress_bar.end()

from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utilities import exceptions

from spinnman.messages.scp.scp_signal import SCPSignal
from spinnman.messages.sdp.sdp_flag import SDPFlag
from spinnman.messages.sdp.sdp_header import SDPHeader
from spinnman.messages.sdp.sdp_message import SDPMessage
from spinnman.model.cpu_state import CPUState

from pacman.utilities.utility_objs.progress_bar import ProgressBar

import struct


class FrontEndCommonApplicationExiter(object):
    """
    FrontEndCommonApplicationExiter
    """

    def __call__(self, app_id, txrx, executable_targets, no_sync_changes,
                 has_ran):

        if not has_ran:
            raise exceptions.ConfigurationException(
                "The ran token is not set correctly, please fix and try again")

        total_processors = executable_targets.total_processors
        all_core_subsets = executable_targets.all_core_subsets

        # reset the state to the old state so that it can be used by the
        # application runner code
        if no_sync_changes % 2 == 0:
            sync_state = SCPSignal.SYNC0
        else:
            sync_state = SCPSignal.SYNC1

        progress_bar = ProgressBar(
            total_processors,
            "Turning off all the cores within the simulation")

        # check that the right number of processors are in sync0
        processors_cpu_state13 = txrx.get_core_state_count(
            app_id, CPUState.CPU_STATE_13)
        finished_cores = processors_cpu_state13

        while processors_cpu_state13 != total_processors:

            if processors_cpu_state13 > finished_cores:
                progress_bar.update(
                    finished_cores - processors_cpu_state13)
                finished_cores = processors_cpu_state13

            processors_rte = txrx.get_core_state_count(
                app_id, CPUState.RUN_TIME_EXCEPTION)
            processors_watchdogged = txrx.get_core_state_count(
                app_id, CPUState.WATCHDOG)

            if processors_rte > 0 or processors_watchdogged > 0:
                fail_message = ""
                if processors_rte > 0:
                    rte_cores = helpful_functions.get_cores_in_state(
                        all_core_subsets, CPUState.RUN_TIME_EXCEPTION, txrx)
                    fail_message += helpful_functions.get_core_status_string(
                        rte_cores)
                if processors_watchdogged > 0:
                    watchdog_cores = helpful_functions.get_cores_in_state(
                        all_core_subsets, CPUState.WATCHDOG, txrx)
                    fail_message += helpful_functions.get_core_status_string(
                        watchdog_cores)
                raise exceptions.ExecutableFailedToStopException(
                    "{} of {} processors went into an error state when"
                    " shutting down: {}".format(
                        processors_rte + processors_watchdogged,
                        total_processors, fail_message))

            successful_cores_cpu_state13 = set(
                helpful_functions.get_cores_in_state(
                    all_core_subsets, CPUState.CPU_STATE_13, txrx))

            all_cores = set(all_core_subsets)
            unsuccessful_cores = all_cores - successful_cores_cpu_state13

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
                                constants
                                .SDP_RUNNING_COMMAND_DESTINATION_PORT),
                            destination_cpu=processor,
                            destination_chip_x=core_subset.x,
                            destination_chip_y=core_subset.y), data=byte_data))

            processors_cpu_state13 = txrx.get_core_state_count(
                app_id, CPUState.CPU_STATE_13)

        txrx.send_signal(app_id, sync_state)

        progress_bar.end()

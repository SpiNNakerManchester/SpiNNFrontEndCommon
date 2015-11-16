from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.utilities import constants
from spinnman.messages.scp.scp_signal import SCPSignal

from spinnman.messages.sdp.sdp_flag import SDPFlag
from spinnman.messages.sdp.sdp_header import SDPHeader
from spinnman.messages.sdp.sdp_message import SDPMessage
from spinnman.model.cpu_state import CPUState

from pacman.utilities.utility_objs.progress_bar import ProgressBar

import copy
import struct


class FrontEndCommonApplicationExiter(object):
    """
    FrontEndCommonApplicationExiter
    """

    def __call__(self, app_id, txrx, executable_targets, no_sync_changes):

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
        processors_finished = \
            txrx.get_core_state_count(app_id, CPUState.FINISHED)
        processors_rte = \
            txrx.get_core_state_count(app_id, CPUState.RUN_TIME_EXCEPTION)
        processors_idle = \
            txrx.get_core_state_count(app_id, CPUState.IDLE)
        processors_watchdogged = \
            txrx.get_core_state_count(app_id, CPUState.WATCHDOG)
        processors_powered_down = \
            txrx.get_core_state_count(app_id, CPUState.POWERED_DOWN)
        processors_cpu_state13 = \
            txrx.get_core_state_count(app_id, CPUState.CPU_STATE_13)

        total_end_stated = \
            processors_finished + processors_idle + processors_rte + \
            processors_watchdogged + processors_powered_down + \
            processors_cpu_state13

        while total_end_stated != total_processors:

            successful_cores_finished = set(
                helpful_functions.get_cores_in_state(
                    all_core_subsets, CPUState.FINISHED, txrx))
            successful_cores_rte = set(
                helpful_functions.get_cores_in_state(
                    all_core_subsets, CPUState.RUN_TIME_EXCEPTION, txrx))
            successful_cores_idle = set(
                helpful_functions.get_cores_in_state(
                    all_core_subsets, CPUState.IDLE, txrx))
            successful_cores_watchdogged = set(
                helpful_functions.get_cores_in_state(
                    all_core_subsets, CPUState.WATCHDOG, txrx))
            successful_cores_powered_down = set(
                helpful_functions.get_cores_in_state(
                    all_core_subsets, CPUState.POWERED_DOWN, txrx))
            successful_cores_cpu_state13 = set(
                helpful_functions.get_cores_in_state(
                    all_core_subsets, CPUState.CPU_STATE_13, txrx))

            all_cores = set(copy.deepcopy(all_core_subsets))
            unsuccessful_cores = all_cores - successful_cores_finished.union(
                successful_cores_rte, successful_cores_idle,
                successful_cores_watchdogged, successful_cores_powered_down,
                successful_cores_cpu_state13)

            if total_end_stated > progress_bar._currently_completed:
                progress_bar.update(
                    progress_bar._currently_completed - total_end_stated)

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

            # check that the right number of processors are in sync0
            processors_finished = \
                txrx.get_core_state_count(app_id, CPUState.FINISHED)
            processors_rte = \
                txrx.get_core_state_count(app_id, CPUState.RUN_TIME_EXCEPTION)
            processors_idle = \
                txrx.get_core_state_count(app_id, CPUState.IDLE)
            processors_watchdogged = \
                txrx.get_core_state_count(app_id, CPUState.WATCHDOG)
            processors_powered_down = \
                txrx.get_core_state_count(app_id, CPUState.POWERED_DOWN)
            processors_cpu_state13 = \
                txrx.get_core_state_count(app_id, CPUState.CPU_STATE_13)

            total_end_stated = \
                processors_finished + processors_idle + processors_rte + \
                processors_watchdogged + processors_powered_down + \
                processors_cpu_state13

        txrx.send_signal(app_id, sync_state)

        progress_bar.end()

from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.utilities import constants

from spinnman.messages.sdp.sdp_flag import SDPFlag
from spinnman.messages.sdp.sdp_header import SDPHeader
from spinnman.messages.sdp.sdp_message import SDPMessage
from spinnman.model.cpu_state import CPUState

import copy


class FrontEndCommonApplicationExiter(object):
    """
    FrontEndCommonApplicationExiter
    """

    def __call__(self, app_id, txrx, executable_targets):

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

        total_processors = executable_targets.total_processors
        all_core_subsets = executable_targets.all_core_subsets

        total_end_stated = \
            processors_finished + processors_idle + processors_rte + \
            processors_watchdogged + processors_powered_down

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

            all_cores = set(copy.deepcopy(all_core_subsets))
            unsuccessful_cores = all_cores - successful_cores_finished.union(
                successful_cores_rte, successful_cores_idle,
                successful_cores_watchdogged, successful_cores_powered_down)

            print "unsuccessful cores are {}".format(unsuccessful_cores)

            for core_subset in unsuccessful_cores:
                for processor in core_subset.processor_ids:
                    byte_data = bytearray()
                    byte_data.append(constants.SDP_STOP_ID_CODE)

                    txrx.send_sdp_message(SDPMessage(
                        sdp_header=SDPHeader(
                            flags=SDPFlag.REPLY_NOT_EXPECTED,
                            destination_port=
                            constants.SDP_EXIT_COMMAND_DESTINATION_PORT,
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

            total_end_stated = \
                processors_finished + processors_idle + processors_rte + \
                processors_watchdogged + processors_powered_down



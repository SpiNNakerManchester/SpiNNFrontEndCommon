import logging

from spinn_front_end_common.utilities import exceptions

from spinnman.model.enums.cpu_state import CPUState
from spinnman.model.enums.executable_start_type import ExecutableStartType

logger = logging.getLogger(__name__)


class FrontEndCommonApplicationRunner(object):
    """ Ensures all cores are initialised correctly, ran, and completed\
        successfully.
    """

    __slots__ = []

    def __call__(
            self, buffer_manager, wait_on_confirmation,
            send_start_notification, notification_interface,
            executable_targets, app_id, txrx, runtime, time_scale_factor,
            loaded_reverse_iptags_token, loaded_iptags_token,
            loaded_routing_tables_token, loaded_binaries_token,
            loaded_application_data_token, no_sync_changes, time_threshold,
            has_loaded_runtime_flag, placements, graph_mapper=None,
            generate_logging_output=True):

        # check all tokens are valid
        if (not loaded_reverse_iptags_token or not loaded_iptags_token or
                not loaded_routing_tables_token or not loaded_binaries_token or
                not loaded_application_data_token or
                not has_loaded_runtime_flag):
            raise exceptions.ConfigurationException(
                "Not all valid tokens have been given in the positive state. "
                "please rerun and try again")

        if generate_logging_output:
            logger.info("*** Running simulation... *** ")

        if no_sync_changes % 2 == 0:
            sync_state = CPUState.SYNC0
        else:
            sync_state = CPUState.SYNC1

        # wait for all cores that are in a barrier to reach the barrier
        txrx.wait_for_cores_to_be_ready(
            executable_targets.get_start_core_subsets(
                ExecutableStartType.SYNC), app_id,
            [CPUState.SYNC0, CPUState.SYNC1])

        # wait for all cores that are in a barrier to reach the barrier
        txrx.wait_for_cores_to_be_ready(
            executable_targets.get_start_core_subsets(
                ExecutableStartType.USES_SIMULATION_INTERFACE), app_id,
            [sync_state])

        # wait for the other cores (which should not be at a barrier)
        # to be in running state
        txrx.wait_for_cores_to_be_ready(
            executable_targets.get_start_core_subsets(
                ExecutableStartType.RUNNING), app_id,
            [CPUState.RUNNING, CPUState.FINISHED, CPUState.PAUSED,
             CPUState.SYNC0, CPUState.SYNC1, CPUState.READY])

        # set the buffer manager into a resume state, so that if it had ran
        # before it'll work again
        buffer_manager.resume()

        # every thing is in sync0 so load the initial buffers
        buffer_manager.load_initial_buffers()

        # wait till external app is ready for us to start if required
        if notification_interface is not None and wait_on_confirmation:
            notification_interface.wait_for_confirmation()

        # collect all the cores that operate on a sync start mode
        sync_cores = executable_targets.get_start_core_subsets(
            ExecutableStartType.USES_SIMULATION_INTERFACE)
        for core_subset in executable_targets.get_start_core_subsets(
                ExecutableStartType.SYNC):
            sync_cores.add_core_subset(core_subset)

        # set off the executables that are in sync state
        txrx.start_all_cores(sync_cores, app_id, no_sync_changes)

        # when it falls out of the running, it'll be in a next sync state,
        # thus update needed
        no_sync_changes += 1

        if notification_interface is not None and send_start_notification:
            notification_interface.send_start_notification()

        if runtime is None:
            if generate_logging_output:
                logger.info("Application is set to run forever - exiting")
        else:
            txrx.wait_for_execution_to_complete(
                executable_targets.all_core_subsets, app_id,
                runtime * time_scale_factor, time_threshold)

        return True, no_sync_changes

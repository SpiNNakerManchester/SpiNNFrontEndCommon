import logging
import time

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
            has_loaded_runtime_flag):

        # check all tokens are valid
        if (not loaded_reverse_iptags_token or not loaded_iptags_token or
                not loaded_routing_tables_token or not loaded_binaries_token or
                not loaded_application_data_token or
                not has_loaded_runtime_flag):
            raise exceptions.ConfigurationException(
                "Not all valid tokens have been given in the positive state. "
                "please rerun and try again")

        logger.info("*** Running simulation... *** ")

        if no_sync_changes % 2 == 0:
            sync_state = CPUState.SYNC0
        else:
            sync_state = CPUState.SYNC1

        # wait for all cores that are in a barrier to reach the barrier
        txrx.wait_for_cores_to_be_in_state(
            executable_targets.get_start_core_subsets(
                ExecutableStartType.SYNC),
            app_id, [CPUState.SYNC0, CPUState.SYNC1])

        # wait for all cores that are in a barrier to reach the barrier
        txrx.wait_for_cores_to_be_in_state(
            executable_targets.get_start_core_subsets(
                ExecutableStartType.USES_SIMULATION_INTERFACE),
            app_id, [sync_state])

        # wait for the other cores to be in an acceptable state
        txrx.wait_for_cores_to_be_in_state(
            executable_targets.get_start_core_subsets(
                ExecutableStartType.RUNNING),
            app_id,
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
        txrx.send_signal(app_id, sync_state)
        txrx.wait_for_cores_to_be_in_state(
            sync_cores, app_id,
            [CPUState.RUNNING, CPUState.PAUSED, CPUState.FINISHED])

        # when it falls out of the running, it'll be in a next sync state,
        # thus update needed
        no_sync_changes += 1

        if notification_interface is not None and send_start_notification:
            notification_interface.send_start_notification()

        if runtime is None:
            logger.info("Application is set to run forever - exiting")
        else:
            time_to_wait = (runtime / 1000.0) + 0.1
            logger.info(
                "Application started - waiting {} seconds for it to stop"
                .format(time_to_wait))
            time.sleep(time_to_wait)

            txrx.wait_for_cores_to_be_in_state(
                executable_targets.all_core_subsets, app_id,
                [CPUState.FINISHED, CPUState.PAUSED], timeout=time_threshold)

        return True, no_sync_changes

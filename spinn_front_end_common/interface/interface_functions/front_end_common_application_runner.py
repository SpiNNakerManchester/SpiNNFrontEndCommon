import logging
import time

from spinn_front_end_common.utilities import exceptions
from spinnman.messages.scp.enums.scp_signal import SCPSignal
from spinn_front_end_common.utilities.utility_objs.executable_start_type \
    import ExecutableStartType

from spinnman.model.enums.cpu_state import CPUState

logger = logging.getLogger(__name__)


class FrontEndCommonApplicationRunner(object):
    """ Ensures all cores are initialised correctly, ran, and completed\
        successfully.
    """

    __slots__ = []

    def __call__(
            self, buffer_manager, wait_on_confirmation, send_stop_notification,
            send_start_notification, notification_interface,
            executable_targets, executable_start_type, app_id, txrx, runtime,
            time_scale_factor, loaded_reverse_iptags_token,
            loaded_iptags_token, loaded_routing_tables_token,
            loaded_binaries_token, loaded_application_data_token,
            no_sync_changes, time_threshold):

        # check all tokens are valid
        if (not loaded_reverse_iptags_token or not loaded_iptags_token or
                not loaded_routing_tables_token or not loaded_binaries_token or
                not loaded_application_data_token):
            raise exceptions.ConfigurationException(
                "Not all valid tokens have been given in the positive state")

        logger.info("*** Running simulation... *** ")

        # Get the expected state of the application, depending on the run type
        expected_states = None
        sync_signal = None
        if executable_start_type == ExecutableStartType.RUNNING:
            expected_states = [
                CPUState.RUNNING, CPUState.FINISHED, CPUState.PAUSED,
                CPUState.SYNC0, CPUState.SYNC1
            ]
        elif executable_start_type == ExecutableStartType.SYNC:
            sync_signal = SCPSignal.SYNC0
            expected_states = [CPUState.SYNC0]
        elif (executable_start_type ==
                ExecutableStartType.USES_SIMULATION_INTERFACE):
            if no_sync_changes % 2 == 0:
                expected_states = [CPUState.SYNC0]
                sync_signal = SCPSignal.SYNC0
            else:
                expected_states = [CPUState.SYNC1]
                sync_signal = SCPSignal.SYNC1

            # when it falls out of the running, it'll be in a next sync state,
            # thus update needed
            no_sync_changes += 1

        if expected_states is None:
            raise exceptions.ConfigurationException(
                "Unknown executable start type {}".format(
                    executable_start_type))

        # wait for all cores to be ready
        txrx.wait_for_cores_to_be_in_state(
            executable_targets.all_core_subsets, app_id, expected_states)

        # set the buffer manager into a resume state, so that if it had ran
        # before it'll work again
        buffer_manager.resume()

        # every thing is in sync0 so load the initial buffers
        buffer_manager.load_initial_buffers()

        # wait till external app is ready for us to start if required
        if notification_interface is not None and wait_on_confirmation:
            notification_interface.wait_for_confirmation()

        # set off the executables that are in sync state
        if sync_signal is not None:
            txrx.send_signal(app_id, sync_signal)
            txrx.wait_for_cores_to_be_in_state(
                executable_targets.all_core_subsets, app_id,
                [CPUState.RUNNING, CPUState.PAUSED, CPUState.FINISHED])

        # Send start notification
        if notification_interface is not None and send_start_notification:
            notification_interface.send_start_resume_notification()

        # Wait for the application to finish
        if runtime is None:
            logger.info("Application is set to run forever - exiting")
        else:
            time_to_wait = ((runtime * time_scale_factor) / 1000.0) + 0.1
            logger.info(
                "Application started - waiting {} seconds for it to stop"
                .format(time_to_wait))
            time.sleep(time_to_wait)

            txrx.wait_for_cores_to_be_in_state(
                executable_targets.all_core_subsets, app_id,
                [CPUState.FINISHED, CPUState.PAUSED], timeout=time_threshold)

        if (notification_interface is not None and
                send_stop_notification and runtime is not None):
            notification_interface.send_stop_pause_notification()

        return True, no_sync_changes

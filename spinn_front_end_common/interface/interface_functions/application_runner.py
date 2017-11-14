import logging
import time

from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.utilities import helpful_functions

from spinnman.messages.scp.enums import Signal
from spinnman.model.enums import CPUState

logger = logging.getLogger(__name__)


class ApplicationRunner(object):
    """ Ensures all cores are initialised correctly, ran, and completed\
        successfully.
    """

    __slots__ = []

    def __call__(
            self, buffer_manager, wait_on_confirmation, send_stop_notification,
            send_start_notification, notification_interface,
            executable_targets, executable_types, app_id, txrx, runtime,
            time_scale_factor, loaded_reverse_iptags_token,
            loaded_iptags_token, loaded_routing_tables_token,
            loaded_binaries_token, loaded_application_data_token,
            no_sync_changes, time_threshold, run_until_complete=False):

        # check all tokens are valid
        if (not loaded_reverse_iptags_token or not loaded_iptags_token or
                not loaded_routing_tables_token or not loaded_binaries_token or
                not loaded_application_data_token):
            raise ConfigurationException(
                "Not all valid tokens have been given in the positive state")

        logger.info("*** Running simulation... *** ")

        # Get the expected state of the application, depending on the run type
        expected_start_states, expected_end_states = \
            helpful_functions.determine_flow_states(
                executable_types, no_sync_changes)

        # wait for all cores to be ready
        for executable_start_type in expected_start_states.keys():
            txrx.wait_for_cores_to_be_in_state(
                executable_types[executable_start_type], app_id,
                expected_start_states[executable_start_type])

        # set the buffer manager into a resume state, so that if it had ran
        # before it'll work again
        buffer_manager.resume()

        # every thing is in sync0 so load the initial buffers
        buffer_manager.load_initial_buffers()

        # wait till external app is ready for us to start if required
        if notification_interface is not None and wait_on_confirmation:
            notification_interface.wait_for_confirmation()

        # set off the executables that are in sync state \
        # (sending to all is just as safe)
        if (ExecutableType.USES_SIMULATION_INTERFACE in
                executable_types.keys() or
                ExecutableType.SYNC in executable_types.keys()):

            # locate all signals needed to set off executables
            sync_signals, no_sync_changes = \
                self._determine_simulation_sync_signals(
                    executable_types, no_sync_changes)

            # fire all signals as required
            for sync_signal in sync_signals:
                txrx.send_signal(app_id, sync_signal)

        # verify all cores are in running states
        txrx.wait_for_cores_to_be_in_state(
            executable_targets.all_core_subsets, app_id,
            [CPUState.RUNNING, CPUState.PAUSED, CPUState.FINISHED])

        # Send start notification
        if notification_interface is not None and send_start_notification:
            notification_interface.send_start_resume_notification()

        # Wait for the application to finish
        if runtime is None and not run_until_complete:
            logger.info("Application is set to run forever - exiting")
        else:
            timeout = None
            if not run_until_complete:
                time_to_wait = ((runtime * time_scale_factor) / 1000.0) + 0.1
                logger.info(
                    "Application started - waiting {} seconds for it to stop"
                    .format(time_to_wait))
                time.sleep(time_to_wait)
                timeout = time_threshold
            else:
                logger.info("Application started - waiting until finished")

            for executable_end_type in expected_end_states.keys():
                txrx.wait_for_cores_to_be_in_state(
                    executable_types[executable_end_type], app_id,
                    expected_end_states[executable_end_type], timeout=timeout)

        if (notification_interface is not None and
                send_stop_notification and runtime is not None):
            notification_interface.send_stop_pause_notification()

        return True, no_sync_changes

    @staticmethod
    def _determine_simulation_sync_signals(executable_types, no_sync_changes):
        """ sorts out start states, and creates core subsets of the states for
        further checks.

        :param no_sync_changes: sync counter
        :param executable_types: the types of executables
        :return: the sync signal and updated no_sync_changes
        """
        sync_signals = list()

        if ExecutableType.USES_SIMULATION_INTERFACE in executable_types:
            if no_sync_changes % 2 == 0:
                sync_signals.append(Signal.SYNC0)
            else:
                sync_signals.append(Signal.SYNC1)
            # when it falls out of the running, it'll be in a next sync \
            # state, thus update needed
            no_sync_changes += 1

        # handle the sync states, but only send once if they work with \
        # the simulation interface requirement
        if ExecutableType.SYNC in executable_types:
            if Signal.SYNC0 not in sync_signals:
                sync_signals.append(Signal.SYNC0)

        return sync_signals, no_sync_changes

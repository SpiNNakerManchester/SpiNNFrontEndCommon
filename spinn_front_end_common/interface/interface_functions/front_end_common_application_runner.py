from spinnman.messages.scp.scp_signal import SCPSignal
from spinnman.model.cpu_state import CPUState

from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.abstract_models.abstract_starts_synchronized \
    import AbstractStartsSynchronized

import logging
import time
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
            has_loaded_runtime_flag, placements, graph_mapper=None):

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
        synchronized_binaries, other_binaries = \
            helpful_functions.get_executables_by_run_type(
                executable_targets, placements, graph_mapper,
                AbstractStartsSynchronized)

        # wait for all cores that are in a barrier to reach the barrier
        helpful_functions.wait_for_cores_to_be_ready(
            synchronized_binaries, app_id, txrx, sync_state)

        # wait for the other cores (which should not be at a barrier)
        # to be in running state
        helpful_functions.wait_for_cores_to_be_ready(
            other_binaries, app_id, txrx, CPUState.RUNNING)

        # set the buffer manager into a resume state, so that if it had ran
        # before it'll work again
        buffer_manager.resume()

        # every thing is in sync0 so load the initial buffers
        buffer_manager.load_initial_buffers()

        # wait till external app is ready for us to start if required
        if notification_interface is not None and wait_on_confirmation:
            notification_interface.wait_for_confirmation()

        self.start_all_cores(
            synchronized_binaries, app_id, txrx, no_sync_changes)

        # when it falls out of the running, it'll be in a next sync state,
        # thus update needed
        no_sync_changes += 1

        if notification_interface is not None and send_start_notification:
            notification_interface.send_start_notification()

        if runtime is None:
            logger.info("Application is set to run forever - exiting")
        else:
            self.wait_for_execution_to_complete(
                executable_targets, app_id, runtime, time_scale_factor, txrx,
                time_threshold)

        return True, no_sync_changes

    @staticmethod
    def start_all_cores(executable_targets, app_id, txrx, sync_state_changes):
        """
        :param executable_targets: the mapping between cores and binaries
        :param app_id: the app id that being used by the simulation
        :param sync_state_changes: the number of runs been done between setup\
                and end
        :param txrx: the python interface to the spinnaker machine
        :return: None
        """

        total_processors = executable_targets.total_processors
        all_core_subsets = executable_targets.all_core_subsets

        # check that the right number of processors are in correct sync
        if sync_state_changes % 2 == 0:
            sync_state = SCPSignal.SYNC0
        else:
            sync_state = SCPSignal.SYNC1

        # if correct, start applications
        logger.info("Starting application ({})".format(sync_state))
        txrx.send_signal(app_id, sync_state)
        sync_state_changes += 1

        # check all apps have gone into run state
        logger.info("Checking that the application has started")
        processors_running = txrx.get_core_state_count(
            app_id, CPUState.RUNNING)
        if processors_running < total_processors:

            processors_finished = (
                txrx.get_core_state_count(app_id, CPUState.PAUSED) +
                txrx.get_core_state_count(app_id, CPUState.FINISHED))

            if processors_running + processors_finished >= total_processors:
                logger.warn("some processors finished between signal "
                            "transmissions. Could be a sign of an error")
            else:
                unsuccessful_cores = helpful_functions.get_cores_not_in_state(
                    all_core_subsets,
                    {CPUState.RUNNING, CPUState.PAUSED, CPUState.FINISHED},
                    txrx)

                # Last chance to get out of error state
                if len(unsuccessful_cores) > 0:
                    break_down = helpful_functions.get_core_status_string(
                        unsuccessful_cores)
                    raise exceptions.ExecutableFailedToStartException(
                        "Only {} of {} processors started:{}".format(
                            processors_running, total_processors, break_down),
                        helpful_functions.get_core_subsets(unsuccessful_cores))



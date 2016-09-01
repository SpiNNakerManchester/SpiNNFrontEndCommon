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
        helpful_functions.wait_for_cores_to_be_ready(
            synchronized_binaries, app_id, txrx, sync_state)
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

    def wait_for_execution_to_complete(
            self, executable_targets, app_id, runtime, time_scaling, txrx,
            time_threshold):
        """

        :param executable_targets:
        :param app_id:
        :param runtime:
        :param time_scaling:
        :param time_threshold:
        :param txrx:
        :param no_sync_state_changes: the number of runs been done between\
                setup and end
        :return:
        """

        total_processors = executable_targets.total_processors
        all_core_subsets = executable_targets.all_core_subsets

        time_to_wait = ((runtime * time_scaling) / 1000.0) + 0.1
        logger.info(
            "Application started - waiting {} seconds for it to stop".format(
                time_to_wait))
        time.sleep(time_to_wait)
        processors_not_finished = total_processors
        start_time = time.time()

        retries = 0
        while (processors_not_finished != 0 and
                not self._has_overrun(start_time, time_threshold)):
            try:
                processors_rte = txrx.get_core_state_count(
                    app_id, CPUState.RUN_TIME_EXCEPTION)
                processors_wdog = txrx.get_core_state_count(
                    app_id, CPUState.WATCHDOG)
                if processors_rte > 0 or processors_wdog > 0:
                    error_cores = helpful_functions.get_cores_in_state(
                        all_core_subsets,
                        {CPUState.RUN_TIME_EXCEPTION, CPUState.WATCHDOG}, txrx)
                    break_down = helpful_functions.get_core_status_string(
                        error_cores)
                    raise exceptions.ExecutableFailedToStopException(
                        "{} cores have gone into an error state:"
                        "{}".format(processors_rte, break_down),
                        helpful_functions.get_core_subsets(error_cores), True)

                processors_not_finished = txrx.get_core_state_count(
                    app_id, CPUState.RUNNING)
                if processors_not_finished > 0:
                    logger.info("Simulation still not finished or failed - "
                                "waiting a bit longer...")
                    time.sleep(0.5)
            except Exception as e:
                retries += 1
                if retries >= 10:
                    logger.error("Error getting state")
                    raise e
                logger.info("Error getting state - retrying...")
                time.sleep(0.5)

        if processors_not_finished != 0:
            running_cores = helpful_functions.get_cores_in_state(
                all_core_subsets, CPUState.RUNNING, txrx)
            if len(running_cores) > 0:
                raise exceptions.ExecutableFailedToStopException(
                    "Simulation did not finish within the time allocated. "
                    "Please try increasing the machine time step and / "
                    "or time scale factor in your simulation.",
                    helpful_functions.get_core_subsets(running_cores), False)

        processors_exited = (
            txrx.get_core_state_count(app_id, CPUState.PAUSED) +
            txrx.get_core_state_count(app_id, CPUState.FINISHED))

        if processors_exited < total_processors:
            unsuccessful_cores = helpful_functions.get_cores_not_in_state(
                all_core_subsets, {CPUState.PAUSED, CPUState.FINISHED}, txrx)

            # Last chance to get out of the error state
            if len(unsuccessful_cores) > 0:
                break_down = helpful_functions.get_core_status_string(
                    unsuccessful_cores)
                raise exceptions.ExecutableFailedToStopException(
                    "{} of {} processors failed to exit successfully:"
                    "{}".format(
                        total_processors - processors_exited, total_processors,
                        break_down),
                    helpful_functions.get_core_subsets(unsuccessful_cores),
                    True)
        logger.info("Application has run to completion")

    @staticmethod
    def _has_overrun(start_time, time_threshold):
        """ Checks if the time has overrun

        :param time_threshold: How long before the time is considered to have\
                    overrun
        :return: bool
        """
        current_time = time.time()
        if current_time - start_time > time_threshold:
            return True
        else:
            return False

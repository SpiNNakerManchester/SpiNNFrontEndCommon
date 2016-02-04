from spinnman.messages.scp.scp_signal import SCPSignal
from spinnman.model.cpu_state import CPUState
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utilities import helpful_functions

import logging
import time
logger = logging.getLogger(__name__)


class FrontEndCommonApplicationRunner(object):
    """
    FrontEndCommonApplicationRunner: functionality which ensures all cores are
    initialised correctly, ran, and competed successfully.
    """

    def __call__(self, buffer_manager, wait_on_confirmation,
                 send_start_notification, notification_interface,
                 executable_targets, app_id, txrx, runtime, time_scale_factor,
                 loaded_reverse_iptags_token, loaded_iptags_token,
                 loaded_routing_tables_token, loaded_binaries_token,
                 loaded_application_data_token, no_sync_changes):

        # check all tokens are valid
        if (not loaded_reverse_iptags_token or not loaded_iptags_token or
                not loaded_routing_tables_token or not loaded_binaries_token or
                not loaded_application_data_token):
            raise exceptions.ConfigurationException(
                "Not all valid tokens have been given in the positive state. "
                "please rerun and try again")

        logger.info("*** Running simulation... *** ")

        # set the buffer manager into a resume state, so that if it had ran
        # before it'll work again
        buffer_manager.resume()

        # every thing is in sync0 so load the initial buffers
        buffer_manager.load_initial_buffers()

        self.wait_for_cores_to_be_ready(
            executable_targets, app_id, txrx, no_sync_changes)

        # wait till external app is ready for us to start if required
        if notification_interface is not None and wait_on_confirmation:
            notification_interface.wait_for_confirmation()

        self.start_all_cores(executable_targets, app_id, txrx, no_sync_changes)

        if notification_interface is not None and send_start_notification:
            notification_interface.send_start_notification()

        if runtime is None:
            logger.info("Application is set to run forever - exiting")
        else:
            self.wait_for_execution_to_complete(
                executable_targets, app_id, runtime, time_scale_factor, txrx,
                no_sync_changes)

            # when it falls out of the running, it'll be in a next sync state,
            # thus update needed
            no_sync_changes += 1

        return {'RanToken': True, "no_sync_changes": no_sync_changes}

    @staticmethod
    def wait_for_cores_to_be_ready(
            executable_targets, app_id, txrx, no_sync_state_changes):
        """

        :param executable_targets: the mapping between cores and binaries
        :param app_id: the app id that being used by the simulation
        :param no_sync_state_changes:  the number of runs been done between\
                setup and end
        :param txrx: the python interface to the spinnaker machine
        :return:
        """

        total_processors = executable_targets.total_processors
        all_core_subsets = executable_targets.all_core_subsets

        processor_c_main = txrx.get_core_state_count(
            app_id, CPUState.C_MAIN)

        # check that everything has gone though c main to reach sync0 or
        # failing for some unknown reason
        while processor_c_main != 0:
            time.sleep(0.1)
            processor_c_main = txrx.get_core_state_count(
                app_id, CPUState.C_MAIN)

        # check that the right number of processors are in correct sync
        if no_sync_state_changes % 2 == 0:
            sync_state = CPUState.SYNC0
        else:
            sync_state = CPUState.SYNC1

        # check that the right number of processors are in sync0
        processors_ready = txrx.get_core_state_count(
            app_id, sync_state)

        if processors_ready != total_processors:
            unsuccessful_cores = helpful_functions.get_cores_not_in_state(
                all_core_subsets, sync_state, txrx)

            # last chance to slip out of error check
            if len(unsuccessful_cores) != 0:
                break_down = helpful_functions.get_core_status_string(
                    unsuccessful_cores)
                raise exceptions.ExecutableFailedToStartException(
                    "Only {} processors out of {} have successfully reached "
                    "{}:{}".format(
                        processors_ready, total_processors, sync_state.name,
                        break_down), unsuccessful_cores)

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
        logger.info("Starting application")
        txrx.send_signal(app_id, sync_state)
        sync_state_changes += 1

        # check all apps have gone into run state
        logger.info("Checking that the application has started")
        processors_running = txrx.get_core_state_count(
            app_id, CPUState.RUNNING)
        if processors_running < total_processors:

            # deduce the correct state value
            if sync_state_changes % 2 == 0:
                sync_state = CPUState.SYNC0
            else:
                sync_state = CPUState.SYNC1

            processors_finished = txrx.get_core_state_count(
                app_id, sync_state)
            if processors_running + processors_finished >= total_processors:
                logger.warn("some processors finished between signal "
                            "transmissions. Could be a sign of an error")
            else:
                unsuccessful_cores = helpful_functions.get_cores_not_in_state(
                    all_core_subsets, CPUState.RUNNING, txrx)
                break_down = helpful_functions.get_core_status_string(
                    unsuccessful_cores)
                raise exceptions.ExecutableFailedToStartException(
                    "Only {} of {} processors started:{}"
                    .format(processors_running, total_processors, break_down),
                    unsuccessful_cores)

    @staticmethod
    def wait_for_execution_to_complete(
            executable_targets, app_id, runtime, time_scaling, txrx,
            no_sync_state_changes):
        """

        :param executable_targets:
        :param app_id:
        :param runtime:
        :param time_scaling:
        :param no_sync_state_changes: the number of runs been done between\
                setup and end
        :return:
        """

        total_processors = executable_targets.total_processors
        all_core_subsets = executable_targets.all_core_subsets

        time_to_wait = ((runtime * time_scaling) / 1000.0) + 1.0
        logger.info("Application started - waiting {} seconds for it to"
                    " stop".format(time_to_wait))
        time.sleep(time_to_wait)
        processors_not_finished = total_processors
        while processors_not_finished != 0:
            processors_rte = txrx.get_core_state_count(
                app_id, CPUState.RUN_TIME_EXCEPTION)
            if processors_rte > 0:
                rte_cores = helpful_functions.get_cores_in_state(
                    all_core_subsets, CPUState.RUN_TIME_EXCEPTION, txrx)
                break_down = \
                    helpful_functions.get_core_status_string(rte_cores)
                raise exceptions.ExecutableFailedToStopException(
                    "{} cores have gone into a run time error state:"
                    "{}".format(processors_rte, break_down), rte_cores)

            processors_not_finished = txrx.get_core_state_count(
                app_id, CPUState.RUNNING)
            if processors_not_finished > 0:
                logger.info("Simulation still not finished or failed - "
                            "waiting a bit longer...")
                time.sleep(0.5)

        if no_sync_state_changes % 2 == 1:
            sync_state = CPUState.SYNC0
        else:
            sync_state = CPUState.SYNC1

        processors_exited = txrx.get_core_state_count(
            app_id, sync_state)

        if processors_exited < total_processors:
            unsuccessful_cores = helpful_functions.get_cores_not_in_state(
                all_core_subsets, sync_state, txrx)
            break_down = helpful_functions.get_core_status_string(
                unsuccessful_cores)
            raise exceptions.ExecutableFailedToStopException(
                "{} of {} processors failed to exit successfully:"
                "{}".format(
                    total_processors - processors_exited, total_processors,
                    break_down), unsuccessful_cores)
        logger.info("Application has run to completion")

from spinnman.messages.scp.scp_signal import SCPSignal
from spinnman.model.cpu_state import CPUState
from spinn_front_end_common.utilities import exceptions

import logging
import time
from collections import OrderedDict
logger = logging.getLogger(__name__)


class FrontEndCommonApplicationRunner(object):
    """
    FrontEndCommonApplicationRunner
    """

    def __call__(self, buffer_manager, wait_on_confirmation,
                 send_start_notification, notification_interface,
                 executable_targets, app_id, txrx, runtime, time_scale_factor,
                 loaded_reverse_iptags_token, loaded_iptags_token,
                 loaded_routing_tables_token, loaded_binaries_token,
                 loaded_application_data_token):

        # check all tokens are valid
        if (not loaded_reverse_iptags_token or not loaded_iptags_token or
                not loaded_routing_tables_token or not loaded_binaries_token or
                not loaded_application_data_token):
            raise exceptions.ExecutableFailedToStartException(
                "Not all valid tokens have been given in the positive state. "
                "please rerun and try again")

        logger.info("*** Running simulation... *** ")
        # every thing is in sync0. load the initial buffers
        buffer_manager.load_initial_buffers()

        self.wait_for_cores_to_be_ready(executable_targets, app_id, txrx)

        # wait till external app is ready for us to start if required
        if notification_interface is not None and wait_on_confirmation:
            notification_interface.wait_for_confirmation()

        self.start_all_cores(executable_targets, app_id, txrx)

        if notification_interface is not None and send_start_notification:
            notification_interface.send_start_notification()

        if runtime is None:
            logger.info("Application is set to run forever - exiting")
        else:
            self.wait_for_execution_to_complete(
                executable_targets, app_id, runtime, time_scale_factor, txrx,
                buffer_manager)

        return {'RanToken': True}

    def wait_for_cores_to_be_ready(self, executable_targets, app_id, txrx):
        """

        :param executable_targets:
        :param app_id:
        :param txrx:
        :return:
        """

        total_processors = executable_targets.total_processors
        all_core_subsets = executable_targets.all_core_subsets

        processor_c_main = txrx.get_core_state_count(app_id,
                                                     CPUState.C_MAIN)
        # check that everything has gone though c main to reach sync0 or
        # failing for some unknown reason
        while processor_c_main != 0:
            time.sleep(0.1)
            processor_c_main = txrx.get_core_state_count(app_id,
                                                         CPUState.C_MAIN)

        # check that the right number of processors are in sync0
        processors_ready = txrx.get_core_state_count(app_id,
                                                     CPUState.SYNC0)

        if processors_ready != total_processors:
            unsuccessful_cores = self._get_cores_not_in_state(
                all_core_subsets, CPUState.SYNC0, txrx)

            # last chance to slip out of error check
            if len(unsuccessful_cores) != 0:
                break_down = self._get_core_status_string(unsuccessful_cores)
                raise exceptions.ExecutableFailedToStartException(
                    "Only {} processors out of {} have successfully reached "
                    "SYNC0:{}".format(
                        processors_ready, total_processors, break_down))

    def start_all_cores(self, executable_targets, app_id, txrx):
        """

        :param executable_targets:
        :param app_id:
        :param txrx:
        :return:
        """

        total_processors = executable_targets.total_processors
        all_core_subsets = executable_targets.all_core_subsets

        # if correct, start applications
        logger.info("Starting application")
        txrx.send_signal(app_id, SCPSignal.SYNC0)

        # check all apps have gone into run state
        logger.info("Checking that the application has started")
        processors_running = txrx.get_core_state_count(
            app_id, CPUState.RUNNING)
        if processors_running < total_processors:

            processors_finished = txrx.get_core_state_count(
                app_id, CPUState.FINISHED)
            if processors_running + processors_finished >= total_processors:
                logger.warn("some processors finished between signal "
                            "transmissions. Could be a sign of an error")
            else:
                unsuccessful_cores = self._get_cores_not_in_state(
                    all_core_subsets, CPUState.RUNNING, txrx)
                break_down = self._get_core_status_string(
                    unsuccessful_cores)
                raise exceptions.ExecutableFailedToStartException(
                    "Only {} of {} processors started:{}"
                    .format(processors_running, total_processors, break_down))

    def wait_for_execution_to_complete(
            self, executable_targets, app_id, runtime, time_scaling,
            txrx, buffer_manager):
        """

        :param executable_targets:
        :param app_id:
        :param runtime:
        :param time_scaling:
        :param buffer_manager:
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
                rte_cores = self._get_cores_in_state(
                    all_core_subsets, CPUState.RUN_TIME_EXCEPTION, txrx)
                break_down = self._get_core_status_string(rte_cores)
                raise exceptions.ExecutableFailedToStopException(
                    "{} cores have gone into a run time error state:"
                    "{}".format(processors_rte, break_down))

            processors_not_finished = txrx.get_core_state_count(
                app_id, CPUState.RUNNING)
            if processors_not_finished > 0:
                logger.info("Simulation still not finished or failed - "
                            "waiting a bit longer...")
                time.sleep(0.5)

        processors_exited = txrx.get_core_state_count(
            app_id, CPUState.FINISHED)

        if processors_exited < total_processors:
            unsuccessful_cores = self._get_cores_not_in_state(
                all_core_subsets, CPUState.FINISHED, txrx)
            break_down = self._get_core_status_string(
                unsuccessful_cores)
            raise exceptions.ExecutableFailedToStopException(
                "{} of {} processors failed to exit successfully:"
                "{}".format(
                    total_processors - processors_exited, total_processors,
                    break_down))
        if buffer_manager is not None:
            buffer_manager.stop()
        logger.info("Application has run to completion")

    @staticmethod
    def _get_cores_in_state(all_core_subsets, state, txrx):
        core_infos = txrx.get_cpu_information(all_core_subsets)
        cores_in_state = OrderedDict()
        for core_info in core_infos:
            if core_info.state == state:
                cores_in_state[
                    (core_info.x, core_info.y, core_info.p)] = core_info
        return cores_in_state

    @staticmethod
    def _get_cores_not_in_state(all_core_subsets, state, txrx):
        core_infos = txrx.get_cpu_information(all_core_subsets)
        cores_not_in_state = OrderedDict()
        for core_info in core_infos:
            if core_info.state != state:
                cores_not_in_state[
                    (core_info.x, core_info.y, core_info.p)] = core_info
        return cores_not_in_state

    @staticmethod
    def _get_core_status_string(core_infos):
        break_down = "\n"
        for ((x, y, p), core_info) in core_infos.iteritems():
            if core_info.state == CPUState.RUN_TIME_EXCEPTION:
                break_down += "    {}:{}:{} in state {}:{}\n".format(
                    x, y, p, core_info.state.name,
                    core_info.run_time_error.name)
            else:
                break_down += "    {}:{}:{} in state {}\n".format(
                    x, y, p, core_info.state.name)
        return break_down

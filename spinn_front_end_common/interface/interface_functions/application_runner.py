# Copyright (c) 2015 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
from time import sleep
import struct
from threading import Condition
from typing import Optional
from spinn_utilities.log import FormatAdapter
from spinnman.messages.scp.enums import Signal
from spinnman.model.enums import ExecutableType, CPUState
from spinnman.exceptions import SpinnmanException
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.exceptions import (
    ConfigurationException)
from spinn_front_end_common.utilities.constants import (
    MICRO_TO_MILLISECOND_CONVERSION)
from spinn_front_end_common.utilities.scp import (
    GetCurrentTimeProcess, SendPauseProcess)

SAFETY_FINISH_TIME = 0.1

logger = FormatAdapter(logging.getLogger(__name__))

_ONE_WORD = struct.Struct("<I")
_LIMIT = 10


def application_runner(
        runtime: Optional[float], time_threshold: Optional[float],
        run_until_complete: bool, state_condition: Condition) -> Optional[int]:
    """
    Ensures all cores are initialised correctly, ran, and completed
    successfully.

    :param runtime:
    :param time_threshold:
    :param run_until_complete:
    :param state_condition:
    :return:
        The current latest time-step if runtime is None and
        run_until_complete is False, else None
    :raises ConfigurationException:
    """
    return _ApplicationRunner().run_app(
        runtime, time_threshold, run_until_complete, state_condition)


class _ApplicationRunner(object):
    """
    Ensures all cores are initialised correctly, ran, and completed
    successfully.
    """

    __slots__ = ("__txrx", "__app_id")

    def __init__(self) -> None:
        self.__txrx = FecDataView.get_transceiver()
        self.__app_id = FecDataView.get_app_id()

    def run_app(
            self, runtime: Optional[float], time_threshold: Optional[float],
            run_until_complete: bool,
            state_condition: Condition) -> Optional[int]:
        """
        :param runtime:
        :param time_threshold:
        :param run_until_complete:
        :param state_condition:
        :return:
            The current latest time-step if runtime is None and
            run_until_complete is False, else None
        :raises ConfigurationException:
        """
        logger.info("*** Running simulation... *** ")

        # wait for all cores to be ready
        self._wait_for_start()

        buffer_manager = FecDataView.get_buffer_manager()
        notification_interface = FecDataView.get_notification_protocol()
        # set the buffer manager into a resume state, so that if it had ran
        # before it'll work again
        buffer_manager.resume()

        # every thing is in sync0 so load the initial buffers
        buffer_manager.load_initial_buffers()

        # clear away any router diagnostics that have been set due to all
        # loading applications
        self.__txrx.clear_router_diagnostic_counters()

        # wait till external app is ready for us to start if required
        notification_interface.wait_for_confirmation()

        # set off the executables that are in sync state
        # (sending to all is just as safe)
        self._send_sync_signal()

        # Send start notification to external applications
        notification_interface.send_start_resume_notification()

        latest_runtime = None
        if runtime is None and not run_until_complete:
            with state_condition:
                while FecDataView.is_no_stop_requested():
                    state_condition.wait()

            core_subsets = FecDataView.get_cores_for_type(
                ExecutableType.USES_SIMULATION_INTERFACE)
            n_cores = len(core_subsets)

            try:
                SendPauseProcess(
                    FecDataView.get_scamp_connection_selector()).send_pause(
                        core_subsets, n_cores)
            except SpinnmanException as e:
                # Check if cores have failed now
                rte_cores = self.__txrx.get_core_state_count(
                    self.__app_id, CPUState.RUN_TIME_EXCEPTION)

                # If there are no cores in the RTE state, then re-raise the
                # original exception, otherwise the wait_for_end will handle it
                if rte_cores == 0:
                    raise e
            self._wait_for_end()

            process = GetCurrentTimeProcess(
                FecDataView.get_scamp_connection_selector())
            latest_runtime = process.get_latest_runtime(n_cores, core_subsets)
        elif run_until_complete:
            # Wait for the application to finish
            logger.info("Application started; waiting until finished")
            self._wait_for_end()
            # This could be a run_until_complete but with a fixed number of
            # untimed steps; in that case we don't need to update the time
            if runtime is None:
                core_subsets = FecDataView.get_cores_for_type(
                    ExecutableType.USES_SIMULATION_INTERFACE)
                n_cores = len(core_subsets)
                process = GetCurrentTimeProcess(
                    FecDataView.get_scamp_connection_selector())
                latest_runtime = process.get_latest_runtime(
                    n_cores, core_subsets)
        else:
            self._run_wait(runtime, time_threshold)

        # Send stop notification to external applications
        notification_interface.send_stop_pause_notification()
        return latest_runtime

    def _run_wait(self, runtime: Optional[float],
                  time_threshold: Optional[float]) -> None:
        assert runtime is not None
        factor = (FecDataView.get_time_scale_factor() /
                  MICRO_TO_MILLISECOND_CONVERSION)
        scaled_runtime = runtime * factor
        time_to_wait = scaled_runtime + SAFETY_FINISH_TIME
        logger.info(
            "Application started; waiting {}s for it to stop",
            time_to_wait)
        sleep(time_to_wait)
        self._wait_for_end(timeout=time_threshold)

    def _wait_for_start(self, timeout: Optional[float] = None) -> None:
        for ex_type, cores in FecDataView.get_executable_types().items():
            self.__txrx.wait_for_cores_to_be_in_state(
                cores, self.__app_id, ex_type.start_state, timeout=timeout)

    def _send_sync_signal(self) -> None:
        """
        Let apps that use the simulation interface or sync signals commence
        running their main processing loops. This is done with a very fast
        synchronisation barrier and a signal.
        """
        executable_types = FecDataView.get_executable_types().keys()
        if (ExecutableType.USES_SIMULATION_INTERFACE in executable_types
                or ExecutableType.SYNC in executable_types):
            # locate all signals needed to set off executables
            sync_signal = self._determine_simulation_sync_signals()

            if sync_signal is not None:
                # fire all signals as required
                self.__txrx.send_signal(self.__app_id, sync_signal)

    def _wait_for_end(self, timeout: Optional[float] = None) -> None:
        for ex_type, cores in FecDataView.get_executable_types().items():
            self.__txrx.wait_for_cores_to_be_in_state(
                cores, self.__app_id, ex_type.end_state, timeout=timeout)

    def _determine_simulation_sync_signals(self) -> Optional[Signal]:
        """
        Determines the start states, and creates core subsets of the
        states for further checks.

        :return: the sync signal
        :raises ConfigurationException:
        """
        sync_signal = None

        executable_types = FecDataView.get_executable_types().keys()
        if ExecutableType.USES_SIMULATION_INTERFACE in executable_types:
            sync_signal = FecDataView.get_next_sync_signal()

        # handle the sync states, but only send once if they work with
        # the simulation interface requirement
        if ExecutableType.SYNC in executable_types:
            if sync_signal == Signal.SYNC1:
                raise ConfigurationException(
                    "There can only be one SYNC signal per run. This is "
                    "because we cannot ensure the cores have not reached the "
                    "next SYNC state before we send the next SYNC, resulting "
                    "in uncontrolled behaviour")
            sync_signal = Signal.SYNC0

        return sync_signal

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
import time
from spinn_utilities.log import FormatAdapter
from spinnman.messages.scp.enums import Signal
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.utilities.constants import (
    MICRO_TO_MILLISECOND_CONVERSION)

SAFETY_FINISH_TIME = 0.1

logger = FormatAdapter(logging.getLogger(__name__))


def application_runner(runtime, time_threshold, run_until_complete):
    """
    Ensures all cores are initialised correctly, ran, and completed
    successfully.

    :param int runtime:
    :param int time_threshold:
    :param bool run_until_complete:
    :raises ConfigurationException:
    """
    runner = _ApplicationRunner()
    # pylint: disable=protected-access
    runner._run(runtime, time_threshold, run_until_complete)


class _ApplicationRunner(object):
    """
    Ensures all cores are initialised correctly, ran, and completed
    successfully.
    """

    __slots__ = ["__txrx", "__app_id"]

    def __init__(self):
        self.__txrx = FecDataView.get_transceiver()
        self.__app_id = FecDataView.get_app_id()

    # Wraps up as a PACMAN algorithm
    def _run(
            self, runtime, time_threshold, run_until_complete=False):
        """
        :param int runtime:
        :param int time_threshold:
        :param bool run_until_complete:
        :return: Number of synchronisation changes
        :rtype: int
        :raises ConfigurationException:
        """
        # pylint: disable=too-many-arguments
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
        for chip in FecDataView.get_machine().chips:
            self.__txrx.clear_router_diagnostic_counters(chip.x, chip.y)

        # wait till external app is ready for us to start if required
        notification_interface.wait_for_confirmation()

        # set off the executables that are in sync state
        # (sending to all is just as safe)
        self._send_sync_signal()

        # Send start notification to external applications
        notification_interface.send_start_resume_notification()

        if runtime is None and not run_until_complete:
            # Do NOT stop the buffer manager at end; app is using it still
            logger.info("Application is set to run forever; exiting")
        else:
            # Wait for the application to finish
            self._run_wait(
                run_until_complete, runtime, time_threshold)

            # Send stop notification to external applications
            notification_interface.send_stop_pause_notification()

    def _run_wait(self, run_until_complete, runtime, time_threshold):
        """
        :param bool run_until_complete:
        :param int runtime:
        :param float time_threshold:
        """
        if not run_until_complete:
            factor = (FecDataView.get_time_scale_factor() /
                      MICRO_TO_MILLISECOND_CONVERSION)
            scaled_runtime = runtime * factor
            time_to_wait = scaled_runtime + SAFETY_FINISH_TIME
            logger.info(
                "Application started; waiting {}s for it to stop",
                time_to_wait)
            time.sleep(time_to_wait)
            self._wait_for_end(timeout=time_threshold)
        else:
            logger.info("Application started; waiting until finished")
            self._wait_for_end()

    def _wait_for_start(self, timeout=None):
        """
        :param timeout:
        :type timeout: float or None
        """
        for ex_type, cores in FecDataView.get_executable_types().items():
            self.__txrx.wait_for_cores_to_be_in_state(
                cores, self.__app_id, ex_type.start_state, timeout=timeout)

    def _send_sync_signal(self):
        """
        Let apps that use the simulation interface or sync signals commence
        running their main processing loops. This is done with a very fast
        synchronisation barrier and a signal.
        """
        executable_types = FecDataView.get_executable_types()
        if (ExecutableType.USES_SIMULATION_INTERFACE in executable_types
                or ExecutableType.SYNC in executable_types):
            # locate all signals needed to set off executables
            sync_signal = self._determine_simulation_sync_signals()

            # fire all signals as required
            self.__txrx.send_signal(self.__app_id, sync_signal)

    def _wait_for_end(self, timeout=None):
        """
        :param timeout:
        :type timeout: float or None
        """
        for ex_type, cores in FecDataView.get_executable_types().items():
            self.__txrx.wait_for_cores_to_be_in_state(
                cores, self.__app_id, ex_type.end_state, timeout=timeout)

    def _determine_simulation_sync_signals(self):
        """
        Determines the start states, and creates core subsets of the
        states for further checks.

        :return: the sync signal
        :rtype: ~.Signal
        :raises ConfigurationException:
        """
        sync_signal = None

        executable_types = FecDataView.get_executable_types()
        if ExecutableType.USES_SIMULATION_INTERFACE in executable_types:
            sync_signal = FecDataView.get_next_sync_signal()

        # handle the sync states, but only send once if they work with
        # the simulation interface requirement
        if ExecutableType.SYNC in executable_types:
            if sync_signal == Signal.SYNC1:
                raise ConfigurationException(
                    "There can only be one SYNC signal per run. This is "
                    "because we cannot ensure the cores have not reached the "
                    "next SYNC state before we send the next SYNC. Resulting "
                    "in uncontrolled behaviour")
            sync_signal = Signal.SYNC0

        return sync_signal

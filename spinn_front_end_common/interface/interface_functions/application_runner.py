# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import time
from spinn_utilities.log import FormatAdapter
from spinnman.messages.scp.enums import Signal
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.utilities.constants import (
    MICRO_TO_MILLISECOND_CONVERSION)

SAFETY_FINISH_TIME = 0.1

logger = FormatAdapter(logging.getLogger(__name__))


class ApplicationRunner(object):
    """ Ensures all cores are initialised correctly, ran, and completed\
        successfully.
    """

    __slots__ = ["__txrx", "__app_id", "__executable_types", "__syncs"]

    # Wraps up as a PACMAN algorithm
    def __call__(
            self, buffer_manager, notification_interface, executable_types,
            app_id, txrx, runtime, time_scale_factor, no_sync_changes,
            time_threshold, machine, run_until_complete=False):
        """
        :param BufferManager buffer_manager:
        :param NotificationProtocol notification_interface:
        :param executable_types:
        :type executable_types:
            dict(ExecutableType,~spinn_machine.CoreSubsets)
        :param int app_id:
        :param ~spinnman.transceiver.Transceiver txrx:
        :param int runtime:
        :param int time_scale_factor:
        :param int no_sync_changes: Number of synchronisation changes
        :param int time_threshold:
        :param ~spinn_machine.Machine machine:
            the spinn machine instance
        :param bool run_until_complete:
        :return: Number of synchronisation changes
        :rtype: int
        :raises ConfigurationException:
        """
        # pylint: disable=too-many-arguments
        logger.info("*** Running simulation... *** ")

        self.__txrx = txrx
        self.__app_id = app_id
        self.__executable_types = executable_types
        self.__syncs = no_sync_changes

        # wait for all cores to be ready
        self._wait_for_start()

        # set the buffer manager into a resume state, so that if it had ran
        # before it'll work again
        buffer_manager.resume()

        # every thing is in sync0 so load the initial buffers
        buffer_manager.load_initial_buffers()

        # clear away any router diagnostics that have been set due to all
        # loading applications
        for chip in machine.chips:
            if not chip.virtual:
                txrx.clear_router_diagnostic_counters(chip.x, chip.y)

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
            try:
                self._run_wait(
                    run_until_complete, runtime, time_scale_factor,
                    time_threshold)
            finally:
                # Stop the buffer manager after run
                buffer_manager.stop()

            # Send stop notification to external applications
            notification_interface.send_stop_pause_notification()

        return self.__syncs

    def _run_wait(self, run_until_complete, runtime, time_scale_factor,
                  time_threshold):
        """
        :param bool run_until_complete:
        :param int runtime:
        :param int time_scale_factor:
        :param float time_threshold:
        """
        if not run_until_complete:
            factor = time_scale_factor / MICRO_TO_MILLISECOND_CONVERSION
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
        for executable_type in self.__executable_types:
            self.__txrx.wait_for_cores_to_be_in_state(
                self.__executable_types[executable_type], self.__app_id,
                executable_type.start_state, timeout=timeout)

    def _send_sync_signal(self):
        """ Let apps that use the simulation interface or sync signals \
            commence running their main processing loops. This is done with \
            a very fast synchronisation barrier and a signal.
        """
        if (ExecutableType.USES_SIMULATION_INTERFACE in self.__executable_types
                or ExecutableType.SYNC in self.__executable_types):
            # locate all signals needed to set off executables
            sync_signal = self._determine_simulation_sync_signals()

            # fire all signals as required
            self.__txrx.send_signal(self.__app_id, sync_signal)

    def _wait_for_end(self, timeout=None):
        """
        :param timeout:
        :type timeout: float or None
        """
        for executable_type in self.__executable_types:
            self.__txrx.wait_for_cores_to_be_in_state(
                self.__executable_types[executable_type], self.__app_id,
                executable_type.end_state, timeout=timeout)

    def _determine_simulation_sync_signals(self):
        """ Determines the start states, and creates core subsets of the\
            states for further checks.

        :return: the sync signal
        :rtype: ~.Signal
        :raises ConfigurationException:
        """
        sync_signal = None

        if ExecutableType.USES_SIMULATION_INTERFACE in self.__executable_types:
            if self.__syncs % 2 == 0:
                sync_signal = Signal.SYNC0
            else:
                sync_signal = Signal.SYNC1
            # when it falls out of the running, it'll be in a next sync
            # state, thus update needed
            self.__syncs += 1

        # handle the sync states, but only send once if they work with
        # the simulation interface requirement
        if ExecutableType.SYNC in self.__executable_types:
            if sync_signal == Signal.SYNC1:
                raise ConfigurationException(
                    "There can only be one SYNC signal per run. This is "
                    "because we cannot ensure the cores have not reached the "
                    "next SYNC state before we send the next SYNC. Resulting "
                    "in uncontrolled behaviour")
            sync_signal = Signal.SYNC0

        return sync_signal

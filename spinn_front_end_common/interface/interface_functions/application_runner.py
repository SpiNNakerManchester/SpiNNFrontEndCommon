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

logger = FormatAdapter(logging.getLogger(__name__))


class _NotificationWrapper(object):
    def __init__(self, notification_interface, wait_on_confirmation):
        self._notifier = notification_interface
        self._wait = wait_on_confirmation and self._notifier is not None

    def wait_for_confirmation(self):
        if self._wait:
            self._notifier.wait_for_confirmation()

    def send_start_resume_notification(self):
        if self._notifier is not None:
            self._notifier.send_start_resume_notification()

    def send_stop_pause_notification(self):
        if self._notifier is not None:
            self._notifier.send_stop_pause_notification()


class ApplicationRunner(object):
    """ Ensures all cores are initialised correctly, ran, and completed\
        successfully.
    """

    __slots__ = []

    # Wraps up as a PACMAN algorithm
    def __call__(
            self, buffer_manager, wait_on_confirmation, notification_interface,
            executable_types, app_id, txrx, runtime, time_scale_factor,
            no_sync_changes, time_threshold, run_until_complete=False):
        # pylint: disable=too-many-arguments, too-many-locals
        logger.info("*** Running simulation... *** ")

        # Simplify the notifications
        notifier = _NotificationWrapper(
            notification_interface, wait_on_confirmation)

        return self.run_application(
            buffer_manager, notifier, executable_types, app_id, txrx, runtime,
            time_scale_factor, no_sync_changes, time_threshold,
            run_until_complete)

    # The actual runner
    def run_application(
            self, buffer_manager, notifier, executable_types, app_id, txrx,
            runtime, time_scale_factor, no_sync_changes, time_threshold,
            run_until_complete):
        # pylint: disable=too-many-arguments

        # wait for all cores to be ready
        self._wait_for_start(txrx, app_id, executable_types)

        # set the buffer manager into a resume state, so that if it had ran
        # before it'll work again
        buffer_manager.resume()

        # every thing is in sync0 so load the initial buffers
        buffer_manager.load_initial_buffers()

        # wait till external app is ready for us to start if required
        notifier.wait_for_confirmation()

        # set off the executables that are in sync state
        # (sending to all is just as safe)
        if (ExecutableType.USES_SIMULATION_INTERFACE in executable_types
                or ExecutableType.SYNC in executable_types):
            # locate all signals needed to set off executables
            sync_signal, no_sync_changes = \
                self._determine_simulation_sync_signals(
                    executable_types, no_sync_changes)

            # fire all signals as required
            txrx.send_signal(app_id, sync_signal)

        # Send start notification to external applications
        notifier.send_start_resume_notification()

        # Wait for the application to finish
        if runtime is None and not run_until_complete:
            logger.info("Application is set to run forever; exiting")
            # Do NOT stop the buffer manager; app is using it still
        else:
            try:
                self._run_wait(
                    txrx, app_id, executable_types, run_until_complete,
                    runtime, time_scale_factor, time_threshold)
            finally:
                # Stop the buffer manager after run
                buffer_manager.stop()

        # Send stop notification
        if runtime is not None:
            notifier.send_stop_pause_notification()

        return no_sync_changes

    def _run_wait(self, txrx, app_id, executable_types, run_until_complete,
                  runtime, time_scale_factor, time_threshold):
        # pylint: disable=too-many-arguments
        if not run_until_complete:
            time_to_wait = runtime * time_scale_factor / 1000.0 + 0.1
            logger.info(
                "Application started; waiting {}s for it to stop",
                time_to_wait)
            time.sleep(time_to_wait)
            self._wait_for_end(txrx, app_id, executable_types,
                               timeout=time_threshold)
        else:
            logger.info("Application started; waiting until finished")
            self._wait_for_end(txrx, app_id, executable_types)

    @staticmethod
    def _wait_for_start(txrx, app_id, executable_types, timeout=None):
        for executable_type in executable_types:
            txrx.wait_for_cores_to_be_in_state(
                executable_types[executable_type], app_id,
                executable_type.start_state, timeout=timeout)

    @staticmethod
    def _wait_for_end(txrx, app_id, executable_types, timeout=None):
        for executable_type in executable_types:
            txrx.wait_for_cores_to_be_in_state(
                executable_types[executable_type], app_id,
                executable_type.end_state, timeout=timeout)

    @staticmethod
    def _determine_simulation_sync_signals(executable_types, no_sync_changes):
        """ Determines the start states, and creates core subsets of the\
            states for further checks.

        :param no_sync_changes: sync counter
        :param executable_types: the types of executables
        :return: the sync signal and updated no_sync_changes
        """
        sync_signal = None

        if ExecutableType.USES_SIMULATION_INTERFACE in executable_types:
            if no_sync_changes % 2 == 0:
                sync_signal = Signal.SYNC0
            else:
                sync_signal = Signal.SYNC1
            # when it falls out of the running, it'll be in a next sync \
            # state, thus update needed
            no_sync_changes += 1

        # handle the sync states, but only send once if they work with \
        # the simulation interface requirement
        if ExecutableType.SYNC in executable_types:
            if sync_signal == Signal.SYNC1:
                raise ConfigurationException(
                    "There can only be one SYNC signal per run. This is "
                    "because we cannot ensure the cores have not reached the "
                    "next SYNC state before we send the next SYNC. Resulting "
                    "in uncontrolled behaviour")
            sync_signal = Signal.SYNC0
            no_sync_changes += 1

        return sync_signal, no_sync_changes

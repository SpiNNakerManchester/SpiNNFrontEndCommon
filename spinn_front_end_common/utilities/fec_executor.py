# Copyright (c) 2017-2018 The University of Manchester
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
import sys
import time
from datetime import timedelta
# pylint: disable=no-name-in-module
from spinn_utilities.config_holder import (get_config_bool)
from spinn_utilities.log import FormatAdapter


logger = FormatAdapter(logging.getLogger(__name__))

if sys.version_info >= (3, 7):
    # acquire the most accurate measurement available (perf_counter_ns)
    _now = time.perf_counter_ns  # pylint: disable=no-member
    # conversion factor
    _NANO_TO_MICRO = 1000.0

    def _convert_to_timedelta(time_diff):
        """ Have to convert to a timedelta for rest of code to read.

        As perf_counter_ns is nano seconds, and time delta lowest is micro,
        need to convert.
        """
        return timedelta(microseconds=time_diff / _NANO_TO_MICRO)

else:
    # acquire the most accurate measurement available (perf_counter)
    _now = time.perf_counter  # pylint: disable=no-member

    def _convert_to_timedelta(time_diff):
        """ Have to convert to a timedelta for rest of code to read.

        As perf_counter is fractional seconds, put into correct time delta.
        """
        return timedelta(seconds=time_diff)


class FecExecutor(object):

    __slots__ = [

        # The start time when the timer was set off
        "_start_time",

        # AbstractSpinnakerBase
        "_simulator",

        # Name of what is being times
        "_name",

        ]

    def __init__(self, simulator, name):
        self._start_time = None
        self._simulator = simulator
        self._name = name

    def __enter__(self):
        self._start_time = _now()
        return self

    def skip(self, reason):
        logger.info(f"{self._name} skipped as {reason}")
        self._start_time = None

    def skip_if_has_not_run(self):
        if self._simulator.has_ran:
            self.skip("simulator.has_run")
            return True
        else:
            return False

    def skip_if_virtual_board(self):
        if self._simulator.use_virtual_board:
            self.skip("simulator.use_virtual_board")
            return True
        else:
            return False

    def skip_if_value_true(self, value, name):
        if value:
            self.skip(name)
        return value

    def skip_if_value_false(self, value, name):
        if value:
            return False
        else:
            self.skip(f"{name} is False")
            return True

    def skip_if_value_is_none(self, value, name):
        if value is None:
            self.skip(f"{name} is None")
            return True
        else:
            return False

    def skip_if_cfg_false(self, section, option):
        if get_config_bool(section, option):
            return False
        else:
            self.skip(f"cfg {section}:{option} is False")
            return True

    def _stop(self, reason):
        time_taken = self._stop_timer()
        logger.info(
            f"{self._name} stopped after {time_taken} as {reason}")

    def stop_if_none(self, value, name):
        if value is None:
            self._stop(f"{name} is None")
            return True
        return False

    def stop_if_virtual_board(self):
        if self._simulator.use_virtual_board:
            self._stop("simulator.use_virtual_board")
            return True
        else:
            return False

    def _stop_timer(self):
        """ Describes how long has elapsed since the instance that the\
            :py:meth:`start_timing` method was last called.

        :rtype: datetime.timedelta
        """
        time_now = _now()
        diff = time_now - self._start_time
        self._start_time = None
        return _convert_to_timedelta(diff)

    def __exit__(self, type, value, traceback):
        if self._start_time is None:
            return False
        time_taken = self._stop_timer()
        if type is None:
            logger.info(f"Time {time_taken} taken by {self._name}")
        else:
            logger.info("{self._name} exited with {type} after {time_taken}")
        return False


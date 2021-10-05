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
import os
import sys
import time
from datetime import timedelta
# pylint: disable=no-name-in-module
from spinn_utilities.config_holder import (get_config_bool)
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.utilities.utility_objs import ProvenanceDataItem

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

_simulator = None
_provenance_path = None


class FecTimer(object):

    __slots__ = [

        # The start time when the timer was set off
        "_start_time",

        # Name of what is being times
        "_name",

        ]

    @classmethod
    def setup(cls, simulator):
        global _simulator, _provenance_path, _print_timings
        _simulator = simulator
        if get_config_bool("Reports", "write_algorithm_timings"):
            _provenance_path = os.path.join(
                simulator._report_default_directory,
                "algorithm_timings.rpt")
        else:
            _provenance_path = None
        _print_timings = get_config_bool(
            "Reports", "display_algorithm_timings")
        cls.clear_provenance()

    @classmethod
    def get_provenance(cls):
        global _provenance_items
        return _provenance_items

    @classmethod
    def clear_provenance(cls):
        global _provenance_items
        _provenance_items = list()

    def __init__(self, name):
        self._start_time = None
        self._name = name

    def __enter__(self):
        self._start_time = _now()
        return self

    def _report(self, message):
        if _provenance_path is not None:
            with open(_provenance_path, "a") as provenance_file:
                provenance_file.write(f"{message}\n")
        if _print_timings:
            logger.info(message)

    def skip(self, reason):
        message = f"{self._name} skipped as {reason}"
        self._report(message)
        self._start_time = None

    def skip_if_has_not_run(self):
        if _simulator.has_ran:
            return False
        else:
            self.skip("simulator.has_run")
            return True

    def skip_if_virtual_board(self):
        if _simulator.use_virtual_board:
            self.skip("simulator.use_virtual_board")
            return True
        else:
            return False

    def skip_if_application_graph_empty(self):
        if _simulator._application_graph.n_vertices:
            return False
        else:
            self.skip("Application graph is empty")
            return True

    def skip_if_value_true(self, value, name):
        if value:
            self.skip(f"{name} is True")
        return value

    def skip_if_value_false(self, value, name):
        if value:
            return False
        else:
            self.skip(f"{name} is False")
            return True

    def skip_if_empty(self, value, name):
        if value:
            return False
        if value is None:
            self.skip(f"{name} is None")
        elif len(value) == 0:
            self.skip(f"{name} is empty")
        else:
            self.skip(f"{name} is False for an unknown reason")
        return True

    def skip_if_value_is_none(self, value, name):
        if value is None:
            self.skip(f"{name} is None")
            return True
        else:
            return False

    def skip_if_value_not_none(self, value, name):
        if value is None:
            return False
        else:
            self.skip(f"{name} is provided")
            return True

    def skip_if_value_already_set(self, value, name):
        if value is None:
            return False
        else:
            self.skip(f"{name} already set")
            return True

    def skip_if_cfg_false(self, section, option):
        if get_config_bool(section, option):
            return False
        else:
            self.skip(f"cfg {section}:{option} is False")
            return True

    def skip_if_cfgs_false(self, section, option1, option2):
        if get_config_bool(section, option1):
            return False
        elif get_config_bool(section, option2):
            return False
        else:
            self.skip(f"cfg {section}:{option1} and {option2} are False")
            return True

    def error(self, reason):
        global _provenance_items
        time_taken = self._stop_timer()
        message = f"{self._name} failed after {time_taken} as {reason}"
        _provenance_items.append(ProvenanceDataItem(
            ["algorithm", "error", f"{self._name} failed due to"], reason))
        _provenance_items.append(ProvenanceDataItem(
            ["algorithm", "timer", f"{self._name} took"], time_taken))
        self._report(message)

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
        global _provenance_items
        if self._start_time is None:
            return False
        time_taken = self._stop_timer()
        if type is None:
            message = f"{self._name} took {time_taken} "
        else:
            try:
                message = f"{self._name} exited with {type.__name__} " \
                          f"after {time_taken}"
            except Exception:
                message = f"{self._name} exited with an exception" \
                          f"after {time_taken}"
            _provenance_items.append(ProvenanceDataItem(
                ["algorithm", "error", f"{self._name} failed due to"], type))

        try:
            _provenance_items.append(ProvenanceDataItem(
                ["algorithm", "timer", f"{self._name} took"], time_taken))
        except NameError:
            raise Exception("Illegal use of FecTime without calling setup")
        self._report(message)
        return False

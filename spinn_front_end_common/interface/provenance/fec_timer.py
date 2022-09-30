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
from spinn_utilities.config_holder import (get_config_bool)
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.provenance.provenance_writer import (
    ProvenanceWriter)

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


class FecTimer(object):

    _simulator = None
    _provenance_path = None
    _print_timings = False
    _category_id = None
    _category_name = None
    _category_time = None
    _machine_on = False
    _previous = []
    __slots__ = [

        # The start time when the timer was set off
        "_start_time",

        # Name of algorithm what is being timed
        "_algorithm",

        # Type of work being done
        "_work"
        ]

    # Category Constants
    WAITING = "Waiting"
    SETTING_UP = "In Setup"
    RUN_OTHER = "In run other"
    GET_MACHINE = "Turning on Machine"
    LOADING = "Loading Stage"
    DATA_GENERATION = "data_generation"
    MAPPING = "Mapping Stage"
    RUN_LOOP = "Running Stage"
    BUFFER = "BufferExtraction"
    RESETTING = "Resetting"
    SHUTTING_DOWN = "Shutting down"
    ERROR = "Error"

    CATEGORIES = [WAITING, SETTING_UP, RUN_OTHER, GET_MACHINE, MAPPING,
                  LOADING, RUN_LOOP, BUFFER, RESETTING, SHUTTING_DOWN, ERROR]

    # Work Type Constants
    OTHER = "Other"
    # LOADING
    BITFIELD = "BitField work"
    # Only for on Machine Compression
    COMPRESSING = "Compressing"
    CONTROL = "Control"
    SYNAPSE = "Expanding Synapse"
    RUNNING = "Running"
    EXTRACTING = "Extracting"
    REPORT = "Reporting"

    WORK_TYPES = [
        OTHER, GET_MACHINE, LOADING, BITFIELD, CONTROL, SYNAPSE, RUNNING,
        EXTRACTING, REPORT]

    # Algorithm Names used elsewhere
    APPLICATION_RUNNER = "Application runner"

    @classmethod
    def setup(cls, simulator):
        # pylint: disable=global-statement, protected-access
        cls._simulator = simulator
        if get_config_bool("Reports", "write_algorithm_timings"):
            cls._provenance_path = os.path.join(
                FecDataView.get_run_dir_path(),
                "algorithm_timings.rpt")
        else:
            cls._provenance_path = None
        cls._print_timings = get_config_bool(
            "Reports", "display_algorithm_timings")

    def __init__(self, algorithm, work):
        self._start_time = None
        self._algorithm = algorithm
        self._work = work

    def __enter__(self):
        self._start_time = _now()
        return self

    def _report(self, message):
        if self._provenance_path is not None:
            with open(self._provenance_path, "a", encoding="utf-8") as p_file:
                p_file.write(f"{message}\n")
        if self._print_timings:
            logger.info(message)

    def skip(self, reason):
        message = f"{self._algorithm} skipped as {reason}"
        timedelta = self._stop_timer()
        with ProvenanceWriter() as db:
            db.insert_timing(self._category_id, self._algorithm, self._work,
                             timedelta, reason)
        self._report(message)

    def skip_if_has_not_run(self):
        if self._simulator.has_ran:
            return False
        else:
            self.skip("simulator.has_run")
            return True

    def skip_if_virtual_board(self):
        if get_config_bool("Machine", "virtual_board"):
            self.skip("virtual_board")
            return True
        else:
            return False

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
        timedelta = self._stop_timer()
        message = f"{self._algorithm} failed after {timedelta} as {reason}"
        with ProvenanceWriter() as db:
            db.insert_timing(self._category_id, self._algorithm,
                             self._work, timedelta, reason)
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

    def __exit__(self, exc_type, exc_value, traceback):
        if self._start_time is None:
            return False
        timedelta = self._stop_timer()
        if exc_type is None:
            message = f"{self._algorithm} took {timedelta} "
            skip = None
        else:
            try:
                message = (f"{self._algorithm} exited with "
                           f"{exc_type.__name__} after {timedelta}")
                skip = exc_type.__name__
            except Exception as ex:  # pylint: disable=broad-except
                message = f"{self._algorithm} exited with an exception" \
                          f"after {timedelta}"
                skip = f"Exception {ex}"

        with ProvenanceWriter() as db:
            db.insert_timing(self._category_id, self._algorithm, self._work,
                             timedelta, skip)
        self._report(message)
        return False

    @classmethod
    def _change_category(cls, category_name):
        """
        This method should only be called via the View!

        :param str category: Category to switch to
        """
        time_now = _now()
        with ProvenanceWriter() as db:
            if cls._category_id:
                diff = _convert_to_timedelta(time_now - cls._category_time)
                db.insert_category_timing(cls._category_id, diff)
            cls._category_id = db.insert_category(
                category_name, cls._machine_on)
        cls._category_name = category_name
        cls._category_time = time_now

    @classmethod
    def start_category(cls, category_name, machine_on=None):
        """
        This method should only be called via the View!

        :param SimulatorStage category: Stage to switch to
        :param machine_on: What to change machine on too.
            Or None to leave as is
        :type machine_on: None or bool
        """
        cls._previous.append(cls._category_name)
        cls._change_category(category_name)
        if machine_on is not None:
            cls._machine_on = machine_on

    @classmethod
    def end_category(cls, category_name):
        """
        This method should only be
        called via the View!

        :param SimulatorStage category: Stage to end
        """
        if cls._category_name != category_name:
            if cls._category_name != cls.ERROR:
                logger.exception(f"Incorrect end of category: {category_name}"
                                 f" when in category{cls._category_name}")
            cls._previous = []
            cls._change_category(cls.ERROR)
        else:
            try:
                previous = cls._previous.pop()
                if previous is None:
                    previous = cls.ERROR
                cls._change_category(previous)
            except IndexError:
                logger.exception(
                    f"End of category: {category_name} with no previous state")
                cls._change_category(cls.ERROR)

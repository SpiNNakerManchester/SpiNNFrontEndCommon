# Copyright (c) 2017 The University of Manchester
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
from datetime import timedelta
from spinn_utilities.config_holder import (get_config_bool)
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.data import FecDataView
from .global_provenance import GlobalProvenance
from spinn_front_end_common.utilities.report_functions.utils import csvopen

logger = FormatAdapter(logging.getLogger(__name__))

# conversion factor
_NANO_TO_MICRO = 1000.0


def _convert_to_timedelta(time_diff):
    """
    Have to convert to a timedelta for rest of code to read.

    As perf_counter_ns is nano seconds, and time delta lowest is micro,
    need to convert.
    """
    return timedelta(microseconds=time_diff / _NANO_TO_MICRO)


class FecTimer(object):

    _simulator = None
    _provenance_path = None
    _print_timings = False
    _category_id = None
    _category = None
    _category_time = None
    _machine_on = False
    _previous = []
    __slots__ = (
        # The start time when the timer was set off
        "_start_time",

        # Name of algorithm what is being timed
        "_algorithm",

        # Type of work being done
        "_work")

    # Algorithm Names used elsewhere
    APPLICATION_RUNNER = "Application runner"

    _CSV_HEADER = "Category,Algorithm,Action,Time Taken,Detail"

    @classmethod
    def setup(cls, simulator):
        # pylint: disable=global-statement, protected-access
        cls._simulator = simulator
        if get_config_bool("Reports", "write_algorithm_timings"):
            cls._provenance_path = FecDataView.get_run_dir_file_name(
                "algorithm_timings.rpt")
            cls._provenance_csv = FecDataView.get_run_dir_file_name(
                "algorithm_timings.csv")
        else:
            cls._provenance_path = None
        cls._print_timings = get_config_bool(
            "Reports", "display_algorithm_timings")

    def __init__(self, algorithm, work):
        self._start_time = None
        self._algorithm = algorithm
        self._work = work

    def __enter__(self):
        self._start_time = time.perf_counter_ns()
        return self

    def _report(self, message, act, time_taken, detail):
        if self._provenance_path is not None:
            with open(self._provenance_path, "a", encoding="utf-8") as p_file:
                p_file.write(f"{message}\n")
        if self._provenance_csv:
            with csvopen(self._provenance_csv, self._CSV_HEADER,
                         mode="a") as c_file:
                c_file.writerow([
                    self._category, self._algorithm, act, time_taken, detail])
        if self._print_timings:
            logger.info(message)

    def _insert_timing(self, time_taken, skip_reason):
        if self._category_id is not None:
            with GlobalProvenance() as db:
                db.insert_timing(
                    self._category_id, self._algorithm, self._work,
                    time_taken, skip_reason)

    def skip(self, reason):
        message = f"{self._algorithm} skipped as {reason}"
        time_taken = self._stop_timer()
        self._insert_timing(time_taken, reason)
        self._report(message, "skip", "", reason)

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
        time_taken = self._stop_timer()
        message = f"{self._algorithm} failed after {time_taken} as {reason}"
        self._insert_timing(time_taken, reason)
        self._report(message, "fail", time_taken, reason)

    def _stop_timer(self):
        """
        Describes how long has elapsed since the instance that the
        :py:meth:`start_timing` method was last called.

        :rtype: datetime.timedelta
        """
        time_now = time.perf_counter_ns()
        diff = time_now - self._start_time
        self._start_time = None
        return _convert_to_timedelta(diff)

    def __exit__(self, exc_type, exc_value, traceback):
        if self._start_time is None:
            return False
        time_taken = self._stop_timer()
        if exc_type is None:
            message = f"{self._algorithm} took {time_taken} "
            act = "run"
            skip = None
        else:
            act = "exception"
            try:
                message = (f"{self._algorithm} exited with "
                           f"{exc_type.__name__} after {time_taken}")
                skip = exc_type.__name__
            except Exception as ex:  # pylint: disable=broad-except
                message = (f"{self._algorithm} exited with an exception"
                           f"after {time_taken}")
                skip = f"Exception {ex}"

        self._insert_timing(time_taken, skip)
        self._report(message, act, time_taken, exc_value if exc_value else "")
        return False

    @classmethod
    def __stop_category(cls):
        """
        Stops the current category and logs how long it took

        :return: Time the stop happened
        """
        time_now = time.perf_counter_ns()
        if cls._category_id:
            with GlobalProvenance() as db:
                diff = _convert_to_timedelta(time_now - cls._category_time)
                db.insert_category_timing(cls._category_id, diff)
        return time_now

    @classmethod
    def _change_category(cls, category):
        """
        This method should only be called via the View!

        :param TimerCategory category: Category to switch to
        """
        time_now = cls.__stop_category()
        with GlobalProvenance() as db:
            cls._category_id = db.insert_category(category, cls._machine_on)
        cls._category = category
        cls._category_time = time_now

    @classmethod
    def start_category(cls, category, machine_on=None):
        """
        This method should only be called via the View!

        :param TimerCategory category: category to switch to
        :param machine_on: What to change machine on too.
            Or `None` to leave as is
        :type machine_on: None or bool
        """
        cls._previous.append(cls._category)
        if cls._category != category:
            cls._change_category(category)
        if machine_on is not None:
            cls._machine_on = machine_on

    @classmethod
    def end_category(cls, category):
        """
        This method should only be
        called via the View!

        :param SimulatorStage category: Stage to end
        """
        if cls._category != category:
            raise ValueError(
                f"Current category is {cls._category} not {category}")
        previous = cls._previous.pop()
        if previous is None:
            raise NotImplementedError(
                "Use stop_category_timing to end the last category")
        if category != previous:
            cls._change_category(previous)

    @classmethod
    def stop_category_timing(cls):
        cls.__stop_category()
        cls._previous = []
        cls._category = None
        cls._category_id = None

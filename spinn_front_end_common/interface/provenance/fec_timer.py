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
from __future__ import annotations
import logging
import time
from datetime import timedelta
from typing import Any, List, Optional, Sized, Union, TYPE_CHECKING
from typing_extensions import Literal, Self
from spinn_utilities.config_holder import (get_config_bool)
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.data import FecDataView
from .global_provenance import GlobalProvenance
from .timer_category import TimerCategory
from spinn_front_end_common.utilities.report_functions.utils import csvopen
if TYPE_CHECKING:
    from spinn_front_end_common.interface.abstract_spinnaker_base import (
        AbstractSpinnakerBase)
    from spinn_front_end_common.interface.provenance import TimerWork

logger = FormatAdapter(logging.getLogger(__name__))

# conversion factor
_NANO_TO_MICRO = 1000.0


class FecTimer(object):
    """
    Timer.
    """

    _simulator: Optional[AbstractSpinnakerBase] = None
    _provenance_path: Optional[str] = None
    _provenance_csv: Optional[str] = None
    _print_timings: bool = False
    _category_id: Optional[int] = None
    _category: Optional[TimerCategory] = None
    _category_time: int = 0
    _machine_on: bool = False
    _previous: List[TimerCategory] = []
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
    def setup(cls, simulator: AbstractSpinnakerBase):
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
            "Reports", "display_algorithm_timings") or False

    def __init__(self, algorithm: str, work: TimerWork):
        self._start_time: Optional[int] = None
        self._algorithm = algorithm
        self._work = work

    def __enter__(self) -> Self:
        self._start_time = time.perf_counter_ns()
        return self

    def _report(self, message: str, act: str, time_taken: Any, detail: Any):
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

    def _insert_timing(
            self, time_taken: timedelta, skip_reason: Optional[str]):
        if self._category_id is not None:
            with GlobalProvenance() as db:
                db.insert_timing(
                    self._category_id, self._algorithm, self._work,
                    time_taken, skip_reason)

    def skip(self, reason: str):
        message = f"{self._algorithm} skipped as {reason}"
        time_taken = self._stop_timer()
        self._insert_timing(time_taken, reason)
        self._report(message, "skip", "", reason)

    def skip_if_has_not_run(self) -> bool:
        if FecDataView.is_ran_ever():
            return False
        else:
            self.skip("simulator.has_run")
            return True

    def skip_if_virtual_board(self) -> bool:
        if get_config_bool("Machine", "virtual_board"):
            self.skip("virtual_board")
            return True
        else:
            return False

    def skip_if_empty(self, value: Optional[
            Union[bool, int, str, Sized]], name: str) -> bool:
        if value:
            return False
        if value is None:
            self.skip(f"{name} is None")
        elif isinstance(value, int) or len(value) == 0:
            self.skip(f"{name} is empty")
        else:
            self.skip(f"{name} is False for an unknown reason")
        return True

    def skip_if_cfg_false(self, section: str, option: str) -> bool:
        if get_config_bool(section, option):
            return False
        else:
            self.skip(f"cfg {section}:{option} is False")
            return True

    def skip_if_cfgs_false(
            self, section: str, option1: str, option2: str) -> bool:
        if get_config_bool(section, option1):
            return False
        elif get_config_bool(section, option2):
            return False
        else:
            self.skip(f"cfg {section}:{option1} and {option2} are False")
            return True

    def error(self, reason: str):
        time_taken = self._stop_timer()
        message = f"{self._algorithm} failed after {time_taken} as {reason}"
        self._insert_timing(time_taken, reason)
        self._report(message, "fail", time_taken, reason)

    def _stop_timer(self) -> timedelta:
        """
        Describes how long has elapsed since the instance that the
        :py:meth:`start_timing` method was last called.

        :rtype: datetime.timedelta
        """
        time_now = time.perf_counter_ns()
        assert self._start_time is not None
        diff = time_now - self._start_time
        self._start_time = None
        return self.__convert_to_timedelta(diff)

    @staticmethod
    def __convert_to_timedelta(time_diff: int) -> timedelta:
        """
        Have to convert to a timedelta for rest of code to read.

        As perf_counter_ns is nano seconds, and time delta lowest is micro,
        need to convert.
        """
        return timedelta(microseconds=time_diff / _NANO_TO_MICRO)

    def __exit__(self, exc_type, exc_value, traceback) -> Literal[False]:
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
    def __stop_category(cls) -> int:
        """
        Stops the current category and logs how long it took

        :return: Time the stop happened
        """
        time_now = time.perf_counter_ns()
        if cls._category_id:
            with GlobalProvenance() as db:
                diff = cls.__convert_to_timedelta(
                    time_now - cls._category_time)
                db.insert_category_timing(cls._category_id, diff)
        return time_now

    @classmethod
    def _change_category(cls, category: TimerCategory):
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
    def start_category(cls, category: TimerCategory, machine_on=None):
        """
        This method should only be called via the View!

        :param TimerCategory category: category to switch to
        :param machine_on: What to change machine on too.
            Or `None` to leave as is
        :type machine_on: None or bool
        """
        if cls._category is not None:
            cls._previous.append(cls._category)
        if cls._category != category:
            cls._change_category(category)
        if machine_on is not None:
            cls._machine_on = machine_on

    @classmethod
    def end_category(cls, category: TimerCategory):
        """
        This method should only be
        called via the View!

        :param TimerCategory category: Stage to end
        """
        if cls._category != category:
            raise ValueError(
                f"Current category is {cls._category} not {category}")
        previous = cls._previous.pop() if cls._previous else None
        if previous is None:
            raise NotImplementedError(
                "Use stop_category_timing to end the last category")
        if category != previous:
            cls._change_category(previous)

    @classmethod
    def stop_category_timing(cls) -> None:
        cls.__stop_category()
        cls._previous = []
        cls._category = None
        cls._category_id = None

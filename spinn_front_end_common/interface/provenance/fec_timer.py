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
from collections.abc import Sized
import logging
import time
from datetime import timedelta
from typing import List, Optional, Tuple, Type, Union, TYPE_CHECKING
from types import TracebackType
from sqlite3 import DatabaseError

from typing_extensions import Literal, Self

from spinn_utilities.config_holder import (
    get_config_bool, get_timestamp_path)
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.data import FecDataView
from .global_provenance import GlobalProvenance
from .timer_category import TimerCategory
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

    @classmethod
    def setup(cls, simulator: AbstractSpinnakerBase) -> None:
        """
        Checks and saves cfg values so they don't have to be read each time

        :param simulator: Not actually used
        """
        cls._simulator = simulator
        if get_config_bool("Reports", "write_algorithm_timings"):
            cls._provenance_path = get_timestamp_path(
                "tpath_algorithm_timings")
        else:
            cls._provenance_path = None
        cls._print_timings = get_config_bool(
            "Reports", "display_algorithm_timings") or False

    def __init__(self, algorithm: str, work: TimerWork):
        """

        :param algorithm: Name of algorithm being timed
        :param work: Type of work being timed
        """
        self._start_time: Optional[int] = None
        self._algorithm = algorithm
        self._work = work

    def __enter__(self) -> Self:
        self._start_time = time.perf_counter_ns()
        return self

    def _report(self, message: str) -> None:
        if self._provenance_path is not None:
            with open(self._provenance_path, "a", encoding="utf-8") as p_file:
                p_file.write(f"{message}\n")
        if self._print_timings:
            logger.info(message)

    def _insert_timing(
            self, time_taken: timedelta, skip_reason: Optional[str]) -> None:
        if self._category_id is not None:
            try:
                with GlobalProvenance() as db:
                    db.insert_timing(
                        self._category_id, self._algorithm, self._work,
                        time_taken, skip_reason)
            except DatabaseError as ex:
                logger.error(f"Timer data error {ex}")

    def skip(self, reason: str) -> None:
        """
        Records that the algorithms is being skipped and ends the timer.

        :param reason: Why the algorithm is being skipped
        """
        message = f"{self._algorithm} skipped as {reason}"
        time_taken = self._stop_timer()
        self._insert_timing(time_taken, reason)
        self._report(message)

    def skip_if_has_not_run(self) -> bool:
        """
        Skips if the simulation has not run.

        If the simulation has run used this methods
        keep the timer running and returns False (did not skip).

        If there was no run this method records the reason,
        ends the timing and returns True (it skipped).

        Currently not used as a better check is skip_if_empty on the data
        needed for the algorithm.

        :returns: True if skip has been called
        """
        if FecDataView.is_ran_ever():
            return False
        else:
            self.skip("simulator.has_run")
            return True

    def skip_if_virtual_board(self) -> bool:
        """
        Skips if a virtual board is being used.

        If a real board is being used this methods
        keep the timer running and returns False (did not skip).

        If a virtual board is being used this method records the reason,
        ends the timing and returns True (it skipped).

        Typically called for algorithms that require a real board to run.

        :returns: True if skip has been called
        """
        if get_config_bool("Machine", "virtual_board"):
            self.skip("virtual_board")
            return True
        else:
            return False

    def skip_if_empty(self, value: Optional[
            Union[bool, int, str, Sized]], name: str) -> bool:
        """
        Skips if the value is one that evaluates to False.

        If the value is considered True (if value) this methods
        keep the timer running and returns False (did not skip).

        If the value is False this method records the reason,
        ends the timing and returns True (it skipped).

        :param value: Value to check if True
        :param name: Name to record for that value if skipping
        :returns: True if skip has been called
        """
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
        """
        Skips if a Boolean cfg values is False.

        If this cfg value is True this methods keep the timer running and
        returns False (did not skip).

        If the cfg value is False this method records the reason,
        ends the timing and returns True (it skipped).

        Typically called if the algorithm should run if the cfg value
        is set True.

        :param section: Section level to be applied to both options
        :param option: The option to check
        :returns: True if skip has been called
        """
        if get_config_bool(section, option):
            return False
        else:
            self.skip(f"cfg {section}:{option} is False")
            return True

    def skip_if_cfgs_false(
            self, section: str, option1: str, option2: str) -> bool:
        """
        Skips if two Boolean cfg values are both False.

        If either cfg value is True this methods keep the timer running and
        returns False (did not skip).

        If both cfg values are False this method records the reason,
        ends the timing and returns True (it skipped).

        Typically called if the algorithm should run if either cfg values
        is set True.

        :param section: Section level to be applied to both options
        :param option1: One of the options to check
        :param option2: The other option to check
        :returns: True if skip has been called
        """
        if get_config_bool(section, option1):
            return False
        elif get_config_bool(section, option2):
            return False
        else:
            self.skip(f"cfg {section}:{option1} and {option2} are False")
            return True

    def skip_all_cfgs_false(
            self, pairs: List[Tuple[str, str]], reason: str) -> bool:
        """
        Skips if all Boolean cfg values are False.

        If either cfg value is True this methods keep the timer running and
        returns False (did not skip).

        If both cfg values are False this method records the reason,
        ends the timing and returns True (it skipped).

        Typically called if the algorithm should run if either cfg values
        is set True.

        :param pairs: section, options pairs to check
        :param reason: Reason to record for the skip
        :returns: True if skip has been called
        """
        for section, option in pairs:
            if get_config_bool(section, option):
                return False
        self.skip(reason)
        return True

    def error(self, reason: str) -> None:
        """
         Ends an algorithm timing and records that it failed.

        :param reason: What caused the error
        """
        time_taken = self._stop_timer()
        message = f"{self._algorithm} failed after {time_taken} as {reason}"
        self._insert_timing(time_taken, reason)
        self._report(message)

    def _stop_timer(self) -> timedelta:
        """
        Describes how long has elapsed since the instance that the
        :py:meth:`start_timing` method was last called.
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

        As perf_counter_ns is nanoseconds, and time delta lowest is micro,
        need to convert.
        """
        return timedelta(microseconds=time_diff / _NANO_TO_MICRO)

    def __exit__(self, exc_type: Optional[Type],
                 exc_val: Optional[BaseException],
                 exc_tb: Optional[TracebackType]) -> Literal[False]:
        if self._start_time is None:
            return False
        time_taken = self._stop_timer()
        if exc_type is None:
            message = f"{self._algorithm} took {time_taken} "
            skip = None
        else:
            try:
                message = (f"{self._algorithm} exited with "
                           f"{exc_type.__name__} after {time_taken}")
                skip = exc_type.__name__
            except Exception as ex:  # pylint: disable=broad-except
                message = (f"{self._algorithm} exited with an exception"
                           f"after {time_taken}")
                skip = f"Exception {ex}"

        self._insert_timing(time_taken, skip)
        self._report(message)
        return False

    @classmethod
    def __stop_category(cls) -> int:
        """
        Stops the current category and logs how long it took

        :return: Time the stop happened
        """
        time_now = time.perf_counter_ns()
        if cls._category_id:
            try:
                with GlobalProvenance() as db:
                    diff = cls.__convert_to_timedelta(
                        time_now - cls._category_time)
                    db.insert_category_timing(cls._category_id, diff)
            except DatabaseError as ex:
                logger.error(f"Timer data error {ex}")
        return time_now

    @classmethod
    def _change_category(cls, category: TimerCategory) -> None:
        """
        This method should only be called via the View!

        :param category: Category to switch to
        """
        time_now = cls.__stop_category()
        try:
            with GlobalProvenance() as db:
                cls._category_id = db.insert_category(
                    category, cls._machine_on)
        except DatabaseError as ex:
            logger.error(f"Timer data error {ex}")
        cls._category = category
        cls._category_time = time_now

    @classmethod
    def start_category(cls, category: TimerCategory,
                       machine_on: Optional[bool] = None) -> None:
        """
        This method should only be called via the View!

        :param category: category to switch to
        :param machine_on: What to change machine on too.
            Or `None` to leave as is
        """
        if cls._category is not None:
            cls._previous.append(cls._category)
        if cls._category != category:
            cls._change_category(category)
        if machine_on is not None:
            cls._machine_on = machine_on

    @classmethod
    def end_category(cls, category: TimerCategory) -> None:
        """
        This method should only be
        called via the View!

        :param category: Stage to end
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
        """
        Stops all the timing.

        Typically only called during simulator shutdown
        """
        cls.__stop_category()
        cls._previous = []
        cls._category = None
        cls._category_id = None

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

import unittest

from testfixtures import LogCapture  # type: ignore[import]

from spinn_utilities.config_holder import set_config

from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.provenance import (
    FecTimer,
    GlobalProvenance,
    TimerCategory,
    TimerWork,
)


class TestFecTimer(unittest.TestCase):

    def setUp(self) -> None:
        unittest_setup()
        set_config("Reports", "write_algorithm_timings", "True")
        FecTimer.setup()  # type: ignore[arg-type]

    def test_simple(self) -> None:
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        with FecTimer("test", TimerWork.OTHER):
            pass

    def test_skip(self) -> None:
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        with FecTimer("test", TimerWork.OTHER) as ft:
            ft.skip("why not")

    def test_error(self) -> None:
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        with LogCapture() as lc:
            try:
                with FecTimer("oops", TimerWork.OTHER):
                    1/0  # pylint: disable=pointless-statement
            except ZeroDivisionError:
                pass
            found = False
            for record in lc.records:
                if "oops" in str(record.msg):
                    found = True
            assert found

    def test_nested(self) -> None:
        FecTimer.start_category(TimerCategory.WAITING)
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        FecTimer.start_category(TimerCategory.MAPPING)
        FecTimer.start_category(TimerCategory.MACHINE_OFF)
        FecTimer.end_category(TimerCategory.MACHINE_OFF)
        FecTimer.end_category(TimerCategory.MAPPING)
        FecTimer.end_category(TimerCategory.RUN_OTHER)
        with GlobalProvenance() as db:
            total = db.get_category_timer_sum(TimerCategory.RUN_OTHER)
            self.assertGreater(total, 0)

    def test_repeat_stopped(self) -> None:
        FecTimer.start_category(TimerCategory.WAITING)
        FecTimer.start_category(TimerCategory.SHUTTING_DOWN)
        with self.assertRaises(ValueError):
            FecTimer.start_category(TimerCategory.SHUTTING_DOWN)
        with GlobalProvenance() as db:
            total = db.get_category_timer_sum(
                TimerCategory.SHUTTING_DOWN)
            self.assertEqual(total, 0)
        FecTimer.stop_category_timing()
        with GlobalProvenance() as db:
            total = db.get_category_timer_sum(
                TimerCategory.SHUTTING_DOWN)
            self.assertGreater(total, 0)

    def test_repeat_mess(self) -> None:
        FecTimer.start_category(TimerCategory.WAITING)
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        FecTimer.start_category(TimerCategory.MAPPING)
        with self.assertRaises(ValueError):
            FecTimer.start_category(TimerCategory.MAPPING)
        FecTimer.end_category(TimerCategory.MAPPING)
        FecTimer.start_category(TimerCategory.DATA_SPEC_OTHER)
        with self.assertRaises(ValueError):
            FecTimer.end_category(TimerCategory.RUN_OTHER)

    def test_mess(self) -> None:
        with self.assertRaises(ValueError):
            FecTimer.end_category(TimerCategory.WAITING)

        FecTimer.start_category(TimerCategory.RUN_OTHER)
        FecTimer.start_category(TimerCategory.MAPPING)
        with self.assertRaises(ValueError):
            FecTimer.end_category(TimerCategory.RUN_OTHER)

    def test_stop_category_timing_clean(self) -> None:
        FecTimer.start_category(TimerCategory.WAITING)
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        with GlobalProvenance() as db:
            before = db.get_category_timer_sum(TimerCategory.WAITING)
        FecTimer.start_category(TimerCategory.MAPPING)
        FecTimer.end_category(TimerCategory.MAPPING)
        FecTimer.end_category(TimerCategory.RUN_OTHER)
        FecTimer.stop_category_timing()
        with GlobalProvenance() as db:
            total = db.get_category_timer_sum(TimerCategory.WAITING)
            self.assertGreater(total, before)
            other = db.get_category_timer_sum(TimerCategory.RUN_OTHER)
            self.assertGreater(other, 0)

    def test_stop_category_timing_messy(self) -> None:
        FecTimer.start_category(TimerCategory.WAITING)
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        with GlobalProvenance() as db:
            before = db.get_category_timer_sum(TimerCategory.WAITING)
        FecTimer.start_category(TimerCategory.MAPPING)
        FecTimer.start_category(TimerCategory.SHUTTING_DOWN)
        FecTimer.end_category(TimerCategory.SHUTTING_DOWN)
        FecTimer.stop_category_timing()
        with GlobalProvenance() as db:
            mapping = db.get_category_timer_sum(TimerCategory.MAPPING)
            self.assertGreater(mapping, 0)
            total = db.get_category_timer_sum(TimerCategory.WAITING)
            # As we never ended RUN_OTHER we never got back to WAITING
            self.assertEqual(total, before)
            other = db.get_category_timer_sum(TimerCategory.RUN_OTHER)
            self.assertGreater(other, 0)

    def test_stop_last_category_blocked(self) -> None:
        FecTimer.start_category(TimerCategory.WAITING)
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        FecTimer.start_category(TimerCategory.MAPPING)
        FecTimer.end_category(TimerCategory.MAPPING)
        FecTimer.end_category(TimerCategory.RUN_OTHER)
        with self.assertRaises(NotImplementedError):
            FecTimer.end_category(TimerCategory.WAITING)


if __name__ == '__main__':
    unittest.main()

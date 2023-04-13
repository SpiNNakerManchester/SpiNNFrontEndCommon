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

import tempfile
import unittest
from testfixtures import LogCapture
from spinn_front_end_common.interface.provenance import (
    FecTimer, GlobalProvenance, TimerCategory, TimerWork)
from spinn_front_end_common.interface.config_setup import unittest_setup


class MockSimulator(object):

    @property
    def _report_default_directory(self):
        return tempfile.mkdtemp()

    @property
    def n_calls_to_run(self):
        return 1

    @property
    def n_loops(self):
        return 1


class TestFecTimer(unittest.TestCase):

    def setUp(self):
        unittest_setup()
        FecTimer.setup(MockSimulator())

    def test_simple(self):
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        with FecTimer("test", TimerWork.OTHER):
            pass

    def test_skip(self):
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        with FecTimer("test", TimerWork.OTHER) as ft:
            ft.skip("why not")

    def test_error(self):
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

    def test_nested(self):
        FecTimer.start_category(TimerCategory.WAITING)
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        FecTimer.start_category(TimerCategory.MAPPING)
        FecTimer.start_category(TimerCategory.GET_MACHINE, True)
        FecTimer.end_category(TimerCategory.GET_MACHINE)
        FecTimer.end_category(TimerCategory.MAPPING)
        FecTimer.end_category(TimerCategory.RUN_OTHER)
        with GlobalProvenance() as db:
            on, off = db.get_category_timer_sums(TimerCategory.RUN_OTHER)
            total = db.get_category_timer_sum(TimerCategory.RUN_OTHER)
            self.assertGreater(on, 0)
            self.assertGreater(off, 0)
            self.assertEqual(total, on + off)
            on, off = db.get_category_timer_sums(TimerCategory.MAPPING)
            self.assertGreater(on, 0)
            self.assertGreater(off, 0)

    def test_repeat_middle(self):
        FecTimer.start_category(TimerCategory.WAITING)
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        FecTimer.start_category(TimerCategory.MAPPING)
        # Hack for easy testing/ demonstration only
        id1 = FecTimer._category_id
        FecTimer.start_category(TimerCategory.MAPPING)
        id2 = FecTimer._category_id
        self.assertEqual(id1, id2)
        FecTimer.end_category(TimerCategory.MAPPING)
        id2 = FecTimer._category_id
        self.assertEqual(id1, id2)
        FecTimer.end_category(TimerCategory.MAPPING)
        id3 = FecTimer._category_id
        self.assertEqual(id1 + 1, id3)
        FecTimer.end_category(TimerCategory.RUN_OTHER)

    def test_repeat_stopped(self):
        FecTimer.start_category(TimerCategory.WAITING)
        FecTimer.start_category(TimerCategory.SHUTTING_DOWN)
        FecTimer.start_category(TimerCategory.SHUTTING_DOWN)
        with GlobalProvenance() as db:
            total = db.get_category_timer_sum(
                TimerCategory.SHUTTING_DOWN)
            self.assertEqual(total, 0)
            FecTimer.stop_category_timing()
            total = db.get_category_timer_sum(
                TimerCategory.SHUTTING_DOWN)
            self.assertGreater(total, 0)

    def test_repeat_mess(self):
        FecTimer.start_category(TimerCategory.WAITING)
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        FecTimer.start_category(TimerCategory.MAPPING)
        FecTimer.start_category(TimerCategory.MAPPING)
        FecTimer.end_category(TimerCategory.MAPPING)
        with self.assertRaises(ValueError):
            FecTimer.end_category(TimerCategory.RUN_OTHER)

    def test_mess(self):
        with self.assertRaises(ValueError):
            FecTimer.end_category(TimerCategory.WAITING)

        FecTimer.start_category(TimerCategory.RUN_OTHER)
        FecTimer.start_category(TimerCategory.MAPPING)
        with self.assertRaises(ValueError):
            FecTimer.end_category(TimerCategory.RUN_OTHER)

    def test_stop_category_timing_clean(self):
        FecTimer.start_category(TimerCategory.WAITING)
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        with GlobalProvenance() as db:
            before = db.get_category_timer_sum(TimerCategory.WAITING)
            FecTimer.start_category(TimerCategory.MAPPING)
            FecTimer.end_category(TimerCategory.MAPPING)
            FecTimer.end_category(TimerCategory.RUN_OTHER)
            FecTimer.stop_category_timing()
            total = db.get_category_timer_sum(TimerCategory.WAITING)
            self.assertGreater(total, before)
            other = db.get_category_timer_sum(TimerCategory.RUN_OTHER)
            self.assertGreater(other, 0)

    def test_stop_category_timing_messy(self):
        FecTimer.start_category(TimerCategory.WAITING)
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        with GlobalProvenance() as db:
            before = db.get_category_timer_sum(TimerCategory.WAITING)
            FecTimer.start_category(TimerCategory.MAPPING)
            FecTimer.start_category(TimerCategory.SHUTTING_DOWN)
            FecTimer.end_category(TimerCategory.SHUTTING_DOWN)
            FecTimer.stop_category_timing()
            mapping = db.get_category_timer_sum(TimerCategory.MAPPING)
            self.assertGreater(mapping, 0)
            total = db.get_category_timer_sum(TimerCategory.WAITING)
            # As we never ended RUN_OTHER we never got back to WAITING
            self.assertEqual(total, before)
            other = db.get_category_timer_sum(TimerCategory.RUN_OTHER)
            self.assertGreater(other, 0)

    def test_stop_last_category_blocked(self):
        FecTimer.start_category(TimerCategory.WAITING)
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        FecTimer.start_category(TimerCategory.MAPPING)
        FecTimer.end_category(TimerCategory.MAPPING)
        FecTimer.end_category(TimerCategory.RUN_OTHER)
        with self.assertRaises(NotImplementedError):
            FecTimer.end_category(TimerCategory.WAITING)


if __name__ == '__main__':
    unittest.main()

# Copyright (c) 2017-2022 The University of Manchester
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

import tempfile
import unittest
from testfixtures import LogCapture
from spinn_front_end_common.interface.provenance import (
    FecTimer, ProvenanceReader, TimerCategory)
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

    def setUp(cls):
        unittest_setup()
        FecTimer.setup(MockSimulator())

    def test_simple(self):
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        with FecTimer("test", FecTimer.OTHER):
            pass

    def test_skip(self):
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        with FecTimer("test", FecTimer.OTHER) as ft:
            ft.skip("why not")

    def test_error(self):
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        with LogCapture() as lc:
            try:
                with FecTimer("oops", FecTimer.OTHER):
                    1/0
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
        on, off = ProvenanceReader().get_category_timer_sums(
            TimerCategory.RUN_OTHER)
        total = ProvenanceReader().get_category_timer_sum(
            TimerCategory.RUN_OTHER)
        self.assertGreater(on, 0)
        self.assertGreater(off, 0)
        self.assertEqual(total, on + off)
        on, off = ProvenanceReader().get_category_timer_sums(
            TimerCategory.MAPPING)
        self.assertGreater(on, 0)
        self.assertGreater(off, 0)

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
        before = ProvenanceReader().get_category_timer_sum(
            TimerCategory.WAITING)
        FecTimer.start_category(TimerCategory.MAPPING)
        FecTimer.end_category(TimerCategory.MAPPING)
        FecTimer.end_category(TimerCategory.RUN_OTHER)
        FecTimer.stop_category_timing()
        total = ProvenanceReader().get_category_timer_sum(
            TimerCategory.WAITING)
        self.assertGreater(total, before)
        other = ProvenanceReader().get_category_timer_sum(
            TimerCategory.RUN_OTHER)
        self.assertGreater(other, 0)

    def test_stop_category_timing_messy(self):
        FecTimer.start_category(TimerCategory.WAITING)
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        before = ProvenanceReader().get_category_timer_sum(
            TimerCategory.WAITING)
        FecTimer.start_category(TimerCategory.MAPPING)
        FecTimer.start_category(TimerCategory.SHUTTING_DOWN)
        FecTimer.end_category(TimerCategory.SHUTTING_DOWN)
        FecTimer.stop_category_timing()
        mapping = ProvenanceReader().get_category_timer_sum(
            TimerCategory.MAPPING)
        self.assertGreater(mapping, 0)
        total = ProvenanceReader().get_category_timer_sum(
            TimerCategory.WAITING)
        # As we never ended RUN_OTHER we never got back to WAITING
        self.assertEqual(total, before)
        other = ProvenanceReader().get_category_timer_sum(
            TimerCategory.RUN_OTHER)
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

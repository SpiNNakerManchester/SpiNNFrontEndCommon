# Copyright (c) 2021 The University of Manchester
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
from spinn_utilities.log import FormatAdapter
from datetime import timedelta
from testfixtures.logcapture import LogCapture
import unittest
from spinn_utilities.config_holder import set_config
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.provenance import (
    LogStoreDB, ProvenanceWriter, ProvenanceReader, TimerCategory, TimerWork)

logger = FormatAdapter(logging.getLogger(__name__))


class TestProvenanceDatabase(unittest.TestCase):

    def setUp(self):
        unittest_setup()

    def test_create(self):
        ProvenanceWriter()
        ProvenanceWriter()

    def as_set(self, items):
        results = set()
        for item in items:
            results.add(
                ("/".join(item.names[:-1]), item.names[-1], item.value))
        return results

    def test_version(self):
        with ProvenanceWriter() as db:
            db.insert_version("spinn_utilities_version", "1!6.0.1")
            db.insert_version("numpy_version", "1.17.4")
        data = ProvenanceReader().run_query("select * from version_provenance")
        versions = [
            (1, 'spinn_utilities_version', '1!6.0.1'),
            (2, 'numpy_version', '1.17.4')]
        self.assertListEqual(data, versions)

    def test_power(self):
        with ProvenanceWriter() as db:
            db.insert_power("num_cores", 34)
            db.insert_power("total time (seconds)", 6.81)
        data = ProvenanceReader().run_query("select * from power_provenance")
        power = [(1, 'num_cores', 34.0), (2, 'total time (seconds)', 6.81)]
        self.assertListEqual(data, power)

    def test_timings(self):
        with ProvenanceWriter() as db:
            mapping_id = db.insert_category(TimerCategory.MAPPING, False)
            db.insert_timing(
                mapping_id, "compressor", TimerWork.OTHER,
                timedelta(milliseconds=12), None)
            db.insert_timing(
                mapping_id, "router_report", TimerWork.REPORT,
                timedelta(milliseconds=123), "cfg says no")
            execute_id = db.insert_category(TimerCategory.RUN_LOOP, False)
            db.insert_timing(
                execute_id, "run", TimerWork.OTHER,
                timedelta(milliseconds=134), None)
            db.insert_timing(
                execute_id, "run", TimerWork.REPORT,
                timedelta(milliseconds=344), None)
            db.insert_timing(
                execute_id, "clear", TimerWork.OTHER,
                timedelta(milliseconds=4), None)
        reader = ProvenanceReader()
        data = reader.get_timer_sum_by_category(TimerCategory.MAPPING)
        self.assertEqual(12 + 123, data)
        data = reader.get_timer_sum_by_category(TimerCategory.RUN_LOOP)
        self.assertEqual(134 + 344 + 4, data)
        data = reader.get_timer_sum_by_category(TimerCategory.SHUTTING_DOWN)
        self.assertEquals(0, data)
        data = reader.get_timer_sum_by_algorithm("router_report")
        self.assertEqual(123, data)
        data = reader.get_timer_sum_by_algorithm("clear")
        self.assertEqual(4, data)
        data = reader.get_timer_sum_by_algorithm("junk")
        self.assertEqual(0, data)

    def test_category_timings(self):
        with ProvenanceWriter() as db:
            id = db.insert_category(TimerCategory.MAPPING, False)
            db.insert_category_timing(id, timedelta(milliseconds=12))

            id = db.insert_category(TimerCategory.MAPPING, True)
            db.insert_category_timing(id, timedelta(milliseconds=123))

            id = db.insert_category(TimerCategory.RUN_LOOP, True)
            db.insert_category_timing(id, timedelta(milliseconds=134))

            id = db.insert_category(TimerCategory.RUN_LOOP, False)
            db.insert_category_timing(id, timedelta(milliseconds=344))

        reader = ProvenanceReader()
        data = reader.get_category_timer_sum(TimerCategory.MAPPING)
        self.assertEqual(12 + 123, data)

    def test_other(self):
        with ProvenanceWriter() as db:
            db.insert_other("foo", "bar", 12)

    def test_gatherer(self):
        with ProvenanceWriter() as db:
            db.insert_gatherer(
                1, 3, 1715886360, 80, 1, "Extraction_time", 00.234)
            db.insert_gatherer(
                1, 3, 1715886360, 80, 1, "Lost Packets", 12)
        reader = ProvenanceReader()
        data = reader.run_query("Select * from gatherer_provenance")
        expected = [(1, 1, 3, 1715886360, 80, 1, 'Extraction_time', 0.234),
                    (2, 1, 3, 1715886360, 80, 1, 'Lost Packets', 12.0)]
        self.assertListEqual(expected, data)

    def test_router(self):
        with ProvenanceWriter() as db:
            db.insert_router(1, 3, "des1", 34, True)
            db.insert_router(1, 2, "des1", 45, True)
            db.insert_router(1, 3, "des2", 67)
            db.insert_router(1, 3, "des1", 48)
            db.insert_router(5, 5, "des1", 48, False)
        reader = ProvenanceReader()
        data = set(reader.get_router_by_chip("des1"))
        chip_set = {(1, 3, 34), (1, 2, 45), (1, 3, 48), (5, 5, 48)}
        self.assertSetEqual(data, chip_set)
        data = reader.get_router_by_chip("junk")
        self.assertEqual(0, len(data))

    def test_monitor(self):
        with ProvenanceWriter() as db:
            db.insert_monitor(1, 3, "des1", 34)
            db.insert_monitor(1, 2, "des1", 45)
            db.insert_monitor(1, 3, "des2", 67)
            db.insert_monitor(1, 3, "des1", 48)
        reader = ProvenanceReader()
        data = set(reader.get_monitor_by_chip("des1"))
        chip_set = {(1, 3, 34), (1, 2, 45), (1, 3, 48)}
        self.assertSetEqual(data, chip_set)
        data = reader.get_monitor_by_chip("junk")
        self.assertEqual(0, len(data))

    def test_cores(self):
        with ProvenanceWriter() as db:
            db.insert_core(1, 3, 2, "des1", 34)
            db.insert_core(1, 2, 3, "des1", 45)
            db.insert_core(1, 3, 2, "des2", 67)
            db.insert_core(1, 3, 1, "des1", 48)

    def test_core_name(self):
        with ProvenanceWriter() as db:
            db.add_core_name(1, 3, 2, "first_core")
            db.add_core_name(1, 3, 3, "second_core")
            db.add_core_name(1, 3, 2, "first_core")
            db.add_core_name(1, 3, 2, "new_name is ignored")
        reader = ProvenanceReader()
        data = reader.run_query("Select * from core_mapping")
        self.assertEqual(2, len(data))

    def test_messages(self):
        set_config("Reports", "provenance_report_cutoff", 3)
        with LogCapture() as lc:
            with ProvenanceWriter() as db:
                db.insert_report("een")
                db.insert_report("twee")
                db.insert_report("drie")
                db.insert_report("vier")
            self.assertEqual(3, len(lc.records))

        reader = ProvenanceReader()
        data = reader.messages()
        self.assertEqual(4, len(data))

    def test_connector(self):
        with ProvenanceWriter() as db:
            db.insert_connector("the pre", "A post", "OneToOne", "foo", 12)
        reader = ProvenanceReader()
        data = reader.run_query("Select * from connector_provenance")
        expected = [(1, 'the pre', 'A post', 'OneToOne', 'foo', 12)]
        self.assertListEqual(expected, data)

    def test_board(self):
        data = {(0, 0): '10.11.194.17', (4, 8): '10.11.194.81'}
        with ProvenanceWriter() as db:
            db.insert_board_provenance(data)

    def test_log(self):
        db1 = LogStoreDB()
        db2 = LogStoreDB()
        db1.store_log(30, "this is a warning")
        db2.store_log(10, "this is a debug")
        db1.store_log(20, "this is an info")
        self.assertListEqual(
            ["this is a warning", "this is a debug", "this is an info"],
            db2.retreive_log_messages())
        self.assertListEqual(
            ["this is a warning", "this is an info"],
            db1.retreive_log_messages(20))
        db2.get_location()

    def test_database_locked(self):
        ls = LogStoreDB()
        logger.set_log_store(ls)
        logger.warning("this works")
        with ProvenanceWriter() as db:
            db._test_log_locked("locked")
            logger.warning("not locked")
        logger.warning("this wis fine")
        # the use of class variables and tests run in parallel dont work.
        if "JENKINS_URL" not in os.environ:
            self.assertListEqual(
                ["this works", "not locked", "this wis fine"],
                ls.retreive_log_messages(20))
        logger.set_log_store(None)

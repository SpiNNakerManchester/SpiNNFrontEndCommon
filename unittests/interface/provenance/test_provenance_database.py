# Copyright (c) 2021 The University of Manchester
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
import os
from sqlite3 import OperationalError
from spinn_utilities.log import FormatAdapter
from datetime import timedelta
from testfixtures.logcapture import LogCapture  # type: ignore[import]
import unittest
from spinn_utilities.config_holder import set_config
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.provenance import (
    LogStoreDB, GlobalProvenance, ProvenanceWriter, ProvenanceReader,
    TimerCategory, TimerWork)

logger = FormatAdapter(logging.getLogger(__name__))


class TestProvenanceDatabase(unittest.TestCase):

    def setUp(self) -> None:
        unittest_setup()
        set_config("Reports", "write_provenance", "true")

    def test_create(self) -> None:
        ProvenanceWriter()
        ProvenanceWriter()

    def test_version(self) -> None:
        with GlobalProvenance() as db:
            db.insert_version("spinn_utilities_version", "1!6.0.1")
            db.insert_version("numpy_version", "1.17.4")
            data = db.run_query("select * from version_provenance")
            versions = [
                (1, 'spinn_utilities_version', '1!6.0.1'),
                (2, 'numpy_version', '1.17.4')]
            self.assertListEqual(data, versions)

    def test_power(self) -> None:
        with ProvenanceWriter() as db:
            db.insert_power("num_cores", 34)
            db.insert_power("total time (seconds)", 6.81)
        with ProvenanceReader() as db:
            data = db.run_query("select * from power_provenance")
            power = [(1, 1, 'num_cores', 34.0),
                     (2, 1, 'total time (seconds)', 6.81)]
            self.assertListEqual(data, power)

    def test_timings(self) -> None:
        with GlobalProvenance() as db:
            db.insert_run_reset_mapping()
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
            data = db.get_timer_sum_by_category(TimerCategory.MAPPING)
            self.assertEqual(12 + 123, data)
            data = db.get_timer_sum_by_category(TimerCategory.RUN_LOOP)
            self.assertEqual(134 + 344 + 4, data)
            data = db.get_timer_sum_by_category(TimerCategory.SHUTTING_DOWN)
            self.assertEqual(0, data)
            data = db.get_timer_sum_by_algorithm("router_report")
            self.assertEqual(123, data)
            data = db.get_timer_sum_by_algorithm("clear")
            self.assertEqual(4, data)
            data = db.get_timer_sum_by_algorithm("junk")
            self.assertEqual(0, data)

    def test_category_timings(self) -> None:
        with GlobalProvenance() as db:
            id = db.insert_category(TimerCategory.MAPPING, False)
            db.insert_category_timing(id, timedelta(milliseconds=12))

            id = db.insert_category(TimerCategory.MAPPING, True)
            db.insert_category_timing(id, timedelta(milliseconds=123))

            id = db.insert_category(TimerCategory.RUN_LOOP, True)
            db.insert_category_timing(id, timedelta(milliseconds=134))

            id = db.insert_category(TimerCategory.RUN_LOOP, False)
            db.insert_category_timing(id, timedelta(milliseconds=344))

            data = db.get_category_timer_sum(TimerCategory.MAPPING)
        self.assertEqual(12 + 123, data)

    def test_gatherer(self) -> None:
        with ProvenanceWriter() as db:
            db.insert_gatherer(
                1, 3, 1715886360, 80, 1, "Extraction_time", 00.234)
            db.insert_gatherer(
                1, 3, 1715886360, 80, 1, "Lost Packets", 12)
        with ProvenanceReader() as db:
            data = db.run_query("Select * from gatherer_provenance")
        expected = [(1, 1, 3, 1715886360, 80, 1, 'Extraction_time', 0.234),
                    (2, 1, 3, 1715886360, 80, 1, 'Lost Packets', 12.0)]
        self.assertListEqual(expected, data)

    def test_router(self) -> None:
        with ProvenanceWriter() as db:
            db.insert_router(1, 3, "des1", 34, True)
            db.insert_router(1, 2, "des1", 45, True)
            db.insert_router(1, 3, "des2", 67)
            db.insert_router(1, 3, "des1", 48)
            db.insert_router(5, 5, "des1", 48, False)
        with ProvenanceReader() as db:
            data1 = set(db.get_router_by_chip("des1"))
            chip_set = {(1, 3, 34), (1, 2, 45), (1, 3, 48), (5, 5, 48)}
            self.assertSetEqual(data1, chip_set)
            data2 = db.get_router_by_chip("junk")
            self.assertEqual(0, len(data2))

    def test_monitor(self) -> None:
        with ProvenanceWriter() as db:
            db.insert_monitor(1, 3, "des1", 34)
            db.insert_monitor(1, 2, "des1", 45)
            db.insert_monitor(1, 3, "des2", 67)
            db.insert_monitor(1, 3, "des1", 48)
        with ProvenanceReader() as db:
            data1 = set(db.get_monitor_by_chip("des1"))
            chip_set = {(1, 3, 34), (1, 2, 45), (1, 3, 48)}
            self.assertSetEqual(data1, chip_set)
            data2 = db.get_monitor_by_chip("junk")
            self.assertEqual(0, len(data2))

    def test_cores(self) -> None:
        with ProvenanceWriter() as db:
            db.insert_core(1, 3, 2, "des1", 34)
            db.insert_core(1, 2, 3, "des1", 45)
            db.insert_core(1, 3, 2, "des2", 67)
            db.insert_core(1, 3, 1, "des1", 48)

    def test_messages(self) -> None:
        set_config("Reports", "provenance_report_cutoff", "3")
        with LogCapture() as lc:
            with ProvenanceWriter() as db:
                db.insert_report("een")
                db.insert_report("twee")
                db.insert_report("drie")
                db.insert_report("vier")
            self.assertEqual(3, len(lc.records))

        with ProvenanceReader() as db:
            data = db.messages()
        self.assertEqual(4, len(data))

    def test_connector(self) -> None:
        with ProvenanceWriter() as db:
            db.insert_connector("the pre", "A post", "OneToOne", "foo", 12)
        with ProvenanceReader() as db:
            data = db.run_query("Select * from connector_provenance")
        expected = [(1, 'the pre', 'A post', 'OneToOne', 'foo', 12)]
        self.assertListEqual(expected, data)

    def test_board(self) -> None:
        data = {(0, 0): '10.11.194.17', (4, 8): '10.11.194.81'}
        with ProvenanceWriter() as db:
            db.insert_board_provenance(data)

    def test_log(self) -> None:
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

    def test_database_locked(self) -> None:
        ls = LogStoreDB()
        logger.set_log_store(ls)
        logger.warning("this works")
        with GlobalProvenance() as db:
            db._test_log_locked("now locked")
        logger.warning("not locked")
        logger.warning("this wis fine")
        # the use of class variables and tests run in parallel dont work.
        if "JENKINS_URL" not in os.environ:
            reported = ls.retreive_log_messages(20)
            self.assertIn("this works", reported)
            self.assertIn("not locked", reported)
            self.assertIn("this wis fine", reported)
            self.assertNotIn("now locked", reported)
        logger.set_log_store(None)

    def test_double_with(self) -> None:
        # Confirm that using the database twice goes boom
        with GlobalProvenance() as db1:
            with GlobalProvenance() as db2:
                # A read does not lock the database
                db1.get_timer_provenance("test")
                db2.get_timer_provenance("test")
                # A write does
                db1.insert_version("a", "foo")
                with self.assertRaises(OperationalError):
                    # So a write from a different transaction goes boom
                    db2.insert_version("b", "bar")

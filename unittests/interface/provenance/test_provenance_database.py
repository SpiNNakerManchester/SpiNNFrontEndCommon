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

from testfixtures.logcapture import LogCapture
import unittest
from spinn_utilities.config_holder import set_config
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.provenance import (
    ProvenanceWriter, ProvenanceReader)


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
            db.insert_timing("mapping", "compressor", 12)
            db.insert_timing("mapping", "router", 123)
            db.insert_timing("execute", "run", 134)
            db.insert_timing("execute", "run", 344)
            db.insert_timing("execute", "clear", 4)
        reader = ProvenanceReader()
        data = reader.get_timer_sum_by_category("mapping")
        self.assertEqual(12 + 123, data)
        data = reader.get_timer_sum_by_category("execute")
        self.assertEqual(134 + 344 + 4, data)
        data = reader.get_timer_sum_by_category("bacon")
        self.assertIsNone(data)
        data = reader.get_timer_sum_by_algorithm("router")
        self.assertEqual(123, data)
        data = reader.get_timer_sum_by_algorithm("clear")
        self.assertEqual(4, data)
        data = reader.get_timer_sum_by_algorithm("junk")
        self.assertIsNone(data)

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

    def test_app_vertex(self):
        with ProvenanceWriter() as db:
            db.insert_app_vertex("pop", "type", "description", 0.5)
        reader = ProvenanceReader()
        data = reader.run_query("Select * from app_vertex_provenance")
        expected = [(1, 'pop', 'type', 'description', 0.5)]
        self.assertListEqual(expected, data)

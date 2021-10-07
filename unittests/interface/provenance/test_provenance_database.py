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

import unittest
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.provenance import (
    ProvenanceWriter, ProvenanceReader)
from spinn_front_end_common.utilities.utility_objs import ProvenanceDataItem


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

    def test_insert_items1(self):
        a = ProvenanceDataItem(["foo", "bar for 1,2", "gamma"], 75)
        b = ProvenanceDataItem(["foo", "alpha for 1,2", "gamma"], 100)
        items = [a, b]
        with ProvenanceWriter() as db:
            db.insert_items(items)
        data = set(ProvenanceReader().get_provenace_items())
        items_set = self.as_set(items)
        self.assertSetEqual(data, items_set)

    def test_insert_items2(self):
        a = ProvenanceDataItem(["foo", "bar for 1,2", "gamma"], 75)
        b = ProvenanceDataItem(["foo", "alpha for 1,2", "gamma"], 100)
        items = [a, b]
        with ProvenanceWriter() as db:
            db.insert_item(["foo", "bar for 1,2", "gamma"], 75)
            db.insert_item(["foo", "alpha for 1,2", "gamma"], 100)
        data = set(ProvenanceReader().get_provenace_items())
        items_set = self.as_set(items)
        self.assertSetEqual(data, items_set)

    def test_cores_(self):
        with ProvenanceWriter() as db:
            db.insert_item(["vertex on 1,2", "gamma"], 75)
            db.insert_item(["another vertex for 2,1", "gamma"], 75)
            db.insert_item(["vertex for 1,2,1", "gamma"], 100)
            db.insert_item(["vertex for 1,2,2", "gamma"], 99)
            db.insert_item(["vertex for 1,2,2", "gamma"], 101)
            db.insert_item(["vertex alpha for 1,3,1", "gamma"], 100)
            db.insert_item(["vertex alpha for 1,3,2", "gamma"], 100)
            db.insert_item(["vertex for 1,3,5", "gamma"], 100)
            db.insert_item(["pizza", "bacon"], 12)
        data = set(ProvenanceReader().get_cores_with_provenace())
        cores_set = {
            (1, 2, 1, "vertex for 1,2,1"),
            (1, 2, 2, "vertex for 1,2,2"),
            (1, 3, 1, "vertex alpha for 1,3,1"),
            (1, 3, 2, "vertex alpha for 1,3,2"),
            (1, 3, 5, "vertex for 1,3,5")}
        self.assertSetEqual(data, cores_set)
        data = ProvenanceReader().get_provenace_sum_by_core(
            1, 2, 2, "gamma")
        self.assertEqual(200, data)
        data = ProvenanceReader().get_provenace_sum_by_core(
            1, 1, 2, "gamma")
        self.assertIsNone(data)
        ProvenanceReader().run_query("select * from core_stats_view")

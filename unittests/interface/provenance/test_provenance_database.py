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
    SqlLiteDatabase, ProvenanceReader)
from spinn_front_end_common.utilities.utility_objs import ProvenanceDataItem


class TestProvenanceDatabase(unittest.TestCase):

    def setUp(self):
        unittest_setup()

    def test_create(self):
        SqlLiteDatabase()
        SqlLiteDatabase()

    def as_set(self, items):
        results = set()
        for item in items:
            results.add(
                ("/".join(item.names[:-1]), item.names[-1], item.value))
        return results

    def test_insert_items1(self):
        a = ProvenanceDataItem(["foo", "bar", "gamma for 1,2"], 75)
        b = ProvenanceDataItem(["foo", "alpha", "gamma for 3,4"], 100)
        items = [a, b]
        with SqlLiteDatabase() as db:
            db.insert_items(items)
        data = set(ProvenanceReader().get_provenace_items())
        items_set = self.as_set(items)
        self.assertSetEqual(data, items_set)

# Copyright (c) 2017-2019 The University of Manchester
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

import os
import random
import unittest
from spinn_front_end_common.interface.buffer_management.recorded import (
    RecordedDatabase)


class TestBufferedReceivingDataWithDB(unittest.TestCase):

    def _random_data(self, timesteps, neuron_ids):
        data = []
        for timestep in timesteps:
            line = []
            line.append(timestep)
            for _ in neuron_ids:
                line.append(random.randint(0, 100000000))
            data.append(line)
        return data

    def test_use_database(self):
        db_file = os.path.join(os.path.dirname(__file__), "main_test.sqlite3")
        if os.path.exists(db_file):
            os.remove(db_file)
        db = RecordedDatabase(db_file)
        db.clear_ds()

        timesteps1 = range(3)
        timesteps2 = range(3, 7)
        neuron_ids1 = range(2)
        neuron_ids2 = range(2, 4, 2)
        key = "timestamp"
        v1_1 = self._random_data(timesteps1, neuron_ids1)
        db.insert_matrix_items("pop1", "v", key, neuron_ids1, v1_1)
        v1_2 = self._random_data(timesteps1, neuron_ids2)
        db.insert_matrix_items("pop1", "v", key, neuron_ids2, v1_2)
        v2_1 = self._random_data(timesteps2, neuron_ids1)
        db.insert_matrix_items("pop1", "v", key, neuron_ids1, v2_1)
        v2_2 = self._random_data(timesteps2, neuron_ids2)
        db.insert_matrix_items("pop1", "v", key, neuron_ids2, v2_2)
        gsyn2_1 = self._random_data(timesteps2, neuron_ids1)
        db.insert_matrix_items("pop1", "gsyn", key, neuron_ids1, gsyn2_1)
        gsyn2_2 = self._random_data(timesteps2, neuron_ids1)
        db.insert_matrix_items("pop1", "gsyn", key, neuron_ids1, gsyn2_2)
        vother = self._random_data(timesteps1, neuron_ids1)
        db.insert_matrix_items("pop2", "v", key, neuron_ids1, vother)

        meta = db.get_variable_map()
        self.assertIn("pop1", meta)
        self.assertIn("v", meta["pop1"])
        self.assertIn("gsyn", meta["pop1"])
        self.assertEqual(2, len(meta["pop1"]))
        self.assertIn("pop2", meta)
        self.assertEqual(2, len(meta))

        self.assertEqual(vother, db.get_data("pop2", "v")[1])
        db.create_all_views()
        self.assertEqual(5, len(db.get_views()))

        gsyn2 = gsyn2_1 + gsyn2_2
        self.assertEqual(gsyn2, db.get_data("pop1", "gsyn")[1])

        v1 = v1_1 + v2_1
        v2 = v1_2 + v2_2
        v = [z[0] + z[1][1:] for z in zip(v1, v2)]
        self.assertEqual(v, db.get_data("pop1", "v")[1])

        self.assertEqual(5, len(db.get_views()))

    def test_missing_data(self):
        db_file = os.path.join(os.path.dirname(__file__), "missing.sqlite3")
        if os.path.exists(db_file):
            os.remove(db_file)
        db = RecordedDatabase(db_file)
        db.clear_ds()

        timesteps1 = [0, 1, 2, 4, 5]
        timesteps2 = [2, 1, 4, 5, 3]
        timesteps3 = [0, 2, 1, 4, 5, 3]
        neuron_ids1 = range(2)
        neuron_ids2 = range(2, 4, 2)
        neuron_ids3 = range(3, 5, 2)
        key = "bacon"
        v1 = self._random_data(timesteps1, neuron_ids1)
        db.insert_matrix_items("pop1", "v", key, neuron_ids1, v1)
        v2 = self._random_data(timesteps2, neuron_ids2)
        db.insert_matrix_items("pop1", "v", key, neuron_ids2, v2)
        v3 = self._random_data(timesteps3, neuron_ids3)
        db.insert_matrix_items("pop1", "v", key, neuron_ids3, v3)

        meta = db.get_variable_map()
        self.assertIn("pop1", meta)
        self.assertIn("v", meta["pop1"])
        self.assertEqual(1, len(meta["pop1"]))
        self.assertEqual(1, len(meta))

        v_result = db.get_data("pop1", "v")[1]
        self.assertEqual(6, len(v_result))

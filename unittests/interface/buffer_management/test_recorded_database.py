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

    def _random_matrix_data(self, timesteps, neuron_ids):
        data = []
        for timestep in timesteps:
            line = []
            line.append(timestep)
            for _ in neuron_ids:
                line.append(random.randint(0, 100000000))
            data.append(line)
        return data

    def _random_exists_data(self, timesteps, neuron_ids):
        data = []
        for timestep in timesteps:
            for neuron_id in neuron_ids:
                count = random.randint(-10, 5)
                for _ in range(count):
                    line = [neuron_id, timestep]
                    data.append(line)
        return data

    def test_use_database(self):
        db_file = os.path.join(os.path.dirname(__file__), "test.sqlite3")
        if os.path.exists(db_file):
            os.remove(db_file)
        db = RecordedDatabase(db_file)
        db.clear_ds()

        timesteps1 = range(3)
        timesteps2 = range(3, 7)
        neuron_ids1 = range(2)
        neuron_ids2 = range(2, 4, 2)
        key = "timestamp"
        v1_1 = self._random_matrix_data(timesteps1, neuron_ids1)
        db.insert_matrix_items("pop1", "v", key, neuron_ids1, v1_1)
        v1_2 = self._random_matrix_data(timesteps1, neuron_ids2)
        db.insert_matrix_items("pop1", "v", key, neuron_ids2, v1_2)
        v2_1 = self._random_matrix_data(timesteps2, neuron_ids1)
        db.insert_matrix_items("pop1", "v", key, neuron_ids1, v2_1)
        v2_2 = self._random_matrix_data(timesteps2, neuron_ids2)
        db.insert_matrix_items("pop1", "v", key, neuron_ids2, v2_2)
        gsyn2_1 = self._random_matrix_data(timesteps2, neuron_ids1)
        db.insert_matrix_items("pop1", "gsyn", key, neuron_ids1, gsyn2_1)
        gsyn2_2 = self._random_matrix_data(timesteps2, neuron_ids1)
        db.insert_matrix_items("pop1", "gsyn", key, neuron_ids1, gsyn2_2)
        vother = self._random_matrix_data(timesteps1, neuron_ids1)
        db.insert_matrix_items("pop2", "v", key, neuron_ids1, vother)
        s1_1 = self._random_exists_data(timesteps1, neuron_ids1)
        db.insert_exists_items("pop1", "spikes", key, s1_1)
        s1_2 = self._random_exists_data(timesteps1, neuron_ids2)
        db.insert_exists_items("pop1", "spikes", key, s1_2)
        s2_1 = self._random_exists_data(timesteps2, neuron_ids1)
        db.insert_exists_items("pop1", "spikes", key, s2_1)
        s2_2 = self._random_exists_data(timesteps2, neuron_ids2)
        db.insert_exists_items("pop1", "spikes", key, s2_2)

        timesteps1 = [0, 1, 2, 4, 5]
        timesteps2 = [2, 1, 4, 5, 3]
        timesteps3 = [0, 2, 1, 4, 5, 3]
        neuron_ids1 = range(2)
        neuron_ids2 = range(2, 4, 2)
        neuron_ids3 = range(3, 5, 2)
        key = "bacon"
        f1 = self._random_matrix_data(timesteps1, neuron_ids1)
        db.insert_matrix_items("pop1", "foo", key, neuron_ids1, f1)
        f2 = self._random_matrix_data(timesteps2, neuron_ids2)
        db.insert_matrix_items("pop1", "foo", key, neuron_ids2, f2)
        f3 = self._random_matrix_data(timesteps3, neuron_ids3)
        db.insert_matrix_items("pop1", "foo", key, neuron_ids3, f3)

        meta = db.get_variable_map()
        self.assertIn("pop1", meta)
        self.assertIn("v", meta["pop1"])
        self.assertIn("gsyn", meta["pop1"])
        self.assertIn("foo", meta["pop1"])
        self.assertIn("spikes", meta["pop1"])
        self.assertEqual(4, len(meta["pop1"]))
        self.assertIn("pop2", meta)
        self.assertIn("pop2", meta)
        self.assertEqual(2, len(meta))

        self.assertEqual(vother, db.get_data("pop2", "v")[1])
        db.create_all_views()
        n_views = len(db.get_views())

        gsyn2 = gsyn2_1 + gsyn2_2
        self.assertEqual(gsyn2, db.get_data("pop1", "gsyn")[1])

        v1 = v1_1 + v2_1
        v2 = v1_2 + v2_2
        v = [z[0] + z[1][1:] for z in zip(v1, v2)]
        # Not guaranteed to be in order but are so far
        self.assertEqual(v, db.get_data("pop1", "v")[1])

        spikes = []
        spikes.extend(s1_1)
        spikes.extend(s1_2)
        spikes.extend(s2_1)
        spikes.extend(s2_2)
        # Not guaranteed to be in order but are so far
        self.assertEqual(spikes, db.get_data("pop1", "spikes")[1])

        foo_result = db.get_data("pop1", "foo")[1]
        self.assertEqual(6, len(foo_result))


        # check getting data did not ada any additional views
        self.assertEqual(n_views, len(db.get_views()))

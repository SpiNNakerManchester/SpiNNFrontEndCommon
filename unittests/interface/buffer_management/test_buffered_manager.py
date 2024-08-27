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
import os
from typing import Sequence

from spinn_utilities.config_holder import set_config
from spinn_utilities.overrides import overrides

from spinn_machine.version.version_strings import VersionStrings

from pacman.model.graphs.machine import SimpleMachineVertex
from pacman.model.placements import Placement, Placements

from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.buffer_management import BufferManager
from spinn_front_end_common.interface.buffer_management.buffer_models import (
    AbstractReceiveBuffersToHost)
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import BufferDatabase
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.utilities.exceptions import (
    BufferedRegionNotPresent)


class MockAbstractReceiveBuffersToHost(SimpleMachineVertex,
                                       AbstractReceiveBuffersToHost):
    @overrides(AbstractReceiveBuffersToHost.get_recorded_region_ids)
    def get_recorded_region_ids(self) -> Sequence[int]:
        return [0]

    @overrides(AbstractReceiveBuffersToHost.get_recording_region_base_address)
    def get_recording_region_base_address(self, placement: Placement) -> int:
        raise NotImplementedError


class TestBufferedDatabase(unittest.TestCase):

    def setUp(self):
        unittest_setup()

    def test_use_database(self):
        set_config("Machine", "versions", VersionStrings.ANY.text)
        writer = FecDataWriter.mock()
        f = BufferDatabase.default_database_file()
        self.assertFalse(os.path.isfile(f), "no existing DB at first")

        info = Placements([])
        p1 = Placement(
            MockAbstractReceiveBuffersToHost(None, label="V1"), 1, 2, 3)
        info.add_placement(p1)
        v2 = SimpleMachineVertex(None, label="V2")
        p2 = Placement(v2, 1, 2, 5)
        info.add_placement(p2)
        info.add_placement(Placement(SimpleMachineVertex(None), 2, 2, 3))
        writer.set_placements(info)
        bm = BufferManager()
        with BufferDatabase() as brd:
            self.assertTrue(os.path.isfile(f), "DB now exists")

            brd.store_vertex_labels()
            label = brd.get_core_name(1, 2, 3)
            self.assertEqual("V1", label)
            label = brd.get_core_name(1, 2, 5)
            self.assertEqual("V2", label)
            label = brd.get_core_name(4, 3, 0)
            self.assertEqual("SCAMP(OS)_4:3", label)

            with self.assertRaises(LookupError):
                brd.get_region_data(1, 2, 3, 0)

        with self.assertRaises(BufferedRegionNotPresent):
            bm.get_data_by_placement(p1, 0)

        with BufferDatabase() as brd:
            brd.start_new_extraction()
            brd.store_data_in_region_buffer(1, 2, 3, 0, False, b"abc")
            data, missing = brd.get_region_data(1, 2, 3, 0)
            self.assertFalse(missing, "data shouldn't be 'missing'")
            self.assertEqual(bytes(data), b"abc")

        data, missing = bm.get_data_by_placement(p1, 0)
        self.assertFalse(missing, "data shouldn't be 'missing'")
        self.assertEqual(bytes(data), b"abc")

        with BufferDatabase() as brd:
            brd.start_new_extraction()
            brd.store_data_in_region_buffer(1, 2, 3, 0, False, b"def")
            data, missing = brd.get_region_data(1, 2, 3, 0)
            self.assertFalse(missing, "data shouldn't be 'missing'")
            self.assertEqual(bytes(data), b"abcdef")

            brd.start_new_extraction()
            brd.store_data_in_region_buffer(1, 2, 3, 0, True, b"g")
            data, missing = brd.get_region_data(1, 2, 3, 0)
            self.assertTrue(missing, "data should be 'missing'")
            self.assertEqual(bytes(data), b"abcdefg")

        data, missing = bm.get_data_by_placement(p1, 0)
        self.assertTrue(missing, "data should be 'missing'")
        self.assertEqual(bytes(data), b"abcdefg")

        with BufferDatabase() as brd:
            data, missing = brd.get_region_data_by_extraction_id(1, 2, 3, 0, 2)
            self.assertFalse(missing, "data shouldn't be 'missing'")
            self.assertEqual(bytes(data), b"def")

            data, missing = brd.get_region_data_by_extraction_id(
                1, 2, 3, 0, -1)
            self.assertTrue(missing, "data should be 'missing'")
            self.assertEqual(bytes(data), b"g")

            self.assertTrue(os.path.isfile(f), "DB still exists")

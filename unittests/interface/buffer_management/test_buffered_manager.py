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
from typing import Sequence, Tuple

from spinn_utilities.config_holder import set_config
from spinn_utilities.overrides import overrides

from spinn_machine.version.version_strings import VersionStrings

from pacman.model.graphs.machine import SimpleMachineVertex
from pacman.model.placements import Placement, Placements

from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.buffer_management import BufferManager
from spinn_front_end_common.interface.buffer_management.buffer_models import (
    AbstractReceiveBuffersToHost, AbstractReceiveRegionsToHost)
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import BufferDatabase
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.utilities.exceptions import (
    BufferedRegionNotPresent)


class MockAbstractReceiveBuffersToHost(
        SimpleMachineVertex, AbstractReceiveBuffersToHost):

    @overrides(AbstractReceiveBuffersToHost.get_recorded_region_ids)
    def get_recorded_region_ids(self) -> Sequence[int]:
        return [0]

    @overrides(AbstractReceiveBuffersToHost.get_recording_region_base_address)
    def get_recording_region_base_address(self, placement: Placement) -> int:
        raise NotImplementedError


class MockAbstractReceiveRegionsToHost(
        SimpleMachineVertex, AbstractReceiveRegionsToHost):

    @overrides(AbstractReceiveRegionsToHost.get_download_regions)
    def get_download_regions(self, placement: Placement) -> Sequence[
            Tuple[int, int, int]]:
        return (0, 1235678, 90)


class TestBufferedDatabase(unittest.TestCase):

    def setUp(self):
        unittest_setup()

    def test_recording(self):
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

            label = brd.get_core_name(0, 0, 0)
            self.assertEqual("SCAMP(OS)_0:0", label)
            version = writer.get_machine_version()
            if version.n_chips_per_board >= 4:
                label = brd.get_core_name(1, 1, 0)
                self.assertEqual("SCAMP(OS)_1:1", label)
            if version.n_chips_per_board >= 40:
                label = brd.get_core_name(4, 3, 0)
                self.assertEqual("SCAMP(OS)_4:3", label)

            with self.assertRaises(LookupError):
                brd.get_recording(1, 2, 3, 0)

        with self.assertRaises(BufferedRegionNotPresent):
            bm.get_recording(p1, 0)

        with BufferDatabase() as brd:
            brd.start_new_extraction()
            brd.store_recording(1, 2, 3, 0, False, b"abc")
            data, missing = brd.get_recording(1, 2, 3, 0)
            self.assertFalse(missing, "data shouldn't be 'missing'")
            self.assertEqual(bytes(data), b"abc")

        data, missing = bm.get_recording(p1, 0)
        self.assertFalse(missing, "data shouldn't be 'missing'")
        self.assertEqual(bytes(data), b"abc")

        with BufferDatabase() as brd:
            brd.start_new_extraction()
            brd.store_recording(1, 2, 3, 0, False, b"def")
            data, missing = brd.get_recording(1, 2, 3, 0)
            self.assertFalse(missing, "data shouldn't be 'missing'")
            self.assertEqual(bytes(data), b"abcdef")

            brd.start_new_extraction()
            brd.store_recording(1, 2, 3, 0, True, b"g")
            data, missing = brd.get_recording(1, 2, 3, 0)
            self.assertTrue(missing, "data should be 'missing'")
            self.assertEqual(bytes(data), b"abcdefg")

        data, missing = bm.get_recording(p1, 0)
        self.assertTrue(missing, "data should be 'missing'")
        self.assertEqual(bytes(data), b"abcdefg")

        with BufferDatabase() as brd:
            data, missing = brd.get_recording_by_extraction_id(1, 2, 3, 0, 2)
            self.assertFalse(missing, "data shouldn't be 'missing'")
            self.assertEqual(bytes(data), b"def")

            data, missing = brd.get_recording_by_extraction_id(
                1, 2, 3, 0, -1)
            self.assertTrue(missing, "data should be 'missing'")
            self.assertEqual(bytes(data), b"g")

            self.assertTrue(os.path.isfile(f), "DB still exists")

    def test_download(self):
        set_config("Machine", "versions", VersionStrings.ANY.text)
        writer = FecDataWriter.mock()

        info = Placements([])
        p1 = Placement(
            MockAbstractReceiveRegionsToHost(None, label="V1"), 1, 2, 3)
        info.add_placement(p1)
        writer.set_placements(info)
        bm = BufferManager()
        with BufferDatabase() as brd:
            brd.store_vertex_labels()
            with self.assertRaises(LookupError):
                brd.get_download_by_extraction_id(1, 2, 3, 0, -1)

        with self.assertRaises(BufferedRegionNotPresent):
            bm.get_download(p1, 0)

        with BufferDatabase() as brd:
            brd.start_new_extraction()
            brd.store_download(1, 2, 3, 0, False, b"abc")
            data, missing = brd.get_download_by_extraction_id(1, 2, 3, 0, -1)
            self.assertFalse(missing, "data should be 'missing'")
            self.assertEqual(bytes(data), b"abc")

        data, missing = bm.get_download(p1, 0)
        self.assertFalse(missing, "data shouldn't be 'missing'")
        self.assertEqual(bytes(data), b"abc")

        with BufferDatabase() as brd:
            brd.start_new_extraction()
            brd.store_download(1, 2, 3, 0, False, b"def")
            data, missing = brd.get_download_by_extraction_id(1, 2, 3, 0, -1)
            self.assertFalse(missing, "data shouldn't be 'missing'")
            self.assertEqual(bytes(data), b"def")

        data, missing = bm.get_download(p1, 0)
        self.assertFalse(missing, "data shouldn't be 'missing'")
        self.assertEqual(bytes(data), b"def")

        with BufferDatabase() as brd:
            brd.start_new_extraction()
            brd.store_download(1, 2, 3, 0, True, b"gh")
            data, missing = brd.get_download_by_extraction_id(1, 2, 3, 0, -1)
            self.assertTrue(missing, "data should be 'missing'")
            self.assertEqual(bytes(data), b"gh")

        data, missing = bm.get_download(p1, 0)
        self.assertTrue(missing, "data should be 'missing'")
        self.assertEqual(bytes(data), b"gh")

    def test_clear(self):
        set_config("Machine", "versions", VersionStrings.ANY.text)
        writer = FecDataWriter.mock()

        info = Placements([])
        p1 = Placement(
            MockAbstractReceiveBuffersToHost(None, label="V1"), 1, 2, 3)
        info.add_placement(p1)
        writer.set_placements(info)

        bm = BufferManager()
        with BufferDatabase() as brd:
            brd.start_new_extraction()
            brd.store_recording(1, 2, 3, 0, False, b"abc")
            brd.start_new_extraction()
            brd.store_recording(1, 2, 3, 0, False, b"def")

        data, missing = bm.get_recording(p1, 0)
        self.assertFalse(missing, "data shouldn't be 'missing'")
        self.assertEqual(bytes(data), b"abcdef")
        bm.clear_recorded_data(1, 2, 3, 0)
        data, missing = bm.get_recording(p1, 0)
        self.assertTrue(missing, "data should be 'missing'")
        self.assertEqual(bytes(data), b"")

    def test_not_recording_type(self):
        writer = FecDataWriter.mock()
        info = Placements([])
        writer.set_placements(info)
        bm = BufferManager()
        v = SimpleMachineVertex(None, label="V2")
        p = Placement(v, 1, 2, 5)
        with self.assertRaises(NotImplementedError):
            bm.get_recording(p, 1)

    def test_not_data_recorded(self):
        writer = FecDataWriter.mock()
        v = MockAbstractReceiveBuffersToHost(None, label="V2")
        p = Placement(v, 1, 2, 5)
        info = Placements([p])
        writer.set_placements(info)
        bm = BufferManager()
        try:
            bm.get_recording(p, 0)
            raise Exception("Exception should have been raised")
        except BufferedRegionNotPresent as ex:
            self.assertIn("should have record region", str(ex))

    def test_not_recording_region(self):
        writer = FecDataWriter.mock()
        v = MockAbstractReceiveBuffersToHost(None, label="V2")
        p = Placement(v, 1, 2, 5)
        info = Placements([p])
        writer.set_placements(info)
        bm = BufferManager()
        try:
            bm.get_recording(p, 1)
            raise Exception("Exception should have been raised")
        except BufferedRegionNotPresent as ex:
            self.assertIn("not set to record or download region 1", str(ex))

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

import os
import tempfile
from typing import Iterable, Optional
import unittest
from spinn_utilities.config_holder import set_config
from spinn_utilities.make_tools.log_sqllite_database import LogSqlLiteDatabase
from spinn_utilities.overrides import overrides
from spinn_machine import CoreSubsets, CoreSubset
from spinnman.model import IOBuffer
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.interface_functions import (
    chip_io_buf_extractor)
from spinnman.model import ExecutableTargets
from spinnman.transceiver.mockable_transceiver import MockableTransceiver


class _PretendTransceiver(MockableTransceiver):
    def __init__(self, iobuffers):
        self._iobuffers = iobuffers

    @overrides(MockableTransceiver.get_iobuf)
    def get_iobuf(self, core_subsets: Optional[CoreSubsets] = None
                  ) -> Iterable[IOBuffer]:
        for iobuf in self._iobuffers:
            if core_subsets.is_core(iobuf.x, iobuf.y, iobuf.p):
                yield iobuf


def mock_text(x, y, p):
    filename = "myfile.c"
    error = "Test Error"
    warning = "Test Warning"
    error_text = "[ERROR]    ({}): {}\n".format(filename, error)
    result_error = "{}, {}, {}: {} ({})".format(x, y, p, error, filename)
    warning_text = "[WARNING]    ({}): {}\n".format(filename, warning)
    result_warning = "{}, {}, {}: {} ({})".format(
        x, y, p, warning, filename)
    text = "Test {} {} {}\n".format(x, y, p) + warning_text + error_text
    return text, result_error, result_warning


text001, result_error001, result_warning001 = mock_text(0, 0, 1)
text002, result_error002, result_warning002 = mock_text(0, 0, 2)
text111, result_error111, result_warning111 = mock_text(1, 1, 1)
text112, result_error112, result_warning112 = mock_text(1, 1, 2)
text003, result_error003, result_warning003 = mock_text(0, 0, 3)

path = os.path.dirname(os.path.abspath(__file__))


def mock_aplx(name):
    return os.path.join(path, "mock{}.aplx".format(name))


executable_targets = ExecutableTargets()
core_subsets = CoreSubsets([CoreSubset(0, 0, [1, 2])])
fooaplx = mock_aplx("foo")
executable_targets.add_subsets(fooaplx, core_subsets)
core_subsets = CoreSubsets([CoreSubset(1, 1, [1, 2])])
baraplx = mock_aplx("bar")
executable_targets.add_subsets(baraplx, core_subsets)
core_subsets = CoreSubsets([CoreSubset(0, 0, [3])])
alphaaplx = mock_aplx("alpha")
executable_targets.add_subsets(alphaaplx, core_subsets)


class TestFrontEndCommonChipIOBufExtractor(unittest.TestCase):

    def setUp(self):
        unittest_setup()
        os.environ["C_LOGS_DICT"] = tempfile.mktemp()
        # There needs to be a dict but it can be empty
        LogSqlLiteDatabase(new_dict=True)
        writer = FecDataWriter.mock()
        writer.set_transceiver(_PretendTransceiver(
            [IOBuffer(0, 0, 1, text001), IOBuffer(0, 0, 2, text002),
             IOBuffer(1, 1, 1, text111), IOBuffer(1, 1, 2, text112),
             IOBuffer(0, 0, 3, text003)]))
        FecDataView.register_binary_search_path(path)
        writer.set_executable_targets(executable_targets)

    def testExectuableFinder(self):
        self.assertIn(fooaplx, FecDataView.get_executable_path(fooaplx))

    def testCallSimple(self):
        folder = FecDataView.get_app_provenance_dir_path()
        error_entries, warn_entries = chip_io_buf_extractor()
        set_config("Reports", "extract_iobuf_from_cores", "None")
        set_config("Reports", "extract_iobuf_from_binary_types", "None")
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_1.txt")
        self.assertTrue(os.path.exists(testfile))
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_2.txt")
        self.assertTrue(os.path.exists(testfile))
        testfile = os.path.join(
            folder, "iobuf_for_chip_1_1_processor_id_1.txt")
        self.assertTrue(os.path.exists(testfile))
        testfile = os.path.join(
            folder, "iobuf_for_chip_1_1_processor_id_2.txt")
        self.assertTrue(os.path.exists(testfile))
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_3.txt")
        self.assertTrue(os.path.exists(testfile))
        self.assertIn(result_error001, error_entries)
        self.assertIn(result_error002, error_entries)
        self.assertIn(result_error111, error_entries)
        self.assertIn(result_error112, error_entries)
        self.assertIn(result_error003, error_entries)
        self.assertIn(result_warning001, warn_entries)
        self.assertIn(result_warning002, warn_entries)
        self.assertIn(result_warning111, warn_entries)
        self.assertIn(result_warning112, warn_entries)
        self.assertIn(result_warning003, warn_entries)
        self.assertEqual(5, len(warn_entries))

    def testCallChips(self):
        folder = FecDataView.get_app_provenance_dir_path()
        set_config("Reports", "extract_iobuf_from_cores", "0,0,2:0,0,3")
        set_config("Reports", "extract_iobuf_from_binary_types", "None")
        error_entries, warn_entries = chip_io_buf_extractor()
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_1.txt")
        self.assertFalse(os.path.exists(testfile))
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_2.txt")
        self.assertTrue(os.path.exists(testfile))
        testfile = os.path.join(
            folder, "iobuf_for_chip_1_1_processor_id_1.txt")
        self.assertFalse(os.path.exists(testfile))
        testfile = os.path.join(
            folder, "iobuf_for_chip_1_1_processor_id_2.txt")
        self.assertFalse(os.path.exists(testfile))
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_3.txt")
        self.assertTrue(os.path.exists(testfile))
        self.assertNotIn(result_error001, error_entries)
        self.assertIn(result_error002, error_entries)
        self.assertNotIn(result_error111, error_entries)
        self.assertNotIn(result_error112, error_entries)
        self.assertIn(result_error003, error_entries)
        self.assertNotIn(result_warning001, warn_entries)
        self.assertIn(result_warning002, warn_entries)
        self.assertNotIn(result_warning111, warn_entries)
        self.assertNotIn(result_warning112, warn_entries)
        self.assertIn(result_warning003, warn_entries)
        self.assertEqual(2, len(warn_entries))

    def testCallBinary(self):
        folder = FecDataView.get_app_provenance_dir_path()
        set_config("Reports", "extract_iobuf_from_cores", "None")
        set_config("Reports", "extract_iobuf_from_binary_types",
                   fooaplx + "," + alphaaplx)
        error_entries, warn_entries = chip_io_buf_extractor()
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_1.txt")
        self.assertTrue(os.path.exists(testfile))
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_2.txt")
        self.assertTrue(os.path.exists(testfile))
        testfile = os.path.join(
            folder, "iobuf_for_chip_1_1_processor_id_1.txt")
        self.assertFalse(os.path.exists(testfile))
        testfile = os.path.join(
            folder, "iobuf_for_chip_1_1_processor_id_2.txt")
        self.assertFalse(os.path.exists(testfile))
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_3.txt")
        self.assertTrue(os.path.exists(testfile))
        self.assertIn(result_error001, error_entries)
        self.assertIn(result_error002, error_entries)
        self.assertIn(result_error003, error_entries)
        self.assertIn(result_warning001, warn_entries)
        self.assertIn(result_warning002, warn_entries)
        self.assertIn(result_warning003, warn_entries)
        self.assertEqual(3, len(warn_entries))

    def testCallBoth(self):
        folder = FecDataView.get_app_provenance_dir_path()
        set_config("Reports", "extract_iobuf_from_cores", "0,0,2:1,1,1")
        set_config("Reports", "extract_iobuf_from_binary_types",
                   fooaplx + "," + alphaaplx)
        error_entries, warn_entries = chip_io_buf_extractor()
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_1.txt")
        self.assertTrue(os.path.exists(testfile))
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_2.txt")
        self.assertTrue(os.path.exists(testfile))
        testfile = os.path.join(
            folder, "iobuf_for_chip_1_1_processor_id_1.txt")
        self.assertTrue(os.path.exists(testfile))
        testfile = os.path.join(
            folder, "iobuf_for_chip_1_1_processor_id_2.txt")
        self.assertFalse(os.path.exists(testfile))
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_3.txt")
        self.assertTrue(os.path.exists(testfile))
        os.unlink(testfile)
        self.assertIn(result_error001, error_entries)
        self.assertIn(result_error002, error_entries)
        self.assertIn(result_error111, error_entries)
        self.assertNotIn(result_error112, error_entries)
        self.assertIn(result_error003, error_entries)
        self.assertIn(result_warning001, warn_entries)
        self.assertIn(result_warning002, warn_entries)
        self.assertIn(result_warning111, warn_entries)
        self.assertNotIn(result_warning112, warn_entries)
        self.assertIn(result_warning003, warn_entries)
        self.assertEqual(4, len(warn_entries))


if __name__ == "__main__":
    unittest.main()

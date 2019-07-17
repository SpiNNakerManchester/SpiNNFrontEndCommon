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
import tempfile
import unittest
from spinn_utilities.executable_finder import ExecutableFinder
from spinn_machine import CoreSubsets, CoreSubset
from spinnman.model import IOBuffer
from spinn_front_end_common.interface.interface_functions import (
    ChipIOBufExtractor)
from spinn_front_end_common.utilities.utility_objs import ExecutableTargets


class _PretendTransceiver(object):
    def __init__(self, iobuffers):
        self._iobuffers = iobuffers

    def get_iobuf(self, core_subsets):
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


def mock_aplx(id):
    return os.path.join(path, "mock{}.aplx".format(id))


extractor = ChipIOBufExtractor()
executableFinder = ExecutableFinder([path])

transceiver = _PretendTransceiver(
    [IOBuffer(0, 0, 1, text001), IOBuffer(0, 0, 2, text002),
     IOBuffer(1, 1, 1, text111), IOBuffer(1, 1, 2, text112),
     IOBuffer(0, 0, 3, text003)])

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

    def testExectuableFinder(self):
        self.assertIn(fooaplx, executableFinder.get_executable_path(fooaplx))

    def testCallSimple(self):
        folder = tempfile.mkdtemp()
        error_entries, warn_entries = extractor(
            transceiver, executable_targets=executable_targets,
            executable_finder=None, provenance_file_path=folder)
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_1.txt")
        self.assertTrue(os.path.exists(testfile))
        os.unlink(testfile)
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_2.txt")
        self.assertTrue(os.path.exists(testfile))
        os.unlink(testfile)
        testfile = os.path.join(
            folder, "iobuf_for_chip_1_1_processor_id_1.txt")
        self.assertTrue(os.path.exists(testfile))
        os.unlink(testfile)
        testfile = os.path.join(
            folder, "iobuf_for_chip_1_1_processor_id_2.txt")
        self.assertTrue(os.path.exists(testfile))
        os.unlink(testfile)
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_3.txt")
        self.assertTrue(os.path.exists(testfile))
        os.unlink(testfile)
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
        os.rmdir(folder)

    def testCallChips(self):
        folder = tempfile.mkdtemp()
        error_entries, warn_entries = extractor(
            transceiver, executable_targets=executable_targets,
            executable_finder=None, provenance_file_path=folder,
            from_cores="0,0,2:0,0,3")
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_1.txt")
        self.assertFalse(os.path.exists(testfile))
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_2.txt")
        self.assertTrue(os.path.exists(testfile))
        os.unlink(testfile)
        testfile = os.path.join(
            folder, "iobuf_for_chip_1_1_processor_id_1.txt")
        self.assertFalse(os.path.exists(testfile))
        testfile = os.path.join(
            folder, "iobuf_for_chip_1_1_processor_id_2.txt")
        self.assertFalse(os.path.exists(testfile))
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_3.txt")
        self.assertTrue(os.path.exists(testfile))
        os.unlink(testfile)
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
        os.rmdir(folder)

    def testCallBinary(self):
        folder = tempfile.mkdtemp()
        error_entries, warn_entries = extractor(
            transceiver, executable_targets=executable_targets,
            executable_finder=executableFinder, provenance_file_path=folder,
            from_cores=None, binary_types=fooaplx + "," + alphaaplx)
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_1.txt")
        self.assertTrue(os.path.exists(testfile))
        os.unlink(testfile)
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_2.txt")
        self.assertTrue(os.path.exists(testfile))
        os.unlink(testfile)
        testfile = os.path.join(
            folder, "iobuf_for_chip_1_1_processor_id_1.txt")
        self.assertFalse(os.path.exists(testfile))
        testfile = os.path.join(
            folder, "iobuf_for_chip_1_1_processor_id_2.txt")
        self.assertFalse(os.path.exists(testfile))
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_3.txt")
        self.assertTrue(os.path.exists(testfile))
        os.unlink(testfile)
        self.assertIn(result_error001, error_entries)
        self.assertIn(result_error002, error_entries)
        self.assertIn(result_error003, error_entries)
        self.assertIn(result_warning001, warn_entries)
        self.assertIn(result_warning002, warn_entries)
        self.assertIn(result_warning003, warn_entries)
        self.assertEqual(3, len(warn_entries))
        os.rmdir(folder)

    def testCallBoth(self):
        folder = tempfile.mkdtemp()
        error_entries, warn_entries = extractor(
            transceiver, executable_targets=executable_targets,
            executable_finder=executableFinder, provenance_file_path=folder,
            from_cores="0,0,2:1,1,1", binary_types=fooaplx + "," + alphaaplx)
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_1.txt")
        self.assertTrue(os.path.exists(testfile))
        os.unlink(testfile)
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_2.txt")
        self.assertTrue(os.path.exists(testfile))
        os.unlink(testfile)
        testfile = os.path.join(
            folder, "iobuf_for_chip_1_1_processor_id_1.txt")
        self.assertTrue(os.path.exists(testfile))
        os.unlink(testfile)
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
        os.rmdir(folder)


if __name__ == "__main__":
    unittest.main()

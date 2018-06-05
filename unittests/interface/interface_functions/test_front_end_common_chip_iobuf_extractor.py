import os
import sys
import tempfile
import unittest
from spinn_front_end_common.interface.interface_functions \
    import ChipIOBufExtractor
from spinn_machine import CoreSubsets, CoreSubset
from spinnman.model import ExecutableTargets, IOBuffer


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

def mock_aplx(id):
    path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(path, "mock{}.aplx".format(id))


text1, result_error1, result_warning1 = mock_text(0, 0, 1)
text2, result_error2, result_warning2 = mock_text(0, 0, 2)
text3, result_error3, result_warning3 = mock_text(1, 1, 1)
text4, result_error4, result_warning4 = mock_text(1, 1, 2)
text5, result_error5, result_warning5 = mock_text(0, 0, 3)

extractor = ChipIOBufExtractor()

transceiver = _PretendTransceiver(
    [IOBuffer(0, 0, 1, text1), IOBuffer(0, 0, 2, text2),
     IOBuffer(1, 1, 1, text3), IOBuffer(1, 1, 2, text4),
     IOBuffer(0, 0, 3, text5)])

executable_targets = ExecutableTargets()
core_subsets = CoreSubsets([CoreSubset(0, 0, [1, 2])])
fooaplx = mock_aplx("foo");
executable_targets.add_subsets(fooaplx, core_subsets)
core_subsets = CoreSubsets([CoreSubset(1, 1, [1, 2])])
baraplx = mock_aplx("bar");
executable_targets.add_subsets(baraplx, core_subsets)
core_subsets = CoreSubsets([CoreSubset(0, 0, [3])])
alphaaplx = mock_aplx("alpha");
executable_targets.add_subsets(alphaaplx, core_subsets)


class _PretendExecutiveFinder(object):

    def get_executable_pathss(self, binary_types):
        for binary_type in binary_types.split(",")

class TestFrontEndCommonChipIOBufExtractor(unittest.TestCase):

    def testcallsimple(self):
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
        self.assertIn(result_error1, error_entries)
        self.assertIn(result_error2, error_entries)
        self.assertIn(result_error3, error_entries)
        self.assertIn(result_error4, error_entries)
        self.assertIn(result_error5, error_entries)
        self.assertIn(result_warning1, warn_entries)
        self.assertIn(result_warning2, warn_entries)
        self.assertIn(result_warning3, warn_entries)
        self.assertIn(result_warning4, warn_entries)
        self.assertIn(result_warning5, warn_entries)
        self.assertEqual(5, len(warn_entries))
        os.rmdir(folder)

    def testcallchips(self):
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
        self.assertNotIn(result_error1, error_entries)
        self.assertIn(result_error2, error_entries)
        self.assertNotIn(result_error3, error_entries)
        self.assertNotIn(result_error4, error_entries)
        self.assertIn(result_error5, error_entries)
        self.assertNotIn(result_warning1, warn_entries)
        self.assertIn(result_warning2, warn_entries)
        self.assertNotIn(result_warning3, warn_entries)
        self.assertNotIn(result_warning4, warn_entries)
        self.assertIn(result_warning5, warn_entries)
        self.assertEqual(2, len(warn_entries))
        os.rmdir(folder)


    def testcallBinary(self):
        folder = tempfile.mkdtemp()
        error_entries, warn_entries = extractor(
            transceiver, executable_targets=executable_targets,
            executable_finder=None, provenance_file_path=folder,
            from_cores=None,binary_types="mockfoo,mockalpha")
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
        self.assertIn(result_error1, error_entries)
        self.assertIn(result_error2, error_entries)
        self.assertIn(result_error3, error_entries)
        self.assertIn(result_error4, error_entries)
        self.assertIn(result_error5, error_entries)
        self.assertIn(result_warning1, warn_entries)
        self.assertIn(result_warning2, warn_entries)
        self.assertIn(result_warning3, warn_entries)
        self.assertIn(result_warning4, warn_entries)
        self.assertIn(result_warning5, warn_entries)
        self.assertEqual(5, len(warn_entries))
        os.rmdir(folder)


if __name__ == "__main__":
    unittest.main()

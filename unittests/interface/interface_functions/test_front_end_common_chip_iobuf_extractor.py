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


class TestFrontEndCommonChipIOBufExtractor(unittest.TestCase):

    def mock_aplx(self, id):
        class_file = sys.modules[self.__module__].__file__
        path = os.path.dirname(os.path.abspath(class_file))
        return os.path.join(path, "mock{}.aplx".format(id))

    def mock_executable_targets(self):
        executable_targets = ExecutableTargets()
        core_subsets = CoreSubsets([CoreSubset(0, 0, [1, 2])])
        aplx = self.mock_aplx("foo");
        executable_targets.add_subsets(aplx, core_subsets)
        core_subsets = CoreSubsets([CoreSubset(1, 1, [1, 2])])
        aplx = self.mock_aplx("bar");
        executable_targets.add_subsets(aplx, core_subsets)
        return executable_targets

    def mock_text(self, x, y, p):
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

    def testcall(self):
        executable_targets = self.mock_executable_targets()
        text1, result_error1, result_warning1 = self.mock_text(0, 0, 1)
        text2, result_error2, result_warning2 = self.mock_text(0, 0, 2)
        text3, result_error3, result_warning3 = self.mock_text(1, 1, 1)
        text4, result_error4, result_warning4 = self.mock_text(1, 1, 2)

        extractor = ChipIOBufExtractor()
        transceiver = _PretendTransceiver(
            [IOBuffer(0, 0, 1, text1), IOBuffer(0, 0, 2, text2),
             IOBuffer(1, 1, 1, text3), IOBuffer(1, 1, 2, text4)])
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
        self.assertEqual(error_entries[0], result_error1)
        self.assertEqual(warn_entries[0], result_warning1)
        self.assertEqual(error_entries[1], result_error2)
        self.assertEqual(warn_entries[1], result_warning2)
        self.assertEqual(error_entries[2], result_error3)
        self.assertEqual(warn_entries[2], result_warning3)
        self.assertEqual(error_entries[3], result_error4)
        self.assertEqual(warn_entries[3], result_warning4)
        self.assertEqual(4, len(warn_entries))
        os.rmdir(folder)


if __name__ == "__main__":
    unittest.main()

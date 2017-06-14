import unittest
from spinn_front_end_common.interface.interface_functions\
    .front_end_common_chip_iobuf_extractor \
    import FrontEndCommonChipIOBufExtractor
from spinn_machine.core_subsets import CoreSubsets
from spinnman.model.io_buffer import IOBuffer
from spinn_machine.core_subset import CoreSubset
import os
import tempfile


class _PretendTransceiver(object):

    def __init__(self, iobuffers):
        self._iobuffers = iobuffers

    def get_iobuf(self, core_subsets):
        for iobuf in self._iobuffers:
            yield iobuf


class TestFrontEndCommonChipIOBufExtractor(unittest.TestCase):

    def testcall(self):
        x = 0
        y = 0
        p = 1
        filename = "myfile.c"
        error = "Test Error"
        warning = "Test Warning"
        error_text = "[ERROR]    ({}): {}\n".format(filename, error)
        result_error = "{}, {}, {}: {} ({})".format(x, y, p, error, filename)
        warning_text = "[WARNING]    ({}): {}\n".format(filename, warning)
        result_warning = "{}, {}, {}: {} ({})".format(
            x, y, p, warning, filename)
        text = "Test\n" + warning_text + error_text
        extractor = FrontEndCommonChipIOBufExtractor()
        core_subsets = CoreSubsets([CoreSubset(x, y, [p])])
        transceiver = _PretendTransceiver([IOBuffer(x, y, p, text)])
        folder = tempfile.mkdtemp()
        error_entries, warn_entries = extractor(
            transceiver, has_ran=True, core_subsets=core_subsets,
            provenance_file_path=folder)
        testfile = os.path.join(folder, "0_0_1.txt")
        self.assertTrue(os.path.exists(testfile))
        self.assertEqual(error_entries[0], result_error)
        self.assertEqual(warn_entries[0], result_warning)
        os.unlink(testfile)
        os.rmdir(folder)


if __name__ == "__main__":
    unittest.main()

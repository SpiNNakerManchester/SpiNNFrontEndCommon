import unittest
from spinn_front_end_common.interface.interface_functions \
    import ChipIOBufExtractor
from spinn_machine import CoreSubsets, CoreSubset
from spinnman.model import IOBuffer
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
        extractor = ChipIOBufExtractor()
        core_subsets = CoreSubsets([CoreSubset(x, y, [p])])
        transceiver = _PretendTransceiver([IOBuffer(x, y, p, text)])
        folder = tempfile.mkdtemp()
        error_entries, warn_entries = extractor(
            transceiver, has_ran=True, core_subsets=core_subsets,
            provenance_file_path=folder)
        testfile = os.path.join(
            folder, "iobuf_for_chip_0_0_processor_id_1.txt")
        self.assertTrue(os.path.exists(testfile))
        self.assertEqual(error_entries[0], result_error)
        self.assertEqual(warn_entries[0], result_warning)
        os.unlink(testfile)
        os.rmdir(folder)


if __name__ == "__main__":
    unittest.main()

import unittest
import tempfile
import os
import shutil
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import BufferedReceivingData
from spinn_front_end_common.interface.buffer_management.storage_objects\
    .buffered_receiving_data import DB_FILE_NAME


class TestBufferedReceivingDataWithDB(unittest.TestCase):

    def test_use_database(self):
        d = tempfile.mkdtemp()
        f = os.path.join(d, DB_FILE_NAME)
        try:
            self.assertFalse(os.path.isfile(f), "no existing DB at first")

            brd = BufferedReceivingData(d)
            self.assertTrue(os.path.isfile(f), "DB now exists")

            # TODO missing
            # data, missing = brd.get_region_data(0, 0, 0, 0)
            # self.assertIsNotNone(missing, "data should be 'missing'")
            # self.assertEqual(data, b"")

            brd.store_data_in_region_buffer(0, 0, 0, 0, b"abc")
            brd.flushing_data_from_region(0, 0, 0, 0, b"def")
            brd.store_end_buffering_state(0, 0, 0, 0, "LOLWUT")
            data, missing = brd.get_region_data(0, 0, 0, 0)

            self.assertIsNone(missing, "data shouldn't be 'missing'")
            self.assertEqual(bytes(data), b"abcdef")

            self.assertTrue(os.path.isfile(f), "DB still exists")
        finally:
            shutil.rmtree(d, True)

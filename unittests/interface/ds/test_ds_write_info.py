import unittest
from six import iteritems
from spinn_front_end_common.interface.ds.ds_write_info import DsWriteInfo
from spinn_front_end_common.interface.ds.ds_pretend_database import\
    DsPretendDatabase


class TestDsWriteInfo(unittest.TestCase):

    def test_dict(self):
        check = dict()
        asDict = DsWriteInfo(DsPretendDatabase())
        c1 = (0, 0, 0)
        foo = dict()
        foo['start_address'] = 123
        foo['memory_used'] = 12
        foo['memory_written'] = 23
        asDict[c1] = foo
        check[c1] = foo
        self.assertEqual(foo, asDict[c1])

        c2 = (1, 2, 3)
        bar = dict()
        bar['start_address'] = 456
        bar['memory_used'] = 45
        bar['memory_written'] = 56
        asDict[c2] = bar
        check[c2] = bar
        self.assertEqual(bar, asDict[c2])

        self.assertEqual(2, len(asDict))

        for key in asDict:
            self.assertDictEqual(check[key], asDict[key])

        for key, value in iteritems(asDict):
            self.assertDictEqual(check[key], value)


if __name__ == "__main__":
    unittest.main()

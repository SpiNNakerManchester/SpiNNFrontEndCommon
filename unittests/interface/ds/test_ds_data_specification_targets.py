import tempfile
import unittest
from six import iteritems
from spinn_front_end_common.interface.ds.data_specification_targets import\
    DataSpecificationTargets
from spinn_front_end_common.interface.ds.data_row_reader import DataRowReader
from spinn_machine.virtual_machine import virtual_machine


class TestDataSpecificationTargets(unittest.TestCase):
    machine = virtual_machine(2, 2)

    def test_dict(self):
        check = dict()
        testdir = tempfile.mkdtemp()
        print(testdir)
        asDict = DataSpecificationTargets(self.machine, testdir)
        c1 = (0, 0, 0)
        foo = bytearray(b"foo")
        with asDict.create_data_spec(0, 0, 0) as writer:
            writer.write(foo)
        check[c1] = DataRowReader(foo)
        self.assertEqual(check[c1], asDict[c1])

        c2 = (0, 1, 2)
        bar = bytearray(b"bar")
        with asDict.create_data_spec(0, 1, 2) as writer:
            writer.write(bar)
        check[c2] = DataRowReader(bar)
        self.assertEqual(check[c2], asDict[c2])

        self.assertEqual(2, len(asDict))

        asDict.set_app_id(12)

        for key in asDict:
            self.assertEqual(check[key], asDict[key])
            (x, y, p) = key
            self.assertEqual(12, asDict.get_app_id(x, y, p))

        for key, value in iteritems(asDict):
            self.assertEqual(check[key], value)


if __name__ == "__main__":
    unittest.main()

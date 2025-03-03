# Copyright (c) 2014 The University of Manchester
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
import decimal
from spinn_front_end_common.interface.ds import DataType


class TestingDataType(unittest.TestCase):

    def test_data_type_enum(self) -> None:
        self.assertEqual(DataType.UINT8.value, 0)
        self.assertEqual(DataType.UINT8.size, 1)
        self.assertEqual(DataType.UINT8.min, 0)
        self.assertEqual(DataType.UINT8.max, 255)

        self.assertEqual(DataType(0), DataType.UINT8)

        self.assertEqual(DataType.UINT16.value, 1)
        self.assertEqual(DataType.UINT16.size, 2)
        self.assertEqual(DataType.UINT16.min, 0)
        self.assertEqual(DataType.UINT16.max, 0xFFFF)

        self.assertEqual(DataType.UINT32.value, 2)
        self.assertEqual(DataType.UINT32.size, 4)
        self.assertEqual(DataType.UINT32.min, 0)
        self.assertEqual(DataType.UINT32.max, 0xFFFFFFFF)

        self.assertEqual(DataType.UINT64.value, 3)
        self.assertEqual(DataType.UINT64.size, 8)
        self.assertEqual(DataType.UINT64.min, 0)
        self.assertEqual(DataType.UINT64.max, 0xFFFFFFFFFFFFFFFF)

        self.assertEqual(DataType.INT8.value, 4)
        self.assertEqual(DataType.INT8.size, 1)
        self.assertEqual(DataType.INT8.min, -128)
        self.assertEqual(DataType.INT8.max, 127)

        self.assertEqual(DataType.INT16.value, 5)
        self.assertEqual(DataType.INT16.size, 2)
        self.assertEqual(DataType.INT16.min, -32768)
        self.assertEqual(DataType.INT16.max, 32767)

        self.assertEqual(DataType.INT32.value, 6)
        self.assertEqual(DataType.INT32.size, 4)
        self.assertEqual(DataType.INT32.min, -2147483648)
        self.assertEqual(DataType.INT32.max, 2147483647)

        self.assertEqual(DataType.INT64.value, 7)
        self.assertEqual(DataType.INT64.size, 8)
        self.assertEqual(DataType.INT64.min, -9223372036854775808)
        self.assertEqual(DataType.INT64.max, 9223372036854775807)

        self.assertEqual(DataType.U88.value, 8)
        self.assertEqual(DataType.U88.size, 2)
        self.assertEqual(DataType.U88.min, decimal.Decimal("0"))
        self.assertEqual(DataType.U88.max, decimal.Decimal("255.99609375"))

        self.assertEqual(DataType.U1616.value, 9)
        self.assertEqual(DataType.U1616.size, 4)
        self.assertEqual(DataType.U1616.min, decimal.Decimal("0"))
        self.assertEqual(DataType.U1616.max, decimal.Decimal("65535.9999847"))

        self.assertEqual(DataType.U3232.value, 10)
        self.assertEqual(DataType.U3232.size, 8)
        self.assertEqual(DataType.U3232.min, decimal.Decimal("0"))
        self.assertEqual(
            DataType.U3232.max,
            decimal.Decimal("4294967295.99999999976716935634613037109375"))

        self.assertEqual(DataType.S87.value, 11)
        self.assertEqual(DataType.S87.size, 2)
        self.assertEqual(DataType.S87.min, decimal.Decimal("-256"))
        self.assertEqual(DataType.S87.max, decimal.Decimal("255.9921875"))

        self.assertEqual(DataType.S1615.value, 12)
        self.assertEqual(DataType.S1615.size, 4)
        self.assertEqual(DataType.S1615.min, decimal.Decimal("-65536"))
        self.assertEqual(
            DataType.S1615.max, decimal.Decimal("65535.999969482421875"))

        # self.assertEqual(
        #    DataType.S1615.closest_representable_value(1.00001), 1.0)
        # self.assertEqual(
        #    DataType.S1615.closest_representable_value_above(0.99997), 1.0)

        self.assertEqual(DataType.S3231.value, 13)
        self.assertEqual(DataType.S3231.size, 8)
        self.assertEqual(DataType.S3231.min, decimal.Decimal("-4294967296"))
        self.assertEqual(
            DataType.S3231.max,
            decimal.Decimal("4294967295.9999999995343387126922607421875"))

        self.assertEqual(DataType.U08.value, 16)
        self.assertEqual(DataType.U08.size, 1)
        self.assertEqual(DataType.U08.min, decimal.Decimal("0"))
        self.assertEqual(DataType.U08.max, decimal.Decimal("0.99609375"))

        self.assertEqual(DataType.U016.value, 17)
        self.assertEqual(DataType.U016.size, 2)
        self.assertEqual(DataType.U016.min, decimal.Decimal("0"))
        self.assertEqual(DataType.U016.max, decimal.Decimal("0.999984741211"))

        self.assertEqual(DataType.U032.value, 18)
        self.assertEqual(DataType.U032.size, 4)
        self.assertEqual(DataType.U032.min, decimal.Decimal("0"))
        self.assertEqual(
            DataType.U032.max,
            decimal.Decimal("0.99999999976716935634613037109375"))

        self.assertEqual(DataType.U064.value, 19)
        self.assertEqual(DataType.U064.size, 8)
        self.assertEqual(DataType.U064.min, decimal.Decimal("0"))
        self.assertEqual(
            DataType.U064.max,
            decimal.Decimal("0.999999999999999999945789891375724"
                            "7782996273599565029"))

        self.assertEqual(DataType.S07.value, 20)
        self.assertEqual(DataType.S07.size, 1)
        self.assertEqual(DataType.S07.min, decimal.Decimal("-1"))
        self.assertEqual(DataType.S07.max, decimal.Decimal("0.9921875"))

        self.assertEqual(DataType.S015.value, 21)
        self.assertEqual(DataType.S015.size, 2)
        self.assertEqual(DataType.S015.min, decimal.Decimal("-1"))
        self.assertEqual(
            DataType.S015.max,
            decimal.Decimal("0.999969482421875"))

        self.assertEqual(DataType.S031.value, 22)
        self.assertEqual(DataType.S031.size, 4)
        self.assertEqual(DataType.S031.min, decimal.Decimal("-1"))
        self.assertEqual(
            DataType.S031.max,
            decimal.Decimal("0.99999999976716935634613037109375"))

        self.assertEqual(DataType.S063.value, 23)
        self.assertEqual(DataType.S063.size, 8)
        self.assertEqual(DataType.S063.min, decimal.Decimal("-1"))
        self.assertEqual(
            DataType.S063.max,
            decimal.Decimal("0.99999999999999999989157978275144"
                            "95565992547199130058"))

        self.assertEqual(DataType.S1615.__doc__,
                         "16.15 signed fixed point number")


if __name__ == '__main__':
    unittest.main()

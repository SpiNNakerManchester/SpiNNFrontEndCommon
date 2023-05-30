# Copyright (c) 2023 The University of Manchester
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
from spinn_machine.virtual_machine import virtual_machine
from pacman.model.graphs.machine import SimpleMachineVertex
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.ds import \
    DataSpecificationGenerator, DsSqlliteDatabase


class TestDataSpecificationTargets(unittest.TestCase):

    def setUp(self):
        unittest_setup()

    def test_none_ds_vertex(self):
        FecDataWriter.mock().set_machine(virtual_machine(2, 2))
        db = DsSqlliteDatabase()
        vertex = SimpleMachineVertex(0)
        dsg = DataSpecificationGenerator(0, 1, 2, vertex, db)


if __name__ == "__main__":
    unittest.main()

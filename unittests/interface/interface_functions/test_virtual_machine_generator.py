# Copyright (c) 2024 The University of Manchester
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
from spinn_utilities.config_holder import set_config
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.interface_functions import (
    virtual_machine_generator)
from spinn_front_end_common.utilities.exceptions import ConfigurationException


class TestVirtualMachineGenerator(unittest.TestCase):

    def setUp(self) -> None:
        unittest_setup()

    def test_only_width(self) -> None:
        set_config("Machine", "version", 5)
        set_config("Machine", "virtual_board", "True")
        set_config("Machine", "width", "8")
        with self.assertRaises(ConfigurationException):
            virtual_machine_generator()

    def test_by_boards(self) -> None:
        set_config("Machine", "version", 5)
        set_config("Machine", "virtual_board", "True")
        # Called by sim.setup
        FecDataWriter.mock().set_n_required(3, None)
        machine = virtual_machine_generator()
        self.assertEqual(3, len(machine.ethernet_connected_chips))

    def test_by_set_chips(self) -> None:
        set_config("Machine", "version", 5)
        set_config("Machine", "virtual_board", "True")
        # Called by sim.setup
        FecDataWriter.mock().set_n_chips_in_graph(100)
        machine = virtual_machine_generator()
        self.assertEqual(3, len(machine.ethernet_connected_chips))

    def test_by_chips(self) -> None:
        set_config("Machine", "version", 5)
        set_config("Machine", "virtual_board", "True")
        # Called after partitioning
        FecDataWriter.mock().set_n_chips_in_graph(1)
        machine = virtual_machine_generator()
        self.assertEqual(1, len(machine.ethernet_connected_chips))


if __name__ == "__main__":
    unittest.main()

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

from spinn_machine.version.version_strings import VersionStrings

from pacman.model.graphs.machine import SimpleMachineVertex
from pacman.model.placements import Placement, Placements

from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.utilities.report_functions import (
    write_json_machine, write_json_placements)


class TestJson(unittest.TestCase):

    def setUp(self) -> None:
        unittest_setup()
        set_config("Mapping", "validate_json", "True")

    def test_placements(self) -> None:
        """
        tests the placements iterator functionality.
        """
        writer = FecDataWriter.mock()
        subv = list()
        for i in range(5):
            subv.append(SimpleMachineVertex(None, ""))

        pl = list()
        for i in range(4):
            pl.append(Placement(subv[i], 0, 0, i))
        writer.set_placements(Placements(pl))

        # write and validate
        write_json_placements()

    def test_machine(self) -> None:
        set_config("Machine", "versions", VersionStrings.ANY.text)
        # write and validate
        write_json_machine()

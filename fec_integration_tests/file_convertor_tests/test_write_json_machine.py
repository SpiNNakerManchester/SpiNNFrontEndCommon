# Copyright (c) 2017 The University of Manchester
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

import filecmp
import json
import os
import sys
import unittest

from spinn_utilities.config_holder import get_report_path, set_config
from spinn_utilities.ping import Ping
from spinn_utilities.typing.json import JsonArray

from spinnman.exceptions import SpallocBoardUnavailableException
import spinnman.spinnman_script as sim

from spinnman.exceptions import SpinnmanIOException
from spinnman.transceiver import create_transceiver_from_hostname

from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.utilities.report_functions.write_json_machine \
    import (write_json_machine)


class TestWriteJson(unittest.TestCase):

    spin4Host = "spinn-4.cs.man.ac.uk"
    spalloc = "spinnaker.cs.man.ac.uk"

    def setUp(self) -> None:
        unittest_setup()
        class_file = sys.modules[self.__module__].__file__
        assert class_file is not None
        class_dir = os.path.abspath(class_file)
        path = os.path.dirname(class_dir)
        os.chdir(path)
        set_config("Machine", "down_chips", "None")
        set_config("Machine", "down_cores", "None")
        set_config("Machine", "down_links", "None")
        set_config("Mapping", "validate_json", "True")

    def _chips_differ(self, chip1: JsonArray, chip2: JsonArray) -> bool:
        if (chip1 == chip2):
            return False
        if len(chip1) != len(chip2):
            return True
        for i in range(len(chip1)):
            chip1i = chip1[i]
            chip2i = chip2[i]
            if chip1i == chip2i:
                continue
            assert isinstance(chip1i, dict)
            assert isinstance(chip2i, dict)
            if len(chip1i) != len(chip2i):
                return True
            for key in chip1i:
                if (chip1i[key] != chip2i[key]):
                    if key != "cores":
                        return True
                    # Toterance of
                    c1 = chip1i[key]
                    c2 = chip2i[key]
                    assert isinstance(c1, int)
                    assert isinstance(c2, int)
                    if c1 < c2 - 1:
                        return True
                    if c1 > c2 + 1:
                        return True
            return False
        return True

    def json_compare(self, file1: str, file2: str) -> None:
        if filecmp.cmp(file1, file2):
            return
        with open(file1, encoding="utf-8") as json_file:
            json1 = json.load(json_file)
        with open(file2, encoding="utf-8") as json_file:
            json2 = json.load(json_file)
        if json1 == json2:
            return
        if json1.keys() != json2.keys():
            raise AssertionError("Keys differ {} {}".format(
                json1.keys(), json2.keys()))
        for key in json1.keys():
            if key == "chips":
                chips1 = json1[key]
                chips2 = json2[key]
                if len(chips1) != len(chips2):
                    raise AssertionError(
                        f"# Chips {len(chips1)} != {len(chips2)}")
                for i in range(len(chips1)):
                    if self._chips_differ(chips1[i], chips2[i]):
                        raise AssertionError(
                            f"Chip {i} differs {chips1[i]} {chips2[i]}")
            else:
                if json1[key] != json2[key]:
                    raise AssertionError(
                        "Values differ for {} found {} {}".format(
                            key, json1[key], json2[key]))

    def testSpin4(self) -> None:
        if not Ping.host_is_reachable(self.spin4Host):
            raise unittest.SkipTest(self.spin4Host + " appears to be down")
        try:
            trans = create_transceiver_from_hostname(self.spin4Host)
        except (SpinnmanIOException):
            self.skipTest("Skipping as getting Job failed")

        machine = trans.get_machine_details()
        FecDataWriter.mock().set_machine(machine)

        filename = write_json_machine(True)

        self.json_compare(filename, "spinn4.json")

        # Create a machine with Exception
        chip = machine[1, 1]
        chip._sdram = chip._sdram - 100
        chip._router._n_available_multicast_entries -= 10
        chip = machine[1, 2]
        chip._sdram = chip._sdram - 101

        json_file = get_report_path("path_json_machine")
        if os.path.exists(json_file):
            os.remove(json_file)
        filename = write_json_machine(True)

        self.json_compare(filename, "spinn4_fiddle.json")
        trans.close()

    def testSpin2(self) -> None:
        try:
            sim.setup(n_boards_required=1)
            machine1 = sim.get_machine()
            print(machine1)

            # needs to be set this way as not part of spinnman.cfg
            set_config("Reports", "path_json_machine",
                       "json_files\machine.json")
            set_config("Mapping", "validate_json","true")
            filename = write_json_machine(False)

            self.json_compare(filename, "spinn2.json")
        except SpallocBoardUnavailableException as ex:
            raise unittest.SkipTest(str(ex))
        finally:
            sim.end()

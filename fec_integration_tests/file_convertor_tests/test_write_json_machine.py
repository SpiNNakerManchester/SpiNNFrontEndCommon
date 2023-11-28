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
from spinn_utilities.config_holder import set_config
from spalloc_client.job import JobDestroyedError
from spinn_utilities.ping import Ping
from spinnman.exceptions import SpinnmanIOException
from spinnman.transceiver import create_transceiver_from_hostname
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.utilities.report_functions.write_json_machine \
    import (write_json_machine, MACHINE_FILENAME)
from spinn_front_end_common.interface.interface_functions import (
    spalloc_allocator)


class TestWriteJson(unittest.TestCase):

    spin4Host = "spinn-4.cs.man.ac.uk"
    spalloc = "spinnaker.cs.man.ac.uk"
    spin2Port = 22245
    mainPort = 22244

    def setUp(self):
        unittest_setup()
        set_config("Machine", "version", 5)
        class_file = sys.modules[self.__module__].__file__
        path = os.path.dirname(os.path.abspath(class_file))
        os.chdir(path)
        set_config("Machine", "down_chips", None)
        set_config("Machine", "down_cores", None)
        set_config("Machine", "down_links", None)

    def _chips_differ(self, chip1, chip2):
        if (chip1 == chip2):
            return False
        if len(chip1) != len(chip2):
            return True
        for i in range(len(chip1)):
            if chip1[i] == chip2[i]:
                continue
            if len(chip1[i]) != len(chip2[i]):
                return True
            for key in chip1[i]:
                if (chip1[i][key] != chip2[i][key]):
                    if key != "cores":
                        return True
                    # Toterance of
                    c1 = int(chip1[i][key])
                    c2 = int(chip2[i][key])
                    if c1 < c2 - 1:
                        return True
                    if c1 > c2 + 1:
                        return True
            return False

    def json_compare(self, file1, file2):
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

    def _remove_old_json(self, folder):
        if not os.path.exists(folder):
            os.makedirs(folder)
        else:
            json_file = os.path.join(folder, MACHINE_FILENAME)
            if os.path.exists(json_file):
                os.remove(json_file)

    def testSpin4(self):
        if not Ping.host_is_reachable(self.spin4Host):
            raise unittest.SkipTest(self.spin4Host + " appears to be down")
        try:
            trans = create_transceiver_from_hostname(self.spin4Host)
        except (SpinnmanIOException):
            self.skipTest("Skipping as getting Job failed")

        machine = trans.get_machine_details()
        FecDataWriter.mock().set_machine(machine)

        folder = "spinn4"
        self._remove_old_json(folder)
        filename = write_json_machine(folder, True)

        self.json_compare(filename, "spinn4.json")

        # Create a machine with Exception
        chip = machine.get_chip_at(1, 1)
        chip._sdram = chip._sdram - 100
        chip._router._n_available_multicast_entries -= 10
        chip = machine.get_chip_at(1, 2)
        chip._sdram = chip._sdram - 101

        folder = "spinn4_fiddle"
        self._remove_old_json(folder)
        filename = write_json_machine(folder, True)

        self.json_compare(filename, "spinn4_fiddle.json")
        trans.close()

    def testSpin2(self):
        if not Ping.host_is_reachable(self.spalloc):
            raise unittest.SkipTest(self.spalloc + " appears to be down")
        set_config(
            "Machine", "spalloc_user", "Integration testing ok to kill")
        set_config("Machine", "spalloc_server", self.spalloc)
        set_config("Machine", "spalloc_port", self.spin2Port)

        writer = FecDataWriter.mock()
        writer.set_n_chips_in_graph(20)
        try:
            (hostname, version, _, _, _, _, m_allocation_controller) = \
                spalloc_allocator()
        except (JobDestroyedError, ConnectionRefusedError):
            self.skipTest("Skipping as getting Job failed")

        trans = create_transceiver_from_hostname(hostname)
        writer.set_machine(trans.get_machine_details())

        m_allocation_controller.close()

        folder = "spinn2"
        self._remove_old_json(folder)
        filename = write_json_machine(folder, False)

        self.json_compare(filename, "spinn2.json")
        trans.close()

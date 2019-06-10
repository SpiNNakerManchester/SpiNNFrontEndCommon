import filecmp
import json
import os
import sys
import unittest
from spalloc.job import JobDestroyedError
from spinn_utilities.ping import Ping
import spinnman.transceiver as transceiver
from pacman.utilities.file_format_converters.convert_to_java_machine \
    import ConvertToJavaMachine
from spinn_front_end_common.interface.interface_functions.spalloc_allocator \
    import SpallocAllocator


class TestConvertJson(unittest.TestCase):

    spin4Host = "spinn-4.cs.man.ac.uk"
    spalloc = "spinnaker.cs.man.ac.uk"
    spin2Port = 22245
    mainPort = 22244

    def setUp(self):
        class_file = sys.modules[self.__module__].__file__
        path = os.path.dirname(os.path.abspath(class_file))
        os.chdir(path)

    def json_compare(self, file1, file2):
        if filecmp.cmp(file1, file2):
            return
        with open(file1) as json_file:
            json1 = json.load(json_file)
        with open(file2) as json_file:
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
                for i in range(len(chips1)):
                    if (chips1[i] != chips2[i]):
                        raise AssertionError("Chip {} differ {} {}".format(
                            i, chips1[i], chips2[i]))
            else:
                if json1[key] != json2[key]:
                    raise AssertionError(
                        "Values differ for {} found {} {}".format(
                            key, json1[key], json2[key]))
        raise AssertionError("Some wierd difference")

    def testSpin4(self):
        if not Ping.host_is_reachable(self.spin4Host):
            raise unittest.SkipTest(self.spin4Host + " appears to be down")
        trans = transceiver.create_transceiver_from_hostname(self.spin4Host, 5)
        trans.ensure_board_is_ready()

        machine = trans.get_machine_details()

        jsonAlgo = ConvertToJavaMachine()

        fn = "test_spinn4.json"
        filename = jsonAlgo(machine, str(fn))

        self.json_compare(filename, "spinn4.json")

        # Create a machione with Exception
        chip = machine.get_chip_at(1, 1)
        chip._sdram._size = chip._sdram._size - 100
        chip._router._clock_speed = chip._router._clock_speed - 100
        chip._router._n_available_multicast_entries -= 10
        chip._virtual = not chip._virtual
        chip = machine.get_chip_at(1, 2)
        chip._sdram._size = chip._sdram._size - 101

        fn = "test_spinn4_fiddle.json"
        filename = jsonAlgo(machine, str(fn))
        self.json_compare(filename, "spinn4_fiddle.json")

        trans.close()

    def testSpin2(self):
        if not Ping.host_is_reachable(self.spalloc):
            raise unittest.SkipTest(self.spalloc + " appears to be down")
        spallocAlgo = SpallocAllocator()

        try:
            (hostname, version, _, _, _, _, _, m_allocation_controller) = \
                spallocAlgo(self.spalloc, "Integration testing ok to kill", 20,
                            self.spin2Port)
        except (JobDestroyedError):
            self.skipTest("Skipping as getting Job failed")

        trans = transceiver.create_transceiver_from_hostname(hostname, 5)
        trans.ensure_board_is_ready()
        machine = trans.get_machine_details()

        m_allocation_controller.close()

        jsonAlgo = ConvertToJavaMachine()

        fn = "test_spinn2.json"
        filename = jsonAlgo(machine, str(fn))

        self.json_compare(filename, "spinn2.json")

        trans.close()

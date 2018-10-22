import filecmp
import os
import time
import unittest
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

    def testSpin4(self):
        assert False
        if not Ping.host_is_reachable(self.spin4Host):
            raise unittest.SkipTest(self.spin4Host + " appears to be down")
        trans = transceiver.create_transceiver_from_hostname(self.spin4Host, 5)
        trans.ensure_board_is_ready()
        machine = trans.get_machine_details()
        print(machine)

        jsonAlgo = ConvertToJavaMachine()

        fn = os.path.join(os.path.dirname(__file__), "test_spinn4.json")
        filename = jsonAlgo(machine, str(fn))

        print(filename)
        check = os.path.join(os.path.dirname(__file__), "spinn4.json")
        assert filecmp.cmp(filename, "check")

        # Create a machione with Exception
        chip = machine.get_chip_at(1, 1)
        chip._sdram._size = chip._sdram._size - 100
        chip.reserve_a_system_processor()
        chip._router._clock_speed = chip._router._clock_speed - 100
        chip._router._n_available_multicast_entries -= 10
        chip._virtual = not chip._virtual
        chip = machine.get_chip_at(1, 2)
        chip._sdram._size = chip._sdram._size - 101
        chip.reserve_a_system_processor()
        chip.reserve_a_system_processor()

        fn = os.path.join(os.path.dirname(__file__), "test_spinn4_fiddle.json")
        filename = jsonAlgo(machine, str(fn))
        print(filename)
        check = os.path.join(os.path.dirname(__file__), "spinn4_fiddle.json")
        assert filecmp.cmp(filename, check)

    def testSpin2(self):
        if not Ping.host_is_reachable(self.spalloc):
            raise unittest.SkipTest(self.spalloc + " appears to be down")
        spallocAlgo = SpallocAllocator()

        print("Spalloc started ")
        (hostname, version, _, _, _, _, _, machine_allocation_controller) = \
            spallocAlgo(self.spalloc, "Integration testing ok to kill", 20,
                        self.spin2Port)

        print("Spalloc returned " + hostname)

        trans = transceiver.create_transceiver_from_hostname(hostname, 5)
        trans.ensure_board_is_ready()
        print("board ready")
        machine = trans.get_machine_details()
        print(machine)

        #print("Foreever keep alive");
        #while (True):
        #    time.sleep(1)

        machine_allocation_controller.close()

        jsonAlgo = ConvertToJavaMachine()

        fn = os.path.join(os.path.dirname(__file__), "test_spinn2.json")
        filename = jsonAlgo(machine, str(fn))

        print(filename)
        check = os.path.join(os.path.dirname(__file__), "spinn2.json")
        assert filecmp.cmp(filename, check)


spin4Host = "spinn-4.cs.man.ac.uk"
spalloc = "spinnaker.cs.man.ac.uk"
spin2Port = 22245
mainPort = 22244
spallocAlgo = SpallocAllocator()

print("Spalloc started ")
(hostname, version, _, _, _, _, _, machine_allocation_controller) = \
    spallocAlgo(spalloc, "Integration testing ok to kill", 20,
                spin2Port)

print("Spalloc returned " + hostname)

trans = transceiver.create_transceiver_from_hostname(hostname, 5)
trans.ensure_board_is_ready()
print("board ready")
machine = trans.get_machine_details()
print(machine)
print("Foreever keep alive");
while (True):
    time.sleep(1)

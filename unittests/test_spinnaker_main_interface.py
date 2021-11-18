# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import unittest
from spinn_utilities.config_holder import get_config_int
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.interface.abstract_spinnaker_base import (
    AbstractSpinnakerBase)
from spinn_front_end_common.utilities import globals_variables
from spinn_front_end_common.utilities.utility_objs import ExecutableFinder


class Close_Once(object):
    __slots__ = ["closed"]

    def __init__(self):
        self.closed = False

    def close(self):
        if self.closed:
            raise Exception("Close called twice")
        self.closed = True


class TestSpinnakerMainInterface(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        unittest_setup()

    def test_stop_init(self):
        class_file = sys.modules[self.__module__].__file__
        path = os.path.dirname(os.path.abspath(class_file))
        os.chdir(path)
        interface = AbstractSpinnakerBase(ExecutableFinder())
        mock_contoller = Close_Once()
        interface._machine_allocation_controller = mock_contoller
        self.assertFalse(mock_contoller.closed)
        interface.stop(turn_off_machine=False, clear_routing_tables=False,
                       clear_tags=False)
        self.assertTrue(mock_contoller.closed)
        with self.assertRaises(ConfigurationException):
            interface.stop(turn_off_machine=False, clear_routing_tables=False,
                           clear_tags=False)

    def test_min_init(self):
        class_file = sys.modules[self.__module__].__file__
        path = os.path.dirname(os.path.abspath(class_file))
        os.chdir(path)
        AbstractSpinnakerBase(ExecutableFinder())

    def test_timings(self):

        # Test defaults stay as in the configs
        machine_time_step = get_config_int("Machine", "machine_time_step")
        time_scale_factor = get_config_int("Machine", "time_scale_factor")
        asb = AbstractSpinnakerBase(ExecutableFinder())
        writer = FecDataWriter()
        writer.set_up_timings(simulation_time_step_us=None, time_scale_factor=None)
        assert machine_time_step == writer.simulation_time_step_us

        # Test specified
        writer.set_up_timings(simulation_time_step_us=200, time_scale_factor=10)
        assert writer.simulation_time_step_us == 200
        assert writer.simulation_time_step_ms == 0.2
        assert writer.simulation_time_step_per_ms == 5.0
        assert writer.time_scale_factor == 10

        with self.assertRaises(ConfigurationException):
            writer.set_up_timings(simulation_time_step_us=-20, time_scale_factor=10)


if __name__ == "__main__":
    unittest.main()

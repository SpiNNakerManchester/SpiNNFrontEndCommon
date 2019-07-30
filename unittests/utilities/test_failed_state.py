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

import unittest
from spinn_front_end_common.utilities import (
    FailedState, globals_variables)


class FakeFailedState(object):

    @property
    def config(self):
        return "STUB!"


class TestFailedState(unittest.TestCase):

    def setUp(self):
        # Not the normal way of doing it but cleans up between tests
        globals_variables._simulator = None
        globals_variables._failed_state = None

    def test_init(self):
        fs = FailedState()
        self.assertIsNotNone(fs)

    def test_unset_failed_state(self):
        with self.assertRaises(ValueError):
            sim = globals_variables.get_simulator()
            self.assertTrue(isinstance(sim, FailedState))

    def test_set_failed_state(self):
        globals_variables.set_failed_state(FailedState())
        sim = globals_variables.get_simulator()
        self.assertTrue(isinstance(sim, FailedState))

    def test_set_failed_State(self):
        fs_new = FakeFailedState()
        globals_variables.set_failed_state(fs_new)
        sim = globals_variables.get_simulator()
        self.assertTrue(isinstance(sim, FakeFailedState))

    def test_set_sim(self):
        globals_variables.set_failed_state(FailedState())
        globals_variables.set_simulator("BOO")
        sim = globals_variables.get_simulator()
        self.assertTrue(isinstance(sim, str))

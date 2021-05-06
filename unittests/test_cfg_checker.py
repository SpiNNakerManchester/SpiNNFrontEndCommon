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
import unittest
from spinn_utilities.config_holder import run_config_checks
from spinn_front_end_common.interface.config_setup import reset_configs


class TestCfgChecker(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        reset_configs()

    def test_cfg_checker(self):
        unittests = os.path.dirname(__file__)
        parent = os.path.dirname(unittests)
        fec = os.path.join(parent, "spinn_front_end_common")
        local = os.path.join(parent, "fec_local_tests")
        fec_it = os.path.join(parent, "fec_integration_tests")
        run_config_checks(directories=[
            fec, local, fec_it, unittests])

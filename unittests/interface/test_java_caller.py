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
from spinn_utilities.config_holder import set_config
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.java_caller import JavaCaller
from spinn_front_end_common.utilities.exceptions import ConfigurationException


class TestJavaCaller(unittest.TestCase):

    # default finding jar automatically tested in
    # fec_local_tests/test_java_caller.py

    def setUp(self):
        unittest_setup()

    @classmethod
    def setUpClass(cls):
        cls.interface = os.path.dirname(os.path.realpath(__file__))
        unittest = os.path.dirname(cls.interface)
        cls.mock = os.path.join(unittest, "mock")
        cls.mock_jar = os.path.join(cls.mock, "spinnaker-exe.jar")

    def test_creation_with_jar_path(self):
        set_config("Java", "java_spinnaker_path", "missing")
        set_config("Java", "java_jar_path", self.mock_jar)
        caller = JavaCaller()
        assert caller is not None

    def test_creation_java_spinnaker_path(self):
        set_config("Java", "java_spinnaker_path", self.mock)
        set_config("Java", "java_properties",
                   "-Dspinnaker.compare.download -Dlogging.level=DEBUG")
        caller = JavaCaller()
        assert caller is not None

    def test_creation_bad_property(self):
        set_config("Java", "java_spinnaker_path", self.mock)
        set_config("Java", "java_properties",
                   "-Dspinnaker.compare.download -logging.level=DEBUG")
        with self.assertRaises(ConfigurationException):
            JavaCaller()

    def test_creation_different(self):
        set_config("Java", "java_spinnaker_path", self.mock)
        set_config("Java", "java_jar_path", self.mock_jar)
        with self.assertRaises(ConfigurationException):
            JavaCaller()

    def test_creation_wrong_java_spinnaker_path(self):
        set_config("Java", "java_spinnaker_path", self.interface)
        with self.assertRaises(ConfigurationException):
            JavaCaller()

    def test_creation_bad_java_spinnaker_path(self):
        set_config("Java", "java_spinnaker_path", self.mock_jar)
        with self.assertRaises(ConfigurationException):
            JavaCaller()

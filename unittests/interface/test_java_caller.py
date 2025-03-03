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

import os
import unittest
from spinn_utilities.config_holder import set_config
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.data.fec_data_writer import FecDataWriter
from spinn_front_end_common.interface.config_setup import unittest_setup
from spinn_front_end_common.interface.java_caller import JavaCaller
from spinn_front_end_common.utilities.exceptions import ConfigurationException


class TestJavaCaller(unittest.TestCase):

    # default finding jar automatically tested in
    # fec_local_tests/test_java_caller.py

    def setUp(self) -> None:
        unittest_setup()

    @classmethod
    def setUpClass(cls):
        cls.interface = os.path.dirname(os.path.realpath(__file__))
        unittest = os.path.dirname(cls.interface)
        cls.mock = os.path.join(unittest, "mock")
        cls.mock_jar = os.path.join(cls.mock, "spinnaker-exe.jar")

    def test_creation_with_jar_path(self) -> None:
        set_config("Java", "java_spinnaker_path", "missing")
        set_config("Java", "java_jar_path", self.mock_jar)
        caller = JavaCaller()
        assert caller is not None
        FecDataWriter.mock().set_java_caller(caller)
        assert FecDataView.has_java_caller()
        self.assertEqual(FecDataView.get_java_caller(), caller)

    def test_creation_java_spinnaker_path(self) -> None:
        set_config("Java", "java_spinnaker_path", self.mock)
        set_config("Java", "java_properties",
                   "-Dspinnaker.compare.download -Dlogging.level=DEBUG")
        caller = JavaCaller()
        assert caller is not None

    def test_creation_bad_property(self) -> None:
        set_config("Java", "java_spinnaker_path", self.mock)
        set_config("Java", "java_properties",
                   "-Dspinnaker.compare.download -logging.level=DEBUG")
        with self.assertRaises(ConfigurationException):
            JavaCaller()

    def test_creation_different(self) -> None:
        set_config("Java", "java_spinnaker_path", self.mock)
        set_config("Java", "java_jar_path", self.mock_jar)
        with self.assertRaises(ConfigurationException):
            JavaCaller()

    def test_creation_wrong_java_spinnaker_path(self) -> None:
        set_config("Java", "java_spinnaker_path", self.interface)
        with self.assertRaises(ConfigurationException):
            JavaCaller()

    def test_creation_bad_java_spinnaker_path(self) -> None:
        set_config("Java", "java_spinnaker_path", self.mock_jar)
        with self.assertRaises(ConfigurationException):
            JavaCaller()

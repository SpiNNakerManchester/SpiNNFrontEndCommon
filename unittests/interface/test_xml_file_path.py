# Copyright (c) 2021 The University of Manchester
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

from os import path
import unittest
from spinn_front_end_common.interface.interface_functions import interface_xml
from spinn_front_end_common.utilities.report_functions import report_xml


class TestXmlFilePath(unittest.TestCase):

    def test_interface_exists(self):
        self.assertTrue(path.exists(interface_xml()))

    def test_report_exists(self):
        self.assertTrue(path.exists(report_xml()))

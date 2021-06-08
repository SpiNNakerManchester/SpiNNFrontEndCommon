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

"""
test for partitioning
"""
import os
import unittest
from pacman.executor import AlgorithmMetadataXmlReader
from spinn_front_end_common.interface.config_setup import reset_configs


class TestXML(unittest.TestCase):

    def setUp(self):
        reset_configs()

    def test_read_xml(self):

        interface_functions = os.path.dirname(__file__)
        interface = os.path.dirname(interface_functions)
        unittests = os.path.dirname(interface)
        fec = os.path.dirname(unittests)
        interface_xml = os.path.join(
            fec, "spinn_front_end_common", "interface", "interface_functions",
            "front_end_common_interface_functions.xml")
        reports_xml = os.path.join(
            fec, "spinn_front_end_common", "utilities", "report_functions",
            "front_end_common_reports.xml")
        paths = [interface_xml, reports_xml]
        reader = AlgorithmMetadataXmlReader(paths)
        reader.decode_algorithm_data_objects()


if __name__ == '__main__':
    unittest.main()

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
from spinn_front_end_common.interface import interface_functions
from spinn_front_end_common.utilities import report_functions
from spinn_front_end_common import mapping_algorithms


def get_front_end_common_pacman_xml_paths():
    """ Get the XML path for the front end common interface functions

    :rtype: list(str)
    """
    return [
        os.path.join(
            os.path.dirname(interface_functions.__file__),
            "front_end_common_interface_functions.xml"),
        os.path.join(
            os.path.dirname(report_functions.__file__),
            "front_end_common_reports.xml"),
        os.path.join(
            os.path.dirname(mapping_algorithms.__file__),
            "front_end_common_mapping_algorithms.xml"
        )
    ]

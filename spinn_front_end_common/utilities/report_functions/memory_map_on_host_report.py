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

import logging
import os
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.utilities.globals_variables import (
    report_default_directory)
logger = FormatAdapter(logging.getLogger(__name__))

_FOLDER_NAME = "memory_map_from_processor_to_address_space"


def memory_map_on_host_report(dsg_targets):
    """ Report on memory usage.

    :param dsg_targets:
    :type dsg_targets:
        dict(tuple(int,int,int),DataWritten)
    """
    file_name = os.path.join(report_default_directory(), _FOLDER_NAME)
    try:
        with open(file_name, "w") as f:
            f.write("On host data specification executor\n")
            for key, data in dsg_targets.info_iteritems():
                f.write(
                    f"{key}: ('start_address': {data.start_address}, "
                    f"hex:{hex(data.start_address)}), "
                    f"'memory_used': {data.memory_used}, "
                    f"'memory_written': {data.memory_written} \n")
    except IOError:
        logger.exception("Generate_placement_reports: Can't open file"
                         " {} for writing.", file_name)

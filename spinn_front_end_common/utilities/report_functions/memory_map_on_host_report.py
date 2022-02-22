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
from spinn_front_end_common.data import FecDataView
logger = FormatAdapter(logging.getLogger(__name__))

_FOLDER_NAME = "memory_map_from_processor_to_address_space"


def memory_map_on_host_report(dsg_targets):
    """ Report on memory usage.

    :param dsg_targets:
    :type dsg_targets:
        dict(tuple(int,int,int),DataWritten)
    """
    file_name = os.path.join(FecDataView.get_run_dir_path(), _FOLDER_NAME)
    try:
        with open(file_name, "w") as f:
            f.write("On host data specification executor\n")
            for key, start_address, memory_used, memory_written in \
                    dsg_targets.info_iteritems():
                f.write(
                    f"{key}: ('start_address': {start_address}, "
                    f"hex:{hex(start_address)}), "
                    f"'memory_used': {memory_used}, "
                    f"'memory_written': {memory_written} \n")
    except IOError:
        logger.exception("Generate_placement_reports: Can't open file"
                         " {} for writing.", file_name)

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


class MemoryMapOnHostReport(object):
    """ Report on memory usage.
    """
    def __call__(
            self, app_core_to_dswrite, system_core_to_dswrite):
        """
        :param app_core_to_dswrite: dswrite per core for application vertexes
        :type app_core_to_dswrite:
            dict(tuple(int,int,int),DataWritten)
        :param system_core_to_dswrite: dswrite per core for system vertexes
        :type system_core_to_dswrite:
            dict(tuple(int,int,int),DataWritten)
        """

        file_name = os.path.join(report_default_directory(), _FOLDER_NAME)
        try:
            with open(file_name, "w") as f:
                self._describe_mem_map(
                    f, app_core_to_dswrite, system_core_to_dswrite)
        except IOError:
            logger.exception("Generate_placement_reports: Can't open file"
                             " {} for writing.", file_name)

    def _describe_mem_map(
            self, f, app_core_to_dswrite, system_core_to_dswrite):
        f.write("On host data specification executor\n")
        for key, data in app_core_to_dswrite.items():
            self._describe_map_entry(f, key, data)
        for key, data in system_core_to_dswrite.items():
            self._describe_map_entry(f, key, data)

    @staticmethod
    def _describe_map_entry(f, key, data):
        """
        :param f:
        :param tuple(int,int,int) key:
        :param DataWritten data:
        """
        f.write(
            "{}: ('start_address': {}, hex:{}), "
            "'memory_used': {}, 'memory_written': {} \n".format(
                key, data.start_address, hex(data.start_address),
                data.memory_used, data.memory_written))

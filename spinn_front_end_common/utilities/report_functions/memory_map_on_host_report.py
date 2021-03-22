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

from .utils import ReportFile

_FOLDER_NAME = "memory_map_from_processor_to_address_space"


class MemoryMapOnHostReport(object):
    """ Report on memory usage.
    """

    def __call__(
            self, report_default_directory,
            processor_to_app_data_base_address):
        """
        :param str report_default_directory:
        :param processor_to_app_data_base_address:
        :type processor_to_app_data_base_address:
            dict(tuple(int,int,int),DataWritten)
        """

        with ReportFile(report_default_directory, _FOLDER_NAME) as f:
            f.write("On host data specification executor\n")
            for key, data in processor_to_app_data_base_address.items():
                self._describe_map_entry(f, key, data)

    @staticmethod
    def _describe_map_entry(f, key, data):
        """
        :param io.TextIOBase f:
        :param tuple(int,int,int) key:
        :param DataWritten data:
        """
        f.write(
            f"{key}: ('start_address': {data.start_address}, "
            f"hex: {hex(data.start_address)}), "
            f"'memory_used': {data.memory_used}, "
            f"'memory_written': {data.memory_written})\n")

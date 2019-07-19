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
from six import iteritems
from spinn_utilities.log import FormatAdapter

logger = FormatAdapter(logging.getLogger(__name__))

_FOLDER_NAME = "memory_map_from_processor_to_address_space"


class MemoryMapOnHostReport(object):
    """ Report on memory usage.
    """

    def __call__(
            self, report_default_directory,
            processor_to_app_data_base_address):
        """
        :param report_default_directory:
        :param processor_to_app_data_base_address:
        :type processor_to_app_data_base_address: \
            dict(?,:py:class:`~spinn_front_end_common.utilities.utility_models.DataWritten`)
        :rtype: None
        """

        file_name = os.path.join(report_default_directory, _FOLDER_NAME)
        try:
            with open(file_name, "w") as f:
                self._describe_mem_map(f, processor_to_app_data_base_address)
        except IOError:
            logger.exception("Generate_placement_reports: Can't open file"
                             " {} for writing.", file_name)

    @staticmethod
    def _describe_mem_map(f, memory_map):
        f.write("On host data specification executor\n")

        for key, data in iteritems(memory_map):
            f.write(
                "{}: ('start_address': {}, hex:{}), "
                "'memory_used': {}, 'memory_written': {} \n".format(
                    key, data.start_address, hex(data.start_address),
                    data.memory_used, data.memory_written))

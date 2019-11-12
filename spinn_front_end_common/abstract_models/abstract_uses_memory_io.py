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

from six import add_metaclass
from spinn_utilities.abstract_base import AbstractBase, abstractmethod


@add_metaclass(AbstractBase)
class AbstractUsesMemoryIO(object):
    """ Indicates that the class will write data using the \
        :py:class:`~spinnman.utilities.io.MemoryIO` interface.
    """

    @abstractmethod
    def get_memory_io_data_size(self):
        """ Get the size of the data area to allocate for this vertex.

        :return: The size of the data area in bytes
        :rtype: int
        """

    @abstractmethod
    def write_data_to_memory_io(self, memory, tag):
        """ Write the data to the given memory object

        :param memory: \
            The memory to write to (and handle to use to do the write)
        :type memory: ~spinnman.utilities.io.MemoryIO
        :param tag: The tag given to the allocated memory
        :type tag: int
        :rtype: None
        """

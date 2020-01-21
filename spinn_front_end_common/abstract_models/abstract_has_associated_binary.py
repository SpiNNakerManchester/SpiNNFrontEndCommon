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
class AbstractHasAssociatedBinary(object):
    """ Marks a machine graph vertex that can be launched on a SpiNNaker core.
    """

    __slots__ = ()

    @abstractmethod
    def get_binary_file_name(self):
        """ Get the binary name to be run for this vertex.

        :rtype: str
        """

    @abstractmethod
    def get_binary_start_type(self):
        """ Get the start type of the binary to be run.

        :rtype: ~spinn_front_end_common.utilities.utility_objs.ExecutableType
        """

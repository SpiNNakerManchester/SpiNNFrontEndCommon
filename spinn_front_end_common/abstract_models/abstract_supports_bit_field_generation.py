# Copyright (c) 2019-2020 The University of Manchester
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
from pacman.model.graphs.machine import MachineVertex
from spinn_front_end_common.utilities.exceptions import SpinnFrontEndException


@add_metaclass(AbstractBase)
class AbstractSupportsBitFieldGeneration(object):
    """ Marks a vertex that can provide information about bitfields it wants \
        generated on-chip.
    """

    _WRONG_VERTEX_TYPE_ERROR = (
        "The vertex {} is not of type MachineVertex. By not being a "
        "machine vertex, the functions that generate bifields will not check "
        "this vertex")

    def __new__(cls, *args, **kwargs):
        if not issubclass(cls, MachineVertex):
            raise SpinnFrontEndException(
                cls._WRONG_VERTEX_TYPE_ERROR.format(cls))
        return super(AbstractSupportsBitFieldGeneration, cls).__new__(cls)

    @abstractmethod
    def bit_field_base_address(self, transceiver, placement):
        """ Returns the SDRAM address for the bit field table data.

        :param ~spinnman.transceiver.Transceiver transceiver:
        :param ~pacman.model.placements.Placement placement:
        :return: the SDRAM address for the bitfield address
        :rtype: int
        """

    @abstractmethod
    def bit_field_builder_region(self, transceiver, placement):
        """ returns the SDRAM address for the bit field builder data

        :param ~spinnman.transceiver.Transceiver transceiver:
        :param ~pacman.model.placements.Placement placement:
        :return: the SDRAM address for the bitfield builder data
        :rtype: int
        """

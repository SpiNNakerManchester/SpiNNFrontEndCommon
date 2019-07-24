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

from spinn_utilities.abstract_base import AbstractBase, abstractmethod
from six import add_metaclass


@add_metaclass(AbstractBase)
class AbstractSupportsBitFieldRoutingCompression(object):

    @abstractmethod
    def key_to_atom_map_region_base_address(self, transceiver, placement):
        """ returns the sdram address for the region that contains key to \
        atom data

        :param transceiver: txrx
        :param placement: placement
        :return: the sdram address for the  key to atom data
        """

    @abstractmethod
    def bit_field_base_address(self, transceiver, placement):
        """ returns the sdram address for the bit field table data

        :param transceiver: txrx
        :param placement: placement
        :return: the sdram address for the bitfield address
        """

    @abstractmethod
    def regeneratable_sdram_blocks_and_sizes(self, transceiver, placement):
        """ returns the sdram address's for the core's sdram that can be used \
        to generate bitfield tables loaded

        :param transceiver: txrx
        :param placement: placement
        :return: list of tuple containing (the sdram address for the cores \
        sdram address's for the core's sdram that can be used \
        to generate bitfield tables loaded
        """

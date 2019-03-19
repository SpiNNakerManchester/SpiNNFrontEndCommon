from spinn_utilities.abstract_base import AbstractBase, abstractmethod
from six import add_metaclass


@add_metaclass(AbstractBase)
class AbstractSupportsBitFieldRoutingCompression(object):

    @abstractmethod
    def key_to_atom_map_region_base_address(self, transceiver, placement):
        """ returns the sdram address for the region that contains key to 
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
        """ returns the sdram address's for the core's sdram that can be used\ 
        to generate bitfield tables loaded 

        :param transceiver: txrx
        :param placement: placement
        :return: list of tuple containing (the sdram address for the cores \
        sdram address's for the core's sdram that can be used\ 
        to generate bitfield tables loaded 
        """
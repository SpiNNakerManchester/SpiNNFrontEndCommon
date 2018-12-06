from six import add_metaclass
from spinn_utilities.abstract_base import (
    AbstractBase, abstractmethod)


@add_metaclass(AbstractBase)
class DsAbstractDatabase(object):
    __slots__ = []

    def commit(self):
        """
        Ensures that all data expected is sent to the database and is
            peristant.
        """

    @abstractmethod
    def close(self):
        """
            Signals that the database can be closed and will not be reused.
            Once this is called any other method in this API is allowed to
                raise any kind of exception.
        """

    @abstractmethod
    def save_ds(self, chip_x, chip_y, chip_p, ethernet_x, ethernet_y, ds):
        """

        :param chip_x: x of the core ds applies to
        :param chip_y: y of the core ds applies to
        :param p: p of the core ds applies to
        :param ethernet_x: x of the ethernet chip of the board core is on
        :param ethernet_y: y of the ethernet chip of the board core is on
        :param ds: the data spec as byte code nbby
        :type ds: bytearray
        """

    def save_ds(self, chip, p, ds):
        """
        Saves the data spec as byte code for this chip

        :param chip: the chip to save it for
        :type chip: :py:class:`~spinn_machine.Chip`
        :param p: p of the core ds applies to
        :param ds: the data spec as byte code
        :type ds: bytearray
        """
        self.save_ds(chip.x, chip.y, p,
                     chip.nearest_ethernet_x, chip.nearest_ethernet_y, ds)

    @abstractmethod
    def get_ds(self, x, y, p):
        """
        Retreives the data spec as byte code for this core
        :param x: core x
        :param y: core y
        :param p: core p
        :return: data spec as byte code
        """

    def save_boards(self, machine):
        """
        Prepares the board table

        :param machine: Machine to get the boards from
        :type machine: :py:class:`~spinn_machine.Machine`
        :return:
        """
        for chip in machine.ethernet_connected_chips:
            self.save_board(chip)

    @abstractmethod
    def save_board(self, ethernet_chip):
        """
        Saves a board based on its ethernet chip

        :param ethernet_chip:
        :type chip: :py:class:`~spinn_machine.Chip`
        """

    @abstractmethod
    def get_write_info(self, x, y, p):
        """
        Gets the provenance returned by the Data Spec executor

        :param x: core x
        :param y: core y
        :param p: core p
        :rtype: dict() with the keys
            'start_address', 'memory_used' and 'memory_written'
        """
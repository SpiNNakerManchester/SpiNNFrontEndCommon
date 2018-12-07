from six import add_metaclass
from spinn_utilities.abstract_base import (
    AbstractBase, abstractmethod)


@add_metaclass(AbstractBase)
class DsAbstractDatabase(object):
    __slots__ = []

    @abstractmethod
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
    def save_ds(self, core_x, core_y, core_p, ethernet_x, ethernet_y, ds):
        """

        :param core_x: x of the core ds applies to
        :param core_y: y of the core ds applies to
        :param p: p of the core ds applies to
        :param ethernet_x: x of the ethernet chip of the board core is on
        :param ethernet_y: y of the ethernet chip of the board core is on
        :param ds: the data spec as byte code nbby
        :type ds: bytearray
        """

    @abstractmethod
    def get_ds(self, x, y, p):
        """
        Retreives the data spec as byte code for this core
        :param x: core x
        :param y: core y
        :param p: core p
        :return: data spec as byte code
        """

    @abstractmethod
    def ds_iteritems(self):
        """
        Yields the keys for the DS data
        :return Yields the (x, y, p) of  each saved ds
        :rtype: iterataor of (int, int, int)
        """

    @abstractmethod
    def ds_n_cores(self):
        """
        Returns the number for cores there is a ds saved for
        """

    def ds_iter_items(self):
        """

        :return:
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

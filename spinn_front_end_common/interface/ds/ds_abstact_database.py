from six import add_metaclass
from spinn_utilities.abstract_base import (
    AbstractBase, abstractmethod)


@add_metaclass(AbstractBase)
class DsAbstractDatabase(object):
    """
    Class which minics the actions of a the databse but only uses two dicts.

    Not currently used but would be faster if Python only and relatively small

    Kept in case needed or for possible testing.
    """
    __slots__ = []

    @abstractmethod
    def close(self):
        """
            Signals that the database can be closed and will not be reused.
            Once this is called any other method in this API is allowed to
                raise any kind of exception.
        """

    @abstractmethod
    def save_ds(self, core_x, core_y, core_p, ds):
        """

        :param core_x: x of the core ds applies to
        :param core_y: y of the core ds applies to
        :param p: p of the core ds applies to
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
        Yields the keys and values  for the DS data

        :return Yields the (x, y, p) and saved ds pairs
        :rtype: ((int, int, int),  bytearray)
        """

    @abstractmethod
    def ds_n_cores(self):
        """
        Returns the number for cores there is a ds saved for

        :rtype: int
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

    @abstractmethod
    def set_write_info(self, x, y, p, info):
        """
        Gets the provenance returned by the Data Spec executor

        :param x: core x
        :param y: core y
        :param p: core p
        :param info: dict() with the keys
            'start_address', 'memory_used' and 'memory_written'
        """

    @abstractmethod
    def info_n_cores(self):
        """
        Returns the number for cores there is a info saved for
        :rtype: int
        """

    @abstractmethod
    def info_iteritems(self):
        """
        Yields the keys and values  for the Info data

        dict with the keys
            'start_address', 'memory_used' and 'memory_written'

        :return Yields the (x, y, p) and Info
        :rtype: ((int, int, int),  dict)
        """

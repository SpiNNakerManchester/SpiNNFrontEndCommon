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
    def clear_ds(self):
        """ Clear all saved data specification data
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
        Retrieves the data spec as byte code for this core
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
    def ds_set_app_id(self, app_id):
        """
        Sets the same app_id for all rows that have ds content

        :param app_id: value to set
        :rtype app_id: int
        """

    @abstractmethod
    def ds_get_app_id(self, x, y, p):
        """
        Gets the app_id set for this core

        :param x: core x
        :param y: core y
        :param p: core p
        :rtype: int
        """

    @abstractmethod
    def ds_mark_as_system(self, core_list):
        """
        Flags a list of processors as running system binaries.

        :param core_list: list of (core x, core y, core p)
        """

    @abstractmethod
    def get_write_info(self, x, y, p):
        """
        Gets the provenance returned by the Data Spec executor

        :param x: core x
        :param y: core y
        :param p: core p
        :rtype: DataWritten
        """

    @abstractmethod
    def set_write_info(self, x, y, p, info):
        """
        Gets the provenance returned by the Data Spec executor

        :param x: core x
        :param y: core y
        :param p: core p
        :param info: DataWritten
        """

    @abstractmethod
    def clear_write_info(self):
        """
        Clears the provenance for all rows
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
        Yields the keys and values for the Info data. Note that a DB \
        transaction may be held while this iterator is processing.

        :return Yields the (x, y, p) and DataWritten
        :rtype: ((int, int, int),  dict)
        """

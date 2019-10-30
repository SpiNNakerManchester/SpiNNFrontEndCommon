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
from spinn_utilities.abstract_base import (
    AbstractBase, abstractmethod)


@add_metaclass(AbstractBase)
class DsAbstractDatabase(object):
    """ Interface supported by all database implementations that store data \
        specifications.
    """
    __slots__ = []

    @abstractmethod
    def close(self):
        """ Signals that the database can be closed and will not be reused.

        .. note::
            Once this is called any other method in this API is allowed to\
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
        :type core_x: int
        :param core_y: y of the core ds applies to
        :type core_y: int
        :param p: p of the core ds applies to
        :type p: int
        :param ds: the data spec as byte code
        :type ds: bytearray
        """

    @abstractmethod
    def get_ds(self, x, y, p):
        """ Retrieves the data spec as byte code for this core.

        :param x: core x
        :type x: int
        :param y: core y
        :type y: int
        :param p: core p
        :type p: int
        :return: data spec as byte code
        :rtype: bytearray
        """

    @abstractmethod
    def ds_iteritems(self):
        """ Yields the keys and values for the DS data

        :return: Yields the (x, y, p) and saved ds pairs
        :rtype: iterable(tuple(tuple(int, int, int), bytearray))
        """

    @abstractmethod
    def ds_n_cores(self):
        """ Returns the number for cores there is a ds saved for

        :rtype: int
        """

    @abstractmethod
    def ds_set_app_id(self, app_id):
        """ Sets the same app_id for all rows that have ds content

        :param app_id: value to set
        :type app_id: int
        """

    @abstractmethod
    def ds_get_app_id(self, x, y, p):
        """ Gets the app_id set for this core

        :param x: core x
        :type x: int
        :param y: core y
        :type y: int
        :param p: core p
        :type p: int
        :rtype: int
        """

    @abstractmethod
    def ds_mark_as_system(self, core_list):
        """
        Flags a list of processors as running system binaries.

        :param core_list: list of (core x, core y, core p)
        :type core_list: iterable(tuple(int,int,int))
        """

    @abstractmethod
    def get_write_info(self, x, y, p):
        """ Gets the provenance returned by the Data Spec executor

        :param x: core x
        :type x: int
        :param y: core y
        :type y: int
        :param p: core p
        :type p: int
        :rtype: ~spinn_front_end_common.utilities.utility_objs.DataWritten
        """

    @abstractmethod
    def set_write_info(self, x, y, p, info):
        """ Sets the provenance returned by the Data Spec executor.

        :param x: core x
        :type x: int
        :param y: core y
        :type y: int
        :param p: core p
        :type p: int
        :param info: DataWritten
        :type info: ~spinn_front_end_common.utilities.utility_objs.DataWritten
        """

    @abstractmethod
    def clear_write_info(self):
        """
        Clears the provenance for all rows
        """

    @abstractmethod
    def info_n_cores(self):
        """ Returns the number for cores there is a info saved for.

        :rtype: int
        """

    @abstractmethod
    def info_iteritems(self):
        """
        Yields the keys and values for the Info data. Note that a DB \
        transaction may be held while this iterator is processing.

        :return: Yields the (x, y, p) and DataWritten
        :rtype: iterable(tuple(tuple(int, int, int),\
            ~spinn_front_end_common.utilities.utility_objs.DataWritten))
        """

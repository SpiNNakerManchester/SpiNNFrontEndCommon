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
class AbstractDatabase(object):
    """
    This API separates the required database calls from the implementation.

    Methods here are designed for the convenience of the caller not the\
    database.

    There should only ever be a single Database Object in use at any time.\
    In the case of application_graph_changed the first should closed and\
    a new one created.

    Do not assume that just because 2 database objects where opened with the\
    same parameters (for example SQLite file)\
    that they hold the same data. \
    In fact the second init is allowed to delete any previous data.

    While not recommended implementation objects are allowed to hold data in \
    memory, with the exception of data required by the java which must be \
    in the database once commit is called.
    """

    __slots__ = ()

    @abstractmethod
    def close(self):
        """ Signals that the database can be closed and will not be reused.

        Once this is called any other method in this API is allowed to\
        raise any kind of exception.
        """

    @abstractmethod
    def store_data_in_region_buffer(self, x, y, p, region, data):
        """ Store some information in the corresponding buffer for a\
            specific chip, core and recording region.

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :param region: Region containing the data to be stored
        :type region: int
        :param data: data to be stored

            .. note::
                Implementations may assume this to be shorter than 1GB

        :type data: bytearray
        """

    @abstractmethod
    def get_region_data(self, x, y, p, region):
        """ Get the data stored for a given region of a given core

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :param region: Region containing the data
        :type region: int
        :return: a buffer containing all the data received during the\
            simulation, and a flag indicating if any data was missing

            .. note::
                Implementations should not assume that the total buffer is \
                necessarily shorter than 1GB.

        :rtype: tuple(memoryview, bool)
        """

    @abstractmethod
    def clear(self):
        """ Clears the data for all regions.

        .. note::
            This method will be removed when the database moves to
            keeping data after reset.

        :rtype: None
        """

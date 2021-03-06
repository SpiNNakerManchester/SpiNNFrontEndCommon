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

import logging
from six import add_metaclass
from spinn_utilities.abstract_base import AbstractBase, abstractmethod
from spinn_utilities.log import FormatAdapter
from pacman.model.graphs.machine import MachineVertex
from spinn_front_end_common.utilities.exceptions import SpinnFrontEndException

logger = FormatAdapter(logging.getLogger(__name__))


@add_metaclass(AbstractBase)
class AbstractSendsBuffersFromHost(object):
    """ Interface to an object that sends buffers of keys to be\
        transmitted at given timestamps in the simulation.
    """

    __slots__ = ()

    _WRONG_VERTEX_TYPE_ERROR = (
        "The vertex {} is not of type MachineVertex. By not being a "
        "machine vertex, the BufferManager/Java will not send the data")

    def __new__(cls, *args, **kwargs):
        if not issubclass(cls, MachineVertex):
            raise SpinnFrontEndException(
                cls._WRONG_VERTEX_TYPE_ERROR.format(cls))
        return super(AbstractSendsBuffersFromHost, cls).__new__(cls)

    @abstractmethod
    def buffering_input(self):
        """ Return True if the input of this vertex is to be buffered.

        :rtype: bool
        """

    @abstractmethod
    def get_regions(self):
        """ Get the set of regions for which there are keys to be sent

        :return: Iterable of region IDs
        :rtype: iterable(int)
        """

    @abstractmethod
    def get_region_buffer_size(self, region):
        """ Get the size of the buffer to be used in SDRAM on the machine\
            for the region in bytes

        :param int region: The region to get the buffer size of
        :return: The size of the buffer space in bytes
        :rtype: int
        """

    @abstractmethod
    def is_next_timestamp(self, region):
        """ Determine if there is another timestamp with data to be sent

        :param int region: The region to determine if there is more data for
        :return: Whether there is more data
        :rtype: bool
        """

    @abstractmethod
    def get_next_timestamp(self, region):
        """ Get the next timestamp at which there are still keys to be sent\
            for the given region

        :param int region: The region to get the timestamp for
        :return: The timestamp of the next available keys
        :rtype: int
        """

    @abstractmethod
    def is_next_key(self, region, timestamp):
        """ Determine if there are still keys to be sent at the given\
            timestamp for the given region

        :param int region: The region to determine if there are keys for
        :param int timestamp:
            The timestamp to determine if there are more keys for
        :return: Whether there are more keys to send for the parameters
        :rtype: bool
        """

    @abstractmethod
    def get_next_key(self, region):
        """ Get the next key in the given region

        :param int region: The region to get the next key from
        :return: The next key, or None if there are no more keys
        :rtype: int
        """

    @abstractmethod
    def is_empty(self, region):
        """ Return true if there are no spikes to be buffered for the\
            specified region

        :param int region: The region to get the next key from
        :return: Whether there are no keys to send for the region
        :rtype: bool
        """

    @abstractmethod
    def rewind(self, region):
        """ Rewinds the internal buffer in preparation of re-sending\
            the spikes

        :param int region: The region to rewind
        """

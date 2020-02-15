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
from spinn_utilities.abstract_base import AbstractBase, abstractmethod


@add_metaclass(AbstractBase)
class AbstractReceiveBuffersToHost(object):
    """ Indicates that this object can receive buffers.
    """

    __slots__ = ()

    @abstractmethod
    def get_recorded_region_ids(self):
        """ Get the recording region IDs that have been recorded using buffering

        :return: The region numbers that have active recording
        :rtype: iterable(int)
        """

    @abstractmethod
    def get_recording_region_base_address(self, txrx, placement):
        """ Get the recording region base address

        :param txrx: the SpiNNMan instance
        :type txrx: ~spinnman.transceiver.Transceiver
        :param placement:\
            the placement object of the core to find the address of
        :type placement: ~pacman.model.placements.Placement
        :return: the base address of the recording region
        :rtype: int
        """

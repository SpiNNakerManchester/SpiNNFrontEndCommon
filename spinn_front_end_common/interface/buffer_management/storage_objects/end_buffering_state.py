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

from .channel_buffer_state import ChannelBufferState
from spinn_front_end_common.utilities.constants import BYTES_PER_WORD


class EndBufferingState(object):
    """ Stores the buffering state at the end of a simulation.
    """

    __slots__ = [
        #: a list of channel state, where each channel is stored in a
        #: ChannelBufferState object
        "_list_channel_buffer_state",

        #: the final state stuff
        "_buffering_out_fsm_state"
    ]

    def __init__(self, buffering_out_fsm_state, list_channel_buffer_state):
        """
        :param buffering_out_fsm_state: Final sequence number received
        :type buffering_out_fsm_state: int
        :param list_channel_buffer_state: a list of channel state, where each\
            channel is stored in a ChannelBufferState object
        :type list_channel_buffer_state: \
            list(~spinn_front_end_common.interface.buffer_management.storage_objects.ChannelBufferState)
        """
        self._buffering_out_fsm_state = buffering_out_fsm_state
        self._list_channel_buffer_state = list_channel_buffer_state

    @property
    def buffering_out_fsm_state(self):
        """
        :rtype: int
        """
        return self._buffering_out_fsm_state

    def channel_buffer_state(self, i):
        """
        :param i: the index into the buffer states
        :type i: int
        :rtype: \
            ~spinn_front_end_common.interface.buffer_management.storage_objects.ChannelBufferState
        """
        return self._list_channel_buffer_state[i]

    def get_state_for_region(self, region_id):
        """
        :param region_id: The region identifier
        :type region_id: int
        :rtype: None or \
             ~spinn_front_end_common.interface.buffer_management.storage_objects.ChannelBufferState
        """
        for state in self._list_channel_buffer_state:
            if state.region_id == region_id:
                return state
        return None

    def get_missing_info_for_region(self, region_id):
        """
        :rtype: bool or None
        """
        state = self.get_state_for_region(region_id)
        return None if state is None else state.missing_info

    @staticmethod
    def size_of_region(n_regions_to_record):
        """
        :param n_regions_to_record: Number of regions to be recorded
        :type n_regions_to_record: int
        :return: Size of region required to hold that state, in bytes
        :rtype: int
        """
        size_of_header = BYTES_PER_WORD * (2 + n_regions_to_record)

        # add size needed for the data region addresses
        size_of_header += BYTES_PER_WORD * n_regions_to_record
        size_of_channel_state = ChannelBufferState.size_of_channel_state()
        return size_of_header + n_regions_to_record * size_of_channel_state

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


class EndBufferingState(object):
    """ Stores the buffering state at the end of a simulation.
    """

    __slots__ = [
        #  a list of channel state, where each channel is stored in a
        # ChannelBufferState object
        "_list_channel_buffer_state",

        # the final state stuff
        "_buffering_out_fsm_state"
    ]

    def __init__(self, buffering_out_fsm_state, list_channel_buffer_state):
        """
        :param buffering_out_fsm_state: Final sequence number received
        :param list_channel_buffer_state: a list of channel state, where each\
            channel is stored in a ChannelBufferState object
        """
        self._buffering_out_fsm_state = buffering_out_fsm_state
        self._list_channel_buffer_state = list_channel_buffer_state

    @property
    def buffering_out_fsm_state(self):
        return self._buffering_out_fsm_state

    def channel_buffer_state(self, i):
        return self._list_channel_buffer_state[i]

    def get_state_for_region(self, region_id):
        for state in self._list_channel_buffer_state:
            if state.region_id == region_id:
                return state
        return None

    def get_missing_info_for_region(self, region_id):
        state = self.get_state_for_region(region_id)
        return None if state is None else state.missing_info

    @staticmethod
    def size_of_region(n_regions_to_record):
        size_of_header = 8 + 4 * n_regions_to_record

        # add size needed for the data region addresses
        size_of_header += 4 * n_regions_to_record
        size_of_channel_state = ChannelBufferState.size_of_channel_state()
        return size_of_header + n_regions_to_record * size_of_channel_state

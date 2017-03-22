from spinn_front_end_common.interface.buffer_management.\
    storage_objects.channel_buffer_state import ChannelBufferState


class EndBufferingState(object):
    """ Stores the buffering state at the end of a simulation
    """

    __slots__ = [
        #  a list of channel state, where each channel is stored in a
        # ChannelBufferState object
        "_list_channel_buffer_state",
    ]

    def __init__(
            self, buffering_out_fsm_state, list_channel_buffer_state):
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
        if state is not None:
            return state.missing_info
        else:
            return None

    @staticmethod
    def size_of_region(n_regions_to_record):
        size_of_header = 8 + 4 * n_regions_to_record

        # add size needed for the data region addresses
        size_of_header += 4 * n_regions_to_record
        size_of_channel_state = ChannelBufferState.size_of_channel_state()
        return size_of_header + n_regions_to_record * size_of_channel_state

from spinn_front_end_common.interface.buffer_management.\
    storage_objects.channel_buffer_state import ChannelBufferState
import struct


class EndBufferingState(object):
    """ Stores the buffering state at the end of a simulation
    """

    __slots__ = [

        # Number of buffering regions used
        "_n_recording_regions",

        # Final sequence number received
        "_buffering_out_fsm_state",

        #  a list of channel state, where each channel is stored in a
        # ChannelBufferState object
        "_list_channel_buffer_state",

        # iterable of ints which represent the memory addresses for where every
        # recorded regions starts
        "_region_addresses"
    ]

    def __init__(
            self, n_recording_regions, buffering_out_fsm_state,
            list_channel_buffer_state, region_addresses):
        """

        :param n_recording_regions: Number of buffering regions used
        :param buffering_out_fsm_state: Final sequence number received
        :param list_channel_buffer_state: a list of channel state, where each\
                channel is stored in a ChannelBufferState object
        :param region_addresses: the memory addresses for the recording regions
        """
        self._n_recording_regions = n_recording_regions
        self._buffering_out_fsm_state = buffering_out_fsm_state
        self._list_channel_buffer_state = list_channel_buffer_state
        self._region_addresses = region_addresses

    @property
    def buffering_out_fsm_state(self):
        return self._buffering_out_fsm_state

    @property
    def region_addresses(self):
        """
        property for the addresses for recording regions.
        :return: list of ints
        """
        return self._region_addresses

    def get_region_address(self, recording_region_id):
        return self._region_addresses[recording_region_id]

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

    @property
    def number_of_recording_regions(self):
        return self._n_recording_regions

    @staticmethod
    def create_from_bytearray(data):
        offset = 0

        n_recording_regions, buffering_out_fsm_state = \
            struct.unpack_from("<II", data, offset)

        offset += 8

        region_data_addresses = list()
        for _ in range(0, n_recording_regions):
            region_data_addresses.append(struct.unpack_from("<I", data, offset))
            offset += 4

        list_channel_buffer_state = list()
        for _ in xrange(n_recording_regions):
            entry = ChannelBufferState.create_from_bytearray(
                data, offset)
            offset += ChannelBufferState.size_of_channel_state()
            list_channel_buffer_state.append(entry)
        final_state = EndBufferingState(
            n_recording_regions, buffering_out_fsm_state,
            list_channel_buffer_state, region_data_addresses)
        return final_state

    @staticmethod
    def size_of_region(n_regions_to_record):
        size_of_header = 8 + 4 * n_regions_to_record
        # add size needed for the data region addresses
        size_of_header += 4 * n_regions_to_record
        size_of_channel_state = ChannelBufferState.size_of_channel_state()
        return size_of_header + n_regions_to_record * size_of_channel_state

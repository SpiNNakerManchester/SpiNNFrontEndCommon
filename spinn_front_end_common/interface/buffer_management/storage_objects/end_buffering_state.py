from spinn_front_end_common.interface.buffer_management.\
    storage_objects.channel_buffer_state import ChannelBufferState
from spinn_front_end_common.utilities import constants
import struct


class EndBufferingState(object):
    """
    This class stores information related to the status of the buffering
    output mechanism at the end of a simulation when the state is
    retrieved from the SpiNNaker machine. Information stored are:
    1 - Number of buffering regions used
    2 - Final state of the state machine (given by the sequence number) which
    controls the buffering output technique
    3 - a list of channel state, where each channel is stored in a
    ChannelBufferState class
    """
    def __init__(
            self, n_recording_regions,
            buffering_out_fsm_state,
            list_channel_buffer_state):
        self._n_recording_regions = n_recording_regions
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

    def get_size_for_region(self, region_id):
        state = self.get_state_for_region(region_id)
        if state is not None:
            return state.end_address - state.start_address
        else:
            return 0

    def get_missing_info_for_region(self, region_id):
        state = self.get_state_for_region(region_id)
        if state is not None:
            return state.missing_info
        else:
            return None

    def update_last_operation_for_region(self, region_id, operation):
        state = self.get_state_for_region(region_id)
        if state is not None:
            state.update_last_operation(operation)

    def is_state_updated_for_region(self, region_id):
        state = self.get_state_for_region(region_id)
        if state is not None:
            return state.update_completed
        else:
            return None

    def update_read_pointer_for_region(self, region_id, read_ptr):
        state = self.get_state_for_region(region_id)
        if state is not None:
            state.update_read_pointer(read_ptr)

    def set_update_completed(self):
        state = self.get_state_for_region(region_id)
        if state is not None:
            return state.set_update_completed()
        else:
            return None

    @property
    def number_of_recording_regions(self):
        return self._n_recording_regions

    @staticmethod
    def create_from_bytearray(data):
        offset = 0
        n_recording_regions, \
            buffering_out_fsm_state = struct.unpack_from(
                "<II", data, offset)
        offset += 8

        list_channel_buffer_state = list()
        for _ in xrange(n_recording_regions):
            entry = ChannelBufferState.create_from_bytearray(
                data, offset)
            offset += ChannelBufferState.size_of_channel_state()
            list_channel_buffer_state.append(entry)
        final_state = EndBufferingState(
            n_recording_regions, buffering_out_fsm_state,
            list_channel_buffer_state)
        return final_state

    @staticmethod
    def size_of_region(n_regions_to_record):
        size_of_header = 8 + 4 * n_regions_to_record
        size_of_channel_state = ChannelBufferState.size_of_channel_state()
        return size_of_header + n_regions_to_record * size_of_channel_state

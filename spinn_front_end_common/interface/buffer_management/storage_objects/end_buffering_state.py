from spinn_front_end_common.interface.buffer_management.\
    storage_objects.channel_buffer_state import ChannelBufferState
from spinn_front_end_common.utilities import constants
import struct


class EndBufferingState(object):
    def __init__(self, buffering_out_fsm_state, list_channel_buffer_state):
        self._buffering_out_fsm_state = buffering_out_fsm_state
        self._list_channel_buffer_state = list_channel_buffer_state

    @property
    def buffering_out_fsm_state(self):
        return self._buffering_out_fsm_state

    def channel_buffer_state(self, i):
        return self._list_channel_buffer_state[i]

    @staticmethod
    def create_from_bytearray(data):
        buffering_out_fsm_state = struct.unpack_from("<I", data, 0)[0]
        list_channel_buffer_state = list()
        offset = 4
        for _ in xrange(constants.OUTPUT_BUFFERING_CHANNELS):
            entry, offset = ChannelBufferState.create_from_bytearray(
                data, offset)
            list_channel_buffer_state.append(entry)
        final_state = EndBufferingState(
            buffering_out_fsm_state, list_channel_buffer_state)
        return final_state

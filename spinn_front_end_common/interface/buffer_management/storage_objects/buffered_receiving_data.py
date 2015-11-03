from spinn_front_end_common.interface.buffer_management.storage_objects.\
    buffered_bytearray_data_storage import BufferedBytearrayDataStorage
from spinn_front_end_common.interface.buffer_management.storage_objects.\
    buffered_file_data_storage import BufferedFileDataStorage
from spinn_front_end_common.interface.buffer_management.storage_objects.\
    end_buffering_state import EndBufferingState


class BufferedReceivingData(object):
    def __init__(self, store_to_file=False):
        self._store_to_file = store_to_file

        self._data = dict()
        self._is_flushed = dict()
        self._sequence_no = dict()
        self._last_packet_received = dict()
        self._last_packet_sent = dict()
        self._end_buffering_state = dict()

    def store_data_in_region_buffer(self, x, y, p, region, data):
        if (x, y, p, region) not in self._data:
            self.create_data_storage_for_region(x, y, p, region)
        self._data[x, y, p, region].write(data)

    def create_data_storage_for_region(self, x, y, p, region):
        if (x, y, p, region) not in self._data:
            if self._store_to_file:
                self._data[x, y, p, region] = BufferedFileDataStorage()
            else:
                self._data[x, y, p, region] = BufferedBytearrayDataStorage()
            self._is_flushed[x, y, p, region] = False

            if (x, y, p) not in self._sequence_no:
                self._sequence_no[x, y, p] = 0xFF

            if (x, y, p) not in self._last_packet_received:
                self._last_packet_received[x, y, p] = None

            if (x, y, p) not in self._last_packet_sent:
                self._last_packet_sent[x, y, p] = None

    def is_data_from_region_flushed(self, x, y, p, region):
        if (x, y, p, region) in self._is_flushed:
            return self._is_flushed[x, y, p, region]
        else:
            return False

    def flushing_data_from_region(self, x, y, p, region, data):
        self.store_data_in_region_buffer(x, y, p, region, data)
        self._is_flushed[x, y, p, region] = True

    def store_last_received_packet_from_core(self, x, y, p, packet):
        self._last_packet_received[x, y, p] = packet

    def last_received_packet_from_core(self, x, y, p):
        return self._last_packet_received[x, y, p]

    def store_last_sent_packet_to_core(self, x, y, p, packet):
        self._last_packet_sent[x, y, p] = packet

    def last_sent_packet_to_core(self, x, y, p):
        return self._last_packet_sent[x, y, p]

    def last_sequence_no_for_core(self, x, y, p):
        return self._sequence_no[x, y, p]

    def update_sequence_no_for_core(self, x, y, p, sequence_no):
        self._sequence_no[x, y, p] = sequence_no

    def get_region_data(self, x, y, p, region):
        if self._end_buffering_state[x, y, p].get_missing_info_for_region(
                region):
            print "Missing information in chip ({0:d},{1:d}), core {2:d} " \
                  "for region {3:d}".format(x, y, p, region)
        data = self._data[x, y, p, region].read_all()
        return data

    def get_region_data_pointer(self, x, y, p, region):
        if self._end_buffering_state[x, y, p].get_missing_info_for_region(
                region):
            print "Missing information in chip ({0:d},{1:d}), core {2:d} " \
                  "for region {3:d}".format(x, y, p, region)
        data_pointer = self._data[x, y, p, region]
        return data_pointer

    def store_end_buffering_state(self, x, y, p, state):
        self._end_buffering_state[x, y, p] = state

    def is_end_buffering_state_recovered(self, x, y, p):
        if (x, y, p) in self._end_buffering_state:
            return True
        else:
            return False

    def get_end_buffering_state(self, x, y, p):
        return self._end_buffering_state[x, y, p]

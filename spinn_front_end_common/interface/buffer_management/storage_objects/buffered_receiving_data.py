from spinn_front_end_common.interface.buffer_management.storage_objects.\
    buffered_bytearray_data_storage import BufferedBytearrayDataStorage
from spinn_front_end_common.interface.buffer_management.storage_objects.\
    buffered_file_data_storage import BufferedFileDataStorage
from spinn_front_end_common.interface.buffer_management.storage_objects.\
    end_buffering_state import EndBufferingState


class BufferedReceivingData(object):
    """
    This object stores the information received through the buffering output
    technique from the SpiNNaker system. The data kept includes the last sent
    packet and last received packet, their correspondent sequence numbers,
    the data retrieved, a flag to identify if the data from a core has been
    flushed and the final state of the buffering output FSM
    """
    def __init__(self, store_to_file=False):
        """

        :param store_to_file: A boolean to identify if the data will be stored
        in memory using a byte array or ina temporary file on the disk
        :type store_to_file: bool
        :return: None
        :rtype: None
        """
        self._store_to_file = store_to_file

        self._data = dict()
        self._is_flushed = dict()
        self._sequence_no = dict()
        self._last_packet_received = dict()
        self._last_packet_sent = dict()
        self._end_buffering_state = dict()

    def store_data_in_region_buffer(self, x, y, p, region, data):
        """
        Store some information in the correspondent buffer class for a
        specific chip, core and region

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :param region: Region containing the data to be stored
        :type region: int
        :param data: data to be stored
        :type data: bytearray
        :return: None
        :rtype: None
        """
        if (x, y, p, region) not in self._data:
            self.create_data_storage_for_region(x, y, p, region)
        self._data[x, y, p, region].write(data)

    def create_data_storage_for_region(self, x, y, p, region):
        """
        Create all the storage elements for a new region which is going to use
        the buffering output technique

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :param region: Region containing the data
        :type region: int
        :return: None
        :rtype: None
        """
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
        """
        Checks if the data region has been flushed

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :param region: Region containing the data
        :type region: int
        :return: True if the region has been flushed. False otherwise
        :rtype: bool
        """
        if (x, y, p, region) in self._is_flushed:
            return self._is_flushed[x, y, p, region]
        else:
            return False

    def flushing_data_from_region(self, x, y, p, region, data):
        """
        Store some information in the correspondent buffer class for a
        specific chip, core and region, and sets the bit to indicate that the
        region has been flushed

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :param region: Region containing the data to be stored
        :type region: int
        :param data: data to be stored
        :type data: bytearray
        :return: None
        :rtype: None
        """
        self.store_data_in_region_buffer(x, y, p, region, data)
        self._is_flushed[x, y, p, region] = True

    def store_last_received_packet_from_core(self, x, y, p, packet):
        """
        Stores the last packet received from the SpiNNaker system related
        the buffering output mechanism

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :param packet: SpinnakerRequestReadData packet received from the
        SpiNNaker system
        :type packet: :py:class:`spinnman.messages.eieio.command_messages.spinnaker_request_read_data.SpinnakerRequestReadData`
        :return: None
        :rtype: None
        """
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
        missing = None
        if self._end_buffering_state[x, y, p].get_missing_info_for_region(
                region):
            missing = (x, y, p, region)
        data = self._data[x, y, p, region].read_all()
        return data, missing

    def get_region_data_pointer(self, x, y, p, region):
        missing = None
        if self._end_buffering_state[x, y, p].get_missing_info_for_region(
                region):
            missing = (x, y, p, region)
        data_pointer = self._data[x, y, p, region]
        return data_pointer, missing

    def store_end_buffering_state(self, x, y, p, state):
        self._end_buffering_state[x, y, p] = state

    def is_end_buffering_state_recovered(self, x, y, p):
        if (x, y, p) in self._end_buffering_state:
            return True
        else:
            return False

    def get_end_buffering_state(self, x, y, p):
        return self._end_buffering_state[x, y, p]

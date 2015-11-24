from spinn_front_end_common.interface.buffer_management.storage_objects.\
    buffered_bytearray_data_storage import BufferedBytearrayDataStorage
from spinn_front_end_common.interface.buffer_management.storage_objects.\
    buffered_file_data_storage import BufferedFileDataStorage
from collections import defaultdict


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

        self._data = None
        if store_to_file:
            self._data = defaultdict(BufferedFileDataStorage)
        else:
            self._data = defaultdict(BufferedBytearrayDataStorage)
        self._is_flushed = defaultdict(lambda: False)
        self._sequence_no = defaultdict(lambda: 0xFF)
        self._last_packet_received = defaultdict(lambda: None)
        self._last_packet_sent = defaultdict(lambda: None)
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
        self._data[x, y, p, region].write(data)

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
        return self._is_flushed[x, y, p, region]

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
        Stores the last packet received from the SpiNNaker system related to
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
        """
        Retrieves the last packet received from the SpiNNaker system related
        to the buffering output mechanism

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :return: SpinnakerRequestReadData packet received from the
        SpiNNaker system
        :rtype: :py:class:`spinnman.messages.eieio.command_messages.spinnaker_request_read_data.SpinnakerRequestReadData`
        """
        return self._last_packet_received[x, y, p]

    def store_last_sent_packet_to_core(self, x, y, p, packet):
        """
        Stores the last packet sent to the SpiNNaker system related to the
        buffering output mechanism

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :param packet: last HostDataRead packet sent to the SpiNNaker system
        :type packet: :py:class:`spinnman.messages.eieio.command_messages.host_data_read.HostDataRead`
        :return: None
        :rtype: None
        """
        self._last_packet_sent[x, y, p] = packet

    def last_sent_packet_to_core(self, x, y, p):
        """
        Retrieves the last packet sent to the SpiNNaker system related to the
        buffering output mechanism

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :return: last HostDataRead packet sent to the SpiNNaker system
        :rtype: :py:class:`spinnman.messages.eieio.command_messages.host_data_read.HostDataRead`
        """
        return self._last_packet_sent[x, y, p]

    def last_sequence_no_for_core(self, x, y, p):
        """
        Returns the sequence number of the last set of packets (sent and
        received) used in the communication with the SpiNNaker system for
        the buffering output technique

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :return: last sequence number used
        :rtype: int
        """
        return self._sequence_no[x, y, p]

    def update_sequence_no_for_core(self, x, y, p, sequence_no):
        """
        Updates the sequence number used in the last set of packets (sent and
        received) used in the communication with the SpiNNaker system for
        the buffering output technique

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :param sequence_no: last sequence number used
        :type sequence_no: int
        :return: None
        :rtype: None
        """
        self._sequence_no[x, y, p] = sequence_no

    def get_region_data(self, x, y, p, region):
        """
        Returns the data related to a specific chip, core and region in a
        bytearray

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :param region: Region containing the data
        :type region: int
        :return: an array contained all the data received during the simulation
        :rtype: bytearray
        """
        missing = None
        if self._end_buffering_state[x, y, p].get_missing_info_for_region(
                region):
            missing = (x, y, p, region)
        data = self._data[x, y, p, region].read_all()
        return data, missing

    def get_region_data_pointer(self, x, y, p, region):
        """
        Returns the structure which contains the data related to a specific
        chip, core

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :param region: Region containing the data
        :type region: int
        :return: a data structure which contains all the data received
        during the simulation. This data structure inherits from :py:class:`spinn_front_end_common.interface.buffer_management.buffer_models.abstract_buffered_data_storage.AbstractBufferedDataStorage`
        :rtype: :py:class:`spinn_front_end_common.interface.buffer_management.buffer_models.abstract_buffered_data_storage.AbstractBufferedDataStorage`
        """
        missing = False
        if self._end_buffering_state[x, y, p].get_missing_info_for_region(
                region):
            missing = True
        data_pointer = self._data[x, y, p, region]
        return data_pointer, missing

    def store_end_buffering_state(self, x, y, p, state):
        self._end_buffering_state[x, y, p] = state

    def is_end_buffering_state_recovered(self, x, y, p):
        return (x, y, p) in self._end_buffering_state

    def get_end_buffering_state(self, x, y, p):
        return self._end_buffering_state[x, y, p]

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
import os
from collections import defaultdict
from .sqllite_database import SqlLiteDatabase

#: Name of the database in the data folder
DB_FILE_NAME = "buffer.sqlite3"


class BufferedReceivingData(object):
    """ Stores the information received through the buffering output\
        technique from the SpiNNaker system. The data kept includes the last\
        sent packet and last received packet, their correspondent sequence\
        numbers, the data retrieved, a flag to identify if the data from a\
        core has been flushed and the final state of the buffering output\
        state machine
    """

    __slots__ = [
        #: the AbstractDatabase holding the data to store
        "_db",

        #: the path to the database
        "_db_file",

        #: dict of booleans indicating if a region on a core has been flushed
        "_is_flushed",

        #: dict of last sequence number received by core
        "_sequence_no",

        #: dict of last packet received by core
        "_last_packet_received",

        #: dict of last packet sent by core
        "_last_packet_sent",

        #: dict of end buffer sequence number
        "_end_buffering_sequence_no",

        #: dict of end state by core
        "_end_buffering_state"
    ]

    def __init__(self, report_folder):
        """
        :param str report_folder:
            The directory to write the database used to store some of the data
        """
        self._db_file = os.path.join(report_folder, DB_FILE_NAME)
        self._db = None
        self.reset()

    def reset(self):
        if os.path.exists(self._db_file):
            if self._db:
                self._db.close()
            os.remove(self._db_file)
        self._db = SqlLiteDatabase(self._db_file)
        self._is_flushed = defaultdict(lambda: False)
        self._sequence_no = defaultdict(lambda: 0xFF)
        self._last_packet_received = defaultdict(lambda: None)
        self._last_packet_sent = defaultdict(lambda: None)
        self._end_buffering_sequence_no = dict()
        self._end_buffering_state = dict()

    def store_data_in_region_buffer(self, x, y, p, region, data):
        """ Store some information in the correspondent buffer class for a\
            specific chip, core and region.

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :param int region: Region containing the data to be stored
        :param bytearray data: data to be stored
        """
        # pylint: disable=too-many-arguments
        self._db.store_data_in_region_buffer(x, y, p, region, data)

    def is_data_from_region_flushed(self, x, y, p, region):
        """ Check if the data region has been flushed.

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :param int region: Region containing the data
        :return: True if the region has been flushed. False otherwise
        :rtype: bool
        """
        return self._is_flushed[x, y, p, region]

    def flushing_data_from_region(self, x, y, p, region, data):
        """ Store flushed data from a region of a core on a chip, and mark it\
            as being flushed.

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :param int region: Region containing the data to be stored
        :param bytearray data: data to be stored
        """
        # pylint: disable=too-many-arguments
        self.store_data_in_region_buffer(x, y, p, region, data)
        self._is_flushed[x, y, p, region] = True

    def store_last_received_packet_from_core(self, x, y, p, packet):
        """ Store the most recent packet received from SpiNNaker for a given\
            core.

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :param packet: SpinnakerRequestReadData packet received
        :type packet:
            ~spinnman.messages.eieio.command_messages.SpinnakerRequestReadData
        """
        self._last_packet_received[x, y, p] = packet

    def last_received_packet_from_core(self, x, y, p):
        """ Get the last packet received for a given core.

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :return: SpinnakerRequestReadData packet received
        :rtype:
            ~spinnman.messages.eieio.command_messages.SpinnakerRequestReadData
        """
        return self._last_packet_received[x, y, p]

    def store_last_sent_packet_to_core(self, x, y, p, packet):
        """ Store the last packet sent to the given core.

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :param packet: last HostDataRead packet sent
        :type packet: ~spinnman.messages.eieio.command_messages.HostDataRead
        """
        self._last_packet_sent[x, y, p] = packet

    def last_sent_packet_to_core(self, x, y, p):
        """ Retrieve the last packet sent to a core.

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :return: last HostDataRead packet sent
        :rtype: ~spinnman.messages.eieio.command_messages.HostDataRead
        """
        return self._last_packet_sent[x, y, p]

    def last_sequence_no_for_core(self, x, y, p):
        """ Get the last sequence number for a core.

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :return: last sequence number used
        :rtype: int
        """
        return self._sequence_no[x, y, p]

    def update_sequence_no_for_core(self, x, y, p, sequence_no):
        """ Set the last sequence number used.

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :param int sequence_no: last sequence number used
        :rtype: None
        """
        self._sequence_no[x, y, p] = sequence_no

    def get_region_data(self, x, y, p, region):
        """ Get the data stored for a given region of a given core.

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :param int region: Region containing the data
        :return: a buffer containing all the data received during the
            simulation, and a flag indicating if any data was missing
        :rtype: tuple(memoryview, bool)
        """
        return self._db.get_region_data(x, y, p, region)

    def get_region_data_pointer(self, x, y, p, region):
        """ It is no longer possible to get access to the data pointer.

        Use :py:meth`get_region_data` to get the data and missing flag
        directly.
        """
        raise NotImplementedError("Use get_region_data instead!.")

    def store_end_buffering_state(self, x, y, p, region, state):
        """ Store the end state of buffering.

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :param int region: Region containing the data
        :param state: The end state
        """
        # pylint: disable=too-many-arguments
        self._end_buffering_state[x, y, p, region] = state

    def is_end_buffering_state_recovered(self, x, y, p, region):
        """ Determine if the end state has been stored.

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :param int region: Region containing the data
        :return: True if the state has been stored
        """
        return (x, y, p, region) in self._end_buffering_state

    def get_end_buffering_state(self, x, y, p, region):
        """ Get the end state of the buffering.

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :param int region:
        :return: The end state
        """
        return self._end_buffering_state[x, y, p, region]

    def store_end_buffering_sequence_number(self, x, y, p, sequence):
        """ Store the last sequence number sent by the core.

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :param int sequence: The last sequence number
        """
        self._end_buffering_sequence_no[x, y, p] = sequence

    def is_end_buffering_sequence_number_stored(self, x, y, p):
        """ Determine if the last sequence number has been retrieved.

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :return: True if the number has been retrieved
        :rtype: bool
        """
        return (x, y, p) in self._end_buffering_sequence_no

    def get_end_buffering_sequence_number(self, x, y, p):
        """ Get the last sequence number sent by the core.

        :param int x: x coordinate of the chip
        :param int y: y coordinate of the chip
        :param int p: Core within the specified chip
        :return: The last sequence number
        :rtype: int
        """
        return self._end_buffering_sequence_no[x, y, p]

    def resume(self):
        """ Resets states so that it can behave in a resumed mode.
        """
        self._end_buffering_state = dict()
        self._is_flushed = defaultdict(lambda: False)
        self._sequence_no = defaultdict(lambda: 0xFF)
        self._last_packet_received = defaultdict(lambda: None)
        self._last_packet_sent = defaultdict(lambda: None)
        self._end_buffering_sequence_no = dict()

    def clear(self, x, y, p, region_id):
        """ Clears the data from a given data region (only clears things\
            associated with a given data recording region).

        :param int x: placement x coordinate
        :param int y: placement y coordinate
        :param int p: placement p coordinate
        :param int region_id: the recording region ID to clear data from
        :rtype: None
        """
        if self._db.clear_region(x, y, p, region_id):
            del self._end_buffering_state[x, y, p, region_id]
            del self._is_flushed[x, y, p, region_id]

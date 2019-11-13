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

import logging
import os
from collections import defaultdict
from spinn_utilities.log import FormatAdapter
from .sqllite_database import SqlLiteDatabase

#: Name of the database in the data folder
DB_FILE_NAME = "buffer.sqlite3"
logger = FormatAdapter(logging.getLogger(__name__))


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
        :param report_folder: The directory to write the database used to
            store some of the data.
        :type report_folder: str
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
        """
        # pylint: disable=too-many-arguments
        self._db.store_data_in_region_buffer(x, y, p, region, data)

    def is_data_from_region_flushed(self, x, y, p, region):
        """ Check if the data region has been flushed.

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
        """ Store flushed data from a region of a core on a chip, and mark it\
            as being flushed.

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
        """
        # pylint: disable=too-many-arguments
        self.store_data_in_region_buffer(x, y, p, region, data)
        self._is_flushed[x, y, p, region] = True

    def store_last_received_packet_from_core(self, x, y, p, packet):
        """ Store the most recent packet received from SpiNNaker for a given\
            core.

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :param packet: SpinnakerRequestReadData packet received
        :type packet:\
            :py:class:`spinnman.messages.eieio.command_messages.SpinnakerRequestReadData`
        """
        self._last_packet_received[x, y, p] = packet

    def last_received_packet_from_core(self, x, y, p):
        """ Get the last packet received for a given core.

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :return: SpinnakerRequestReadData packet received
        :rtype:\
            :py:class:`spinnman.messages.eieio.command_messages.SpinnakerRequestReadData`
        """
        return self._last_packet_received[x, y, p]

    def store_last_sent_packet_to_core(self, x, y, p, packet):
        """ Store the last packet sent to the given core.

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :param packet: last HostDataRead packet sent
        :type packet:\
            :py:class:`spinnman.messages.eieio.command_messages.HostDataRead`
        """
        self._last_packet_sent[x, y, p] = packet

    def last_sent_packet_to_core(self, x, y, p):
        """ Retrieve the last packet sent to a core.

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :return: last HostDataRead packet sent
        :rtype:\
            :py:class:`spinnman.messages.eieio.command_messages.HostDataRead`
        """
        return self._last_packet_sent[x, y, p]

    def last_sequence_no_for_core(self, x, y, p):
        """ Get the last sequence number for a core.

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
        """ Set the last sequence number used.

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :param sequence_no: last sequence number used
        :type sequence_no: int
        :rtype: None
        """
        self._sequence_no[x, y, p] = sequence_no

    def get_region_data(self, x, y, p, region):
        """ Get the data stored for a given region of a given core.

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :param region: Region containing the data
        :type region: int
        :return: an array contained all the data received during the\
            simulation, and a flag indicating if any data was missing
        :rtype: tuple(memoryview, bool)
        """
        return self._db.get_region_data(x, y, p, region)

    def get_region_data_pointer(self, x, y, p, region):
        """ It is no longer possible to get access to the data pointer.

        Use get_region_data to get the data and missing flag directly.
        """
        raise NotImplementedError("Use get_region_data instead!.")

    def store_end_buffering_state(self, x, y, p, region, state):
        """ Store the end state of buffering.

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :param state: The end state
        """
        # pylint: disable=too-many-arguments
        self._end_buffering_state[x, y, p, region] = state

    def is_end_buffering_state_recovered(self, x, y, p, region):
        """ Determine if the end state has been stored.

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :return: True if the state has been stored
        """
        return (x, y, p, region) in self._end_buffering_state

    def get_end_buffering_state(self, x, y, p, region):
        """ Get the end state of the buffering.

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :return: The end state
        """
        return self._end_buffering_state[x, y, p, region]

    def store_end_buffering_sequence_number(self, x, y, p, sequence):
        """ Store the last sequence number sent by the core.

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :param sequence: The last sequence number
        :type sequence: int
        """
        self._end_buffering_sequence_no[x, y, p] = sequence

    def is_end_buffering_sequence_number_stored(self, x, y, p):
        """ Determine if the last sequence number has been retrieved.

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :return: True if the number has been retrieved
        :rtype: bool
        """
        return (x, y, p) in self._end_buffering_sequence_no

    def get_end_buffering_sequence_number(self, x, y, p):
        """ Get the last sequence number sent by the core.

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
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

    # ToDo Being changed in later PR so currently broken
    def clear(self, x, y, p, region_id):  # pylint: disable=unused-argument
        """ Clears the data from a given data region (only clears things\
            associated with a given data recording region).

        :param x: placement x coordinate
        :type x: int
        :param y: placement y coordinate
        :type y: int
        :param p: placement p coordinate
        :type p: int
        :param region_id: the recording region ID to clear data from
        :type region_id: int
        :rtype: None
        """
        logger.warning("unimplemented method")
        # del self._end_buffering_state[x, y, p, region_id]
        # with self._db:
        #     c = self._db.cursor()
        #     self.__delete_contents(c, x, y, p, region_id)
        # del self._is_flushed[x, y, p, region_id]

from collections import defaultdict
import os
import sqlite3
from spinn_storage_handlers import (
    BufferedBytearrayDataStorage, BufferedTempfileDataStorage)

DDL_FILE = os.path.join(os.path.dirname(__file__), "db.sql")


class BufferedReceivingData(object):
    """ Stores the information received through the buffering output\
        technique from the SpiNNaker system. The data kept includes the last\
        sent packet and last received packet, their correspondent sequence\
        numbers, the data retrieved, a flag to identify if the data from a\
        core has been flushed and the final state of the buffering output\
        state machine
    """

    __slots__ = [
        # the data to store, unless a DB is used
        "_data",

        # the database holding the data to store, if used
        "_db",

        # dict of booleans indicating if a region on a core has been flushed
        "_is_flushed",

        # dict of last sequence number received by core
        "_sequence_no",

        # dict of last packet received by core
        "_last_packet_received",

        # dict of last packet sent by core
        "_last_packet_sent",

        # dict of end buffer sequence number
        "_end_buffering_sequence_no",

        # dict of end state by core
        "_end_buffering_state"
    ]

    def __init__(self, store_to_file=False, database_file=None):
        """
        :param store_to_file: A boolean to identify if the data will be stored\
            in memory using a byte array or in a temporary file on the disk
            Ignored if database_file is not null.
        :type store_to_file: bool
        :param database_file: The name of a file that contains (or will\
            contain) an SQLite database holding the data.
        :type database_file: str
        """
        self._data = None
        self._db = None
        if database_file is not None:
            self._db = sqlite3.connect(database_file)
            self._db.text_factory = memoryview
            self.__init_db()
        elif store_to_file:
            self._data = defaultdict(BufferedTempfileDataStorage)
        else:
            self._data = defaultdict(BufferedBytearrayDataStorage)
        self._is_flushed = defaultdict(lambda: False)
        self._sequence_no = defaultdict(lambda: 0xFF)
        self._last_packet_received = defaultdict(lambda: None)
        self._last_packet_sent = defaultdict(lambda: None)
        self._end_buffering_sequence_no = dict()
        self._end_buffering_state = dict()

    def __del__(self):
        self.close()

    def close(self):
        if self._db is not None:
            self._db.close()
            self._db = None

    def __init_db(self):
        """ Set up the database if required. """
        self._db.row_factory = sqlite3.Row
        with open(DDL_FILE) as f:
            sql = f.read()
        self._db.executescript(sql)

    def __append_contents(self, cursor, x, y, p, region, contents):
        cursor.execute(
            "INSERT INTO storage(x, y, processor, region, content) "
            + "VALUES(?, ?, ?, ?, ?) "
            + "ON CONFLICT(x, y, processor, region) DO "
            + "UPDATE SET content = storage.content || excluded.content",
            (x, y, p, region, sqlite3.Binary(contents)))

    def __hacky_append(self, cursor, x, y, p, region, contents):
        """ Used to do an UPSERT when the version of SQLite used by Python\
            doesn't support the correct syntax for it (because it is older\
            than 3.24). Not really a problem with Python 3.6 or later.
        """
        cursor.execute(
            "INSERT OR IGNORE INTO storage(x, y, processor, region, content) "
            + "VALUES(?, ?, ?, ?, ?)",
            (x, y, p, region, sqlite3.Binary(b"")))
        cursor.execute(
            "UPDATE storage SET content = content || ? "
            + "WHERE x = ? AND y = ? AND processor = ? AND region = ?",
            (sqlite3.Binary(contents), x, y, p, region))

    def _read_contents(self, cursor, x, y, p, region):
        for row in cursor.execute(
                "SELECT content FROM storage "
                + "WHERE x = ? AND y = ? AND processor = ? AND region = ?",
                (x, y, p, region)):
            return row["content"]
        return b""

    def __delete_contents(self, cursor, x, y, p, region):
        cursor.execute(
            "DELETE FROM storage WHERE " +
            "x = ? AND y = ? AND processor = ? AND region = ?",
            (x, y, p, region))

    def store_data_in_region_buffer(self, x, y, p, region, data):
        """ Store some information in the correspondent buffer class for a\
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
        """
        # pylint: disable=too-many-arguments
        if self._db is not None:
            try:
                with self._db:
                    c = self._db.cursor()
                    self.__append_contents(c, x, y, p, region, data)
            except sqlite3.Error:
                with self._db:
                    c = self._db.cursor()
                    self.__hacky_append(c, x, y, p, region, data)
        else:
            self._data[x, y, p, region].write(data)

    def is_data_from_region_flushed(self, x, y, p, region):
        """ Check if the data region has been flushed

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
            as being flushed

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
            core

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :param packet: SpinnakerRequestReadData packet received
        :type packet:\
            :py:class:`spinnman.messages.eieio.command_messages.spinnaker_request_read_data.SpinnakerRequestReadData`
        """
        self._last_packet_received[x, y, p] = packet

    def last_received_packet_from_core(self, x, y, p):
        """ Get the last packet received for a given core

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :return: SpinnakerRequestReadData packet received
        :rtype:\
            :py:class:`spinnman.messages.eieio.command_messages.spinnaker_request_read_data.SpinnakerRequestReadData`
        """
        return self._last_packet_received[x, y, p]

    def store_last_sent_packet_to_core(self, x, y, p, packet):
        """ Store the last packet sent to the given core

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :param packet: last HostDataRead packet sent
        :type packet:\
            :py:class:`spinnman.messages.eieio.command_messages.host_data_read.HostDataRead`
        """
        self._last_packet_sent[x, y, p] = packet

    def last_sent_packet_to_core(self, x, y, p):
        """ Retrieve the last packet sent to a core

        :param x: x coordinate of the chip
        :type x: int
        :param y: y coordinate of the chip
        :type y: int
        :param p: Core within the specified chip
        :type p: int
        :return: last HostDataRead packet sent
        :rtype:\
            :py:class:`spinnman.messages.eieio.command_messages.host_data_read.HostDataRead`
        """
        return self._last_packet_sent[x, y, p]

    def last_sequence_no_for_core(self, x, y, p):
        """ Get the last sequence number for a core

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
        """ Set the last sequence number used

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
        """ Get the data stored for a given region of a given core

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
        :rtype: (bytearray, bool)
        """
        missing = None
        if (x, y, p, region) not in self._end_buffering_state:
            missing = (x, y, p, region)
        if self._db is not None:
            with self._db:
                c = self._db.cursor()
                data = self._read_contents(c, x, y, p, region)
        else:
            data = self._data[x, y, p, region].read_all()
        return data, missing

    def get_region_data_pointer(self, x, y, p, region):
        """
        It is no longer possible to get access to the data pointer.

        Use get_region_data to get the data and missing flag directly.
        """
        raise NotImplementedError("Use get_region_data instead!.")

    def store_end_buffering_state(self, x, y, p, region, state):
        """ Store the end state of buffering

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
        """ Determine if the end state has been stored

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
        """ Get the end state of the buffering

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
        """ Store the last sequence number sent by the core

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
        """ Determine if the last sequence number has been retrieved

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
        """ Get the last sequence number sent by the core

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
        """ Resets states so that it can behave in a resumed mode
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

        :param x: placement x coordinate
        :param y: placement y coordinate
        :param p: placement p coordinate
        :param region_id: the recording region ID to clear data from
        :rtype: None
        """
        del self._end_buffering_state[x, y, p, region_id]
        if self._db is not None:
            with self._db:
                c = self._db.cursor()
                self.__delete_contents(c, x, y, p, region_id)
        else:
            del self._data[x, y, p, region_id]
        del self._is_flushed[x, y, p, region_id]

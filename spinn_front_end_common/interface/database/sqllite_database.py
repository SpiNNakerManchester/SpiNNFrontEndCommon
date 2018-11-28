from collections import defaultdict
import os
import sqlite3

DDL_FILE = os.path.join(os.path.dirname(__file__), "db.sql")


class SqlLiteDatabase(DatabaseInterface):
    """ Specific implemematation of the Database for SqlLite
    """

    __slots__ = [
        # the database holding the data to store
        "_db",
    ]

    def __init__(self, database_file=None):
        """
        :param store_to_file: A boolean to identify if the data will be stored\
            in memory using a byte array or in a temporary file on the disk
            Ignored if database_file is not null.
        :type store_to_file: bool
        :param database_file: The name of a file that contains (or will\
            contain) an SQLite database holding the data.
        :type database_file: str
        """
        self._db = sqlite3.connect(database_file)
        self._db.text_factory = memoryview
        self.__init_db()

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
            data = row["content"]
            return memoryview(data)
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
        try:
            with self._db:
                c = self._db.cursor()
                self.__append_contents(c, x, y, p, region, data)
        except sqlite3.Error:
            with self._db:
                c = self._db.cursor()
                self.__hacky_append(c, x, y, p, region, data)

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
            :py:class:`spinnman.messages.eieio.command_messages.SpinnakerRequestReadData`
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
            :py:class:`spinnman.messages.eieio.command_messages.SpinnakerRequestReadData`
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
            :py:class:`spinnman.messages.eieio.command_messages.HostDataRead`
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
            :py:class:`spinnman.messages.eieio.command_messages.HostDataRead`
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
        with self._db:
            c = self._db.cursor()
            data = self._read_contents(c, x, y, p, region)
        return data, missing

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
        with self._db:
            c = self._db.cursor()
            self.__delete_contents(c, x, y, p, region_id)
        del self._is_flushed[x, y, p, region_id]

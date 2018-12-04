import os
import sqlite3
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import AbstractDatabase

DDL_FILE = os.path.join(os.path.dirname(__file__), "db.sql")


class SqlLiteDatabase(AbstractDatabase):
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

    def clear(self):
        print("TODO")

    def commit(self):
        """
        No need to commit
        :return:
        """

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
        if self._db is not None:
            with self._db:
                c = self._db.cursor()
                data = self._read_contents(c, x, y, p, region)
                # TODO missing data
        else:
            data = self._data[x, y, p, region].read_all()
        return data, missing

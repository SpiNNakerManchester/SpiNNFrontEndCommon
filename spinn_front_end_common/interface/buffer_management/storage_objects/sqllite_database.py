import os
import sqlite3
import time
import sys
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import AbstractDatabase
from spinn_utilities.overrides import overrides

if sys.version_info < (3,):
    memoryview = buffer  # noqa

DDL_FILE = os.path.join(os.path.dirname(__file__), "db.sql")
SECONDS_TO_MICRO_SECONDS_CONVERSION = 1000


class SqlLiteDatabase(AbstractDatabase):
    """ Specific implementation of the Database for SqlLite
    """

    __slots__ = [
        # the database holding the data to store
        "_db",
    ]

    def __init__(self, database_file=None):
        """
        :param database_file: The name of a file that contains (or will\
            contain) an SQLite database holding the data.
        :type database_file: str
        """
        self._db = sqlite3.connect(database_file)
        self._db.text_factory = memoryview
        self.__init_db()

    def __del__(self):
        self.close()

    @overrides(AbstractDatabase.close)
    def close(self):
        if self._db is not None:
            self._db.close()
            self._db = None

    @overrides(AbstractDatabase.clear)
    def clear(self):
        with self._db:
            cursor = self._db.cursor()
            cursor.execute(
                "UPDATE region "
                + "SET content = ?, fetches = 0, append_time = NULL",
                (sqlite3.Binary(b"")))

    def __init_db(self):
        """ Set up the database if required. """
        self._db.row_factory = sqlite3.Row
        with open(DDL_FILE) as f:
            sql = f.read()
        self._db.executescript(sql)

    @staticmethod
    def _read_contents(cursor, x, y, p, region):
        for row in cursor.execute(
                "SELECT content FROM region_view "
                + "WHERE x = ? AND y = ? AND processor = ? "
                + "AND local_region_index = ?",
                (x, y, p, region)):
            data = row["content"]
            return memoryview(data)
        return b""

    @staticmethod
    def _get_core_id(cursor, x, y, p):
        for row in cursor.execute(
                "SELECT core_id FROM region_view "
                + "WHERE x = ? AND y = ? AND processor = ? ",
                (x, y, p)):
            return row["core_id"]
        cursor.execute(
            "INSERT INTO core(x, y, processor) VALUES(?, ?, ?)",
            (x, y, p))
        return cursor.lastrowid

    def _get_region_id(self, cursor, x, y, p, region):
        for row in cursor.execute(
                "SELECT region_id FROM region_view "
                + "WHERE x = ? AND y = ? AND processor = ? "
                + "AND local_region_index = ?",
                (x, y, p, region)):
            return row["region_id"]
        core_id = self._get_core_id(cursor, x, y, p)
        cursor.execute(
            "INSERT INTO region(core_id, local_region_index, content, "
            + "fetches) "
            + "VALUES(?, ?, ?, 0)",
            (core_id, region, sqlite3.Binary(b"")))
        return cursor.lastrowid

    @overrides(AbstractDatabase.store_data_in_region_buffer)
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
        with self._db:
            cursor = self._db.cursor()
            region_id = self._get_region_id(cursor, x, y, p, region)
            cursor.execute(
                "UPDATE region SET content = content || ?, "
                + "fetches = fetches + 1, append_time = ?"
                + "WHERE region_id = ? ",
                (sqlite3.Binary(data),
                 int(time.time() * SECONDS_TO_MICRO_SECONDS_CONVERSION),
                 region_id))
            assert cursor.rowcount == 1

    @overrides(AbstractDatabase.get_region_data)
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

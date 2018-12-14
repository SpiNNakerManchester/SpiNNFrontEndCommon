import logging
import os
import sqlite3
from spinn_utilities.overrides import overrides
from .ds_abstact_database import DsAbstractDatabase


DDL_FILE = os.path.join(os.path.dirname(__file__), "dse.sql")
logger = logging.getLogger(__name__)


class DsSqlliteDatabase(DsAbstractDatabase):
    __slots__ = [
        # the database holding the data to store, if used
        "_db",
        # The machine cached for getting the "board"
        "_machine",
        # The root ethernet board id if required
        "_root_board_id"
    ]

    def __init__(self, machine, report_folder):
        self._machine = machine
        database_file = os.path.join(report_folder, "ds.sqlite3")

        self._db = sqlite3.connect(database_file)
        self._db.text_factory = memoryview
        self.__init_db()

    def __init_db(self):
        """ Set up the database if required. """
        self._db.row_factory = sqlite3.Row
        with open(DDL_FILE) as f:
            sql = f.read()
        self._db.executescript(sql)

        first_id = None
        first_x = None
        first_y = None
        self._root_board_id = None
        with self._db:
            cursor = self._db.cursor()
            for ethernet in self._machine.ethernet_connected_chips:
                cursor.execute(
                    "INSERT INTO board(ethernet_x, ethernet_y, address) "
                    + "VALUES(?, ?, ?) ",
                    (ethernet.x, ethernet.y, ethernet.ip_address))
                if (ethernet.x == 0 and ethernet.y == 0):
                    self._root_board_id = cursor.lastrowid
                elif first_id is None:
                    first_id = cursor.lastrowid
                    first_x = ethernet.x
                    first_y = ethernet.y
        if self._root_board_id is None:
            if first_id is None:
                raise Exception("No ethernet chip found")
            self._root_board_id = first_id
            logger.warning(
                "No Ethernet chip found at 0, 0 using {} : {} "
                "for all boards with no ip address.".format(first_x, first_y))

    def __del__(self):
        self.close()

    @overrides(DsAbstractDatabase.close)
    def close(self):
        if self._db is not None:
            self._db.close()
            self._db = None

    def _get_board(self, ethernet_x, ethernet_y):
        with self._db:
            cursor = self._db.cursor()
            for row in cursor.execute(
                "SELECT board_id FROM board "
                + "WHERE ethernet_x = ? AND ethernet_y = ?",
                    (ethernet_x, ethernet_y)):
                return row["board_id"]
        return self._root_board_id

    @overrides(DsAbstractDatabase.save_ds)
    def save_ds(self, core_x, core_y, core_p, ds):
        chip = self._machine.get_chip_at(core_x, core_y)
        board_id = self._get_board(
            chip.nearest_ethernet_x, chip.nearest_ethernet_y)
        with self._db:
            cursor = self._db.cursor()
            cursor.execute(
                "INSERT INTO core(x, y, processor, board_id, content) "
                + "VALUES(?, ?, ?, ?, ?) ",
                (core_x, core_y, core_p, board_id, sqlite3.Binary(ds)))

    @overrides(DsAbstractDatabase.get_ds)
    def get_ds(self, x, y, p):
        with self._db:
            cursor = self._db.cursor()
            for row in cursor.execute(
                    "SELECT content FROM core "
                    + "WHERE x = ? AND y = ? AND processor = ? ", (x, y, p)):
                return row["content"]
        return b""

    @overrides(DsAbstractDatabase.ds_iteritems)
    def ds_iteritems(self):
        with self._db:
            cursor = self._db.cursor()
            for row in cursor.execute(
                    "SELECT x, y, processor, content FROM core "
                    + "WHERE content IS NOT NULL"):
                print(row["x"], row["y"], row["processor"])
                yield (row["x"], row["y"], row["processor"]), row["content"]

    @overrides(DsAbstractDatabase.ds_n_cores)
    def ds_n_cores(self):
        with self._db:
            cursor = self._db.cursor()
            for row in cursor.execute(
                    "SELECT COUNT(*) as count FROM core "
                    + "WHERE content IS NOT NULL"):
                return row["count"]
        raise Exception("Count query failed")

    def _row_to_info(self, row):
        return {key: row[key]
                for key in ["start_address", "memory_used", "memory_written"]}

    @overrides(DsAbstractDatabase.get_write_info)
    def get_write_info(self, x, y, p):
        with self._db:
            cursor = self._db.cursor()
            for row in cursor.execute(
                    "SELECT start_address, memory_used, memory_written "
                    + "FROM core "
                    + "WHERE x = ? AND y = ? AND processor = ?", (x, y, p)):
                return self._row_to_info(row)
        raise ValueError("No info for {}:{}:{}".format(x, y, p))

    @overrides(DsAbstractDatabase.set_write_info)
    def set_write_info(self, x, y, p, info):
        """
        Gets the provenance returned by the Data Spec executor

        :param x: core x
        :param y: core y
        :param p: core p
        :param info: dict() with the keys
            'start_address', 'memory_used' and 'memory_written'
        """
        with self._db:
            cursor = self._db.cursor()
            cursor.execute(
                "UPDATE core SET "
                + "start_address = ?, memory_used = ?, memory_written = ? "
                + "WHERE x = ? AND y = ? AND processor = ? ",
                (info["start_address"], info["memory_used"],
                 info["memory_written"], x, y, p))
            if cursor.rowcount == 0:
                chip = self._machine.get_chip_at(x, y)
                board_id = self._get_board(
                    chip.nearest_ethernet_x, chip.nearest_ethernet_y)
                cursor.execute(
                    "INSERT INTO core(x, y, processor, board_id, "
                    + "start_address, memory_used, memory_written) "
                    + "VALUES(?, ?, ?, ?, ?, ?, ?) ",
                    (x, y, p, board_id, info["start_address"],
                     info["memory_used"], info["memory_written"]))

    @overrides(DsAbstractDatabase.info_n_cores)
    def info_n_cores(self):
        with self._db:
            cursor = self._db.cursor()
            for row in cursor.execute(
                    "SELECT count(*) as count FROM core "
                    + "WHERE start_address IS NOT NULL"):
                return row["count"]
        raise Exception("Count query failed")

    @overrides(DsAbstractDatabase.info_iteritems)
    def info_iteritems(self):
        with self._db:
            cursor = self._db.cursor()
            for row in cursor.execute(
                    "SELECT x, y, processor, "
                    + "start_address, memory_used, memory_written "
                    + "FROM core "
                    + "WHERE start_address IS NOT NULL"):
                yield (row["x"], row["y"], row["processor"]), \
                      self._row_to_info(row)

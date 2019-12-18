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
import sqlite3
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.utilities.utility_objs import DataWritten

DB_NAME = "ds.sqlite3"
DDL_FILE = os.path.join(os.path.dirname(__file__), "dse.sql")
logger = FormatAdapter(logging.getLogger(__name__))


class DsSqlliteDatabase(object):
    __slots__ = [
        # the database holding the data to store, if used
        "_db",
        # The machine cached for getting the "ethernet"s
        "_machine",
        # The root ethernet id if required
        "_root_ethernet_id"
    ]

    def __init__(self, machine, report_folder, init=None):
        """
        :param ~spinn_machine.Machine machine:
        :param str report_folder:
        :param init:
        :type init: bool or None
        """
        self._machine = machine
        database_file = os.path.join(report_folder, DB_NAME)

        if init is None:
            init = not os.path.exists(database_file)

        self._db = sqlite3.connect(database_file)
        self._db.text_factory = memoryview
        self._db.row_factory = sqlite3.Row
        if init:
            self.__init_db()

    def __init_db(self):
        """ Set up the database if required. """
        with open(DDL_FILE) as f:
            sql = f.read()
        self._db.executescript(sql)

        first_id = None
        first_x = None
        first_y = None
        self._root_ethernet_id = None
        with self._db:
            cursor = self._db.cursor()
            for ethernet in self._machine.ethernet_connected_chips:
                cursor.execute(
                    "INSERT INTO ethernet(ethernet_x, ethernet_y, ip_address) "
                    + "VALUES(?, ?, ?) ",
                    (ethernet.x, ethernet.y, ethernet.ip_address))
                if ethernet.x == 0 and ethernet.y == 0:
                    self._root_ethernet_id = cursor.lastrowid
                elif first_id is None:
                    first_id = cursor.lastrowid
                    first_x = ethernet.x
                    first_y = ethernet.y
        if self._root_ethernet_id is None:
            if first_id is None:
                raise Exception("No ethernet chip found")
            self._root_ethernet_id = first_id
            logger.warning(
                "No Ethernet chip found at 0, 0 using {} : {} "
                "for all boards with no IP address.", first_x, first_y)

    def __del__(self):
        self.close()

    def close(self):
        """ Signals that the database can be closed and will not be reused.

        .. note::
            Once this is called any other method in this API is allowed to
            raise any kind of exception.
        """
        if self._db is not None:
            self._db.close()
            self._db = None

    def __get_ethernet(self, ethernet_x, ethernet_y):
        """
        :param int ethernet_x:
        :param int ethernet_y:
        :rtype: int
        """
        with self._db:
            for row in self._db.execute(
                    "SELECT ethernet_id FROM ethernet "
                    + "WHERE ethernet_x = ? AND ethernet_y = ?",
                    (ethernet_x, ethernet_y)):
                return row["ethernet_id"]
        return self._root_ethernet_id

    def clear_ds(self):
        """ Clear all saved data specification data
        """
        with self._db:
            self._db.execute(
                "DELETE FROM core")

    def save_ds(self, core_x, core_y, core_p, ds):
        """
        :param int core_x: x of the core ds applies to
        :param int core_y: y of the core ds applies to
        :param int p: p of the core ds applies to
        :param bytearray ds: the data spec as byte code
        """
        chip = self._machine.get_chip_at(core_x, core_y)
        ethernet_id = self.__get_ethernet(
            chip.nearest_ethernet_x, chip.nearest_ethernet_y)
        with self._db:
            self._db.execute(
                "INSERT INTO core(x, y, processor, ethernet_id, content) "
                + "VALUES(?, ?, ?, ?, ?) ",
                (core_x, core_y, core_p, ethernet_id, sqlite3.Binary(ds)))

    def get_ds(self, x, y, p):
        """ Retrieves the data spec as byte code for this core.

        :param int x: core x
        :param int y: core y
        :param int p: core p
        :return: data spec as byte code
        :rtype: bytearray
        """
        with self._db:
            for row in self._db.execute(
                    "SELECT content FROM core "
                    + "WHERE x = ? AND y = ? AND processor = ? ", (x, y, p)):
                return row["content"]
        return b""

    def ds_iteritems(self):
        """ Yields the keys and values for the DS data

        :return: Yields the (x, y, p) and saved ds pairs
        :rtype: iterable(tuple(tuple(int, int, int), bytearray))
        """
        with self._db:
            for row in self._db.execute(
                    "SELECT x, y, processor, content FROM core "
                    + "WHERE content IS NOT NULL"):
                yield (row["x"], row["y"], row["processor"]), row["content"]

    def ds_n_cores(self):
        """ Returns the number for cores there is a ds saved for

        :rtype: int
        """
        with self._db:
            for row in self._db.execute(
                    "SELECT COUNT(*) as count FROM core "
                    + "WHERE content IS NOT NULL"):
                return row["count"]
        raise Exception("Count query failed")

    def ds_set_app_id(self, app_id):
        """ Sets the same app_id for all rows that have ds content

        :param int app_id: value to set
        """
        with self._db:
            self._db.execute(
                "UPDATE core SET app_id = ? WHERE content IS NOT NULL",
                (app_id,))

    def ds_get_app_id(self, x, y, p):
        """ Gets the app_id set for this core

        :param int x: core x
        :param int y: core y
        :param int p: core
        :rtype: int
        """
        with self._db:
            for row in self._db.execute(
                    "SELECT app_id FROM core "
                    "WHERE x = ? AND y = ? AND processor = ? ", (x, y, p)):
                return row["app_id"]
        return None

    def ds_mark_as_system(self, core_list):
        """
        Flags a list of processors as running system binaries.

        :param core_list: list of (core x, core y, core p)
        :type core_list: iterable(tuple(int,int,int))
        """
        with self._db:
            for xyp in core_list:
                self._db.execute(
                    "UPDATE core SET is_system = 1 "
                    "WHERE x = ? AND y = ? AND processor = ?", xyp)

    def _row_to_info(self, row):
        """
        :param ~sqlite3.Row row:
        :rtype: DataWritten
        """
        return DataWritten(start_address=row["start_address"],
                           memory_used=row["memory_used"],
                           memory_written=row["memory_written"])

    def get_write_info(self, x, y, p):
        """ Gets the provenance returned by the Data Spec executor

        :param int x: core x
        :param int y: core y
        :param int p: core p
        :rtype: DataWritten
        """
        with self._db:
            for row in self._db.execute(
                    "SELECT start_address, memory_used, memory_written "
                    + "FROM core "
                    + "WHERE x = ? AND y = ? AND processor = ?", (x, y, p)):
                return self._row_to_info(row)
        raise ValueError("No info for {}:{}:{}".format(x, y, p))

    def set_write_info(self, x, y, p, info):
        """ Sets the provenance returned by the Data Spec executor.

        :param int x: core x
        :param int y: core y
        :param int p: core p
        :param DataWritten info:
        """
        if isinstance(info, DataWritten):
            start = info.start_address
            used = info.memory_used
            written = info.memory_written
        else:
            start = info["start_address"]
            used = info["memory_used"]
            written = info["memory_written"]
        with self._db:
            cursor = self._db.cursor()
            cursor.execute(
                "UPDATE core SET "
                + "start_address = ?, memory_used = ?, memory_written = ? "
                + "WHERE x = ? AND y = ? AND processor = ? ",
                (start, used, written, x, y, p))
            if cursor.rowcount == 0:
                chip = self._machine.get_chip_at(x, y)
                ethernet_id = self.__get_ethernet(
                    chip.nearest_ethernet_x, chip.nearest_ethernet_y)
                cursor.execute(
                    "INSERT INTO core(x, y, processor, ethernet_id, "
                    + "start_address, memory_used, memory_written) "
                    + "VALUES(?, ?, ?, ?, ?, ?, ?) ",
                    (x, y, p, ethernet_id, start, used, written))

    def clear_write_info(self):
        """ Clears the provenance for all rows
        """
        with self._db:
            self._db.execute(
                "UPDATE core SET "
                + "start_address = NULL, memory_used = NULL, "
                + "memory_written = NULL")

    def info_n_cores(self):
        """ Returns the number for cores there is a info saved for.

        :rtype: int
        """
        with self._db:
            for row in self._db.execute(
                    "SELECT count(*) as count FROM core "
                    + "WHERE start_address IS NOT NULL"):
                return row["count"]
        raise Exception("Count query failed")

    def info_iteritems(self):
        """
        Yields the keys and values for the Info data. Note that a DB \
        transaction may be held while this iterator is processing.

        :return: Yields the (x, y, p) and DataWritten
        :rtype: iterable(tuple(tuple(int, int, int),\
            ~spinn_front_end_common.utilities.utility_objs.DataWritten))
        """
        with self._db:
            for row in self._db.execute(
                    "SELECT x, y, processor, "
                    + "start_address, memory_used, memory_written "
                    + "FROM core "
                    + "WHERE start_address IS NOT NULL"):
                yield (row["x"], row["y"], row["processor"]), \
                      self._row_to_info(row)

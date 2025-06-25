# Copyright (c) 2017 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
from typing import Dict, Optional, Tuple
from spinn_utilities.config_holder import (
    get_config_int_or_none, get_config_bool)
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.base_database import (
    BaseDatabase, _SqliteTypes)

logger = FormatAdapter(logging.getLogger(__name__))


class ProvenanceWriter(BaseDatabase):
    """
    Specific implementation of the Database for SQLite 3.

    .. note::
        *Not thread safe on the same database file.*
        Threads can access different DBs just fine.

    .. note::
        This totally relies on the way SQLite's type affinities function.
        You can't port to a different database engine without a lot of work.
    """

    __slots__ = ()

    def __init__(self, database_file: Optional[str] = None):
        """
        :param database_file:
            The name of a file that contains (or will contain) an SQLite
            database holding the data.
            If omitted, either the default file path or an unshared in-memory
            database will be used (suitable only for testing).
        """
        super().__init__(database_file)

    def insert_power(self, description: str, the_value: _SqliteTypes) -> None:
        """
        Inserts a general power value into the `power_provenance` table.

        :param description: Type of value
        :param the_value: data
        """
        if not get_config_bool("Reports", "write_provenance"):
            return
        run = FecDataView.get_run_number()
        self.cursor().execute(
            """
            INSERT INTO power_provenance(
                run, description, the_value)
            VALUES(?, ?, ?)
            """, [run, description, the_value])

    def insert_gatherer(
            self, x: int, y: int, address: int, bytes_read: int, run: int,
            description: str, the_value: _SqliteTypes) -> None:
        """
        Records provenance into the `gatherer_provenance` table.

        :param x: X coordinate of the chip
        :param y: Y coordinate of the chip
        :param address: SDRAM address read from
        :param bytes_read: number of bytes read
        :param run: run number
        :param description: type of value
        :param the_value: data
        """
        if not get_config_bool("Reports", "write_provenance"):
            return
        self.cursor().execute(
            """
            INSERT INTO gatherer_provenance(
                x, y, address, bytes, run, description, the_value)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """, [x, y, address, bytes_read, run, description, the_value])

    def insert_monitor(self, x: int, y: int, description: str,
                       the_value: _SqliteTypes) -> None:
        """
        Inserts data into the `monitor_provenance` table.

        Will only save data is write_provance is on.

        :param x: X coordinate of the chip
        :param y: Y coordinate of the chip
        :param description: type of value
        :param the_value: data
        """
        if get_config_bool("Reports", "write_provenance"):
            self.insert_monitor_value(x, y, description, the_value)

    def insert_monitor_value(self, x: int, y: int, description: str,
                             the_value: _SqliteTypes) -> None:
        """
        Inserts data into the `monitor_provenance` table.

        Always saves the data even if write_provence is off.

        :param x: X coordinate of the chip
        :param y: Y coordinate of the chip
        :param description: type of value
        :param the_value: data
        """
        self.cursor().execute(
            """
            INSERT INTO monitor_provenance(
                x, y, description, the_value)
            VALUES(?, ?, ?, ?)
            """, [x, y, description, the_value])

    def insert_router(
            self, x: int, y: int, description: str,
            the_value: int,
            expected: bool = True) -> None:
        """
        Inserts data into the `router_provenance` table.

        :param x: X coordinate of the chip
        :param y: Y coordinate of the chip
        :param  description: type of value
        :param the_value: data
        :param expected: Flag to say this data was expected
        """
        if not get_config_bool("Reports", "write_provenance"):
            return
        self.cursor().execute(
            """
            INSERT INTO router_provenance(
                x, y, description, the_value, expected)
            VALUES(?, ?, ?, ?, ?)
            """, [x, y, description, the_value, expected])

    def insert_core(
            self, x: int, y: int, p: int, description: str,
            the_value: _SqliteTypes) -> None:
        """
        Inserts data for a specific core into the `core_provenance` table.

        :param x: X coordinate of the chip
        :param y: Y coordinate of the chip
        :param p: ID of the core
        :param description: type of value
        :param the_value: data
        """
        if not get_config_bool("Reports", "write_provenance"):
            return
        core_id = self._get_core_id(x, y, p)
        self.cursor().execute(
            """
            INSERT INTO core_provenance(
                core_id, description, the_value)
            VALUES(?, ?, ?)
            """, [core_id, description, the_value])

    def insert_report(self, message: str) -> None:
        """
        Save and if applicable logs a message to the `reports` table.

        Only logs the messages up to the cut-off set by
        configuration `provenance_report_cutoff`

        :param message:
        """
        if not get_config_bool("Reports", "write_provenance"):
            logger.warning(message)
            return
        self.cursor().execute(
            """
            INSERT INTO reports(message)
            VALUES(?)
            """, [message])
        recorded = self.lastrowid
        assert recorded is not None

        cutoff = get_config_int_or_none("Reports", "provenance_report_cutoff")
        if cutoff is None or recorded < cutoff:
            logger.warning(message)
        elif recorded == cutoff:
            logger.warning(f"Additional interesting provenance items in "
                           f"{self._database_file}")

    def insert_connector(
            self, pre_population: str, post_population: str, the_type: str,
            description: str, the_value: _SqliteTypes) -> None:
        """
        Inserts edge data into the `connector_provenance`

        :param pre_population: Name of the pre-population / vertex
        :param post_population: Name of the post-population / vertex
        :param the_type: Class of the connector
        :param description: type of value
        :param the_value: data
        """
        if not get_config_bool("Reports", "write_provenance"):
            return
        self.cursor().execute(
            """
            INSERT OR IGNORE INTO connector_provenance(
                pre_population, post_population, the_type, description,
                the_value)
            VALUES(?, ?, ?, ?, ?)
            """,
            [pre_population, post_population, the_type, description,
             the_value])

    def insert_board_provenance(self, connections: Optional[
            Dict[Tuple[int, int], str]]) -> None:
        """
        Write the connection details retrieved from spalloc_client job to the
        `boards_provenance` table.

        :param connections: {(x, y): hostname, ...} or None
        """
        if not get_config_bool("Reports", "write_provenance"):
            return
        if not connections:
            return
        self.cursor().executemany(
            """
            INSERT OR IGNORE INTO boards_provenance(
            ethernet_x, ethernet_y, ip_addres)
            VALUES (?, ?, ?)
            """, ((x, y, ipaddress)
                  for ((x, y), ipaddress) in connections.items()))

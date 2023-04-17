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

import io
import logging
import os
import sqlite3
from spinn_utilities.log import FormatAdapter
from spinnman.spalloc.spalloc_job import SpallocJob
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.exceptions import DsDatabaseException
from spinn_front_end_common.utilities.sqlite_db import SQLiteDB
from .data_row_writer import DataRowWriter

_DDL_FILE = os.path.join(os.path.dirname(__file__), "dse.sql")
logger = FormatAdapter(logging.getLogger(__name__))


class DsSqlliteDatabase(SQLiteDB):
    """
    A database for holding data specification details.
    """
    __slots__ = [
        # The root ethernet id if required
        "__root_ethernet_id"
    ]

    def __init__(self, init_file=None):
        """
        :param bool init_file:
            Whether to initialise the DB from our DDL file. If not specified,
            this is guessed from whether we can read the file.
        """
        database_file = self.default_database_file()

        if init_file is None:
            init_file = not os.path.exists(database_file)

        super().__init__(
            database_file, ddl_file=_DDL_FILE if init_file else None)
        if init_file:
            self.__init_db_contents()
        self.__root_ethernet_id = self.__find_root_id()

    @classmethod
    def default_database_file(cls):
        return os.path.join(FecDataView.get_run_dir_path(),
                            f"ds{FecDataView.get_reset_str()}.sqlite3")

    def __init_db_contents(self):
        """
        Set up the database contents from the machine.
        """
        eth_chips = FecDataView.get_machine().ethernet_connected_chips
        with self.transaction() as cursor:
            cursor.executemany(
                """
                INSERT INTO ethernet(
                    ethernet_x, ethernet_y, ip_address)
                VALUES(?, ?, ?)
                """, (
                    (ethernet.x, ethernet.y, ethernet.ip_address)
                    for ethernet in eth_chips))

    def __find_root_id(self):
        first_x = first_y = root_id = None
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT ethernet_id, ethernet_x, ethernet_y FROM ethernet
                    ORDER BY ethernet_x, ethernet_y
                    LIMIT 1
                    """):
                root_id = row["ethernet_id"]
                first_x = row["ethernet_x"]
                first_y = row["ethernet_y"]
        if root_id is None:
            # Should only be reachable for an empty machine
            raise DsDatabaseException("No ethernet chip found")
        if first_x or first_y:
            logger.warning(
                "No Ethernet chip found at 0,0 using {},{} "
                "for all boards with no IP address.", first_x, first_y)
        return root_id

    def write_data_spec(self, core_x, core_y, core_p, spec_bytes):
        """
        :param int core_x:
            X coordinate of the core that `spec_bytes` applies to
        :param int core_y:
            Y coordinate of the core that `spec_bytes` applies to
        :param int p: Processor ID of the core that `spec_bytes` applies to
        :param bytes spec_bytes: the data specification byte-code
        """
        chip = FecDataView().get_chip_at(core_x, core_y)
        with self.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO core(
                    x, y, processor, content, ethernet_id, app_id)
                VALUES(?, ?, ?, ?, (
                    SELECT COALESCE((
                        SELECT ethernet_id FROM ethernet
                        WHERE ethernet_x = ? AND ethernet_y = ?
                    ), ?)), ?)
                """, (
                    core_x, core_y, core_p, sqlite3.Binary(spec_bytes),
                    chip.nearest_ethernet_x, chip.nearest_ethernet_y,
                    self.__root_ethernet_id, FecDataView().get_app_id()))

    def get_ds(self, x, y, p):
        """
        Retrieves the data specification as byte-code for this core.

        :param int x: core X coordinate
        :param int y: core Y coordinate
        :param int p: core processor ID
        :return: data specification as byte code
        :rtype: bytes
        """
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT content FROM core
                    WHERE x = ? AND y = ? AND processor = ?
                    LIMIT 1
                    """, (x, y, p)):
                return row["content"]
        return b""

    def keys(self):
        """
        Yields the keys.

        .. note::
            Do not use the database for anything else while iterating.

        :return: Yields the (x, y, p)
        :rtype: iterable(tuple(int,int,int))
        """
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT x, y, processor FROM core
                    WHERE content IS NOT NULL
                    """):
                yield (row["x"], row["y"], row["processor"])

    def items(self):
        """
        Yields the keys and values for the data specification data.

        .. note::
            Do not use the database for anything else while iterating.

        :return:
            Yields the (x, y, p) and saved data specification byte-code pairs
        :rtype: iterable(tuple(tuple(int,int,int),~io.RawIOBase))
        """
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT x, y, processor, content FROM core
                    WHERE content IS NOT NULL
                    """):
                yield ((row["x"], row["y"], row["processor"]),
                       io.BytesIO(row["content"]))

    def system_items(self):
        """
        Yields the keys and values for the data specification data for system
        cores.

        .. note::
            Do not use the database for anything else while iterating.

        :return: Yields the (x, y, p), saved data specification byte-code, and
            region_size triples
        :rtype: iterable(tuple(tuple(int,int,int),~io.RawIOBase, int))
        """
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT x, y, processor, content, memory_used FROM core
                    WHERE content IS NOT NULL AND is_system = 1
                    """):
                yield ((row["x"], row["y"], row["processor"]),
                       io.BytesIO(row["content"]), row["memory_used"])

    def app_items(self):
        """
        Yields the keys and values for the data specification data for
        application cores.

        .. note::
            Do not use the database for anything else while iterating.

        :return:
            Yields the (x, y, p) and saved data specification byte-code pairs
        :rtype: iterable(tuple(tuple(int,int,int),~io.RawIOBase, int))
        """
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT x, y, processor, content, memory_used  FROM core
                    WHERE content IS NOT NULL AND is_system = 0
                    """):
                yield ((row["x"], row["y"], row["processor"]),
                       io.BytesIO(row["content"]), row["memory_used"])

    def ds_n_cores(self):
        """
        Returns the number for cores there is a data specification saved for.

        :rtype: int
        :raises DsDatabaseException:
        """
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT COUNT(*) as count FROM core
                    WHERE content IS NOT NULL
                    LIMIT 1
                    """):
                return row["count"]
        raise DsDatabaseException("Count query failed")

    def ds_n_app_cores(self):
        """
        Returns the number for application cores there is a data specification
        saved for.

        :rtype: int
        :raises DsDatabaseException:
        """
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT COUNT(*) as count FROM core
                    WHERE content IS NOT NULL AND is_system = 0
                    LIMIT 1
                    """):
                return row["count"]
        raise DsDatabaseException("Count query failed")

    def ds_n_system_cores(self):
        """
        Returns the number for system cores there is a data specification
        saved for.

        :rtype: int
        :raises DsDatabaseException:
        """
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT COUNT(*) as count FROM core
                    WHERE content IS NOT NULL  AND is_system = 1
                    LIMIT 1
                    """):
                return row["count"]
        raise DsDatabaseException("Count query failed")

    def set_app_id(self, app_id):
        """
        Sets the same app_id for all rows that have data specification content.

        :param int app_id: value to set
        """
        with self.transaction() as cursor:
            cursor.execute(
                """
                UPDATE core SET
                    app_id = ?
                WHERE content IS NOT NULL
                """, (app_id,))

    def get_app_id(self, x, y, p):
        """
        Gets the `app_id` set for this core.

        :param int x: core X coordinate
        :param int y: core Y coordinate
        :param int p: core processor ID
        :rtype: int
        """
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT app_id FROM core
                    WHERE x = ? AND y = ? AND processor = ?
                    LIMIT 1
                    """, (x, y, p)):
                return row["app_id"]
        return None

    def mark_system_cores(self, core_subsets):
        """
        Flags a set of processors as running system binaries.

        :param ~spinn_machine.CoreSubsets core_subsets:
            Which cores to mark.
        """
        with self.transaction() as cursor:
            cursor.executemany(
                """
                UPDATE core SET
                    is_system = 1
                WHERE x = ? AND y = ? AND processor = ?
                """, (
                    (subset.x, subset.y, p)
                    for subset in core_subsets
                    for p in subset.processor_ids))

    def get_write_info(self, x, y, p):
        """
        Gets the provenance returned by the data specification executor.

        :param int x: core X coordinate
        :param int y: core Y coordinate
        :param int p: core processor ID
        :return: start_address, memory_used, memory_written
        :rtype: DataWritten
        """
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT start_address, memory_used, memory_written
                    FROM core
                    WHERE x = ? AND y = ? AND processor = ?
                    LIMIT 1
                    """, (x, y, p)):
                return (row["start_address"], row["memory_used"],
                        row["memory_written"])
        raise ValueError(f"No info for {x}:{y}:{p}")

    def set_write_info(
            self, x, y, p, start, used, written):
        """
        Sets the provenance returned by the data specification executor.

        :param int x: core X coordinate
        :param int y: core Y coordinate
        :param int p: core processor ID
        :param int start: base address
        :param int used: size allocated
        :param int written: bytes written
        """
        with self.transaction() as cursor:
            cursor.execute(
                """
                UPDATE core SET
                    start_address = ?,
                    memory_used = ?,
                    memory_written = ?
                WHERE x = ? AND y = ? AND processor = ?
                """, (start, used, written, x, y, p))
            if cursor.rowcount == 0:
                chip = FecDataView().get_chip_at(x, y)
                cursor.execute(
                    """
                    INSERT INTO core(
                        x, y, processor, start_address,
                        memory_used, memory_written, ethernet_id)
                    VALUES(?, ?, ?, ?, ?, ?, (
                        SELECT COALESCE((
                            SELECT ethernet_id FROM ethernet
                            WHERE ethernet_x = ? AND ethernet_y = ?
                        ), ?)))
                    """, (
                        x, y, p, start, used, written, chip.nearest_ethernet_x,
                        chip.nearest_ethernet_y, self.__root_ethernet_id))

    def set_size_info(self, x, y, p, memory_used):
        with self.transaction() as cursor:
            cursor.execute(
                """
                UPDATE core SET
                    memory_used = ?
                WHERE x = ? AND y = ? AND processor = ?
                """, (memory_used, x, y, p))
            if cursor.rowcount == 0:
                chip = FecDataView().get_chip_at(x, y)
                cursor.execute(
                    """
                    INSERT INTO core(
                        x, y, processor, memory_used, ethernet_id)
                    VALUES(?, ?, ?, ?, (
                        SELECT COALESCE((
                            SELECT ethernet_id FROM ethernet
                            WHERE ethernet_x = ? AND ethernet_y = ?
                        ), ?)))
                    """, (
                        x, y, p, int(memory_used),
                        chip.nearest_ethernet_x, chip.nearest_ethernet_y,
                        self.__root_ethernet_id))

    def clear_write_info(self):
        """
        Clears the provenance for all rows.
        """
        with self.transaction() as cursor:
            cursor.execute(
                """
                UPDATE core SET
                    start_address = NULL,
                    memory_used = NULL,
                    memory_written = NULL
                """)

    def info_n_cores(self):
        """
        Returns the number for cores there is a info saved for.

        :rtype: int
        :raises DsDatabaseException:
        """
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT count(*) as count FROM core
                    WHERE start_address IS NOT NULL
                    LIMIT 1
                    """):
                return row["count"]
        raise DsDatabaseException("Count query failed")

    def info_iteritems(self):
        """
        Yields the keys and values for the Info data.

        .. note::
            A DB transaction may be held while this iterator is processing.
            Reentrant use of this class is not supported.

        :return: Yields the (x, y, p), start_address, memory_used
            and memory_written
        :rtype: iterable(tuple(tuple(int, int, int), int, int, int))
        """
        with self.transaction() as cursor:
            for row in cursor.execute(
                    """
                    SELECT
                        x, y, processor,
                        start_address, memory_used, memory_written
                    FROM core
                    WHERE start_address IS NOT NULL
                    """):
                yield ((row["x"], row["y"], row["processor"]),
                       row["start_address"], row["memory_used"],
                       row["memory_written"])

    def create_data_spec(self, x, y, p):
        """
        Get a stream that will write the data specification for a particular
        core to this database.

        :param int x: X coordinate of the core
        :param int y: Y coordinate of the core
        :param int p: Processor ID of the core
        :return: the stream; the write only happens when the stream is closed
        :rtype: DataRowWriter
        """
        return DataRowWriter(x, y, p, self)

    def write_session_credentials_to_db(self):
        """
        Write Spalloc session credentials to the database, if in use.
        """
        # pylint: disable=protected-access
        if not FecDataView.has_allocation_controller():
            return
        mac = FecDataView.get_allocation_controller()
        if mac.proxying:
            # This is now assumed to be a SpallocJobController;
            # can't check that because of import circularity.
            job = mac._job
            if isinstance(job, SpallocJob):
                with self.transaction() as cur:
                    job._write_session_credentials_to_db(cur)

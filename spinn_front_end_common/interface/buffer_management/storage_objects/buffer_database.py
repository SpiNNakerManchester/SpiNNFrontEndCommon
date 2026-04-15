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

from sqlite3 import Binary, IntegrityError
import time
from typing import Optional, Tuple
from spinn_utilities.config_holder import get_config_bool
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.base_database import BaseDatabase

_SECONDS_TO_MICRO_SECONDS_CONVERSION = 1000
PROVENANCE_CORE_KEY = "Power_Monitor_Core"


def _timestamp() -> int:
    return int(time.time() * _SECONDS_TO_MICRO_SECONDS_CONVERSION)


class BufferDatabase(BaseDatabase):
    """
    Specific implementation of the Database for SQLite 3.

    There should only ever be a single Database Object in use at any time.
    In the case of application_graph_changed the first should closed and
    a new one created.

    If 2 database objects where opened with the database_file they hold the
    same data. Unless someone else deletes that file.

    .. note::
        *Not thread safe on the same database file!*
        Threads can access different DBs just fine.
    """

    __slots__ = ()

    def clear_recording_region(
            self, x: int, y: int, p: int, region: int) -> bool:
        """
        Clears the data for a single region.

        .. note::
            This method *loses information!*

        :param x: x coordinate of the chip
        :param y: y coordinate of the chip
        :param p: Core within the specified chip
        :param region: Region containing the data to be cleared
        :return: True if any region was changed
        """
        for row in self.cursor().execute(
                """
                SELECT recording_region_id FROM recording_region_view
                WHERE x = ? AND y = ? AND processor = ?
                    AND local_region_index = ?
                LIMIT 1
                """, (x, y, p, region)):
            region_id = int(row["recording_region_id"])
            break
        else:
            return False

        return self._clear_recording_region(region_id)

    def _clear_recording_region(self, region_id: int) -> bool:
        """
        Clears out a region leaving empty data and a missing of 2

        :param region_id: region to clear
        :return:
        """
        self.cursor().execute(
            """
            UPDATE recording_data SET
            content = CAST('' AS BLOB), content_len = 0, missing_data = 2
            WHERE recording_region_id = ?
            """, (region_id,))
        return True

    def _read_recording(self, region_id: int) -> memoryview:
        """
        Read a recording region

        :param region_id:
        """
        content, _ = self._read_recording_with_missing(region_id)
        return content

    def _read_recording_with_missing(self, region_id: int) -> Tuple[
            memoryview, bool]:
        """
        Get the contents from a recording region

        :param region_id:
        """
        for row in self.cursor().execute(
                """
                SELECT count(*) as n_extractions,
                SUM(content_len) as total_content_length
                FROM recording_data
                WHERE recording_region_id = ?
                LIMIT 1
                """, (region_id, )):
            n_extractions = row["n_extractions"]
            total_content_length = row["total_content_length"]
        if n_extractions <= 1:
            return self._read_contents_single(region_id)
        else:
            return self._read_recording_multiple(
                region_id, total_content_length)

    def _read_contents_single(self, region_id: int) -> Tuple[
            memoryview, bool]:
        """
        Reads the content for a single block for this recording region

        :param region_id:
        """
        for row in self.cursor().execute(
                """
                SELECT content, missing_data
                FROM recording_data
                WHERE recording_region_id = ?
                LIMIT 1
                """, (region_id,)):
            return memoryview(row["content"]), row['missing_data'] != 0

        if get_config_bool("Machine", "virtual_board"):
            return memoryview(bytearray()), True
        else:
            raise LookupError(f"no record for region {region_id}")

    def _read_recording_by_extraction_id(
            self, region_id: int,
            extraction_id: int) -> Tuple[memoryview, bool]:
        """
        Reads the content for a single block for this region
        """
        if extraction_id < 0:
            last_extraction_id = self.get_last_extraction_id()
            extraction_id = last_extraction_id + 1 + extraction_id

        for row in self.cursor().execute(
                """
                SELECT content, missing_data
                FROM recording_data
                WHERE recording_region_id = ? AND extraction_id = ?
                LIMIT 1
                """, (region_id, extraction_id)):
            return memoryview(row["content"]), row['missing_data'] != 0

        raise LookupError(
            f"no record for {region_id=} and {extraction_id=}")

    def _read_download_by_extraction_id(
            self, region_id: int,
            extraction_id: int) -> Tuple[memoryview, bool]:
        """
        Reads the content for a single block for this region
        """
        if extraction_id < 0:
            last_extraction_id = self.get_last_extraction_id()
            extraction_id = last_extraction_id + 1 + extraction_id

        for row in self.cursor().execute(
                """
                SELECT content, missing_data
                FROM download_data
                WHERE download_region_id = ? AND extraction_id = ?
                LIMIT 1
                """, (region_id, extraction_id)):
            return memoryview(row["content"]), row['missing_data'] != 0

        raise LookupError(
            f"no record for {region_id=} and {extraction_id=}")

    def _read_recording_multiple(
            self, region_id: int, total_content_length: int) -> Tuple[
            memoryview, bool]:
        """
        Reads the contents of all blocks for this regions.

        :param region_id:
        :param total_content_length: total size of content for this region
        """
        c_buffer = bytearray(total_content_length)
        missing_data = False
        idx = 0
        for row in self.cursor().execute(
                """
                SELECT content, missing_data FROM recording_data
                WHERE recording_region_id = ? ORDER BY extraction_id ASC
                """, (region_id, )):
            item = row["content"]
            c_buffer[idx:idx + len(item)] = item
            idx += len(item)
            missing_data = missing_data or row["missing_data"] != 0
        return memoryview(c_buffer), missing_data

    def _find_existing_recording_region_id(
            self, x: int, y: int, p: int, region: int) -> Optional[int]:
        for row in self.cursor().execute(
                """
                SELECT recording_region_id
                FROM recording_region_view
                WHERE x = ? AND y = ? AND processor = ?
                    AND local_region_index = ?
                LIMIT 1
                """, (x, y, p, region)):
            return row["recording_region_id"]
        return None

    def _find_existing_download_region_id(
            self, x: int, y: int, p: int, region: int) -> Optional[int]:
        for row in self.cursor().execute(
                """
                SELECT download_region_id
                FROM download_region_view
                WHERE x = ? AND y = ? AND processor = ?
                    AND local_region_index = ?
                LIMIT 1
                """, (x, y, p, region)):
            return row["download_region_id"]
        return None

    def _get_existing_recording_region_id(
            self, x: int, y: int, p: int, region: int) -> int:
        region_id = self._find_existing_recording_region_id(x, y, p, region)
        if region_id is None:
            raise LookupError(
                f"There is no region for {x=} {y=} {p=} {region=}")
        else:
            return region_id

    def _get_existing_download_region_id(
            self, x: int, y: int, p: int, region: int) -> int:
        region_id = self._find_existing_download_region_id(x, y, p, region)
        if region_id is None:
            raise LookupError(
                f"There is no region for {x=} {y=} {p=} {region=}")
        else:
            return region_id

    def _get_recording_region_id(
            self, x: int, y: int, p: int, region: int) -> int:
        region_info = self._find_existing_recording_region_id(x, y, p, region)
        if region_info is not None:
            return region_info

        core_id = self._get_core_id(x, y, p)
        self.cursor().execute(
            """
            INSERT INTO recording_region(
                core_id, local_region_index)
            VALUES(?, ?)
            """, (core_id, region))
        region_id = self.lastrowid
        assert region_id is not None
        return region_id

    def _get_download_region_id(
            self, x: int, y: int, p: int, region: int) -> int:
        region_info = self._find_existing_download_region_id(x, y, p, region)
        if region_info is not None:
            return region_info

        core_id = self._get_core_id(x, y, p)
        self.cursor().execute(
            """
            INSERT INTO download_region(
                core_id, local_region_index)
            VALUES(?, ?)
            """, (core_id, region))
        region_id = self.lastrowid
        assert region_id is not None
        return region_id

    def store_setup_data(self) -> None:
        """
        Stores data passed into simulator setup
        """
        for _ in self.cursor().execute(
                """
                SELECT hardware_time_step_ms
                FROM setup
                """):
            return

        self.cursor().execute(
            """
            INSERT INTO setup(
                setup_id, hardware_time_step_ms, time_scale_factor)
            VALUES(0, ?, ?)
            """, (
                FecDataView.get_hardware_time_step_ms(),
                FecDataView.get_time_scale_factor()))

    def start_new_extraction(self) -> int:
        """
        Stores the metadata for the extractions about to occur

        :returns: Id for this extraction
        """
        run_timesteps = FecDataView.get_current_run_timesteps() or 0
        self.cursor().execute(
            """
            INSERT INTO extraction(run_timestep, n_run, n_loop, extract_time)
            VALUES(?, ?, ?, ?)
            """, (
                run_timesteps, FecDataView.get_run_number(),
                FecDataView.get_run_step(), _timestamp()))
        extraction_id = self.lastrowid
        assert extraction_id is not None
        return extraction_id

    def get_last_extraction_id(self) -> int:
        """
        :returns: The id of the current/ last extraction
        """
        for row in self.cursor().execute(
                """
                SELECT max(extraction_id) as max_id
                FROM extraction
                LIMIT 1
                """):
            return row["max_id"]
        raise LookupError("No Extraction id found")

    def store_recording(self, x: int, y: int, p: int, region: int,
                        missing: bool, data: bytes) -> None:
        """
        Store some information in the corresponding buffer for a
        specific chip, core and recording region.

        :param x: x coordinate of the chip
        :param y: y coordinate of the chip
        :param p: Core within the specified chip
        :param region: Region containing the data to be stored
        :param missing: Whether any data is missing
        :param data: data to be stored

        .. note::
                    Must be shorter than 1GB
        """
        datablob = Binary(data)
        region_id = self._get_recording_region_id(x, y, p, region)
        extraction_id = self.get_last_extraction_id()
        self.cursor().execute(
            """
            INSERT INTO recording_data(
                recording_region_id, extraction_id, content, content_len,
                missing_data)
            VALUES (?, ?, CAST(? AS BLOB), ?, ?)
            """,
            (region_id, extraction_id, datablob, len(data), missing))
        assert self.rowcount == 1

    def store_download(
            self, x: int, y: int, p: int, region: int, missing: bool,
            data: bytes) -> None:
        """
        Store some information in the corresponding buffer for a
        specific chip, core and recording region.

        :param x: x coordinate of the chip
        :param y: y coordinate of the chip
        :param p: Core within the specified chip
        :param region: Region containing the data to be stored
        :param missing: Whether any data is missing
        :param data: data to be stored

            .. note::
                    Must be shorter than 1GB
        """
        datablob = Binary(data)
        download_region_id = self._get_download_region_id(x, y, p, region)
        extraction_id = self.get_last_extraction_id()
        self.cursor().execute(
            """
            INSERT INTO download_data(
                download_region_id, extraction_id, content, content_len,
                missing_data)
            VALUES (?, ?, CAST(? AS BLOB), ?, ?)
            """, (download_region_id, extraction_id, datablob, len(data),
                  missing))
        assert self.rowcount == 1

    def get_recording(self, x: int, y: int, p: int, region: int) -> Tuple[
            memoryview, bool]:
        """
        Get the data stored for a given region of a given core.

        If this is a recoding region the data for all extractions is combined.

        For none recording regions only the last data extracted is returned.

        :param x: x coordinate of the chip
        :param y: y coordinate of the chip
        :param p: Core within the specified chip
        :param region: Region containing the data
        :return:
            A buffer containing all the data received during the
            simulation, and a flag indicating if any data was missing.

            .. note::
                Implementations should not assume that the total buffer is
                necessarily shorter than 1GB.

        :raises LookupErrror: If no data is available nor marked missing.
        """
        region_id = self._get_existing_recording_region_id(
            x, y, p, region)
        return self._read_recording_with_missing(region_id)

    def get_recording_by_extraction_id(
            self, x: int, y: int, p: int, region: int,
            extraction_id: int) -> Tuple[memoryview, bool]:
        """
        Get the data stored for a given region of a given core.

        :param x: x coordinate of the chip
        :param y: y coordinate of the chip
        :param p: Core within the specified chip
        :param region: Region containing the data
        :param extraction_id: ID of the extraction top get data for.
           Negative values will be counted from the end.
        :return:
            A buffer containing all the data received during the
            simulation, and a flag indicating if any data was missing.

            .. note::
                Implementations should not assume that the total buffer is
                necessarily shorter than 1GB.
        """
        try:
            region_id = self._get_existing_recording_region_id(
                x, y, p, region)
            return self._read_recording_by_extraction_id(
                region_id, extraction_id)
        except LookupError:
            return memoryview(b''), True

    def get_download_by_extraction_id(
            self, x: int, y: int, p: int, region: int,
            extraction_id: int) -> Tuple[memoryview, bool]:
        """
        Get the data stored for a given region of a given core.

        :param x: x coordinate of the chip
        :param y: y coordinate of the chip
        :param p: Core within the specified chip
        :param region: Region containing the data
        :param extraction_id: ID of the extraction top get data for.
           Negative values will be counted from the end.
        :return:
            A buffer containing all the data received during the
            simulation, and a flag indicating if any data was missing.

            .. note::
                Implementations should not assume that the total buffer is
                necessarily shorter than 1GB.
        """
        region_id = self._get_existing_download_region_id(x, y, p, region)
        return self._read_download_by_extraction_id(
            region_id, extraction_id)

    def write_session_credentials_to_db(self) -> None:
        """
        Write Spalloc session credentials to the database if in use.
        """
        job = FecDataView.get_spalloc_job()
        if job is not None:
            config = job.get_session_credentials_for_db()
            self.cursor().executemany(
                """
                INSERT INTO proxy_configuration(kind, name, value)
                VALUES(?, ?, ?)
                """, [(k1, k2, v) for (k1, k2), v in config.items()])

    def _set_core_name(
            self, x: int, y: int, p: int, core_name: Optional[str]) -> None:
        try:
            self.cursor().execute(
                """
                INSERT INTO core (x, y, processor, core_name)
                VALUES (?, ?, ? ,?)
                """, (x, y, p, core_name))
        except IntegrityError:
            self.cursor().execute(
                """
                UPDATE core SET core_name = ?
                WHERE x = ? AND y = ? and processor = ?
                """, (core_name, x, y, p))

    def store_vertex_labels(self) -> None:
        """
        Goes though all placement an monitor cores to set a label.
        """
        for placement in FecDataView.iterate_placemements():
            self._set_core_name(
                placement.x, placement.y, placement.p, placement.vertex.label)
        for chip in FecDataView.get_machine().chips:
            for p in chip.scamp_processors_ids:
                self._set_core_name(
                    chip.x, chip.y, p, f"SCAMP(OS)_{chip.x}:{chip.y}")

    def get_core_name(self, x: int, y: int, p: int) -> Optional[str]:
        """
        Gets the label (typically vertex label) for this core.

        Returns None if the core at x, y, p is not known.

        :param x: core x
        :param y: core y
        :param p: core p
        :returns: label for (vertex on) this core or None
        """
        for row in self.cursor().execute(
                """
                SELECT core_name
                FROM core
                WHERE x = ? AND y = ? and processor = ?
                """, (x, y, p)):
            return str(row["core_name"], 'utf8')
        return None

    def get_power_monitor_core(self, x: int, y: int) -> int:
        """
        :returns: The power monitor core for chip x, y
        """
        for row in self.cursor().execute(
                """
                SELECT the_value
                FROM monitor_provenance
                WHERE x = ? AND y = ? AND description = ?
                """, (x, y, PROVENANCE_CORE_KEY)):
            return int(row["the_value"])
        raise LookupError(f"No power monitor core for {x=} {y=}")

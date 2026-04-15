# Copyright (c) 2015 The University of Manchester
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
from typing import Dict, List, Optional, Tuple
from spinnman.spalloc import SpallocClient, SpallocJob
from spinn_front_end_common.utilities.sqlite_db import SQLiteDB


class DatabaseReader(SQLiteDB):
    """
    A reader for the database.
    """
    __slots__ = ("__job", "__looked_for_job")

    def __init__(self, database_path: str):
        """
        :param database_path: The path to the database
        """
        super().__init__(database_path, read_only=True, text_factory=str)
        self.__job: Optional[SpallocJob] = None
        self.__looked_for_job = False

    def get_job(self) -> Optional[SpallocJob]:
        """
        Get the job described in the database. If no job exists, direct
        connection to boards should be used.

        :return: Job handle, if one exists. ``None`` otherwise.
        """
        # This is maintaining an object we only make once
        if not self.__looked_for_job:
            service_url = None
            job_url = None
            cookies = {}
            headers = {}
            for row in self.cursor().execute(
                    """
                    SELECT kind, name, value FROM proxy_configuration
                    """):
                kind, name, value = row
                if kind == "SPALLOC":
                    if name == "service uri":
                        service_url = value
                    elif name == "job uri":
                        job_url = value
                elif kind == "COOKIE":
                    cookies[name] = value
                elif kind == "HEADER":
                    headers[name] = value
            self.__looked_for_job = True
            if not service_url or not job_url or not cookies or not headers:
                # Cannot possibly work without a session or job
                return None
            self.__job = SpallocClient.open_job_from_database(
                service_url, job_url, cookies, headers)
        return self.__job

    def get_key_to_atom_id_mapping(self, label: str) -> Dict[int, int]:
        """
        Get a mapping of event key to atom ID for a given vertex.

        :param label: The label of the vertex
        :return: dictionary of atom IDs indexed by event key
        """
        return {
            row["event"]: row["atom"]
            for row in self.cursor().execute(
                """
                SELECT * FROM label_event_atom_view
                WHERE label = ?
                """, (label, ))}

    def get_atom_id_to_key_mapping(self, label: str) -> Dict[int, int]:
        """
        Get a mapping of atom ID to event key for a given vertex.

        :param label: The label of the vertex
        :return: dictionary of event keys indexed by atom ID
        """
        return {
            row["atom"]: row["event"]
            for row in self.cursor().execute(
                """
                SELECT * FROM label_event_atom_view
                WHERE label = ?
                """, (label, ))}

    def get_live_output_details(
            self, label: str, receiver_label: str) -> Tuple[
                str, int, bool, str, int, int, int]:
        """
        Get the IP address, port and whether the SDP headers are to be
        stripped from the output from a vertex.

        :param label: The label of the pre vertex
        :param receiver_label: The label of the post vertex
        :return: tuple of (IP address, port, strip SDP, board address, tag,
            chip_x, chip_y)
        """
        self.cursor().execute(
            """
            SELECT * FROM app_output_tag_view
            WHERE pre_vertex_label = ?
            AND post_vertex_label LIKE ?
            LIMIT 1
            """, (label, str(receiver_label) + "%"))
        row = self.fetchone()
        return (row["ip_address"], row["port"], row["strip_sdp"],
                row["board_address"], row["tag"], row["chip_x"],
                row["chip_y"])

    def get_configuration_parameter_value(
            self, parameter_name: str) -> Optional[float]:
        """
        Get the value of a configuration parameter.

        :param parameter_name: The name of the parameter
        :return: The value of the parameter
        """
        self.cursor().execute(
            """
            SELECT value FROM configuration_parameters
            WHERE parameter_id = ?
            LIMIT 1
            """, (parameter_name,))
        row = self.fetchone()
        return None if row is None else float(row["value"])

    def get_placements(self, label: str) -> List[Tuple[int, int, int]]:
        """
        Get the placements of an application vertex with a given label.

        :param label: The label of the vertex
        :return: A list of x, y, p coordinates of the vertices
        """
        return [
            (int(row["x"]), int(row["y"]), int(row["p"]))
            for row in self.cursor().execute(
                """
                SELECT x, y, p FROM application_vertex_placements
                WHERE vertex_label = ?
                """, (label, ))]

    def get_ip_address(self, x: int, y: int) -> Optional[str]:
        """
        Get an IP address to contact a chip.

        :param x: The x-coordinate of the chip
        :param y: The y-coordinate of the chip
        :return: The IP address of the Ethernet to use to contact the chip
        """
        self.cursor().execute(
            """
            SELECT eth_ip_address FROM chip_eth_info
            WHERE x = ? AND y = ? OR x = 0 AND y = 0
            ORDER BY x DESC
            LIMIT 1
            """, (x, y))
        row = self.fetchone()
        # Should only fail if no machine is present or a bad XY given!
        return None if row is None else row["eth_ip_address"]

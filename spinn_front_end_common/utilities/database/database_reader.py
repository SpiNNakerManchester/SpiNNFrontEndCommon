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
from spinn_front_end_common.utilities.sqlite_db import SQLiteDB
from spinnman.spalloc import SpallocClient


class DatabaseReader(SQLiteDB):
    """
    A reader for the database.
    """
    __slots__ = ("__job", "__looked_for_job")

    def __init__(self, database_path):
        """
        :param str database_path: The path to the database
        """
        super().__init__(database_path, read_only=True, text_factory=str)
        self.__job = None
        self.__looked_for_job = False

    def __exec_one(self, query, *args):
        with self.transaction() as cur:
            cur.execute(query + " LIMIT 1", args)
            return cur.fetchone()

    @staticmethod
    def __r2t(row, *args):
        return tuple(None if row is None else row[key] for key in args)

    def get_job(self):
        """
        Get the job described in the database. If no job exists, direct
        connection to boards should be used.

        :return: Job handle, if one exists. ``None`` otherwise.
        :rtype: ~spinnman.spalloc.SpallocJob
        """
        # This is maintaining an object we only make once
        if not self.__looked_for_job:
            with self.transaction() as cur:
                self.__job = SpallocClient.open_job_from_database(cur)
            self.__looked_for_job = True
        return self.__job

    def get_key_to_atom_id_mapping(self, label):
        """
        Get a mapping of event key to atom ID for a given vertex.

        :param str label: The label of the vertex
        :return: dictionary of atom IDs indexed by event key
        :rtype: dict(int, int)
        """
        with self.transaction() as cur:
            return {
                row["event"]: row["atom"]
                for row in cur.execute(
                    """
                    SELECT * FROM label_event_atom_view
                    WHERE label = ?
                    """, (label, ))}

    def get_atom_id_to_key_mapping(self, label):
        """
        Get a mapping of atom ID to event key for a given vertex.

        :param str label: The label of the vertex
        :return: dictionary of event keys indexed by atom ID
        :rtype: dict(int, int)
        """
        with self.transaction() as cur:
            return {
                row["atom"]: row["event"]
                for row in cur.execute(
                    """
                    SELECT * FROM label_event_atom_view
                    WHERE label = ?
                    """, (label, ))}

    def get_live_output_details(self, label, receiver_label):
        """
        Get the IP address, port and whether the SDP headers are to be
        stripped from the output from a vertex.

        :param str label: The label of the vertex
        :return: tuple of (IP address, port, strip SDP, board address, tag,
            chip_x, chip_y)
        :rtype: tuple(str, int, bool, str, int, int, int)
        """
        return self.__r2t(
            self.__exec_one(
                """
                SELECT * FROM app_output_tag_view
                WHERE pre_vertex_label = ?
                    AND post_vertex_label LIKE ?
                """, label, str(receiver_label) + "%"),
            "ip_address", "port", "strip_sdp", "board_address", "tag",
            "chip_x", "chip_y")

    def get_configuration_parameter_value(self, parameter_name):
        """
        Get the value of a configuration parameter.

        :param str parameter_name: The name of the parameter
        :return: The value of the parameter
        :rtype: float or None
        """
        row = self.__exec_one(
            """
            SELECT value FROM configuration_parameters
            WHERE parameter_id = ?
            """, parameter_name)
        return None if row is None else float(row["value"])

    @staticmethod
    def __xyp(row):
        return int(row["x"]), int(row["y"]), int(row["p"])

    def get_placements(self, label):
        """
        Get the placements of an application vertex with a given label.

        :param str label: The label of the vertex
        :return: A list of x, y, p coordinates of the vertices
        :rtype: list(tuple(int, int, int))
        """
        with self.transaction() as cur:
            return [
                self.__xyp(row) for row in cur.execute(
                    """
                    SELECT x, y, p FROM application_vertex_placements
                    WHERE vertex_label = ?
                    """, (label, ))]

    def get_ip_address(self, x, y):
        """
        Get an IP address to contact a chip.

        :param int x: The x-coordinate of the chip
        :param int y: The y-coordinate of the chip
        :return: The IP address of the Ethernet to use to contact the chip
        :rtype: str or None
        """
        row = self.__exec_one(
            """
            SELECT eth_ip_address FROM chip_eth_info
            WHERE x = ? AND y = ? OR x = 0 AND y = 0
            ORDER BY x DESC
            """, x, y)
        # Should only fail if no machine is present!
        return None if row is None else row["eth_ip_address"]

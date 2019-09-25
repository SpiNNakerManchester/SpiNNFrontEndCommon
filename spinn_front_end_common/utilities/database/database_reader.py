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

import sqlite3


class DatabaseReader(object):
    """ A reader for the database.
    """

    __slots__ = [
        # the database connection (is basically a lock on the database)
        "_connection",

        # the handle for working on the DB
        "_cursor"
    ]

    def __init__(self, database_path):
        """
        :param database_path: The path to the database
        :type database_path: str
        """
        self._connection = sqlite3.connect(database_path)
        self._connection.row_factory = sqlite3.Row
        self._cursor = self._connection.cursor()

    @property
    def cursor(self):
        """ The database cursor.  Allows custom SQL queries to be performed.

        :rtype: :py:class:`sqlite3.Cursor`
        """
        return self._cursor

    def __exec_one(self, query, *args):
        self._cursor.execute(query + " LIMIT 1", args)
        return self._cursor.fetchone()

    def __exec_all(self, query, *args):
        self._cursor.execute(query, args)
        return self._cursor.fetchall()

    @staticmethod
    def __r2t(row, *args):
        return tuple(None if row is None else row[key] for key in args)

    def get_key_to_atom_id_mapping(self, label):
        """ Get a mapping of event key to atom ID for a given vertex

        :param label: The label of the vertex
        :type label: str
        :return: dictionary of atom IDs indexed by event key
        :rtype: dict(int, int)
        """
        return {row["event"]: row["atom"]
                for row in self.__exec_all(
                    "SELECT * FROM label_event_atom_view"
                    " WHERE label = ?", label)}

    def get_atom_id_to_key_mapping(self, label):
        """ Get a mapping of atom ID to event key for a given vertex

        :param label: The label of the vertex
        :type label: str
        :return: dictionary of event keys indexed by atom ID
        :rtype: dict(int, int)
        """
        return {row["atom"]: row["event"]
                for row in self.__exec_all(
                    "SELECT * FROM label_event_atom_view"
                    " WHERE label = ?", label)}

    def get_live_output_details(self, label, receiver_label):
        """ Get the IP address, port and whether the SDP headers are to be\
            stripped from the output from a vertex

        :param label: The label of the vertex
        :type label: str
        :return: tuple of (IP address, port, strip SDP)
        :rtype: tuple(str, int, bool)
        """
        return self.__r2t(
            self.__exec_one(
                "SELECT * FROM app_output_tag_view"
                " WHERE pre_vertex_label = ? AND post_vertex_label LIKE ?",
                label, str(receiver_label) + "%"),
            "ip_address", "port", "strip_sdp", "board_address", "tag")

    def get_live_input_details(self, label):
        """ Get the IP address and port where live input should be sent\
            for a given vertex

        :param label: The label of the vertex
        :type label: str
        :return: tuple of (IP address, port)
        :rtype: tuple(str, int)
        """
        return self.__r2t(
            self.__exec_one(
                "SELECT * FROM app_input_tag_view"
                " WHERE application_label = ?", label),
            "board_address", "port")

    def get_machine_live_output_details(self, label, receiver_label):
        """ Get the IP address, port and whether the SDP headers are to be\
            stripped from the output from a machine vertex

        :param label: The label of the vertex
        :type label: str
        :return: tuple of (IP address, port, strip SDP)
        :rtype: tuple(str, int, bool)
        """
        return self.__r2t(
            self.__exec_one(
                "SELECT * FROM machine_output_tag_view"
                " WHERE pre_vertex_label = ? AND post_vertex_label LIKE ?",
                label, str(receiver_label) + "%"),
            "ip_address", "port", "strip_sdp", "board_address", "tag")

    def get_machine_live_input_details(self, label):
        """ Get the IP address and port where live input should be sent\
            for a given machine vertex

        :param label: The label of the vertex
        :type label: str
        :return: tuple of (IP address, port)
        :rtype: tuple(str, int)
        """
        return self.__r2t(
            self.__exec_one(
                "SELECT * FROM machine_input_tag_view"
                " WHERE machine_label = ?", label),
            "board_address", "port")

    def get_machine_live_output_key(self, label, receiver_label):
        return self.__r2t(
            self.__exec_one(
                "SELECT * FROM machine_edge_key_view"
                " WHERE pre_vertex_label = ? AND post_vertex_label LIKE ?",
                label, str(receiver_label) + "%"),
            "key", "mask")

    def get_machine_live_input_key(self, label):
        return self.__r2t(
            self.__exec_one(
                "SELECT * FROM machine_edge_key_view"
                " WHERE pre_vertex_label = ?", label),
            "key", "mask")

    def get_n_atoms(self, label):
        """ Get the number of atoms in a given vertex

        :param label: The label of the vertex
        :type label: str
        :return: The number of atoms
        :rtype: int
        """
        row = self.__exec_one(
            "SELECT no_atoms FROM Application_vertices "
            "WHERE vertex_label = ?", label)
        return 0 if row is None else row["no_atoms"]

    def get_configuration_parameter_value(self, parameter_name):
        """ Get the value of a configuration parameter

        :param parameter_name: The name of the parameter
        :type parameter_name: str
        :return: The value of the parameter
        :rtype: float
        """
        row = self.__exec_one(
            "SELECT value FROM configuration_parameters"
            " WHERE parameter_id = ?", parameter_name)
        return None if row is None else float(row["value"])

    @staticmethod
    def __xyp(row):
        return int(row["x"]), int(row["y"]), int(row["p"])

    def get_placement(self, label):
        """ Get the placement of a machine vertex with a given label

        :param label: The label of the vertex
        :type label: str
        :return: The x, y, p coordinates of the vertex
        :rtype: tuple(int, int, int)
        """
        row = self.__exec_one(
            "SELECT x, y, p FROM machine_vertex_placement"
            " WHERE vertex_label = ?", label)
        return (None, None, None) if row is None else self.__xyp(row)

    def get_placements(self, label):
        """ Get the placements of an application vertex with a given label

        :param label: The label of the vertex
        :type label: str
        :return: A list of x, y, p coordinates of the vertices
        :rtype: list(tuple(int, int, int))
        """

        return [self.__xyp(row) for row in self.__exec_all(
            "SELECT x, y, p FROM application_vertex_placements"
            " WHERE vertex_label = ?", label)]

    def get_ip_address(self, x, y):
        """ Get an IP address to contact a chip

        :param x: The x-coordinate of the chip
        :param y: The y-coordinate of the chip
        :return: The IP address of the Ethernet to use to contact the chip
        """
        row = self.__exec_one(
            "SELECT eth_ip_address FROM chip_eth_info"
            " WHERE x = ? AND y = ? OR x = 0 AND y = 0"
            " ORDER BY x DESC", x, y)
        # Should only fail if no machine is present!
        return None if row is None else row["eth_ip_address"]

    def close(self):
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # @UnusedVariable
        self._connection.close()
        return False

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

        # the location for writing
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

    def get_key_to_atom_id_mapping(self, label):
        """ Get a mapping of event key to atom ID for a given vertex

        :param label: The label of the vertex
        :type label: str
        :return: dictionary of atom IDs indexed by event key
        :rtype: dict(int, int)
        """
        event_id_to_atom_id_mapping = dict()
        for row in self._cursor.execute(
                "SELECT * FROM label_event_atom_view"
                " WHERE label = ?", (label, )):
            event_id_to_atom_id_mapping[row["event"]] = row["atom"]
        return event_id_to_atom_id_mapping

    def get_atom_id_to_key_mapping(self, label):
        """ Get a mapping of atom ID to event key for a given vertex

        :param label: The label of the vertex
        :type label: str
        :return: dictionary of event keys indexed by atom ID
        :rtype: dict(int, int)
        """
        atom_to_event_id_mapping = dict()
        for row in self._cursor.execute(
                "SELECT * FROM label_event_atom_view"
                " WHERE label = ?", (label, )):
            atom_to_event_id_mapping[row["atom"]] = row["event"]
        return atom_to_event_id_mapping

    def get_live_output_details(self, label, receiver_label):
        """ Get the IP address, port and whether the SDP headers are to be\
            stripped from the output from a vertex

        :param label: The label of the vertex
        :type label: str
        :return: tuple of (IP address, port, strip SDP)
        :rtype: tuple(str, int, bool)
        """
        self._cursor.execute(
            "SELECT * FROM app_output_tag_view"
            " WHERE pre_vertex_label = ?"
            "   AND post_vertex_label LIKE ?"
            " LIMIT 1", (label, str(receiver_label) + "%"))
        row = self._cursor.fetchone()
        if row is None:
            return (None, None, None, None, None)
        return (
            row["ip_address"], row["port"], row["strip_sdp"],
            row["board_address"], row["tag"])

    def get_live_input_details(self, label):
        """ Get the IP address and port where live input should be sent\
            for a given vertex

        :param label: The label of the vertex
        :type label: str
        :return: tuple of (IP address, port)
        :rtype: tuple(str, int)
        """
        self._cursor.execute(
            "SELECT * FROM app_input_tag_view"
            " WHERE application_label = ?"
            " LIMIT 1", (label, ))
        row = self._cursor.fetchone()
        if row is None:
            return (None, None)
        return row["board_address"], row["port"]

    def get_machine_live_output_details(self, label, receiver_label):
        """ Get the IP address, port and whether the SDP headers are to be\
            stripped from the output from a machine vertex

        :param label: The label of the vertex
        :type label: str
        :return: tuple of (IP address, port, strip SDP)
        :rtype: tuple(str, int, bool)
        """
        self._cursor.execute(
            "SELECT * FROM machine_output_tag_view"
            " WHERE pre_vertex_label = ?"
            "   AND post_vertex_label LIKE ?"
            " LIMIT 1", (label, str(receiver_label) + "%"))
        row = self._cursor.fetchone()
        if row is None:
            return (None, None, None, None, None)
        return (
            row["ip_address"], row["port"], row["strip_sdp"],
            row["board_address"], row["tag"])

    def get_machine_live_input_details(self, label):
        """ Get the IP address and port where live input should be sent\
            for a given machine vertex

        :param label: The label of the vertex
        :type label: str
        :return: tuple of (IP address, port)
        :rtype: tuple(str, int)
        """
        self._cursor.execute(
            "SELECT * FROM machine_input_tag_view"
            " WHERE machine_label = ?"
            " LIMIT 1", (label, ))
        row = self._cursor.fetchone()
        if row is None:
            return (None, None)
        return row["board_address"], row["port"]

    def get_machine_live_output_key(self, label, receiver_label):
        self._cursor.execute(
            "SELECT * FROM machine_edge_key_view"
            " WHERE pre_vertex_label = ?"
            "   AND post_vertex_label LIKE ?"
            " LIMIT 1", (label, str(receiver_label) + "%"))
        row = self._cursor.fetchone()
        if row is None:
            return (None, None)
        return (row["key"], row["mask"])

    def get_machine_live_input_key(self, label):
        self._cursor.execute(
            "SELECT * FROM machine_edge_key_view"
            " WHERE pre_vertex_label = ? LIMIT 1", (label, ))
        row = self._cursor.fetchone()
        if row is None:
            return (None, None)
        return (row["key"], row["mask"])

    def get_n_atoms(self, label):
        """ Get the number of atoms in a given vertex

        :param label: The label of the vertex
        :type label: str
        :return: The number of atoms
        :rtype: int
        """
        self._cursor.execute(
            "SELECT no_atoms FROM Application_vertices "
            "WHERE vertex_label = ?"
            " LIMIT 1", (label, ))
        row = self._cursor.fetchone()
        if row is None:
            return 0
        return row["no_atoms"]

    def get_configuration_parameter_value(self, parameter_name):
        """ Get the value of a configuration parameter

        :param parameter_name: The name of the parameter
        :type parameter_name: str
        :return: The value of the parameter
        :rtype: float
        """
        self._cursor.execute(
            "SELECT value FROM configuration_parameters"
            " WHERE parameter_id = ?"
            " LIMIT 1", (parameter_name, ))
        return float(self._cursor.fetchone()["value"])

    def get_placement(self, label):
        """ Get the placement of a machine vertex with a given label

        :param label: The label of the vertex
        :type label: str
        :return: The x, y, p coordinates of the vertex
        :rtype: tuple(int, int, int)
        """
        self._cursor.execute(
            "SELECT x, y, p FROM machine_vertex_placement"
            " WHERE vertex_label = ? LIMIT 1", (label, ))
        row = self._cursor.fetchone()
        if row is None:
            return (None, None, None)
        return (int(row["x"]), int(row["y"]), int(row["p"]))

    def get_placements(self, label):
        """ Get the placements of an application vertex with a given label

        :param label: The label of the vertex
        :type label: str
        :return: A list of x, y, p coordinates of the vertices
        :rtype: list(tuple(int, int, int))
        """
        self._cursor.execute(
            "SELECT x, y, p FROM application_vertex_placements"
            " WHERE vertex_label = ?", (label, ))
        return [(int(row["x"]), int(row["y"]), int(row["p"]))
                for row in self._cursor.fetchall()]

    def get_ip_address(self, x, y):
        """ Get an IP address to contact a chip

        :param x: The x-coordinate of the chip
        :param y: The y-coordinate of the chip
        :return: The IP address of the Ethernet to use to contact the chip
        """
        self._cursor.execute(
            "SELECT eth_chip.ip_address FROM Machine_chip as chip"
            " JOIN Machine_chip as eth_chip"
            "   ON chip.nearest_ethernet_x = eth_chip.chip_x AND "
            "     chip.nearest_ethernet_y = eth_chip.chip_y"
            " WHERE chip.chip_x = ? AND chip.chip_y = ?", (x, y))
        row = self._cursor.fetchone()
        if row is None:
            self._cursor.execute(
                "SELECT ip_address FROM Machine_chip"
                " WHERE chip_x = 0 AND chip_y = 0")
            row = self._cursor.fetchone()
        if row is None:
            return None
        return row["ip_address"]

    def close(self):
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # @UnusedVariable
        self._connection.close()
        return False

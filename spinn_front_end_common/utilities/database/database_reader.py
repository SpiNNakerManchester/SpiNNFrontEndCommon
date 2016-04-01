import sqlite3 as sqlite


class DatabaseReader(object):
    """ A reader for the database
    """

    def __init__(self, database_path):
        """

        :param database_path: The path to the database
        :type database_path: str
        """
        self._connection = sqlite.connect(database_path)
        self._connection.row_factory = sqlite.Row
        self._cursor = self._connection.cursor()

    @property
    def cursor(self):
        """ The database cursor.  Allows custom SQL queries to be performed.

        :rtype: :py:class:`sqlite3.Cursor`
        """
        return self._cursor

    def get_key_to_atom_id_mapping(self, label):
        """ Get a mapping of event key to atom id for a given vertex

        :param label: The label of the vertex
        :type label: str
        :return: dictionary of atom ids indexed by event key
        :rtype: dict
        """
        event_id_to_atom_id_mapping = dict()
        for row in self._cursor.execute(
            "SELECT n.atom_id as a_id, n.event_id as event"
            " FROM event_to_atom_mapping as n"
            " JOIN Partitionable_vertices as p ON n.vertex_id = p.vertex_id"
                " WHERE p.vertex_label=\"{}\"".format(label)):
            event_id_to_atom_id_mapping[row["event"]] = row["a_id"]
        return event_id_to_atom_id_mapping

    def get_atom_id_to_key_mapping(self, label):
        """ Get a mapping of atom id to event key for a given vertex

        :param label: The label of the vertex
        :type label: str
        :return: dictionary of event keys indexed by atom id
        """
        atom_to_event_id_mapping = dict()
        for row in self._cursor.execute(
            "SELECT n.atom_id as a_id, n.event_id as event"
            " FROM event_to_atom_mapping as n"
            " JOIN Partitionable_vertices as p ON n.vertex_id = p.vertex_id"
                " WHERE p.vertex_label=\"{}\"".format(label)):
            atom_to_event_id_mapping[row["a_id"]] = row["event"]
        return atom_to_event_id_mapping

    def get_live_output_details(self, label, receiver_label):
        """ Get the ip address, port and whether the SDP headers are to be\
            stripped from the output from a vertex

        :param label: The label of the vertex
        :type label: str
        :return: tuple of (ip address, port, strip SDP)
        :rtype: (str, int, bool)
        """
        self._cursor.execute(
            "SELECT * FROM IP_tags as tag"
            " JOIN graph_mapper_vertex as mapper"
            " ON tag.vertex_id = mapper.partitioned_vertex_id"
            " JOIN Partitionable_vertices as post_vertices"
            " ON mapper.partitionable_vertex_id = post_vertices.vertex_id"
            " JOIN Partitionable_edges as edges"
            " ON mapper.partitionable_vertex_id == edges.post_vertex"
            " JOIN Partitionable_vertices as pre_vertices"
            " ON edges.pre_vertex == pre_vertices.vertex_id"
            " WHERE pre_vertices.vertex_label == \"{}\""
            " AND post_vertices.vertex_label == \"{}\""
            .format(label, receiver_label))
        row = self._cursor.fetchone()
        return (row["ip_address"], row["port"], row["strip_sdp"])

    def get_live_input_details(self, label):
        """ Get the ip address and port where live input should be sent\
            for a given vertex

        :param label: The label of the vertex
        :type label: str
        :return: tuple of (ip address, port)
        :rtype: (str, int)
        """
        self._cursor.execute(
            "SELECT tag.board_address, tag.port as port"
            " FROM Reverse_IP_tags as tag"
            " JOIN graph_mapper_vertex as mapper"
            " ON tag.vertex_id = mapper.partitioned_vertex_id"
            " JOIN Partitionable_vertices as partitionable"
            " ON mapper.partitionable_vertex_id = partitionable.vertex_id"
            " WHERE partitionable.vertex_label=\"{}\"".format(label))
        row = self._cursor.fetchone()
        return row["board_address"], row["port"]

    def get_partitioned_live_output_details(self, label, receiver_label):
        """ Get the ip address, port and whether the SDP headers are to be\
            stripped from the output from a partitioned vertex

        :param label: The label of the vertex
        :type label: str
        :return: tuple of (ip address, port, strip SDP)
        :rtype: (str, int, bool)
        """
        self._cursor.execute(
            "SELECT * FROM IP_tags as tag"
            " JOIN Partitioned_vertices as post_vertices"
            " ON tag.vertex_id == post_vertices.vertex_id"
            " JOIN Partitioned_edges as edges"
            " ON post_vertices.vertex_id == edges.post_vertex"
            " JOIN Partitioned_vertices as pre_vertices"
            " ON edges.pre_vertex == pre_vertices.vertex_id"
            " WHERE pre_vertices.label == \"{}\""
            " AND post_vertices.label == \"{}\""
            .format(label, receiver_label))
        row = self._cursor.fetchone()
        return (row["ip_address"], row["port"], row["strip_sdp"])

    def get_partitioned_live_input_details(self, label):
        """ Get the ip address and port where live input should be sent\
            for a given partitioned vertex

        :param label: The label of the vertex
        :type label: str
        :return: tuple of (ip address, port)
        :rtype: (str, int)
        """
        self._cursor.execute(
            "SELECT tag.board_address, tag.port as port"
            " FROM Reverse_IP_tags as tag"
            " JOIN Partitioned_vertices as post_vertices"
            " ON tag.vertex_id = post_vertices.vertex_id"
            " WHERE post_vertices.label=\"{}\"".format(label))
        row = self._cursor.fetchone()
        return row["board_address"], row["port"]

    def get_partitioned_live_output_key(self, label, receiver_label):
        self._cursor.execute(
            "SELECT * FROM Routing_info as r_info"
            " JOIN Partitioned_edges as edges"
            " ON edges.edge_id == r_info.edge_id"
            " JOIN Partitioned_vertices as post_vertices"
            " ON post_vertices.vertex_id == edges.post_vertex"
            " JOIN Partitioned_vertices as pre_vertices"
            " ON pre_vertices.vertex_id == edges.pre_vertex"
            " WHERE pre_vertices.label == \"{}\""
            " AND post_vertices.label == \"{}\""
            .format(label, receiver_label))
        row = self._cursor.fetchone()
        return (row["key"], row["mask"])

    def get_partitioned_live_input_key(self, label):
        self._cursor.execute(
            "SELECT * FROM Routing_info as r_info"
            " JOIN Partitioned_edges as edges"
            " ON edges.edge_id == r_info.edge_id"
            " JOIN Partitioned_vertices as pre_vertices"
            " ON pre_vertices.vertex_id == edges.pre_vertex"
            " WHERE pre_vertices.label == \"{}\""
            .format(label))
        row = self._cursor.fetchone()
        return (row["key"], row["mask"])

    def get_n_atoms(self, label):
        """ Get the number of atoms in a given vertex

        :param label: The label of the vertex
        :type label: str
        :return: The number of atoms
        :rtype: int
        """
        self._cursor.execute(
            "SELECT no_atoms FROM Partitionable_vertices "
            "WHERE vertex_label = \"{}\"".format(label))
        return self._cursor.fetchone()["no_atoms"]

    def get_configuration_parameter_value(self, parameter_name):
        """ Get the value of a configuration parameter

        :param parameter_name: The name of the parameter
        :type parameter_name: str
        :return: The value of the parameter
        :rtype: float
        """
        self._cursor.execute(
            "SELECT value FROM configuration_parameters"
            " WHERE parameter_id = \"{}\"".format(parameter_name))
        return float(self._cursor.fetchone()["value"])

    def close(self):
        self._connection.close()

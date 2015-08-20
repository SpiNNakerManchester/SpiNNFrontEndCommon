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

    def get_key_to_neuron_id_mapping(self, label):
        """ Get a mapping of spike key to neuron id for a given population

        :param label: The label of the population
        :type label: str
        :return: dictionary of neuron ids indexed by spike key
        :rtype: dict
        """
        key_to_neruon_id = dict()
        for row in self._cursor.execute(
            "SELECT n.neuron_id as n_id, n.key as key"
            " FROM key_to_neuron_mapping as n"
            " JOIN Partitionable_vertices as p ON n.vertex_id = p.vertex_id"
                " WHERE p.vertex_label=\"{}\"".format(label)):
            key_to_neruon_id[row["key"]] = row["n_id"]
        return key_to_neruon_id

    def get_neuron_id_to_key_mapping(self, label):
        """ Get a mapping of neuron id to spike key for a given population

        :param label: The label of the population
        :type label: str
        :return: dictionary of spike keys indexed by neuron id
        """
        neuron_id_to_key = dict()
        for row in self._cursor.execute(
            "SELECT n.neuron_id as n_id, n.key as key"
            " FROM key_to_neuron_mapping as n"
            " JOIN Partitionable_vertices as p ON n.vertex_id = p.vertex_id"
                " WHERE p.vertex_label=\"{}\"".format(label)):
            neuron_id_to_key[row["n_id"]] = row["key"]
        return neuron_id_to_key

    def get_live_output_details(self, label):
        """ Get the ip address, port and whether the sdp headers are to be\
            stripped from the output from a population

        :param label: The label of the population
        :type label: str
        :return: tuple of (ip address, port, strip sdp)
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
            " AND post_vertices.vertex_label == \"LiveSpikeReceiver\""
            .format(label))
        row = self._cursor.fetchone()
        return (row["ip_address"], row["port"], row["strip_sdp"])

    def get_live_input_details(self, label):
        """ Get the ip address and port where live input should be sent\
            for a given population

        :param label: The label of the population
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

    def get_n_neurons(self, label):
        """ Get the number of neurons in a given population

        :param label: The label of the population
        :type label: str
        :return: The number of neurons
        :rtype: int
        """
        self._cursor.execute(
            "SELECT no_atoms FROM Partitionable_vertices "
            "WHERE vertex_label = \"{}\"".format(label))
        return self._cursor.fetchone()["no_atoms"]

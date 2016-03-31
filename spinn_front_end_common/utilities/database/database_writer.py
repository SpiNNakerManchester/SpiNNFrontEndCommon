# spinn front end common
from spinn_front_end_common.abstract_models.abstract_recordable import \
    AbstractRecordable
from spinn_front_end_common.utility_models.\
    live_packet_gather_partitioned_vertex import \
    LivePacketGatherPartitionedVertex
from spinn_front_end_common.utility_models.\
    reverse_ip_tag_multicast_source_partitioned_vertex import \
    ReverseIPTagMulticastSourcePartitionedVertex

# general imports
import logging
import traceback
import os

logger = logging.getLogger(__name__)


class DatabaseWriter(object):
    """ The interface for the database system for main front ends.\
        Any special tables needed from a front end should be done\
        by sub classes of this interface.
    """

    def __init__(self, database_directory):

        self._done = False
        self._database_directory = database_directory
        self._database_path = os.path.join(
            self._database_directory, "input_output_database.db")

        # delete any old database
        if os.path.isfile(self._database_path):
            os.remove(self._database_path)

        # set up checks
        self._machine_id = 0

    @staticmethod
    def auto_detect_database(partitioned_graph):
        """ Auto detects if there is a need to activate the database system

        :param partitioned_graph: the partitioned graph of the application\
                problem space.
        :return: a bool which represents if the database is needed
        """
        for vertex in partitioned_graph.subvertices:
            if (isinstance(vertex, LivePacketGatherPartitionedVertex) or
                    (isinstance(
                        vertex,
                        ReverseIPTagMulticastSourcePartitionedVertex) and
                     vertex.is_in_injection_mode)):
                return True
        else:
            return False

    @property
    def database_path(self):
        """

        :return:
        """
        return self._database_path

    def add_machine_objects(self, machine):
        """ Store the machine object into the database

        :param machine: the machine object.
        :return: None
        """

        # noinspection PyBroadException
        try:
            import sqlite3 as sqlite
            connection = sqlite.connect(self._database_path)
            cur = connection.cursor()
            cur.execute(
                "CREATE TABLE Machine_layout("
                "machine_id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " x_dimension INT, y_dimension INT)")
            cur.execute(
                "CREATE TABLE Machine_chip("
                "no_processors INT, chip_x INTEGER, chip_y INTEGER, "
                "machine_id INTEGER, avilableSDRAM INT, "
                "PRIMARY KEY(chip_x, chip_y, machine_id), "
                "FOREIGN KEY (machine_id) "
                "REFERENCES Machine_layout(machine_id))")
            cur.execute(
                "CREATE TABLE Processor("
                "chip_x INTEGER, chip_y INTEGER, machine_id INTEGER, "
                "available_DTCM INT, available_CPU INT, physical_id INTEGER, "
                "PRIMARY KEY(chip_x, chip_y, machine_id, physical_id), "
                "FOREIGN KEY (chip_x, chip_y, machine_id) "
                "REFERENCES Machine_chip(chip_x, chip_y, machine_id))")

            x_di = machine.max_chip_x + 1
            y_di = machine.max_chip_y + 1
            cur.execute("INSERT INTO Machine_layout("
                        "x_dimension, y_dimension)"
                        " VALUES({}, {})".format(x_di, y_di))
            self._machine_id += 1
            for chip in machine.chips:
                cur.execute(
                    "INSERT INTO Machine_chip("
                    "no_processors, chip_x, chip_y, machine_id) "
                    "VALUES ({}, {}, {}, {})"
                    .format(len(list(chip.processors)), chip.x, chip.y,
                            self._machine_id))
                for processor in chip.processors:
                    cur.execute(
                        "INSERT INTO Processor("
                        "chip_x, chip_y, machine_id, available_DTCM, "
                        "available_CPU, physical_id)"
                        "VALUES({}, {}, {}, {}, {}, {})"
                        .format(chip.x, chip.y, self._machine_id,
                                processor.dtcm_available,
                                processor.cpu_cycles_available,
                                processor.processor_id))
            connection.commit()
            connection.close()
        except Exception:
            traceback.print_exc()

    def add_partitionable_vertices(self, partitionable_graph):
        """

        :param partitionable_graph:
        :return:
        """

        try:
            import sqlite3 as sqlite
            connection = sqlite.connect(self._database_path)
            cur = connection.cursor()
            cur.execute(
                "CREATE TABLE Partitionable_vertices("
                "vertex_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "vertex_label TEXT, no_atoms INT, max_atom_constrant INT,"
                "recorded INT)")
            cur.execute(
                "CREATE TABLE Partitionable_edges("
                "edge_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "pre_vertex INTEGER, post_vertex INTEGER, edge_label TEXT, "
                "FOREIGN KEY (pre_vertex)"
                " REFERENCES Partitionable_vertices(vertex_id), "
                "FOREIGN KEY (post_vertex)"
                " REFERENCES Partitionable_vertices(vertex_id))")
            cur.execute(
                "CREATE TABLE Partitionable_graph("
                "vertex_id INTEGER, edge_id INTEGER, "
                "FOREIGN KEY (vertex_id) "
                "REFERENCES Partitionable_vertices(vertex_id), "
                "FOREIGN KEY (edge_id) "
                "REFERENCES Partitionable_edges(edge_id), "
                "PRIMARY KEY (vertex_id, edge_id))")

            # add vertices
            for vertex in partitionable_graph.vertices:
                if isinstance(vertex, AbstractRecordable):
                    cur.execute(
                        "INSERT INTO Partitionable_vertices("
                        "vertex_label, no_atoms, max_atom_constrant, recorded)"
                        " VALUES('{}', {}, {}, {});"
                        .format(vertex.label, vertex.n_atoms,
                                vertex.get_max_atoms_per_core(),
                                int(vertex.is_recording_spikes())))
                else:
                    cur.execute(
                        "INSERT INTO Partitionable_vertices("
                        "vertex_label, no_atoms, max_atom_constrant, recorded)"
                        " VALUES('{}', {}, {}, 0);"
                        .format(vertex.label, vertex.n_atoms,
                                vertex.get_max_atoms_per_core()))

            # add edges
            vertices = partitionable_graph.vertices
            for vertex in partitionable_graph.vertices:
                for edge in partitionable_graph.\
                        outgoing_edges_from_vertex(vertex):
                    cur.execute(
                        "INSERT INTO Partitionable_edges ("
                        "pre_vertex, post_vertex, edge_label) "
                        "VALUES({}, {}, '{}');"
                        .format(vertices.index(edge.pre_vertex) + 1,
                                vertices.index(edge.post_vertex) + 1,
                                edge.label))

            # update graph
            edge_id_offset = 0
            for vertex in partitionable_graph.vertices:
                edges = partitionable_graph.outgoing_edges_from_vertex(vertex)
                for edge in partitionable_graph.\
                        outgoing_edges_from_vertex(vertex):
                    cur.execute(
                        "INSERT INTO Partitionable_graph ("
                        "vertex_id, edge_id)"
                        " VALUES({}, {})"
                        .format(vertices.index(vertex) + 1,
                                edges.index(edge) + edge_id_offset))
                edge_id_offset += len(edges)
            connection.commit()
            connection.close()
        except Exception:
            traceback.print_exc()

    def add_system_params(self, time_scale_factor, machine_time_step, runtime):
        """ Write system params into the database

        :param time_scale_factor: the time scale factor used in timing
        :param machine_time_step: the machine time step used in timing
        :param runtime: the amount of time the application is to run for
        """

        # noinspection PyBroadException
        try:
            import sqlite3 as sqlite
            connection = sqlite.connect(self._database_path)
            cur = connection.cursor()
            # create table
            cur.execute(
                "CREATE TABLE configuration_parameters("
                "parameter_id TEXT, value REAL, "
                "PRIMARY KEY (parameter_id))")

            # Done in 3 statements, as Windows seems to not support
            # multiple value sets in a single statement
            cur.execute(
                "INSERT INTO configuration_parameters (parameter_id, value)"
                " VALUES ('machine_time_step', {})".format(machine_time_step)
            )
            cur.execute(
                "INSERT INTO configuration_parameters (parameter_id, value)"
                " VALUES ('time_scale_factor', {})".format(time_scale_factor)
            )
            if runtime is not None:
                cur.execute(
                    "INSERT INTO configuration_parameters"
                    " (parameter_id, value) VALUES ('infinite_run', 'False')"
                )
                cur.execute(
                    "INSERT INTO configuration_parameters"
                    " (parameter_id, value) VALUES ('runtime', {})".format(
                        runtime)
                )
            else:
                cur.execute(
                    "INSERT INTO configuration_parameters"
                    " (parameter_id, value) VALUES ('infinite_run', 'True')"
                )
                cur.execute(
                    "INSERT INTO configuration_parameters"
                    " (parameter_id, value) VALUES ('runtime', {})".format(-1)
                )

            connection.commit()
            connection.close()
        except Exception:
            traceback.print_exc()

    def add_partitioned_vertices(self, partitioned_graph, graph_mapper,
                                 partitionable_graph):
        """ Add the partitioned graph, graph mapper and partitionable graph \
            into the database.

        :param partitioned_graph: the partitioned graph object
        :param graph_mapper: the graph mapper object
        :param partitionable_graph: the partitionable graph object
        :return: None
        """

        # noinspection PyBroadException
        try:
            import sqlite3 as sqlite
            connection = sqlite.connect(self._database_path)
            cur = connection.cursor()
            cur.execute(
                "CREATE TABLE Partitioned_vertices("
                "vertex_id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, "
                "cpu_used INT, sdram_used INT, dtcm_used INT)")
            cur.execute(
                "CREATE TABLE Partitioned_edges("
                "edge_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "pre_vertex INTEGER, post_vertex INTEGER, label TEXT, "
                "FOREIGN KEY (pre_vertex)"
                " REFERENCES Partitioned_vertices(vertex_id), "
                "FOREIGN KEY (post_vertex)"
                " REFERENCES Partitioned_vertices(vertex_id))")
            cur.execute(
                "CREATE TABLE Partitioned_graph("
                "vertex_id INTEGER, edge_id INTEGER, "
                "PRIMARY KEY(vertex_id, edge_id), "
                "FOREIGN KEY (vertex_id)"
                " REFERENCES Partitioned_vertices(vertex_id), "
                "FOREIGN KEY (edge_id)"
                " REFERENCES Partitioned_edges(edge_id))")

            # add partitioned vertex
            for subvert in partitioned_graph.subvertices:
                cur.execute(
                    "INSERT INTO Partitioned_vertices ("
                    "label, cpu_used, sdram_used, dtcm_used) "
                    "VALUES('{}', {}, {}, {});"
                    .format(subvert.label,
                            subvert.resources_required.cpu.get_value(),
                            subvert.resources_required.sdram.get_value(),
                            subvert.resources_required.dtcm.get_value()))

            # add partitioned_edges
            subverts = list(partitioned_graph.subvertices)
            for subedge in partitioned_graph.subedges:
                cur.execute(
                    "INSERT INTO Partitioned_edges ("
                    "pre_vertex, post_vertex, label) "
                    "VALUES({}, {}, '{}');"
                    .format(subverts.index(subedge.pre_subvertex) + 1,
                            subverts.index(subedge.post_subvertex) + 1,
                            subedge.label))

            # add to partitioned graph
            edge_id_offset = 0
            subedges = list(partitioned_graph.subedges)
            for vertex in partitioned_graph.subvertices:
                edges = partitioned_graph.\
                    outgoing_subedges_from_subvertex(vertex)
                for edge in partitioned_graph.\
                        outgoing_subedges_from_subvertex(vertex):
                    cur.execute(
                        "INSERT INTO Partitioned_graph ("
                        "vertex_id, edge_id)"
                        " VALUES({}, {});"
                        .format(subverts.index(vertex) + 1,
                                subedges.index(edge) + 1 + edge_id_offset))
                edge_id_offset += len(edges)

            if partitionable_graph is not None:

                # create mapper tables
                cur.execute(
                    "CREATE TABLE graph_mapper_vertex("
                    "partitionable_vertex_id INTEGER, "
                    "partitioned_vertex_id INTEGER, lo_atom INT, hi_atom INT, "
                    "PRIMARY KEY(partitionable_vertex_id, "
                    "partitioned_vertex_id), "
                    "FOREIGN KEY (partitioned_vertex_id)"
                    " REFERENCES Partitioned_vertices(vertex_id), "
                    "FOREIGN KEY (partitionable_vertex_id)"
                    " REFERENCES Partitionable_vertices(vertex_id))")
                cur.execute(
                    "CREATE TABLE graph_mapper_edges("
                    "partitionable_edge_id INTEGER,"
                    " partitioned_edge_id INTEGER, "
                    "PRIMARY KEY(partitionable_edge_id, partitioned_edge_id), "
                    "FOREIGN KEY (partitioned_edge_id)"
                    " REFERENCES Partitioned_edges(edge_id), "
                    "FOREIGN KEY (partitionable_edge_id)"
                    " REFERENCES Partitionable_edges(edge_id))")

                # add mapper for vertices
                subverts = list(partitioned_graph.subvertices)
                vertices = partitionable_graph.vertices
                for subvert in partitioned_graph.subvertices:
                    vertex = graph_mapper.get_vertex_from_subvertex(subvert)
                    vertex_slice = graph_mapper.get_subvertex_slice(subvert)
                    cur.execute(
                        "INSERT INTO graph_mapper_vertex ("
                        "partitionable_vertex_id, partitioned_vertex_id, "
                        "lo_atom, hi_atom) "
                        "VALUES({}, {}, {}, {});"
                        .format(vertices.index(vertex) + 1,
                                subverts.index(subvert) + 1,
                                vertex_slice.lo_atom, vertex_slice.hi_atom))

                # add graph_mapper edges
                edges = partitionable_graph.edges
                for subedge in partitioned_graph.subedges:
                    edge = graph_mapper.\
                        get_partitionable_edge_from_partitioned_edge(subedge)
                    cur.execute(
                        "INSERT INTO graph_mapper_edges ("
                        "partitionable_edge_id, partitioned_edge_id) "
                        "VALUES({}, {})"
                        .format(edges.index(edge) + 1,
                                subedges.index(subedge) + 1))

            connection.commit()
            connection.close()
        except Exception:
            traceback.print_exc()

    def add_placements(self, placements, partitioned_graph):
        """ Adds the placements objects into the database

        :param placements: the placements object
        :param partitioned_graph: the partitioned graph object
        :return: None
        """

        # noinspection PyBroadException
        try:
            import sqlite3 as sqlite
            connection = sqlite.connect(self._database_path)
            cur = connection.cursor()

            # create tables
            cur.execute(
                "CREATE TABLE Placements("
                "vertex_id INTEGER PRIMARY KEY, machine_id INTEGER, "
                "chip_x INT, chip_y INT, chip_p INT, "
                "FOREIGN KEY (vertex_id) "
                "REFERENCES Partitioned_vertices(vertex_id), "
                "FOREIGN KEY (chip_x, chip_y, chip_p, machine_id) "
                "REFERENCES Processor(chip_x, chip_y, physical_id, "
                "machine_id))")

            # add records
            subverts = list(partitioned_graph.subvertices)
            for placement in placements.placements:
                cur.execute(
                    "INSERT INTO Placements("
                    "vertex_id, chip_x, chip_y, chip_p, machine_id) "
                    "VALUES({}, {}, {}, {}, {})"
                    .format(subverts.index(placement.subvertex) + 1,
                            placement.x, placement.y, placement.p,
                            self._machine_id))
            connection.commit()
            connection.close()
        except Exception:
            traceback.print_exc()

    def add_routing_infos(self, routing_infos, partitioned_graph):
        """ Adds the routing information (key masks etc) into the database

        :param routing_infos: the routing information object
        :param partitioned_graph: the partitioned graph object
        :return:
        """

        # noinspection PyBroadException
        try:
            import sqlite3 as sqlite
            connection = sqlite.connect(self._database_path)
            cur = connection.cursor()
            cur.execute(
                "CREATE TABLE Routing_info("
                "edge_id INTEGER, key INT, mask INT, "
                "PRIMARY KEY (edge_id, key, mask), "
                "FOREIGN KEY (edge_id) REFERENCES Partitioned_edges(edge_id))")

            all_subedges = list(partitioned_graph.subedges)

            for partition in partitioned_graph.partitions:
                keys_and_masks = \
                    routing_infos.get_keys_and_masks_from_partition(partition)
                sub_edges = partition.edges
                for sub_edge in sub_edges:
                    for key_mask in keys_and_masks:
                        cur.execute(
                            "INSERT INTO Routing_info("
                            "edge_id, key, mask) "
                            "VALUES({}, {}, {})"
                            .format(all_subedges.index(sub_edge) + 1,
                                    key_mask.key, key_mask.mask))
            connection.commit()
            connection.close()
        except Exception:
            traceback.print_exc()

    def add_routing_tables(self, routing_tables):
        """ Adds the routing tables into the database

        :param routing_tables: the routing tables object
        :return: None
        """

        # noinspection PyBroadException
        try:
            import sqlite3 as sqlite
            connection = sqlite.connect(self._database_path)
            cur = connection.cursor()

            cur.execute(
                "CREATE TABLE Routing_table("
                "chip_x INTEGER, chip_y INTEGER, position INTEGER, "
                "key_combo INT, mask INT, route INT, "
                "PRIMARY KEY (chip_x, chip_y, position))")

            for routing_table in routing_tables.routing_tables:
                counter = 0
                for entry in routing_table.multicast_routing_entries:
                    route_entry = 0
                    for processor_id in entry.processor_ids:
                        route_entry |= (1 << (6 + processor_id))
                    for link_id in entry.link_ids:
                        route_entry |= (1 << link_id)
                    cur.execute(
                        "INSERT INTO Routing_table("
                        "chip_x, chip_y, position, key_combo, mask, route) "
                        "VALUES({}, {}, {}, {}, {}, {})"
                        .format(routing_table.x, routing_table.y, counter,
                                entry.routing_entry_key, entry.mask,
                                route_entry))
                    counter += 1
            connection.commit()
            connection.close()
        except Exception:
            traceback.print_exc()

    def add_tags(self, partitioned_graph, tags):
        """ Adds the tags into the database

        :param partitioned_graph: the partitioned graph object
        :param tags: the tags object
        :return:
        """

        # noinspection PyBroadException
        try:
            import sqlite3 as sqlite
            connection = sqlite.connect(self._database_path)
            cur = connection.cursor()
            cur.execute(
                "CREATE TABLE IP_tags("
                "vertex_id INTEGER, tag INTEGER, "
                "board_address TEXT, ip_address TEXT, port INTEGER, "
                "strip_sdp BOOLEAN,"
                "PRIMARY KEY ("
                "vertex_id, tag, board_address, ip_address, port, strip_sdp),"
                "FOREIGN KEY (vertex_id) REFERENCES "
                "Partitioned_vertices(vertex_id))")
            cur.execute(
                "CREATE TABLE Reverse_IP_tags("
                "vertex_id INTEGER PRIMARY KEY, tag INTEGER, "
                "board_address TEXT, port INTEGER, "
                "FOREIGN KEY (vertex_id) REFERENCES "
                "Partitioned_vertices(vertex_id))")

            vertices = list(partitioned_graph.subvertices)
            for partitioned_vertex in partitioned_graph.subvertices:
                ip_tags = tags.get_ip_tags_for_vertex(partitioned_vertex)
                index = vertices.index(partitioned_vertex) + 1
                if ip_tags is not None:
                    for ip_tag in ip_tags:
                        cur.execute(
                            "INSERT INTO IP_tags(vertex_id, tag,"
                            " board_address, ip_address, port, strip_sdp)"
                            " VALUES ({}, {}, '{}', '{}', {}, {})"
                            .format(index, ip_tag.tag, ip_tag.board_address,
                                    ip_tag.ip_address, ip_tag.port,
                                    "1" if ip_tag.strip_sdp else "0"))
                reverse_ip_tags = tags.get_reverse_ip_tags_for_vertex(
                    partitioned_vertex)
                if reverse_ip_tags is not None:
                    for reverse_ip_tag in reverse_ip_tags:
                        cur.execute(
                            "INSERT INTO Reverse_IP_tags(vertex_id, tag,"
                            " board_address, port)"
                            " VALUES ({}, {}, '{}', {})"
                            .format(index, reverse_ip_tag.tag,
                                    reverse_ip_tag.board_address,
                                    reverse_ip_tag.port))
            connection.commit()
            connection.close()
        except Exception:
            traceback.print_exc()

    def create_atom_to_event_id_mapping(
            self, partitionable_graph, partitioned_graph, routing_infos,
            graph_mapper):
        """

        :param partitionable_graph:
        :param partitioned_graph:
        :param routing_infos:
        :param graph_mapper:
        :return:
        """

        # noinspection PyBroadException
        try:
            import sqlite3 as sqlite
            connection = sqlite.connect(self._database_path)
            cur = connection.cursor()

            # create table
            self._done_mapping = True
            cur.execute(
                "CREATE TABLE event_to_atom_mapping("
                "vertex_id INTEGER, atom_id INTEGER, "
                "event_id INTEGER PRIMARY KEY, "
                "FOREIGN KEY (vertex_id)"
                " REFERENCES Partitioned_vertices(vertex_id))")

            if (partitionable_graph is not None and
                    len(partitionable_graph.vertices) != 0):

                # insert into table
                vertices = list(partitionable_graph.vertices)
                for partitioned_vertex in partitioned_graph.subvertices:
                    partitions = partitioned_graph.\
                        outgoing_edges_partitions_from_vertex(
                            partitioned_vertex)
                    for partition in partitions.values():
                        routing_info = routing_infos.\
                            get_routing_info_from_partition(partition)
                        vertex = graph_mapper.get_vertex_from_subvertex(
                            partitioned_vertex)
                        vertex_id = vertices.index(vertex) + 1
                        vertex_slice = graph_mapper.get_subvertex_slice(
                            partitioned_vertex)
                        low_atom_id = vertex_slice.lo_atom
                        event_ids = routing_info.get_keys(vertex_slice.n_atoms)
                        for key in event_ids:
                            cur.execute(
                                "INSERT INTO event_to_atom_mapping("
                                "vertex_id, event_id, atom_id) "
                                "VALUES ({}, {}, {})"
                                .format(vertex_id, key, low_atom_id))
                            low_atom_id += 1
            else:
                # insert into table
                vertices = list(partitioned_graph.subvertices)
                for partitioned_vertex in partitioned_graph.subvertices:
                    out_going_partitions = partitioned_graph.\
                        outgoing_edges_partitions_from_vertex(
                            partitioned_vertex)
                    for partition in out_going_partitions.values():
                        routing_info = routing_infos.\
                            get_routing_info_from_partition(partition)
                        vertex_id = vertices.index(partitioned_vertex) + 1
                        event_ids = routing_info.get_keys()
                        for key in event_ids:
                            cur.execute(
                                "INSERT INTO event_to_atom_mapping("
                                "vertex_id, event_id, atom_id) "
                                "VALUES ({}, {}, {})"
                                .format(vertex_id, key, 0))
            connection.commit()
            connection.close()
        except Exception:
            traceback.print_exc()

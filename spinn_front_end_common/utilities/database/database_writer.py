# spinn front end common
from pacman.model.abstract_classes.abstract_has_global_max_atoms import \
    AbstractHasGlobalMaxAtoms
from spinn_front_end_common.abstract_models.\
    abstract_provides_key_to_atom_mapping import \
    AbstractProvidesKeyToAtomMapping
from spinn_front_end_common.abstract_models.abstract_recordable import \
    AbstractRecordable
from spinn_front_end_common.utility_models.\
    live_packet_gather_machine_vertex import \
    LivePacketGatherMachineVertex
from spinn_front_end_common.utility_models.\
    reverse_ip_tag_multicast_source_machine_vertex import \
    ReverseIPTagMulticastSourceMachineVertex

# general imports
import logging
import traceback
import os
import sys

logger = logging.getLogger(__name__)


class DatabaseWriter(object):
    """ The interface for the database system for main front ends.\
        Any special tables needed from a front end should be done\
        by sub classes of this interface.
    """

    __slots__ = [

        # boolean flag for when the database writer has finished
        "_done",

        # the directory of where the database is to be written
        "_database_directory",

        # the path of the database
        "_database_path",

        # the identifier for the SpiNNaker machine
        "_machine_id"
    ]

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
    def auto_detect_database(machine_graph):
        """ Auto detects if there is a need to activate the database system

        :param machine_graph: the machine graph of the application\
                problem space.
        :return: a bool which represents if the database is needed
        """
        for vertex in machine_graph.vertices:
            if (isinstance(vertex, LivePacketGatherMachineVertex) or
                    (isinstance(
                        vertex,
                        ReverseIPTagMulticastSourceMachineVertex) and
                     vertex.is_in_injection_mode)):
                return True
        else:
            return False

    @property
    def database_path(self):
        return self._database_path

    def add_machine_objects(self, machine):
        """ Store the machine object into the database

        :param machine: the machine object.
        :rtype: None
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

    def add_application_vertices(self, application_graph):
        """

        :param application_graph:
        :rtype: None
        """

        try:
            import sqlite3 as sqlite
            connection = sqlite.connect(self._database_path)
            cur = connection.cursor()
            cur.execute(
                "CREATE TABLE Application_vertices("
                "vertex_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "vertex_label TEXT, no_atoms INT, max_atom_constrant INT,"
                "recorded INT)")
            cur.execute(
                "CREATE TABLE Application_edges("
                "edge_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "pre_vertex INTEGER, post_vertex INTEGER, edge_label TEXT, "
                "FOREIGN KEY (pre_vertex)"
                " REFERENCES Application_vertices(vertex_id), "
                "FOREIGN KEY (post_vertex)"
                " REFERENCES Application_vertices(vertex_id))")
            cur.execute(
                "CREATE TABLE Application_graph("
                "vertex_id INTEGER, edge_id INTEGER, "
                "FOREIGN KEY (vertex_id) "
                "REFERENCES Application_vertices(vertex_id), "
                "FOREIGN KEY (edge_id) "
                "REFERENCES Application_edges(edge_id), "
                "PRIMARY KEY (vertex_id, edge_id))")

            # add vertices
            for vertex in application_graph.vertices:
                if isinstance(vertex, AbstractRecordable):
                    cur.execute(
                        "INSERT INTO Application_vertices("
                        "vertex_label, no_atoms, max_atom_constrant, recorded)"
                        " VALUES('{}', {}, {}, {});"
                        .format(vertex.label, vertex.n_atoms,
                                vertex.get_max_atoms_per_core(),
                                int(vertex.is_recording_spikes())))
                else:
                    if isinstance(vertex, AbstractHasGlobalMaxAtoms):
                        cur.execute(
                            "INSERT INTO Application_vertices("
                            "vertex_label, no_atoms, max_atom_constrant, "
                            "recorded) VALUES('{}', {}, {}, 0);"
                            .format(vertex.label, vertex.n_atoms,
                                    vertex.get_max_atoms_per_core()))
                    else:
                        cur.execute(
                            "INSERT INTO Application_vertices("
                            "vertex_label, no_atoms, max_atom_constrant, "
                            "recorded) VALUES('{}', {}, {}, 0);"
                            .format(vertex.label, vertex.n_atoms, sys.maxint))

            # add edges
            vertices = list(application_graph.vertices)
            edges = list(application_graph.edges)
            for vertex in application_graph.vertices:
                for edge in application_graph.\
                        get_edges_starting_at_vertex(vertex):
                    cur.execute(
                        "INSERT INTO Application_edges ("
                        "pre_vertex, post_vertex, edge_label) "
                        "VALUES({}, {}, '{}');"
                        .format(vertices.index(edge.pre_vertex) + 1,
                                vertices.index(edge.post_vertex) + 1,
                                edge.label))

            # update graph
            edge_id_offset = 0
            for vertex in application_graph.vertices:
                for edge in application_graph.\
                        get_edges_starting_at_vertex(vertex):
                    cur.execute(
                        "INSERT INTO Application_graph ("
                        "vertex_id, edge_id)"
                        " VALUES({}, {})"
                        .format(vertices.index(vertex) + 1,
                                edges.index(edge) + edge_id_offset))
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

    def add_vertices(self, machine_graph, graph_mapper, application_graph):
        """ Add the machine graph, graph mapper and application graph \
            into the database.

        :param machine_graph: the machine graph object
        :param graph_mapper: the graph mapper object
        :param application_graph: the application graph object
        :rtype: None
        """

        # noinspection PyBroadException
        try:
            import sqlite3 as sqlite
            connection = sqlite.connect(self._database_path)
            cur = connection.cursor()
            cur.execute(
                "CREATE TABLE Machine_vertices("
                "vertex_id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, "
                "cpu_used INT, sdram_used INT, dtcm_used INT)")
            cur.execute(
                "CREATE TABLE Machine_edges("
                "edge_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "pre_vertex INTEGER, post_vertex INTEGER, label TEXT, "
                "FOREIGN KEY (pre_vertex)"
                " REFERENCES Machine_vertices(vertex_id), "
                "FOREIGN KEY (post_vertex)"
                " REFERENCES Machine_vertices(vertex_id))")
            cur.execute(
                "CREATE TABLE Machine_graph("
                "vertex_id INTEGER, edge_id INTEGER, "
                "PRIMARY KEY(vertex_id, edge_id), "
                "FOREIGN KEY (vertex_id)"
                " REFERENCES Machine_vertices(vertex_id), "
                "FOREIGN KEY (edge_id)"
                " REFERENCES Machine_edges(edge_id))")

            # add machine vertex
            for vertex in machine_graph.vertices:
                cur.execute(
                    "INSERT INTO Machine_vertices ("
                    "label, cpu_used, sdram_used, dtcm_used) "
                    "VALUES('{}', {}, {}, {});"
                    .format(vertex.label,
                            vertex.resources_required.cpu_cycles.get_value(),
                            vertex.resources_required.sdram.get_value(),
                            vertex.resources_required.dtcm.get_value()))

            # add machine edges
            machine_vertices = list(machine_graph.vertices)
            machine_edges = list(machine_graph.edges)
            for edge in machine_edges:
                cur.execute(
                    "INSERT INTO Machine_edges ("
                    "pre_vertex, post_vertex, label) "
                    "VALUES({}, {}, '{}');"
                    .format(machine_vertices.index(edge.pre_vertex) + 1,
                            machine_vertices.index(edge.post_vertex) + 1,
                            edge.label))

            # add to machine graph
            for vertex in machine_graph.vertices:
                for edge in machine_graph.get_edges_starting_at_vertex(vertex):
                    cur.execute(
                        "INSERT INTO Machine_graph ("
                        "vertex_id, edge_id)"
                        " VALUES({}, {});"
                        .format(machine_vertices.index(vertex) + 1,
                                machine_edges.index(edge) + 1))

            if application_graph is not None:

                # create mapper tables
                cur.execute(
                    "CREATE TABLE graph_mapper_vertex("
                    "application_vertex_id INTEGER, "
                    "machine_vertex_id INTEGER, lo_atom INT, hi_atom INT, "
                    "PRIMARY KEY(application_vertex_id, "
                    "machine_vertex_id), "
                    "FOREIGN KEY (machine_vertex_id)"
                    " REFERENCES Machine_vertices(vertex_id), "
                    "FOREIGN KEY (application_vertex_id)"
                    " REFERENCES Application_vertices(vertex_id))")
                cur.execute(
                    "CREATE TABLE graph_mapper_edges("
                    "application_edge_id INTEGER,"
                    " machine_edge_id INTEGER, "
                    "PRIMARY KEY(application_edge_id, machine_edge_id), "
                    "FOREIGN KEY (machine_edge_id)"
                    " REFERENCES Machine_edges(edge_id), "
                    "FOREIGN KEY (application_edge_id)"
                    " REFERENCES Application_edges(edge_id))")

                # add mapper for vertex
                app_vertices = list(application_graph.vertices)
                for machine_vertex in machine_vertices:
                    app_vertex = graph_mapper.get_application_vertex(
                        machine_vertex)
                    vertex_slice = graph_mapper.get_slice(machine_vertex)
                    cur.execute(
                        "INSERT INTO graph_mapper_vertex ("
                        "application_vertex_id, machine_vertex_id, "
                        "lo_atom, hi_atom) "
                        "VALUES({}, {}, {}, {});"
                        .format(app_vertices.index(app_vertex) + 1,
                                machine_vertices.index(machine_vertex) + 1,
                                vertex_slice.lo_atom, vertex_slice.hi_atom))

                # add graph_mapper edges
                app_edges = list(application_graph.edges)
                for edge in machine_edges:
                    app_edge = graph_mapper.get_application_edge(edge)
                    cur.execute(
                        "INSERT INTO graph_mapper_edges ("
                        "application_edge_id, machine_edge_id) "
                        "VALUES({}, {})"
                        .format(machine_edges.index(edge) + 1,
                                app_edges.index(app_edge) + 1))

            connection.commit()
            connection.close()
        except Exception:
            traceback.print_exc()

    def add_placements(self, placements, machine_graph):
        """ Adds the placements objects into the database

        :param placements: the placements object
        :param machine_graph: the machine graph object
        :rtype: None
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
                "REFERENCES Machine_vertices(vertex_id), "
                "FOREIGN KEY (chip_x, chip_y, chip_p, machine_id) "
                "REFERENCES Processor(chip_x, chip_y, physical_id, "
                "machine_id))")

            # add records
            machine_vertices = list(machine_graph.vertices)
            for placement in placements.placements:
                cur.execute(
                    "INSERT INTO Placements("
                    "vertex_id, chip_x, chip_y, chip_p, machine_id) "
                    "VALUES({}, {}, {}, {}, {})"
                    .format(machine_vertices.index(placement.vertex) + 1,
                            placement.x, placement.y, placement.p,
                            self._machine_id))
            connection.commit()
            connection.close()
        except Exception:
            traceback.print_exc()

    def add_routing_infos(self, routing_infos, machine_graph):
        """ Adds the routing information (key masks etc) into the database

        :param routing_infos: the routing information object
        :param machine_graph: the machine graph object
        :rtype: None:
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
                "FOREIGN KEY (edge_id) REFERENCES Machine_edges(edge_id))")

            all_edges = list(machine_graph.edges)

            for partition in machine_graph.outgoing_edge_partitions:
                rinfo = routing_infos.get_routing_info_from_partition(
                    partition)
                for edge in partition.edges:
                    for key_mask in rinfo.keys_and_masks:
                        cur.execute(
                            "INSERT INTO Routing_info("
                            "edge_id, key, mask) "
                            "VALUES({}, {}, {})"
                            .format(all_edges.index(edge) + 1,
                                    key_mask.key, key_mask.mask))
            connection.commit()
            connection.close()
        except Exception:
            traceback.print_exc()

    def add_routing_tables(self, routing_tables):
        """ Adds the routing tables into the database

        :param routing_tables: the routing tables object
        :rtype: None
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

    def add_tags(self, machine_graph, tags):
        """ Adds the tags into the database

        :param machine_graph: the machine graph object
        :param tags: the tags object
        :rtype: None
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
                "Machine_vertices(vertex_id))")
            cur.execute(
                "CREATE TABLE Reverse_IP_tags("
                "vertex_id INTEGER PRIMARY KEY, tag INTEGER, "
                "board_address TEXT, port INTEGER, "
                "FOREIGN KEY (vertex_id) REFERENCES "
                "Machine_vertices(vertex_id))")

            vertices = list(machine_graph.vertices)
            for vertex in machine_graph.vertices:
                ip_tags = tags.get_ip_tags_for_vertex(vertex)
                index = vertices.index(vertex) + 1
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
                    vertex)
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
            self, application_graph, machine_graph, routing_infos,
            graph_mapper):
        """

        :param application_graph:
        :param machine_graph:
        :param routing_infos:
        :param graph_mapper:
        :rtype: None
        """

        # noinspection PyBroadException
        try:
            import sqlite3 as sqlite
            connection = sqlite.connect(self._database_path)
            cur = connection.cursor()

            # create table
            cur.execute(
                "CREATE TABLE event_to_atom_mapping("
                "vertex_id INTEGER, atom_id INTEGER, "
                "event_id INTEGER PRIMARY KEY, "
                "FOREIGN KEY (vertex_id)"
                " REFERENCES Machine_vertices(vertex_id))")

            if (application_graph is not None and
                    application_graph.n_vertices != 0):

                # insert into table
                vertices = list(application_graph.vertices)
                for vertex in machine_graph.vertices:
                    partitions = machine_graph.\
                        get_outgoing_edge_partitions_starting_at_vertex(
                            vertex)
                    for partition in partitions:
                        routing_info = routing_infos.\
                            get_routing_info_from_partition(partition)
                        app_vertex = graph_mapper.get_application_vertex(
                            vertex)
                        vertex_id = vertices.index(app_vertex) + 1
                        self._insert_vertex_atom_to_key_map(
                            app_vertex, partition, vertex_id, routing_info,
                            cur)
            else:
                # insert into table
                vertices = list(machine_graph.vertices)
                for vertex in machine_graph.vertices:
                    out_going_partitions = machine_graph.\
                        get_outgoing_edge_partitions_starting_at_vertex(
                            vertex)
                    for partition in out_going_partitions:
                        routing_info = routing_infos.\
                            get_routing_info_from_partition(partition)
                        vertex_id = vertices.index(vertex) + 1
                        self._insert_vertex_atom_to_key_map(
                            vertex, partition, vertex_id, routing_info, cur)

            connection.commit()
            connection.close()
        except Exception:
            traceback.print_exc()

    @staticmethod
    def _insert_vertex_atom_to_key_map(
            vertex, partition, vertex_id, routing_info, cur):
        """

        :param vertex:
        :param partition:
        :param vertex_id:
        :param routing_info:
        :param cur:
        :return:
        """
        if isinstance(vertex, AbstractProvidesKeyToAtomMapping):
            mapping = vertex.routing_key_partition_atom_mapping(
                routing_info, partition)
            for (atom_id, key) in mapping:
                cur.execute(
                    "INSERT INTO event_to_atom_mapping("
                    "vertex_id, event_id, atom_id) "
                    "VALUES ({}, {}, {})".format(vertex_id, key, atom_id))

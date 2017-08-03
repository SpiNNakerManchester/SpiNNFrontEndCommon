# spinn front end common
from pacman.model.abstract_classes import AbstractHasGlobalMaxAtoms
from spinn_front_end_common.abstract_models \
    import AbstractProvidesKeyToAtomMapping, AbstractRecordable, \
    AbstractSupportsDatabaseInjection

# general imports
import logging
import os
import sqlite3
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

        # the path of the initialisation SQL
        "_init_sql_path",

        # the identifier for the SpiNNaker machine
        "_machine_id",

        # the database connection itself
        "_connection",

        # Mappings used to accelerate inserts
        "_machine_to_id", "_vertex_to_id", "_edge_to_id"
    ]

    def __init__(self, database_directory):
        self._done = False
        self._database_directory = database_directory
        self._database_path = os.path.join(
            self._database_directory, "input_output_database.db")
        self._init_sql_path = os.path.join(
            os.path.dirname(__file__), "db.sql")
        self._connection = None
        self._machine_to_id = dict()
        self._vertex_to_id = dict()
        self._edge_to_id = dict()

        # delete any old database
        if os.path.isfile(self._database_path):
            os.remove(self._database_path)

        # set up checks
        self._machine_id = 0

    def __enter__(self):
        self._connection = sqlite3.connect(self._database_path)
        self.create_schema()
        return self
         
    def __exit__(self, exc_type, exc_val, exc_tb):  # @UnusedVariable
        self._connection.close()
        self._connection = None
        return False

    @staticmethod
    def auto_detect_database(machine_graph):
        """ Auto detects if there is a need to activate the database system

        :param machine_graph: the machine graph of the application\
                problem space.
        :return: a bool which represents if the database is needed
        """
        for vertex in machine_graph.vertices:
            if (isinstance(vertex, AbstractSupportsDatabaseInjection) and
                    vertex.is_in_injection_mode):
                return True
        else:
            return False

    @property
    def database_path(self):
        return self._database_path

    def _ins(self, sql, *args):
        c = self._connection.cursor()
        c.execute(sql, args)
        return c.lastrowid

    def create_schema(self):
        with self._connection, open(self._init_sql_path) as f:
            sql = f.read()
            self._connection.executescript(sql)

    def add_machine_objects(self, machine):
        """ Store the machine object into the database

        :param machine: the machine object.
        :rtype: None
        """
        with self._connection:
            x_di = machine.max_chip_x + 1
            y_di = machine.max_chip_y + 1
            self._machine_to_id[machine] = self._ins(
                "INSERT INTO Machine_layout("
                "  x_dimension, y_dimension) "
                "VALUES(?, ?)", x_di, y_di)
            self._machine_id += 1
            for chip in machine.chips:
                self._ins(
                    "INSERT INTO Machine_chip("
                    "  no_processors, chip_x, chip_y, machine_id) "
                    "VALUES (?, ?, ?, ?)",
                    len(list(chip.processors)), chip.x, chip.y,
                    self._machine_id)
                for processor in chip.processors:
                    self._ins(
                        "INSERT INTO Processor("
                        "  chip_x, chip_y, machine_id, available_DTCM, "
                        "  available_CPU, physical_id) "
                        "VALUES(?, ?, ?, ?, ?, ?)",
                        chip.x, chip.y, self._machine_id,
                        processor.dtcm_available,
                        processor.cpu_cycles_available,
                        processor.processor_id)

    def add_application_vertices(self, application_graph):
        """

        :param application_graph:
        :rtype: None
        """
        with self._connection:
            # add vertices
            for vertex in application_graph.vertices:
                if isinstance(vertex, AbstractRecordable):
                    self._vertex_to_id[vertex] = self._insert_app_vertex(
                        vertex, vertex.get_max_atoms_per_core(),
                        vertex.is_recording_spikes())
                elif isinstance(vertex, AbstractHasGlobalMaxAtoms):
                    self._vertex_to_id[vertex] = self._insert_app_vertex(
                        vertex, vertex.get_max_atoms_per_core(), 0)
                else:
                    self._vertex_to_id[vertex] = self._insert_app_vertex(
                        vertex, sys.maxint, 0)

            # add edges
            for vertex in application_graph.vertices:
                for edge in application_graph.\
                        get_edges_starting_at_vertex(vertex):
                    self._edge_to_id[edge] = self._ins(
                        "INSERT INTO Application_edges ("
                        "  pre_vertex, post_vertex, edge_label) "
                        "VALUES(?, ?, ?)",
                        self._vertex_to_id[edge.pre_vertex],
                        self._vertex_to_id[edge.post_vertex],
                        edge.label)

            # update graph
            for vertex in application_graph.vertices:
                for edge in application_graph.\
                        get_edges_starting_at_vertex(vertex):
                    self._ins(
                        "INSERT INTO Application_graph ("
                        "  vertex_id, edge_id) "
                        "VALUES(?, ?)",
                        self._vertex_to_id[vertex],
                        self._edge_to_id[edge])

    def _insert_app_vertex(self, vertex, max_atoms, is_recording):
        return self._ins(
            "INSERT INTO Application_vertices("
            "  vertex_label, no_atoms, max_atom_constrant, recorded) "
            "VALUES(?, ?, ?, ?)",
            vertex.label, vertex.n_atoms, max_atoms, int(is_recording))

    def add_system_params(self, time_scale_factor, machine_time_step, runtime):
        """ Write system params into the database

        :param time_scale_factor: the time scale factor used in timing
        :param machine_time_step: the machine time step used in timing
        :param runtime: the amount of time the application is to run for
        """
        with self._connection:
            self._insert_cfg("machine_time_step", machine_time_step)
            self._insert_cfg("time_scale_factor", time_scale_factor)
            if runtime is not None:
                self._insert_cfg("infinite_run", "False")
                self._insert_cfg("runtime", runtime)
            else:
                self._insert_cfg("infinite_run", "True")
                self._insert_cfg("runtime", -1)

    def _insert_cfg(self, parameter_id, value):
        self._ins(
            "INSERT INTO configuration_parameters ("
            "  parameter_id, value) "
            "VALUES (?, ?)",
            parameter_id, value)

    def add_vertices(self, machine_graph, graph_mapper, application_graph):
        """ Add the machine graph, graph mapper and application graph \
            into the database.

        :param machine_graph: the machine graph object
        :param graph_mapper: the graph mapper object
        :param application_graph: the application graph object
        :rtype: None
        """
        with self._connection:
            for vertex in machine_graph.vertices:
                self._vertex_to_id[vertex] = self._ins(
                    "INSERT INTO Machine_vertices ("
                    "  label, cpu_used, sdram_used, dtcm_used) "
                    "VALUES(?, ?, ?, ?)",
                    vertex.label,
                    vertex.resources_required.cpu_cycles.get_value(),
                    vertex.resources_required.sdram.get_value(),
                    vertex.resources_required.dtcm.get_value())

            # add machine edges
            for edge in machine_graph.edges:
                self._ins(
                    "INSERT INTO Machine_edges ("
                    "  pre_vertex, post_vertex, label) "
                    "VALUES(?, ?, ?)",
                    self._vertex_to_id[edge.pre_vertex],
                    self._vertex_to_id[edge.post_vertex], edge.label)

            # add to machine graph
            for vertex in machine_graph.vertices:
                for edge in machine_graph.get_edges_starting_at_vertex(vertex):
                    self._ins(
                        "INSERT INTO Machine_graph ("
                        "  vertex_id, edge_id) "
                        "VALUES(?, ?)",
                        self._vertex_to_id[vertex], self._edge_to_id[edge])

            if application_graph is not None:
                for machine_vertex in machine_graph.vertices:
                    app_vertex = graph_mapper.get_application_vertex(
                        machine_vertex)
                    vertex_slice = graph_mapper.get_slice(machine_vertex)
                    self._ins(
                        "INSERT INTO graph_mapper_vertex ("
                        "  application_vertex_id, machine_vertex_id, "
                        "  lo_atom, hi_atom) "
                        "VALUES(?, ?, ?, ?)",
                        self._vertex_to_id[app_vertex],
                        self._vertex_to_id[machine_vertex],
                        vertex_slice.lo_atom, vertex_slice.hi_atom)

                # add graph_mapper edges
                for edge in machine_graph.edges:
                    app_edge = graph_mapper.get_application_edge(edge)
                    self._ins(
                        "INSERT INTO graph_mapper_edges ("
                        "  application_edge_id, machine_edge_id) "
                        "VALUES(?, ?)",
                        self._edge_to_id[edge], self._edge_to_id[app_edge])

    def add_placements(self, placements):
        """ Adds the placements objects into the database

        :param placements: the placements object
        :param machine_graph: the machine graph object
        :rtype: None
        """
        with self._connection:
            # add records
            for placement in placements.placements:
                self._ins(
                    "INSERT INTO Placements("
                    "  vertex_id, chip_x, chip_y, chip_p, machine_id) "
                    "VALUES(?, ?, ?, ?, ?)",
                    self._vertex_to_id[placement.vertex],
                    placement.x, placement.y, placement.p, self._machine_id)

    def add_routing_infos(self, routing_infos, machine_graph):
        """ Adds the routing information (key masks etc) into the database

        :param routing_infos: the routing information object
        :param machine_graph: the machine graph object
        :rtype: None:
        """
        with self._connection:
            for partition in machine_graph.outgoing_edge_partitions:
                rinfo = routing_infos.get_routing_info_from_partition(
                    partition)
                for edge in partition.edges:
                    for key_mask in rinfo.keys_and_masks:
                        self._ins(
                            "INSERT INTO Routing_info("
                            "  edge_id, \"key\", mask) "
                            "VALUES(?, ?, ?)",
                            self._edge_to_id[edge],
                            key_mask.key, key_mask.mask)

    def add_routing_tables(self, routing_tables):
        """ Adds the routing tables into the database

        :param routing_tables: the routing tables object
        :rtype: None
        """
        with self._connection:
            for routing_table in routing_tables.routing_tables:
                for counter, entry in \
                        enumerate(routing_table.multicast_routing_entries):
                    route_entry = 0
                    for processor_id in entry.processor_ids:
                        route_entry |= 1 << (6 + processor_id)
                    for link_id in entry.link_ids:
                        route_entry |= 1 << link_id
                    self._ins(
                        "INSERT INTO Routing_table("
                        "  chip_x, chip_y, position, key_combo, mask, route) "
                        "VALUES(?, ?, ?, ?, ?, ?)",
                        routing_table.x, routing_table.y, counter,
                        entry.routing_entry_key, entry.mask, route_entry)

    def add_tags(self, machine_graph, tags):
        """ Adds the tags into the database

        :param machine_graph: the machine graph object
        :param tags: the tags object
        :rtype: None
        """
        with self._connection:
            for vertex in machine_graph.vertices:
                vertex_id = self._vertex_to_id[vertex]
                ip_tags = tags.get_ip_tags_for_vertex(vertex)
                if ip_tags is not None:
                    for ip_tag in ip_tags:
                        self._ins(
                            "INSERT INTO IP_tags("
                            "  vertex_id, tag, board_address, ip_address,"
                            "  port, strip_sdp) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            vertex_id, ip_tag.tag, ip_tag.board_address,
                            ip_tag.ip_address, ip_tag.port,
                            1 if ip_tag.strip_sdp else 0)
                reverse_ip_tags = tags.get_reverse_ip_tags_for_vertex(
                    vertex)
                if reverse_ip_tags is not None:
                    for reverse_ip_tag in reverse_ip_tags:
                        self._ins(
                            "INSERT INTO Reverse_IP_tags("
                            "  vertex_id, tag, board_address, port) "
                            "VALUES (?, ?, ?, ?)",
                            vertex_id, reverse_ip_tag.tag,
                            reverse_ip_tag.board_address,
                            reverse_ip_tag.port)

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
        have_app_graph = (application_graph is not None and
                          application_graph.n_vertices != 0)
        with self._connection:
            for vertex in machine_graph.vertices:
                for partition in machine_graph.\
                        get_outgoing_edge_partitions_starting_at_vertex(
                            vertex):
                    if have_app_graph:
                        self._insert_vertex_atom_to_key_map(
                            graph_mapper.get_application_vertex(vertex),
                            partition, routing_infos)
                    else:
                        self._insert_vertex_atom_to_key_map(
                            vertex, partition, routing_infos)

    def _insert_vertex_atom_to_key_map(
            self, vertex, partition, routing_infos):
        """

        :param vertex:
        :param partition:
        :param routing_infos:
        :rtype: None
        """
        if isinstance(vertex, AbstractProvidesKeyToAtomMapping):
            vertex_id = self._vertex_to_id[vertex]
            routing_info = routing_infos.get_routing_info_from_partition(
                partition)
            for atom_id, key in vertex.routing_key_partition_atom_mapping(
                    routing_info, partition):
                self._ins(
                    "INSERT INTO event_to_atom_mapping("
                    "  vertex_id, event_id, atom_id) "
                    "VALUES (?, ?, ?)",
                    vertex_id, key, atom_id)

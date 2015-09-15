"""
FrontEndCommonDataBaseInterface
"""

# front end common imports imports
from spinn_front_end_common.utilities.notification_protocol.\
    notification_protocol import NotificationProtocol

# general imports
from multiprocessing.pool import ThreadPool
import threading
import os
import logging
import traceback


logger = logging.getLogger(__name__)


class DatabaseWriter(object):
    """
    DatabaseWriter: the interface for the database system for
    main front ends, any speical tables needed from a front end should be done
    by sub classes of this interface.
    """

    def __init__(self, database_directory, wait_for_read_confirmation,
                 socket_addresses):

        # notification protocol
        self._notification_protocol = \
            NotificationProtocol(socket_addresses, wait_for_read_confirmation)

        self._done = False
        self._database_directory = database_directory
        self._database_path = os.path.join(self._database_directory,
                                           "input_output_database.db")

        # Thread pools
        self._thread_pool = ThreadPool(processes=1)

        # set up checks
        self._machine_id = 0
        self._lock_condition = threading.Condition()

    def add_machine_objects(self, machine):
        """
        stores the machine object into the database
        :param machine: the machine object.
        :return: None
        """
        self._thread_pool.apply_async(self._add_machine, args=[machine])

    def _add_machine(self, machine):
        # noinspection PyBroadException
        try:
            import sqlite3 as sqlite
            self._lock_condition.acquire()
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
            self._lock_condition.release()
        except Exception:
            traceback.print_exc()

    def wait_for_confirmation(self):
        """
        helper method which waits for devices to confirm they have read the
        databse via the notifiication protocol
        :return:
        """
        self._notification_protocol.wait_for_confirmation()

    def send_read_notification(self):
        """
        helper method for sending the read notifcations from the notification
        protocol
        :return:
        """
        # syncorise when the database is written
        self._thread_pool.close()
        self._thread_pool.join()
        self._notification_protocol.send_read_notification(self._database_path)

    def send_start_notification(self):
        """
        helper method for sending the start notifcations from the notification
        protocol
        :return:
        """
        self._notification_protocol.send_start_notification()

    def add_system_params(self, time_scale_factor, machine_time_step, runtime):
        """
        writes system params into the database
        :param time_scale_factor: the time scale factor used in timing
        :param machine_time_step: the machien time step used in timing
        :param runtime: the amount of time the application is to run for
        :return: Nonw
        """
        self._thread_pool.apply_async(
            self._add_system_params,
            args=[time_scale_factor, machine_time_step, runtime])

    def _add_system_params(self, time_scale_factor, machine_time_step,
                           runtime):
        # noinspection PyBroadException
        try:
            import sqlite3 as sqlite
            self._lock_condition.acquire()
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
            self._lock_condition.release()
        except Exception:
            traceback.print_exc()

    def add_partitioned_vertices(self, partitioned_graph, graph_mapper,
                                 partitionable_graph):
        """
        writes the partitioned graph, graphmapper into the database. linsk
        to the partitionable graph
        :param partitioned_graph: the partitioned graph object
        :param graph_mapper: the graph mapper object
        :param partitionable_graph: the partitionable graph object
        :return: None
        """
        self._thread_pool.apply_async(self._add_partitioned_vertices,
                                      args=[partitioned_graph, graph_mapper,
                                            partitionable_graph])

    def _add_partitioned_vertices(self, partitioned_graph, graph_mapper,
                                  partitionable_graph):
        # noinspection PyBroadException
        try:
            self._lock_condition.acquire()
            import sqlite3 as sqlite
            self._lock_condition.acquire()
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

            # create mapper tables
            cur.execute(
                "CREATE TABLE graph_mapper_vertex("
                "partitionable_vertex_id INTEGER, "
                "partitioned_vertex_id INTEGER, lo_atom INT, hi_atom INT, "
                "PRIMARY KEY(partitionable_vertex_id, partitioned_vertex_id), "
                "FOREIGN KEY (partitioned_vertex_id)"
                " REFERENCES Partitioned_vertices(vertex_id), "
                "FOREIGN KEY (partitionable_vertex_id)"
                " REFERENCES Partitionable_vertices(vertex_id))")
            cur.execute(
                "CREATE TABLE graph_mapper_edges("
                "partitionable_edge_id INTEGER, partitioned_edge_id INTEGER, "
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
                    "partitionable_vertex_id, partitioned_vertex_id, lo_atom, "
                    "hi_atom) "
                    "VALUES({}, {}, {}, {});"
                    .format(vertices.index(vertex) + 1,
                            subverts.index(subvert) + 1,
                            vertex_slice.lo_atom, vertex_slice.hi_atom))

            # add partitioned_edges
            for subedge in partitioned_graph.subedges:
                cur.execute(
                    "INSERT INTO Partitioned_edges ("
                    "pre_vertex, post_vertex, label) "
                    "VALUES({}, {}, '{}');"
                    .format(subverts.index(subedge.pre_subvertex) + 1,
                            subverts.index(subedge.post_subvertex) + 1,
                            subedge.label))

            # add graph_mapper edges
            subedges = list(partitioned_graph.subedges)
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

            # add to partitioned graph
            edge_id_offset = 0
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
            connection.commit()
            connection.close()
            self._lock_condition.release()
        except Exception:
            traceback.print_exc()

    def add_placements(self, placements, partitioned_graph):
        """
        writes the placements objects itno the database
        :param placements: the placements object
        :param partitioned_graph: the partitioned graph object
        :return: None
        """
        self._thread_pool.apply_async(self._add_placements,
                                      args=[placements, partitioned_graph])

    def _add_placements(self, placements, partitioned_graph):
        # noinspection PyBroadException
        try:
            self._lock_condition.acquire()
            import sqlite3 as sqlite
            self._lock_condition.acquire()
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
            self._lock_condition.release()
        except Exception:
            traceback.print_exc()

    def add_routing_infos(self, routing_infos, partitioned_graph):
        """
        writes the routing infos (key masks etc) into the database
        :param routing_infos: the routing infos object
        :param partitioned_graph: the partitioned graph object
        :return:
        """
        self._thread_pool.apply_async(self._add_routing_infos,
                                      args=[routing_infos, partitioned_graph])

    def _add_routing_infos(self, routing_infos, partitioned_graph):
        # noinspection PyBroadException
        try:
            self._lock_condition.acquire()
            import sqlite3 as sqlite
            self._lock_condition.acquire()
            connection = sqlite.connect(self._database_path)
            cur = connection.cursor()
            cur.execute(
                "CREATE TABLE Routing_info("
                "edge_id INTEGER, key INT, mask INT, "
                "PRIMARY KEY (edge_id, key, mask), "
                "FOREIGN KEY (edge_id) REFERENCES Partitioned_edges(edge_id))")

            sub_edges = list(partitioned_graph.subedges)
            for routing_info in routing_infos.all_subedge_info:
                for key_mask in routing_info.keys_and_masks:
                    cur.execute(
                        "INSERT INTO Routing_info("
                        "edge_id, key, mask) "
                        "VALUES({}, {}, {})"
                        .format(sub_edges.index(routing_info.subedge) + 1,
                                key_mask.key, key_mask.mask))
            connection.commit()
            connection.close()
            self._lock_condition.release()
        except Exception:
            traceback.print_exc()

    def add_routing_tables(self, routing_tables):
        """ loads the routing tbales into the database

        :param routing_tables: the routing tables object to be wrirten
        to the database
        :return: None
        """
        self._thread_pool.apply_async(self._add_routing_tables,
                                      args=[routing_tables])

    def _add_routing_tables(self, routing_tables):
        # noinspection PyBroadException
        try:
            self._lock_condition.acquire()
            import sqlite3 as sqlite
            self._lock_condition.acquire()
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
                                entry.key_combo, entry.mask, route_entry))
                    counter += 1
            connection.commit()
            connection.close()
            self._lock_condition.release()
        except Exception:
            traceback.print_exc()

    def add_tags(self, partitioned_graph, tags):
        """ loads the tags into the database

        :param partitioned_graph: the partitioned grapg object
        :param tags: the tags object
        :return:
        """
        self._thread_pool.apply_async(self._add_tags,
                                      args=[partitioned_graph, tags])

    def _add_tags(self, partitioned_graph, tags):
        # noinspection PyBroadException
        try:
            self._lock_condition.acquire()
            import sqlite3 as sqlite
            self._lock_condition.acquire()
            connection = sqlite.connect(self._database_path)
            cur = connection.cursor()
            cur.execute(
                "CREATE TABLE IP_tags("
                "vertex_id INTEGER PRIMARY KEY, tag INTEGER, "
                "board_address TEXT, ip_address TEXT, port INTEGER, "
                "strip_sdp BOOLEAN,"
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
            self._lock_condition.release()
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
        self._thread_pool.apply_async(
            self._create_atom_to_event_id_mapping,
            args=[partitionable_graph, partitioned_graph, routing_infos,
                  graph_mapper])

    def _create_atom_to_event_id_mapping(
            self, partitionable_graph, partitioned_graph, routing_infos,
            graph_mapper):
        # noinspection PyBroadException
        try:
            import sqlite3 as sqlite
            self._lock_condition.acquire()
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

            # insert into table
            vertices = list(partitionable_graph.vertices)
            for partitioned_vertex in partitioned_graph.subvertices:
                out_going_edges = (partitioned_graph
                                   .outgoing_subedges_from_subvertex(
                                       partitioned_vertex))
                if len(out_going_edges) > 0:
                    routing_info = (routing_infos
                                    .get_subedge_information_from_subedge(
                                        out_going_edges[0]))
                    vertex = graph_mapper.get_vertex_from_subvertex(
                        partitioned_vertex)
                    vertex_id = vertices.index(vertex) + 1
                    vertex_slice = graph_mapper.get_subvertex_slice(
                        partitioned_vertex)
                    event_ids = routing_info.get_keys(vertex_slice.n_atoms)
                    low_atom_id = vertex_slice.lo_atom
                    for key in event_ids:
                        cur.execute(
                            "INSERT INTO event_to_atom_mapping("
                            "vertex_id, event_id, atom_id) "
                            "VALUES ({}, {}, {})"
                            .format(vertex_id, key, low_atom_id))
                        low_atom_id += 1
            connection.commit()
            connection.close()
            self._lock_condition.release()
        except Exception:
            traceback.print_exc()

    def stop(self):
        """
        ends the nofitication protocol
        :return:
        """
        logger.debug("[data_base_thread] Stopping")
        self._notification_protocol.close()

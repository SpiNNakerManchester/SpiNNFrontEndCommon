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

import logging
import os
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.utilities.sqlite_db import SQLiteDB
from spinn_front_end_common.abstract_models import (
    AbstractProvidesKeyToAtomMapping,
    AbstractSupportsDatabaseInjection)
from spinn_front_end_common.utilities.globals_variables import (
    machine_time_step, report_default_directory, time_scale_factor)

logger = FormatAdapter(logging.getLogger(__name__))
DB_NAME = "input_output_database.sqlite3"
INIT_SQL = "db.sql"


def _extract_int(x):
    return None if x is None else int(x)


class DatabaseWriter(SQLiteDB):
    """ The interface for the database system for main front ends.\
        Any special tables needed from a front end should be done\
        by sub classes of this interface.
    """

    __slots__ = [
        # the path of the database
        "_database_path",

        # the identifier for the SpiNNaker machine
        "_machine_id",

        # Mappings used to accelerate inserts
        "__machine_to_id", "__vertex_to_id", "__edge_to_id"
    ]

    def __init__(self):
        self._database_path = os.path.join(report_default_directory(), DB_NAME)
        init_sql_path = os.path.join(os.path.dirname(__file__), INIT_SQL)

        # delete any old database
        if os.path.isfile(self._database_path):
            os.remove(self._database_path)

        super().__init__(self._database_path, ddl_file=init_sql_path)
        self.__machine_to_id = dict()
        self.__vertex_to_id = dict()
        self.__edge_to_id = dict()

        # set up checks
        self._machine_id = 0

    @staticmethod
    def auto_detect_database(app_graph):
        """ Auto detects if there is a need to activate the database system

        :param ~pacman.model.graphs.application.ApplicationGraph app_graph:
            the graph of the application problem space.
        :return: whether the database is needed for the application
        :rtype: bool
        """
        return any(isinstance(vertex, AbstractSupportsDatabaseInjection)
                   and vertex.is_in_injection_mode
                   for app_vertex in app_graph.vertices
                   for vertex in app_vertex.machine_vertices)

    @property
    def database_path(self):
        """
        :rtype: str
        """
        return self._database_path

    def __insert(self, cur, sql, *args):
        """
        :param ~sqlite3.Cursor cur:
        :param str sql:
        :rtype: int
        """
        try:
            cur.execute(sql, args)
            return cur.lastrowid
        except Exception:
            logger.exception("problem with insertion; argument types are {}",
                             str(map(type, args)))
            raise

    def add_machine_objects(self, machine):
        """ Store the machine object into the database

        :param ~spinn_machine.Machine machine: the machine object.
        """
        with self.transaction() as cur:
            self.__machine_to_id[machine] = self._machine_id = self.__insert(
                cur,
                """
                INSERT INTO Machine_layout(
                    x_dimension, y_dimension)
                VALUES(?, ?)
                """, machine.width, machine.height)
            cur.executemany(
                """
                INSERT INTO Machine_chip(
                    no_processors, chip_x, chip_y, machine_id)
                VALUES (?, ?, ?, ?)
                """, (
                    (chip.n_processors, chip.x, chip.y, self._machine_id)
                    for chip in machine.chips if chip.virtual))
            cur.executemany(
                """
                INSERT INTO Machine_chip(
                    no_processors, chip_x, chip_y, machine_id,
                    ip_address, nearest_ethernet_x, nearest_ethernet_y)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    (chip.n_processors, chip.x, chip.y, self._machine_id,
                     chip.ip_address,
                     chip.nearest_ethernet_x, chip.nearest_ethernet_y)
                    for chip in machine.chips if not chip.virtual))
            cur.executemany(
                """
                INSERT INTO Processor(
                    chip_x, chip_y, machine_id, available_DTCM,
                    available_CPU, physical_id)
                VALUES(?, ?, ?, ?, ?, ?)
                """, (
                    (chip.x, chip.y, self._machine_id, proc.dtcm_available,
                     proc.cpu_cycles_available, proc.processor_id)
                    for chip in machine.chips
                    for proc in chip.processors))

    def add_application_vertices(self, application_graph, data_n_timesteps):
        """ Stores the main application graph description (vertices, edges).

        :param application_graph: The graph to add from
        :type application_graph:
            ~pacman.model.graphs.application.ApplicationGraph
        """
        with self.transaction() as cur:
            # add vertices
            for vertex in application_graph.vertices:
                vertex_id = self.__insert(
                    cur,
                    """
                    INSERT INTO Application_vertices(
                        vertex_label, vertex_class, no_atoms,
                        max_atom_constrant)
                    VALUES(?, ?, ?, ?)
                    """,
                    vertex.label, vertex.__class__.__name__, vertex.n_atoms,
                    vertex.get_max_atoms_per_core())
                self.__vertex_to_id[vertex] = vertex_id
                for m_vertex in vertex.machine_vertices:
                    req = m_vertex.resources_required
                    m_vertex_id = self.__insert(
                        cur,
                        """
                        INSERT INTO Machine_vertices (
                            label, class, cpu_used, sdram_used, dtcm_used)
                        VALUES(?, ?, ?, ?, ?)
                        """,
                        str(m_vertex.label), m_vertex.__class__.__name__,
                        _extract_int(req.cpu_cycles.get_value()),
                        _extract_int(req.sdram.get_total_sdram(
                            data_n_timesteps)),
                        _extract_int(req.dtcm.get_value()))
                    self.__vertex_to_id[m_vertex] = m_vertex_id
                    self.__insert(
                        """
                        INSERT INTO graph_mapper_vertex (
                            application_vertex_id, machine_vertex_id, lo_atom,
                            hi_atom)
                        VALUES(?, ?, ?, ?)
                        """,
                        vertex_id, m_vertex_id, m_vertex.vertex_slice.lo_atom,
                        m_vertex.vertex_slice.hi_atom)

            # add edges
            for edge in application_graph.edges:
                self.__edge_to_id[edge] = self.__insert(
                    cur,
                    """
                    INSERT INTO Application_edges (
                        pre_vertex, post_vertex, edge_label, edge_class)
                    VALUES(?, ?, ?, ?)
                    """,
                    self.__vertex_to_id[edge.pre_vertex],
                    self.__vertex_to_id[edge.post_vertex],
                    edge.label, edge.__class__.__name__)

            # update graph
            cur.executemany(
                """
                INSERT INTO Application_graph (
                    vertex_id, edge_id)
                VALUES(?, ?)
                """, (
                    (self.__vertex_to_id[vertex], self.__edge_to_id[edge])
                    for vertex in application_graph.vertices
                    for edge in application_graph.get_edges_starting_at_vertex(
                        vertex)))

    def add_system_params(self, runtime, app_id):
        """ Write system params into the database

        :param int runtime: the amount of time the application is to run for
        """
        with self.transaction() as cur:
            cur.executemany(
                """
                INSERT INTO configuration_parameters (
                    parameter_id, value)
                VALUES (?, ?)
                """, [
                    ("machine_time_step", machine_time_step()),
                    ("time_scale_factor", time_scale_factor()),
                    ("infinite_run", str(runtime is None)),
                    ("runtime", -1 if runtime is None else runtime),
                    ("app_id", app_id)])

    def add_placements(self, placements):
        """ Adds the placements objects into the database

        :param ~pacman.model.placements.Placements placements:
            the placements object
        """
        with self.transaction() as cur:
            # add records
            cur.executemany(
                """
                INSERT INTO Placements(
                    vertex_id, chip_x, chip_y, chip_p, machine_id)
                VALUES(?, ?, ?, ?, ?)
                """, (
                    (self.__vertex_to_id[placement.vertex],
                     placement.x, placement.y, placement.p, self._machine_id)
                    for placement in placements.placements))

    def add_routing_infos(self, routing_infos, app_graph):
        """ Adds the routing information (key masks etc) into the database

        :param ~pacman.model.routing_info.RoutingInfo routing_infos:
            the routing information object
        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
            the machine graph object
        """
        with self.transaction() as cur:
            cur.executemany(
                """
                INSERT INTO Routing_info(
                    pre_vertex_id, partition_id, "key", mask)
                VALUES(?, ?, ?)
                """, (
                    (self.__vertex_to_id[vertex],
                     partition.identifier, key_mask.key, key_mask.mask)
                    for partition in app_graph.outgoing_edge_partitions
                    for vertex in partition.pre_vertex.machine_vertices
                    for key_mask in routing_infos
                    .get_routing_info_from_pre_vertex(
                        vertex, partition.identifier)))

    def add_routing_tables(self, routing_tables):
        """ Adds the routing tables into the database

        :param routing_tables: the routing tables object
        :type routing_tables:
            ~pacman.model.routing_tables.MulticastRoutingTables
        """
        with self.transaction() as cur:
            cur.executemany(
                """
                INSERT INTO Routing_table(
                    chip_x, chip_y, position, key_combo, mask, route)
                VALUES(?, ?, ?, ?, ?, ?)
                """, (
                    (routing_table.x, routing_table.y, counter,
                     entry.routing_entry_key, entry.mask,
                     entry.spinnaker_route)
                    for routing_table in routing_tables.routing_tables
                    for counter, entry in
                    enumerate(routing_table.multicast_routing_entries)))

    def add_tags(self, app_graph, tags):
        """ Adds the tags into the database

        :param ~pacman.model.graphs.application.ApplicationGraph app_graph:
            the graph object
        :param ~pacman.model.tags.Tags tags: the tags object
        """
        with self.transaction() as cur:
            for app_vertex in app_graph.vertices:
                for vertex in app_vertex.machine_vertices:
                    v_id = self.__vertex_to_id[vertex]
                    cur.executemany(
                        """
                        INSERT INTO IP_tags(
                            vertex_id, tag, board_address, ip_address, port,
                            strip_sdp)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            (v_id, ipt.tag, ipt.board_address, ipt.ip_address,
                             ipt.port or 0, 1 if ipt.strip_sdp else 0)
                            for ipt in tags.get_ip_tags_for_vertex(vertex)
                            or []))
                    cur.executemany(
                        """
                        INSERT INTO Reverse_IP_tags(
                            vertex_id, tag, board_address, port)
                        VALUES (?, ?, ?, ?)
                        """, (
                            (v_id, ript.tag, ript.board_address,
                             ript.port or 0)
                            for ript in tags.get_reverse_ip_tags_for_vertex(
                                vertex) or ()))

    def create_atom_to_event_id_mapping(
            self, app_graph, routing_infos):
        """
        :param app_graph:
        :type app_graph:
            ~pacman.model.graphs.application.ApplicationGraph
        :param ~pacman.model.routing_info.RoutingInfo routing_infos:
        """
        with self.transaction() as cur:
            cur.executemany(
                """
                INSERT INTO event_to_atom_mapping(
                    vertex_id, event_id, atom_id)
                VALUES (?, ?, ?)
                """, (
                    (self.__vertex_to_id[part.pre_vertex], int(key), int(a_id))
                    for part in app_graph.outgoing_edge_partitions
                    if isinstance(
                        part.pre_vertex, AbstractProvidesKeyToAtomMapping)
                    for a_id, key in
                    part.pre_vertex.routing_key_partition_atom_mapping(
                        routing_infos.get_routing_info_from_pre_vertex(
                            part.pre_vertex, part.identifier))))

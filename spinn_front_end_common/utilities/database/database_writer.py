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
    def auto_detect_database(app_graph, lpg_for_m_vertex):
        """ Auto detects if there is a need to activate the database system

        :param ~pacman.model.graphs.application.ApplicationGraph app_graph:
            the graph of the application problem space.
        :return: whether the database is needed for the application
        :rtype: bool
        """
        return (lpg_for_m_vertex or
                any(isinstance(vertex, AbstractSupportsDatabaseInjection)
                    and vertex.is_in_injection_mode
                    for app_vertex in app_graph.vertices
                    for vertex in app_vertex.machine_vertices))

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

    def add_application_vertices(self, application_graph):
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
                    "INSERT INTO Application_vertices(vertex_label) VALUES(?)",
                    vertex.label)
                self.__vertex_to_id[vertex] = vertex_id
                for m_vertex in vertex.machine_vertices:
                    m_vertex_id = self.__add_machine_vertex(cur, m_vertex)
                    self.__insert(
                        cur,
                        """
                        INSERT INTO graph_mapper_vertex (
                            application_vertex_id, machine_vertex_id)
                        VALUES(?, ?)
                        """,
                        vertex_id, m_vertex_id)

    def __add_machine_vertex(self, cur, m_vertex):
        m_vertex_id = self.__insert(
            cur, "INSERT INTO Machine_vertices (label)  VALUES(?)",
            str(m_vertex.label))
        self.__vertex_to_id[m_vertex] = m_vertex_id
        return m_vertex_id

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
            # Make sure machine vertices are represented
            for placement in placements.placements:
                if placement.vertex not in self.__vertex_to_id:
                    self.__add_machine_vertex(cur, placement.vertex)
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

    def add_tags(self, tags):
        """ Adds the tags into the database

        :param ~pacman.model.graphs.application.ApplicationGraph app_graph:
            the graph object
        :param ~pacman.model.tags.Tags tags: the tags object
        """
        with self.transaction() as cur:
            cur.executemany(
                """
                INSERT INTO IP_tags(
                    vertex_id, tag, board_address, ip_address, port,
                    strip_sdp)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    (self.__vertex_to_id[vert], ipt.tag, ipt.board_address,
                     ipt.ip_address, ipt.port or 0, 1 if ipt.strip_sdp else 0)
                    for ipt, vert in tags.ip_tags_vertices))

    def create_atom_to_event_id_mapping(
            self, lpg_for_m_vertex, routing_infos):
        """
        :param app_graph:
        :type app_graph:
            ~pacman.model.graphs.application.ApplicationGraph
        :param ~pacman.model.routing_info.RoutingInfo routing_infos:
        """
        with self.transaction() as cur:
            for m_vertex, partition_id in lpg_for_m_vertex.keys():
                r_info = routing_infos.get_routing_info_from_pre_vertex(
                    m_vertex, partition_id)
                vertex_slice = m_vertex.vertex_slice
                keys = r_info.get_keys(vertex_slice.n_atoms)
                start = vertex_slice.lo_atom
                m_vertex_id = self.__vertex_to_id[m_vertex]
                cur.executemany(
                    """
                    INSERT INTO event_to_atom_mapping(
                        vertex_id, event_id, atom_id)
                    VALUES (?, ?, ?)
                    """, ((m_vertex_id, int(key), i)
                          for i, key in enumerate(keys, start))
                )

    def add_lpg_mapping(self, lpg_for_m_vertex):
        """ Add mapping from machine vertex to LPG machine vertex

        :param dict(MachineVertex,LivePacketGatherMachineVertex)
            lpg_for_m_vertex:
        """
        with self.transaction() as cur:
            cur.executemany(
                """
                INSERT INTO m_vertex_to_lpg_vertex(
                    pre_vertex_id, post_vertex_id)
                VALUES(?, ?)
                """, ((self.__vertex_to_id[m_vertex],
                       self.__vertex_to_id[lpg_m_vertex])
                      for (m_vertex, _part_id), lpg_m_vertex
                      in lpg_for_m_vertex.items()))

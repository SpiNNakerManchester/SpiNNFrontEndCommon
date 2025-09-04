# Copyright (c) 2015 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations
import logging
import os
from typing import (
    cast, Dict, Iterable, List, Optional, Tuple, TYPE_CHECKING, Union)

from spinn_utilities.config_holder import get_report_path
from spinn_utilities.log import FormatAdapter

from spinn_machine import Machine

from pacman.model.graphs import AbstractVertex
from pacman.model.graphs.machine import MachineVertex
from pacman.model.graphs.application.abstract import (
    AbstractOneAppOneMachineVertex)
from pacman.utilities.utility_calls import get_keys
from pacman.model.graphs.abstract_edge_partition import AbstractEdgePartition

from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.sqlite_db import SQLiteDB
from spinn_front_end_common.abstract_models import (
    AbstractSupportsDatabaseInjection, HasCustomAtomKeyMap, LiveOutputDevice)
from spinn_front_end_common.utility_models import (
    LivePacketGather, LivePacketGatherMachineVertex)
if TYPE_CHECKING:
    from spinn_front_end_common.utility_models.live_packet_gather import (
        _LPGSplitter)

logger = FormatAdapter(logging.getLogger(__name__))
INIT_SQL = "db.sql"


class DatabaseWriter(SQLiteDB):
    """
    The interface for the database system for main front ends.
    Any special tables needed from a front end should be done
    by subclasses of this interface.
    """

    __slots__ = (
        # the path of the database
        "_database_path",
        # the identifier for the SpiNNaker machine
        "_machine_id",
        # Mappings used to accelerate inserts
        "__machine_to_id", "__vertex_to_id")

    def __init__(self) -> None:
        self._database_path = get_report_path("path_input_output_database")
        init_sql_path = os.path.join(os.path.dirname(__file__), INIT_SQL)

        # delete any old database
        if os.path.isfile(self._database_path):
            os.remove(self._database_path)

        super().__init__(self._database_path, ddl_file=init_sql_path)
        self.__machine_to_id: Dict[Machine, int] = dict()
        self.__vertex_to_id: Dict[AbstractVertex, int] = dict()

        # set up checks
        self._machine_id = 0

    @staticmethod
    def auto_detect_database() -> bool:
        """
        Auto detects if there is a need to activate the database system.

        :return: whether the database is needed for the application
        """
        if FecDataView.get_vertices_by_type(LivePacketGather):
            return True
        for vertex in FecDataView.get_vertices_by_type(
                AbstractSupportsDatabaseInjection):
            if vertex.is_in_injection_mode:
                return True
        return False

    @property
    def database_path(self) -> str:
        """
        The location of this database
        """
        return self._database_path

    def __insert(self, sql: str, *args: Union[str, int, None]) -> int:
        try:
            self.cursor().execute(sql, args)
            return self.lastrowid
        except Exception:
            logger.exception("problem with insertion; argument types are {}",
                             str(map(type, args)))
            raise

    def add_machine_objects(self) -> None:
        """
        Store the machine object into the database.
        """
        machine = FecDataView.get_machine()
        self.__machine_to_id[machine] = self._machine_id = self.__insert(
            """
            INSERT INTO Machine_layout(
                x_dimension, y_dimension)
            VALUES(?, ?)
            """, machine.width, machine.height)
        self.cursor().executemany(
            """
            INSERT INTO Machine_chip(
                no_processors, chip_x, chip_y, machine_id,
                ip_address, nearest_ethernet_x, nearest_ethernet_y)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                (chip.n_processors, chip.x, chip.y, self._machine_id,
                 chip.ip_address,
                 chip.nearest_ethernet_x, chip.nearest_ethernet_y)
                for chip in machine.chips))

    def add_application_vertices(self) -> None:
        """
        Stores the main application graph description (vertices, edges).
        """
        # add vertices
        for vertex in FecDataView.iterate_vertices():
            vertex_id = self.__insert(
                "INSERT INTO Application_vertices(vertex_label) VALUES(?)",
                vertex.label)
            self.__vertex_to_id[vertex] = vertex_id
            for m_vertex in vertex.machine_vertices:
                m_vertex_id = self.__add_machine_vertex(m_vertex)
                self.__insert(
                    """
                    INSERT INTO graph_mapper_vertex (
                        application_vertex_id, machine_vertex_id)
                    VALUES(?, ?)
                    """,
                    vertex_id, m_vertex_id)

    def __add_machine_vertex(self, m_vertex: MachineVertex) -> int:
        m_vertex_id = self.__insert(
            "INSERT INTO Machine_vertices (label)  VALUES(?)",
            str(m_vertex.label))
        self.__vertex_to_id[m_vertex] = m_vertex_id
        return m_vertex_id

    def add_system_params(self, runtime: Optional[float]) -> None:
        """
        Write system parameters into the database.

        :param runtime: the amount of time the application is to run for
        """
        self.cursor().executemany(
            """
            INSERT INTO configuration_parameters (
                parameter_id, value)
            VALUES (?, ?)
            """, [
                ("machine_time_step",
                 FecDataView.get_simulation_time_step_us()),
                ("time_scale_factor",
                 FecDataView.get_time_scale_factor()),
                ("infinite_run", str(runtime is None)),
                ("runtime", -1 if runtime is None else runtime),
                ("app_id", FecDataView.get_app_id())])

    def add_proxy_configuration(self) -> None:
        """
        Store the proxy configuration.
        """
        job = FecDataView.get_spalloc_job()
        if job is not None:
            config = job.get_session_credentials_for_db()
            self.cursor().executemany(
                """
                INSERT INTO proxy_configuration(kind, name, value)
                VALUES(?, ?, ?)
                """,   [(k1, k2, v) for (k1, k2), v in config.items()])

    def add_placements(self) -> None:
        """
        Adds the placements objects into the database.
        """
        # Make sure machine vertices are represented
        for placement in FecDataView.iterate_placemements():
            if placement.vertex not in self.__vertex_to_id:
                self.__add_machine_vertex(placement.vertex)
        # add records
        self.cursor().executemany(
            """
            INSERT INTO Placements(
                vertex_id, chip_x, chip_y, chip_p, machine_id)
            VALUES(?, ?, ?, ?, ?)
            """, (
                (self.__vertex_to_id[placement.vertex],
                 placement.x, placement.y, placement.p, self._machine_id)
                for placement in FecDataView.iterate_placemements()))

    def add_tags(self) -> None:
        """
        Adds the tags into the database.
        """
        tags = FecDataView.get_tags()
        self.cursor().executemany(
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
            self, machine_vertices: Optional[
                Iterable[Tuple[MachineVertex, str]]]) -> None:
        """
        Creates atom keys and stores them in the database.

        :param machine_vertices:
        """
        routing_infos = FecDataView.get_routing_infos()
        # This could happen if there are no LPGs
        if machine_vertices is None:
            return
        key_vertices: Dict[int, MachineVertex] = dict()
        for (m_vertex, partition_id) in machine_vertices:
            atom_keys: Iterable[Tuple[int, int]] = ()
            if isinstance(m_vertex.app_vertex, HasCustomAtomKeyMap):
                atom_keys = list(m_vertex.app_vertex.get_atom_key_map(
                    m_vertex, partition_id, routing_infos))
            else:
                r_info = routing_infos.get_info_from(
                    m_vertex, partition_id)
                vertex_slice = m_vertex.vertex_slice
                keys = get_keys(r_info.key, vertex_slice)
                start = vertex_slice.lo_atom
                atom_keys = [(i, k) for i, k in enumerate(keys, start)]
            for _atom, key in atom_keys:
                if key in key_vertices:
                    raise KeyError(
                        f"Key {key} cannot be assigned to {m_vertex} "
                        f"because it is already assigned to "
                        f"{key_vertices[key]}")
                key_vertices[key] = m_vertex
            m_vertex_id = self.__vertex_to_id[m_vertex]
            self.cursor().executemany(
                """
                INSERT INTO event_to_atom_mapping(
                    vertex_id, event_id, atom_id)
                VALUES (?, ?, ?)
                """, ((m_vertex_id, int(key), int(i)) for i, key in atom_keys)
            )

    def create_device_atom_event_id_mapping(
            self, devices: Iterable[LiveOutputDevice]) -> None:
        """
        Add output mappings for devices.
        """
        for device in devices:
            for m_vertex, atom_keys in device.get_device_output_keys().items():
                m_vertex_id = self.__vertex_to_id[m_vertex]
                self.cursor().executemany(
                    """
                    INSERT INTO event_to_atom_mapping(
                        vertex_id, event_id, atom_id)
                    VALUES (?, ?, ?)
                    """, ((m_vertex_id, int(key), int(i))
                          for i, key in atom_keys)
                )

    def _get_machine_lpg_mappings(
            self, part: AbstractEdgePartition) -> Iterable[
                Tuple[MachineVertex, str, MachineVertex]]:
        """
        Get places where an LPG Machine vertex has been added to a graph
        "directly" (via SpiNNakerGraphFrontEnd);
        and so it's application vertex *isn't* a LivePacketGather
        """
        for edge in part.edges:
            if (isinstance(edge.pre_vertex,
                           AbstractOneAppOneMachineVertex) and
                    isinstance(edge.post_vertex,
                               AbstractOneAppOneMachineVertex) and
                    isinstance(edge.post_vertex.machine_vertex,
                               LivePacketGatherMachineVertex) and
                    not isinstance(edge.post_vertex, LivePacketGather)):
                yield (edge.pre_vertex.machine_vertex, part.identifier,
                       edge.post_vertex.machine_vertex)

    @staticmethod
    def __lpg_splitter(vertex: LivePacketGather) -> _LPGSplitter:
        return cast('_LPGSplitter', vertex.splitter)

    def add_lpg_mapping(self) -> List[Tuple[MachineVertex, str]]:
        """
        Add mapping from machine vertex to LPG machine vertex.

        :return: A list of (source vertex, partition id)
        """
        targets: List[Tuple[MachineVertex, str, MachineVertex]] = [
            (m_vertex, part_id, lpg_m_vertex)
            for vertex in FecDataView.iterate_vertices()
            if isinstance(vertex, LivePacketGather)
            for lpg_m_vertex, m_vertex, part_id
            in self.__lpg_splitter(vertex).targeted_lpgs]
        targets.extend(
            (m_vertex, part_id, lpg_m_vertex)
            for part in FecDataView.iterate_partitions()
            for (m_vertex, part_id, lpg_m_vertex) in
            self._get_machine_lpg_mappings(part))

        self.cursor().executemany(
            """
            INSERT INTO m_vertex_to_lpg_vertex(
                pre_vertex_id, partition_id, post_vertex_id)
            VALUES(?, ?, ?)
            """, ((self.__vertex_to_id[m_vertex], part_id,
                   self.__vertex_to_id[lpg_m_vertex])
                  for m_vertex, part_id, lpg_m_vertex in targets))

        return [(source, part_id) for source, part_id, _target in targets]

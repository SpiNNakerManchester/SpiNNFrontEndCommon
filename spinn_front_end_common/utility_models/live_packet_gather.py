# Copyright (c) 2017 The University of Manchester
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
from typing import Dict, List, Optional, Set, Sequence, Tuple, TypeVar
from spinn_utilities.overrides import overrides
from pacman.model.graphs.application import ApplicationVertex
from pacman.model.graphs.common import Slice
from pacman.model.graphs.machine import MachineVertex
from pacman.model.partitioner_splitters import AbstractSplitterCommon
from pacman.model.placements import Placement, Placements
from pacman.utilities.algorithm_utilities.routing_algorithm_utilities import (
    vertex_chip)
from pacman.utilities.utility_objs import ChipCounter
from spinn_front_end_common.utilities.utility_calls import (
    pick_core_for_system_placement)
from spinn_front_end_common.utilities.utility_objs import (
    LivePacketGatherParameters)
from spinn_front_end_common.data import FecDataView
from .live_packet_gather_machine_vertex import LivePacketGatherMachineVertex
#: :meta private:
MV = TypeVar("MV", bound=MachineVertex)


class _LPGSplitter(AbstractSplitterCommon["LivePacketGather"]):
    """
    Splitter for the :py:class:`LivePacketGather` vertex.
    """
    __slots__ = (
        "__m_vertices_by_ethernet",
        "__targeted_lpgs")

    def __init__(self) -> None:
        super().__init__()
        self.__m_vertices_by_ethernet: Dict[
            Tuple[int, int], LivePacketGatherMachineVertex] = dict()
        self.__targeted_lpgs: Set[Tuple[
            LivePacketGatherMachineVertex, MachineVertex, str]] = set()

    def create_sys_vertices(self, system_placements: Placements) -> None:
        """
        Special way of making LPG machine vertices, where one is placed
        on each Ethernet-enabled chip.

        .. note::
            This adds to system placements.
        """
        machine = FecDataView.get_machine()
        for eth in machine.ethernet_connected_chips:
            lpg_vtx = LivePacketGatherMachineVertex(
                self.governed_app_vertex.params, self.governed_app_vertex)
            self.governed_app_vertex.remember_machine_vertex(lpg_vtx)
            p = pick_core_for_system_placement(system_placements, eth)
            system_placements.add_placement(
                Placement(lpg_vtx, eth.x, eth.y, p))
            self.__m_vertices_by_ethernet[eth.x, eth.y] = lpg_vtx

    @overrides(AbstractSplitterCommon.create_machine_vertices)
    def create_machine_vertices(self, chip_counter: ChipCounter) -> None:
        # Skip here, and do later!  This is a special case...
        pass

    @overrides(AbstractSplitterCommon.get_in_coming_slices)
    def get_in_coming_slices(self) -> List[Slice]:
        # There are none!
        return []

    @overrides(AbstractSplitterCommon.get_out_going_slices)
    def get_out_going_slices(self) -> List[Slice]:
        # There are also none (but this should never be a pre-vertex)
        return []

    @overrides(AbstractSplitterCommon.get_in_coming_vertices)
    def get_in_coming_vertices(self, partition_id: str) -> Sequence[
            LivePacketGatherMachineVertex]:
        return tuple(self.governed_app_vertex.machine_vertices)

    @overrides(AbstractSplitterCommon.get_source_specific_in_coming_vertices)
    def get_source_specific_in_coming_vertices(
            self, source_vertex: ApplicationVertex[MV],
            partition_id: str) -> Sequence[Tuple[
                LivePacketGatherMachineVertex,
                Sequence[ApplicationVertex[MV]]]]:
        # Find the nearest placement for the first machine vertex of the source
        m_vertex = next(iter(source_vertex.splitter.get_out_going_vertices(
            partition_id)))
        chip = vertex_chip(m_vertex)
        lpg_vertex = self.__m_vertices_by_ethernet[
            chip.nearest_ethernet_x, chip.nearest_ethernet_y]
        for m_vertex in source_vertex.splitter.get_out_going_vertices(
                partition_id):
            self.__targeted_lpgs.add(
                (lpg_vertex, m_vertex, partition_id))
            lpg_vertex.add_incoming_source(m_vertex, partition_id)
        return [(lpg_vertex, [source_vertex])]

    @property
    def targeted_lpgs(self) -> Set[Tuple[
            LivePacketGatherMachineVertex, MachineVertex, str]]:
        """
        Which LPG machine vertex is targeted by which machine vertex
        and partition.

        A set of (LPG machine vertex, source machine vertex, partition_id)
        """
        return self.__targeted_lpgs

    @overrides(AbstractSplitterCommon.get_out_going_vertices)
    def get_out_going_vertices(self, partition_id: str) -> List[MachineVertex]:
        # There are none!
        return []

    @overrides(AbstractSplitterCommon.machine_vertices_for_recording)
    def machine_vertices_for_recording(
            self, variable_to_record: str) -> List[MachineVertex]:
        # Nothing to record here...
        return []

    @overrides(AbstractSplitterCommon.reset_called)
    def reset_called(self) -> None:
        self.__m_vertices_by_ethernet = dict()
        self.__targeted_lpgs = set()


class LivePacketGather(ApplicationVertex[LivePacketGatherMachineVertex]):
    """
    A vertex that gathers and forwards multicast packets to the host.
    """
    __slots__ = ("__params", )

    def __init__(self, params: LivePacketGatherParameters,
                 label: Optional[str] = None):
        """
        :param params: The parameters object
        :param label: An optional label
        """
        super().__init__(label=label, splitter=_LPGSplitter())
        self.__params = params

    @property
    def n_atoms(self) -> int:  # type: ignore[override]
        return 0

    @property
    def params(self) -> LivePacketGatherParameters:
        """
        The params value passed into the init.
        """
        return self.__params

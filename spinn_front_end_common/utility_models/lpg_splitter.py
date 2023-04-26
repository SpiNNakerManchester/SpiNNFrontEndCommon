# Copyright (c) 2020 The University of Manchester
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
from spinn_utilities.overrides import overrides
from pacman.model.partitioner_splitters.abstract_splitters import (
    AbstractSplitterCommon)
from pacman.model.placements import Placement
from pacman.utilities.algorithm_utilities.routing_algorithm_utilities import (
    vertex_xy)
from spinn_front_end_common.data import FecDataView
from .live_packet_gather_machine_vertex import LivePacketGatherMachineVertex


class LPGSplitter(AbstractSplitterCommon):
    """
    Splitter for the :py:class:`LivePacketGather` vertex.
    """

    __slots__ = [
        "__m_vertices_by_ethernet",
        "__targeted_lpgs"
    ]

    def __init__(self):
        super(LPGSplitter, self).__init__()

        self.__m_vertices_by_ethernet = dict()
        self.__targeted_lpgs = set()

    def create_vertices(self, system_placements):
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
            cores = self.__cores(eth.x, eth.y)
            p = cores[system_placements.n_placements_on_chip(eth.x, eth.y)]
            system_placements.add_placement(
                Placement(lpg_vtx, eth.x, eth.y, p))
            self.__m_vertices_by_ethernet[eth.x, eth.y] = lpg_vtx

    def __cores(self, x, y):
        return [p.processor_id
                for p in FecDataView.get_chip_at(x, y).processors
                if not p.is_monitor]

    @overrides(AbstractSplitterCommon.create_machine_vertices)
    def create_machine_vertices(self, chip_counter):
        # Skip here, and do later!  This is a special case...
        pass

    @overrides(AbstractSplitterCommon.get_in_coming_slices)
    def get_in_coming_slices(self):
        # There are none!
        return []

    @overrides(AbstractSplitterCommon.get_out_going_slices)
    def get_out_going_slices(self):
        # There are also none (but this should never be a pre-vertex)
        return []

    @overrides(AbstractSplitterCommon.get_in_coming_vertices)
    def get_in_coming_vertices(self, partition_id):
        return self.governed_app_vertex.machine_vertices

    @overrides(AbstractSplitterCommon.get_source_specific_in_coming_vertices)
    def get_source_specific_in_coming_vertices(
            self, source_vertex, partition_id):
        # Find the nearest placement for the first machine vertex of the source
        m_vertex = next(iter(source_vertex.splitter.get_out_going_vertices(
            partition_id)))
        x, y = vertex_xy(m_vertex)
        chip = FecDataView.get_chip_at(x, y)
        lpg_vertex = self.__m_vertices_by_ethernet[
            chip.nearest_ethernet_x, chip.nearest_ethernet_y]
        for m_vertex in source_vertex.splitter.get_out_going_vertices(
                partition_id):
            self.__targeted_lpgs.add(
                (lpg_vertex, m_vertex, partition_id))
            lpg_vertex.add_incoming_source(m_vertex, partition_id)
        return [(lpg_vertex, [source_vertex])]

    @property
    def targeted_lpgs(self):
        """
        Which LPG machine vertex is targeted by which machine vertex
        and partition.

        :return:
             A set of (LPG machine vertex, source machine vertex, partition_id)
        :rtype: set(tuple(LivePacketGatherMachineVertex,
            ~pacman.model.graphs.machine.MachineVertex, str))
        """
        return self.__targeted_lpgs

    @overrides(AbstractSplitterCommon.get_out_going_vertices)
    def get_out_going_vertices(self, partition_id):
        # There are none!
        return []

    @overrides(AbstractSplitterCommon.machine_vertices_for_recording)
    def machine_vertices_for_recording(self, variable_to_record):
        # Nothing to record here...
        return []

    @overrides(AbstractSplitterCommon.reset_called)
    def reset_called(self):
        self.__m_vertices_by_ethernet = dict()
        self.__targeted_lpgs = set()

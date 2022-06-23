# Copyright (c) 2020-2021 The University of Manchester
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
from spinn_utilities.overrides import overrides
from pacman.model.partitioner_splitters.abstract_splitters import (
    AbstractSplitterCommon)
from pacman.model.placements import Placement
from pacman.utilities.algorithm_utilities.routing_algorithm_utilities import (
    vertex_xy)
from collections import defaultdict
from .live_packet_gather_machine_vertex import LivePacketGatherMachineVertex


class LPGSplitter(AbstractSplitterCommon):

    __slots__ = [
        "__machine",
        "__placements",
        "__m_vertices_by_ethernet",
        "__targeted_lpgs"
    ]

    def __init__(self):
        super(LPGSplitter, self).__init__()
        self.__machine = None
        self.__placements = None
        self.__m_vertices_by_ethernet = dict()
        self.__targeted_lpgs = set()

    def create_vertices(self, machine, system_placements):
        self.__machine = machine
        for eth in machine.ethernet_connected_chips:
            lpg_vtx = LivePacketGatherMachineVertex(
                self.governed_app_vertex.params)
            self.governed_app_vertex.remember_machine_vertex(lpg_vtx)
            cores = self.__cores(machine, eth.x, eth.y)
            p = cores[system_placements.n_placements_on_chip(eth.x, eth.y)]
            system_placements.add_placement(
                Placement(lpg_vtx, eth.x, eth.y, p))
            self.__m_vertices_by_ethernet[eth.x, eth.y] = lpg_vtx

    def __cores(self, machine, x, y):
        return [p.processor_id for p in machine.get_chip_at(x, y).processors
                if not p.is_monitor]

    def set_placements(self, placements):
        self.__placements = placements

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
        # Find the nearest placement for each machine vertex of the source
        target_map = defaultdict(list)
        for m_vertex in source_vertex.splitter.get_out_going_vertices(
                partition_id):
            x, y = vertex_xy(m_vertex, self.__placements, self.__machine)
            chip = self.__machine.get_chip_at(x, y)
            lpg_vertex = self.__m_vertices_by_ethernet[
                chip.nearest_ethernet_x, chip.nearest_ethernet_y]
            target_map[lpg_vertex].append(m_vertex)
            self.__targeted_lpgs.add(
                (lpg_vertex, m_vertex, partition_id))
        return [(tgt, sources) for tgt, sources in target_map.items()]

    @property
    def targeted_lpgs(self):
        """ Get which LPG machine vertex is targeted by which machine vertex
            and partition

        :return:
             A set of (lpg machine vertex, source machine vertex, partition_id)
        :rtype: set(LivePacketGatherMachineVertex, MachineVertex, str)
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

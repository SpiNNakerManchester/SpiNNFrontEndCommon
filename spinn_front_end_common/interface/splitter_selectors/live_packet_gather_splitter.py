# Copyright (c) 2021 The University of Manchester
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
from pacman.model.constraints.placer_constraints import ChipAndCoreConstraint
from spinn_front_end_common.utility_models import LivePacketGatherMachineVertex


class LivePacketGatherSplitter(AbstractSplitterCommon):
    """ A "splitter" for LivePacketGather that uses external calls to update
        it
    """

    __slots__ = [
        # Dict of machine vertices of the LPG by chip
        "__machine_vertices_by_chip",

        # Dict of machine vertices to LPG machine vertices to indicate
        # which sends to where
        "__machine_vertex_to_lpg"
    ]

    def __init__(self):
        super(LivePacketGatherSplitter, self).__init__("LPGSplitter")
        self.__machine_vertices_by_chip = dict()
        self.__machine_vertex_to_lpg = dict()

    def really_create_machine_vertices(self, machine):
        """ This is where the machine vertices are really created, which is
            called after splitting and machine creation.  Vertices
            will be put on each Ethernet chip for each parameter set.

        :param Machine machine:
            The machine for which the vertices are to be created
        """
        params = self._governed_app_vertex.parameters
        for chip in machine.ethernet_connected_chips:
            lpg_vtx = LivePacketGatherMachineVertex(
                params, [ChipAndCoreConstraint(x=chip.x, y=chip.y)])
            self._governed_app_vertex.remember_machine_vertex(lpg_vtx)
            self.__machine_vertices_by_chip[chip.x, chip.y] = lpg_vtx

    def associate(self, machine, machine_vertex, placements):
        """ Associate the given machine vertex with one of the local vertices
            based on which is on the same board
        """
        placement = placements.get_placement_of_vertex(machine_vertex)
        chip = machine.get_chip_at(placement.x, placement.y)
        x = chip.nearest_ethernet_x
        y = chip.nearest_ethernet_y
        lpg = self.__machine_vertices_by_chip[x, y]
        self.__machine_vertex_to_lpg[machine_vertex] = lpg

    @overrides(AbstractSplitterCommon.create_machine_vertices)
    def create_machine_vertices(self, chip_counter):
        # We don't actually do anything here, because these are to be added
        # later
        pass

    @overrides(AbstractSplitterCommon.get_out_going_slices)
    def get_out_going_slices(self):
        # Return empty as this isn't really needed here
        return []

    @overrides(AbstractSplitterCommon.get_in_coming_slices)
    def get_in_coming_slices(self):
        # Return empty as this isn't really needed here
        return []

    @overrides(AbstractSplitterCommon.get_out_going_vertices)
    def get_out_going_vertices(self, outgoing_edge_partition):
        # Genuinely OK to return nothing here
        return []

    @overrides(AbstractSplitterCommon.get_in_coming_vertices)
    def get_in_coming_vertices(self, outgoing_edge_partition, pre_m_vertex):
        # This has been decided previously
        return [self.__machine_vertex_to_lpg[pre_m_vertex]]

    @overrides(AbstractSplitterCommon.machine_vertices_for_recording)
    def machine_vertices_for_recording(self, variable_to_record):
        # Nothing is recordable
        return []

    @overrides(AbstractSplitterCommon.reset_called)
    def reset_called(self):
        self.__machine_vertices_by_chip = dict()
        self.__machine_vertex_to_lpg = dict()

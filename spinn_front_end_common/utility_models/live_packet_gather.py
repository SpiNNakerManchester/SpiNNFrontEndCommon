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

from spinn_utilities.overrides import overrides
from pacman.model.partitioner_interfaces import LegacyPartitionerAPI
from pacman.model.graphs.application import ApplicationVertex
from pacman.model.resources import (
    ConstantSDRAM, CPUCyclesPerTickResource, DTCMResource, ResourceContainer)
from .live_packet_gather_machine_vertex import LivePacketGatherMachineVertex


class LivePacketGather(ApplicationVertex, LegacyPartitionerAPI):
    """ A model which stores all the events it receives during a timer tick\
        and then compresses them into Ethernet packets and sends them out of\
        a SpiNNaker machine.
    """

    def __init__(self, lpg_params, constraints=None):
        """
        :param LivePacketGatherParameters lpg_params:
        :param constraints:
        :type constraints:
            iterable(~pacman.model.constraints.AbstractConstraint)
        """
        label = lpg_params.label or "Live Packet Gatherer"
        super().__init__(label, constraints, 1)
        self._lpg_params = lpg_params

    @overrides(LegacyPartitionerAPI.create_machine_vertex)
    def create_machine_vertex(
            self, vertex_slice, resources_required,
            label=None, constraints=None):
        machine_vertex = LivePacketGatherMachineVertex(
            self._lpg_params, constraints, self, label)
        if vertex_slice:
            assert (vertex_slice == machine_vertex.vertex_slice)
        if resources_required:
            assert (resources_required == machine_vertex.resources_required)
        return machine_vertex

    @property
    @overrides(LegacyPartitionerAPI.n_atoms)
    def n_atoms(self):
        return 1

    @overrides(LegacyPartitionerAPI.get_resources_used_by_atoms)
    def get_resources_used_by_atoms(self, vertex_slice):  # @UnusedVariable
        return ResourceContainer(
            sdram=ConstantSDRAM(
                LivePacketGatherMachineVertex.get_sdram_usage()),
            dtcm=DTCMResource(LivePacketGatherMachineVertex.get_dtcm_usage()),
            cpu_cycles=CPUCyclesPerTickResource(
                LivePacketGatherMachineVertex.get_cpu_usage()),
            iptags=[self._lpg_params.get_iptag_resource()])

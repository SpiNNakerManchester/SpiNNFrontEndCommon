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
from pacman.model.graphs.application import ApplicationVertex
from pacman.model.resources import (
    ConstantSDRAM, CPUCyclesPerTickResource, DTCMResource, ResourceContainer)
from .live_packet_gather_machine_vertex import LivePacketGatherMachineVertex
from spinn_front_end_common.abstract_models import (
    AbstractGeneratesDataSpecification, AbstractHasAssociatedBinary)
from spinn_front_end_common.utilities.utility_objs import ExecutableType


class LivePacketGather(
        ApplicationVertex, AbstractGeneratesDataSpecification,
        AbstractHasAssociatedBinary):
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
        super(LivePacketGather, self).__init__(label, constraints, 1)
        self._lpg_params = lpg_params

    @overrides(ApplicationVertex.create_machine_vertex)
    def create_machine_vertex(
            self, vertex_slice, resources_required,  # @UnusedVariable
            label=None, constraints=None):
        m_vtx = LivePacketGatherMachineVertex(
            self._lpg_params, self, vertex_slice, label, constraints)
        self.remember_associated_machine_vertex(m_vtx)
        return m_vtx

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return 'live_packet_gather.aplx'

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return ExecutableType.USES_SIMULATION_INTERFACE

    @property
    @overrides(ApplicationVertex.n_atoms)
    def n_atoms(self):
        return 1

    @overrides(ApplicationVertex.get_resources_used_by_atoms)
    def get_resources_used_by_atoms(self, vertex_slice):  # @UnusedVariable
        return ResourceContainer(
            sdram=ConstantSDRAM(
                LivePacketGatherMachineVertex.get_sdram_usage()),
            dtcm=DTCMResource(LivePacketGatherMachineVertex.get_dtcm_usage()),
            cpu_cycles=CPUCyclesPerTickResource(
                LivePacketGatherMachineVertex.get_cpu_usage()),
            iptags=[self._lpg_params.get_iptag_resource()])

    @overrides(AbstractGeneratesDataSpecification.generate_data_specification)
    def generate_data_specification(self, spec, placement):
        # generate spec for the machine vertex
        placement.vertex.generate_data_specification(spec, placement)

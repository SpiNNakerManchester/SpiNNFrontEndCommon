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
from spinn_front_end_common.abstract_models import (
    AbstractHasAssociatedBinary, AbstractGeneratesDataSpecification)
from .extra_monitor_support_machine_vertex import (
    ExtraMonitorSupportMachineVertex)


class ExtraMonitorSupport(
        ApplicationVertex, AbstractHasAssociatedBinary,
        AbstractGeneratesDataSpecification):
    """ Control over the extra monitors.
    """

    __slots__ = []

    def __init__(self, constraints):
        """
        :param constraints: The constraints on the vertex
        :type constraints: \
            iterable(~pacman.model.constraints.AbstractConstraint)
        """
        super(ExtraMonitorSupport, self).__init__(
            label="ExtraMonitorSupport", constraints=constraints)

    @overrides(ApplicationVertex.create_machine_vertex)
    def create_machine_vertex(self, vertex_slice, resources_required,
                              label=None, constraints=None):
        return ExtraMonitorSupportMachineVertex(constraints=constraints)

    @property
    @overrides(ApplicationVertex.n_atoms)
    def n_atoms(self):
        return 1

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return ExtraMonitorSupportMachineVertex.static_get_binary_start_type()

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return ExtraMonitorSupportMachineVertex.static_get_binary_file_name()

    @overrides(ApplicationVertex.get_resources_used_by_atoms)
    def get_resources_used_by_atoms(self, vertex_slice):
        return ExtraMonitorSupportMachineVertex.static_resources_required()

    @overrides(AbstractGeneratesDataSpecification.generate_data_specification)
    def generate_data_specification(self, spec, placement):
        placement.vertex.generate_data_specification(
            spec=spec, placement=placement)

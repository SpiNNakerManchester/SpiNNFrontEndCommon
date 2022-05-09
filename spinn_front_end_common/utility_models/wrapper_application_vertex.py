# Copyright (c) 2022-202 The University of Manchester
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

from pacman.model.graphs import AbstractSupportsSDRAMEdges, AbstractVirtual
from pacman.model.graphs.application.abstract import (
    AbstractOneAppOneMachineVertex)


class WrapperApplicationVertex(AbstractOneAppOneMachineVertex):

    def __init__(self, machine_vertex, constraints=None):
        """
        Creates an ApplicationVertex which has exactly one predefined \
        MachineVertex

        :param machine_vertex: MachineVertex
        :param iterable(AbstractConstraint) constraints:
            The optional initial constraints of the vertex.
        :raise PacmanInvalidParameterException:
            If one of the constraints is not valid
        """
        if isinstance(machine_vertex, AbstractSupportsSDRAMEdges):
            raise NotImplementedError(
                "Wrapping a vertex which implements "
                "AbstractSupportsSDRAMEdges is not supported yet")
        if isinstance(machine_vertex, AbstractVirtual):
            raise NotImplementedError(
                "Wrapping a virtual vertex is not supported yet")
        super().__init__(
            machine_vertex, machine_vertex.label, constraints,
            machine_vertex.vertex_slice.n_atoms)
        machine_vertex._app_vertex = self

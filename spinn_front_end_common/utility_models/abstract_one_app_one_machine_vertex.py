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


class AbstractOneAppOneMachineVertex(
        ApplicationVertex, AbstractHasAssociatedBinary):
    """ An Application Vertex that has a fixed Singleton Machine Vertex

    The overiding class MUST create the MachineVertex in its init
    """
    __slots__ = [
        # A pointer to the machine vertex that must be set by the sub class
        "_machine_vertex"]

    def __init__(self, label, constraints):
        """
        :param str label: The optional name of the vertex.
        :param iterable(AbstractConstraint) constraints:
            The optional initial constraints of the vertex.
        :raise PacmanInvalidParameterException:
            If one of the constraints is not valid
        """
        super(AbstractOneAppOneMachineVertex, self).__init__(
            label, constraints, 1)
        # Will be None until after the MachineVertex is created and remembered
        self._machine_vertex = None

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return self._machine_vertex.get_binary_file_name()

    @overrides(ApplicationVertex.get_resources_used_by_atoms)
    def get_resources_used_by_atoms(self, vertex_slice):
        return self._machine_vertex.resources_required

    @overrides(ApplicationVertex.create_machine_vertex)
    def create_machine_vertex(self, vertex_slice, resources_required,
                              label=None, constraints=None):
        raise NotImplementedError("Use next(iter(foo.machine_vertices))")

    @overrides(ApplicationVertex.remember_associated_machine_vertex)
    def remember_associated_machine_vertex(self, machine_vertex):
        # During init this method is called before machine_vertex is set
        if self._machine_vertex:
            assert (machine_vertex == self._machine_vertex)
        super(AbstractOneAppOneMachineVertex, self).\
            remember_associated_machine_vertex(machine_vertex)

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return self._machine_vertex.get_binary_start_type()

    @property
    @overrides(ApplicationVertex.n_atoms)
    def n_atoms(self):
        return 1

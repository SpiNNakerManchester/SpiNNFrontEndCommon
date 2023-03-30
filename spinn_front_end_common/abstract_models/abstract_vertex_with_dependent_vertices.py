# Copyright (c) 2016 The University of Manchester
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

from spinn_utilities.abstract_base import AbstractBase, abstractmethod
from spinn_utilities.require_subclass import require_subclass
from pacman.model.graphs.application import ApplicationVertex


@require_subclass(ApplicationVertex)
class AbstractVertexWithEdgeToDependentVertices(
        object, metaclass=AbstractBase):
    """
    A vertex with a dependent vertices, which should be connected to this
    vertex by an edge directly to each of them.
    """

    __slots__ = ()

    @abstractmethod
    def dependent_vertices(self):
        """
        Return the vertices which this vertex depends upon.

        :rtype: iterable(~pacman.model.graphs.application.ApplicationVertex)
        """

    @abstractmethod
    def edge_partition_identifiers_for_dependent_vertex(self, vertex):
        """
        Return the dependent edge identifiers for a particular dependent
        vertex.

        :param ~pacman.model.graphs.application.ApplicationVertex vertex:
        :rtype: iterable(str)
        """

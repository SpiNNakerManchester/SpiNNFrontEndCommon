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
from typing import Iterable
from spinn_utilities.abstract_base import AbstractBase, abstractmethod
from spinn_utilities.require_subclass import require_subclass
from pacman.model.graphs.application import ApplicationVertex
# mypy: disable-error-code=empty-body


@require_subclass(ApplicationVertex)
class AbstractVertexWithEdgeToDependentVertices(
        object, metaclass=AbstractBase):
    """
    A vertex with a dependent vertices, which should be connected to this
    vertex by an edge directly to each of them.
    """

    __slots__ = ()

    @abstractmethod
    def dependent_vertices(self) -> Iterable[ApplicationVertex]:
        """
        :returns: The vertices which this vertex depends upon.
        """
        raise NotImplementedError

    @abstractmethod
    def edge_partition_identifiers_for_dependent_vertex(
            self, vertex: ApplicationVertex) -> Iterable[str]:
        """
        :param vertex:
        :returns:
           The dependent edge identifiers for a particular dependent  vertex.
        """
        raise NotImplementedError

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

from spinn_utilities.abstract_base import AbstractBase, abstractmethod
from pacman.model.graphs.application import ApplicationVertex
from spinn_front_end_common.utilities.class_utils import check_class_type


class AbstractVertexWithEdgeToDependentVertices(
        object, metaclass=AbstractBase):
    """ A vertex with a dependent vertices, which should be connected to this\
        vertex by an edge directly to each of them
    """

    __slots__ = ()

    def __init_subclass__(cls, **kwargs):  # @NoSelf
        check_class_type(cls, ApplicationVertex)
        super().__init_subclass__(**kwargs)

    @abstractmethod
    def dependent_vertices(self):
        """ Return the vertices which this vertex depends upon

        :rtype: iterable(~pacman.model.graphs.application.ApplicationVertex)
        """

    @abstractmethod
    def edge_partition_identifiers_for_dependent_vertex(self, vertex):
        """ Return the dependent edge identifiers for a particular dependent\
            vertex.

        :param ~pacman.model.graphs.application.ApplicationVertex vertex:
        :rtype: iterable(str)
        """

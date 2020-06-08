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

from six import add_metaclass
from spinn_utilities.abstract_base import AbstractBase, abstractmethod


@add_metaclass(AbstractBase)
class AbstractProvidesNKeysForPartition(object):
    """ Allows a vertex to provide the number of keys for a partition of edges,\
        rather than relying on the number of atoms in the pre-vertex.
    """

    __slots__ = ()

    @abstractmethod
    def get_n_keys_for_partition(self, partition, graph_mapper):
        """ Get the number of keys required by the given partition of edges.

        :param partition: An partition that comes out of this vertex
        :type partition: ~pacman.model.graphs.AbstractOutgoingEdgePartition
        :param graph_mapper: A mapper between the graphs
        :type graph_mapper: :py:class:`~pacman.model.graph.GraphMapper`
        :return: A list of constraints
        :rtype: list(~pacman.model.constraints.AbstractConstraint)
        """

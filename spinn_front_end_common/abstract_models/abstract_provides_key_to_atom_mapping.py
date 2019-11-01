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
class AbstractProvidesKeyToAtomMapping(object):
    """ Interface to provide a mapping between routing key partitions and\
        atom IDs
    """

    __slots__ = ()

    @abstractmethod
    def routing_key_partition_atom_mapping(self, routing_info, partition):
        """ Returns a list of atom to key mapping.

        :param routing_info: the routing info object to consider
        :type routing_info: ~pacman.model.routing_info.RoutingInfo
        :param partition: the routing partition to handle.
        :type partition: ~pacman.model.graphs.AbstractOutgoingEdgePartition
        :return: a iterable of tuples of atom IDs to keys.
        :rtype: iterable(tuple(int,int))
        """

# Copyright (c) 2022 The University of Manchester
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
from spinn_utilities.require_subclass import require_subclass
from pacman.model.graphs.application import ApplicationVertex


@require_subclass(ApplicationVertex)
class HasCustomAtomKeyMap(object, metaclass=AbstractBase):
    """ An object that can provide a custom atom-key mapping for a partition.
        Useful when there isn't a one-to-one correspondence between atoms
        and keys for a given partition.
    """

    @abstractmethod
    def get_atom_key_map(self, pre_vertex, partition_id, routing_info):
        """ Get the mapping between atoms and keys for the given partition id,
            and for the given machine pre-vertex

        :param MachineVertex pre_vertex: The machine vertex to get the map for
        :param str partition_id: The partition to get the map for
        :param RoutingInfo routing_info: Routing information
        :return: A list of (atom_id, key)
        :rtype: list(tuple(int,int))
        """

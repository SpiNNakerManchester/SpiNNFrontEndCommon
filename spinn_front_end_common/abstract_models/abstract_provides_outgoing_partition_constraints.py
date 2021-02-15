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
from spinn_utilities.require_subclass import require_subclass
from pacman.model.graphs import AbstractVertex


@require_subclass(AbstractVertex)
class AbstractProvidesOutgoingPartitionConstraints(
        object, metaclass=AbstractBase):
    """ A vertex that can provide constraints for its outgoing edge partitions.

    If a Machine_vertex is an instance the Application vertex will not be
    checked. However if the MachineVertex does not implement this API
    ProcessPartitionConstraint will then check the ApplicationVertex
    """

    __slots__ = ()

    @abstractmethod
    def get_outgoing_partition_constraints(self, partition):
        """ Get constraints to be added to the given edge partition that comes\
            out of this vertex.

        :param ~pacman.model.graphs.AbstractOutgoingEdgePartition partition:
            An edge that comes out of this vertex
        :return: A list of constraints
        :rtype: list(~pacman.model.constraints.AbstractConstraint)
        """

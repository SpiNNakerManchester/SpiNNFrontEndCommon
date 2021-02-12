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


class AbstractProvidesLocalProvenanceData(object, metaclass=AbstractBase):
    """ Indicates an object that provides locally obtained provenance data.

    GraphProvenanceGatherer will check all Vertices and all Edges in both the
    MachineGraph and if it exists the ApplicationGraph
    """

    __slots__ = ()

    @abstractmethod
    def get_local_provenance_data(self):
        """ Get an iterable of provenance data items.

        :return: the provenance items
        :rtype:
            iterable(~spinn_front_end_common.utilities.utility_objs.ProvenanceDataItem)
        """

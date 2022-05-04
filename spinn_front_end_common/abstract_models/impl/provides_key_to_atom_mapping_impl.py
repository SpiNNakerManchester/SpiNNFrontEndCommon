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
from spinn_front_end_common.abstract_models import (
    AbstractProvidesKeyToAtomMapping)


class ProvidesKeyToAtomMappingImpl(AbstractProvidesKeyToAtomMapping):
    __slots__ = ()

    @overrides(
        AbstractProvidesKeyToAtomMapping.routing_key_partition_atom_mapping)
    def routing_key_partition_atom_mapping(self, routing_info, partition):
        for m_vertex in partition.pre_vertex.machine_vertices:
            vertex_slice = m_vertex.vertex_slice
            r_info = routing_info.get_routing_info_from_pre_vertex(
                m_vertex, partition.identifier)
            keys = r_info.get_keys(vertex_slice.n_atoms)
            start = vertex_slice.lo_atom
            yield from enumerate(keys, start)

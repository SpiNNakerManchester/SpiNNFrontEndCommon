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
from pacman.executor.injection_decorator import inject_items
from spinn_front_end_common.abstract_models import (
    AbstractProvidesKeyToAtomMapping)


class ProvidesKeyToAtomMappingImpl(AbstractProvidesKeyToAtomMapping):
    __slots__ = ()

    @inject_items({
        "graph_mapper": "MemoryGraphMapper"
    })
    @overrides(
        AbstractProvidesKeyToAtomMapping.routing_key_partition_atom_mapping,
        additional_arguments={"graph_mapper"})
    def routing_key_partition_atom_mapping(
            self, routing_info, partition, graph_mapper):
        # pylint: disable=arguments-differ
        vertex_slice = graph_mapper.get_slice(partition.pre_vertex)
        keys = routing_info.get_keys(vertex_slice.n_atoms)
        return list(enumerate(keys, vertex_slice.lo_atom))

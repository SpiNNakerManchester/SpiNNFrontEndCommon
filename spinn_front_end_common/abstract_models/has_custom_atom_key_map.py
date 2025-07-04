# Copyright (c) 2022 The University of Manchester
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
from typing import Iterable, Tuple
from spinn_utilities.abstract_base import AbstractBase, abstractmethod
from spinn_utilities.require_subclass import require_subclass
from pacman.model.graphs.application import ApplicationVertex
from pacman.model.graphs.machine.machine_vertex import MachineVertex
from pacman.model.routing_info.routing_info import RoutingInfo
# mypy: disable-error-code=empty-body


@require_subclass(ApplicationVertex)
class HasCustomAtomKeyMap(object, metaclass=AbstractBase):
    """
    An object that can provide a custom atom-key mapping for a partition.
    Useful when there isn't a one-to-one correspondence between atoms
    and keys for a given partition.
    """

    @abstractmethod
    def get_atom_key_map(
            self, pre_vertex: MachineVertex, partition_id: str,
            routing_info: RoutingInfo) -> Iterable[Tuple[int, int]]:
        """
        Get the mapping between atoms and keys for the given partition id,
        and for the given machine pre-vertex.

        :param pre_vertex:
            The machine vertex to get the map for
        :param partition_id: The partition to get the map for
        :param routing_info:
            Routing information
        :return: A list of (atom_id, key)
        """
        raise NotImplementedError

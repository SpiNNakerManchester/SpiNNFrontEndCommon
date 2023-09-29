# Copyright (c) 2019 The University of Manchester
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

from spinn_utilities.abstract_base import AbstractBase, abstractmethod
from spinn_utilities.require_subclass import require_subclass
from pacman.model.graphs.machine import MachineVertex


@require_subclass(MachineVertex)
class AbstractSupportsBitFieldRoutingCompression(
        object, metaclass=AbstractBase):
    """
    Marks a machine vertex that can support having the on-chip bitfield
    compressor running on its core.
    """
    __slots__ = ()

    @abstractmethod
    def bit_field_base_address(self, placement):
        """
        Returns the SDRAM address for the bit-field table data.

        :param ~pacman.model.placements.Placement placement:
        :return: the SDRAM address for the bitfield address
        :rtype: int
        """

    @abstractmethod
    def regeneratable_sdram_blocks_and_sizes(self, placement):
        """
        Returns the SDRAM addresses and sizes for the cores' SDRAM that
        are available (borrowed) for generating bitfield tables.

        :param ~pacman.model.placements.Placement placement:
        :return: list of tuples containing (the SDRAM address for the cores
            SDRAM address's for the core's SDRAM that can be used to generate
            bitfield tables loaded, and the size of memory chunks located
            there)
        :rtype: list(tuple(int,int))
        """

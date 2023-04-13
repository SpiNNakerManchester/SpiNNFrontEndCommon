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
class AbstractSupportsBitFieldGeneration(object, metaclass=AbstractBase):
    """
    Marks a vertex that can provide information about bitfields it wants
    generated on-chip.
    """
    __slots__ = ()

    @abstractmethod
    def bit_field_base_address(self, placement):
        """
        Returns the SDRAM address for the bit field table data.

        :param ~pacman.model.placements.Placement placement:
        :return: the SDRAM address for the bitfield address
        :rtype: int
        """

    @abstractmethod
    def bit_field_builder_region(self, placement):
        """
        Returns the SDRAM address for the bit field builder data.

        :param ~pacman.model.placements.Placement placement:
        :return: the SDRAM address for the bitfield builder data
        :rtype: int
        """

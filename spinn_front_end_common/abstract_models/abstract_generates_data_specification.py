# Copyright (c) 2016 The University of Manchester
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
from __future__ import annotations
from typing import TYPE_CHECKING
from spinn_utilities.abstract_base import AbstractBase, abstractmethod
from spinn_utilities.overrides import overrides
from spinn_utilities.require_subclass import require_subclass
from pacman.model.graphs.machine import MachineVertex
from pacman.model.placements import Placement
from pacman.model.resources import AbstractSDRAM

from .abstract_has_associated_binary import AbstractHasAssociatedBinary
if TYPE_CHECKING:
    from spinn_front_end_common.interface.ds import DataSpecificationGenerator


@require_subclass(AbstractHasAssociatedBinary)
class AbstractGeneratesDataSpecification(object, metaclass=AbstractBase):
    """
    A machine vertex that generates a data specification that describes what
    its binary's initialisation data is.
    """
    __slots__ = ()

    @abstractmethod
    def generate_data_specification(self, spec: DataSpecificationGenerator,
                                    placement: Placement) -> None:
        """
        Generate a data specification.

        :param ~data_specification.DataSpecificationGenerator spec:
            The data specification to write to
        :param ~pacman.model.placements.Placement placement:
            The placement the vertex is located at
        """
        raise NotImplementedError

    @property
    @overrides(MachineVertex.sdram_required)
    @abstractmethod
    def sdram_required(self) -> AbstractSDRAM:
        # pylint: disable=missing-function-docstring
        raise NotImplementedError

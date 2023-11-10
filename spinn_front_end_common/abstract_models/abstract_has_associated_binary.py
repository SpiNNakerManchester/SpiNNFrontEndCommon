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

from spinn_utilities.abstract_base import AbstractBase, abstractmethod
from spinn_utilities.require_subclass import require_subclass
from pacman.model.graphs.machine import MachineVertex
from spinnman.model.enums import ExecutableType
# mypy: disable-error-code=empty-body


@require_subclass(MachineVertex)
class AbstractHasAssociatedBinary(object, metaclass=AbstractBase):
    """
    Marks a machine graph vertex that can be launched on a SpiNNaker core.
    """

    __slots__ = ()

    @abstractmethod
    def get_binary_file_name(self) -> str:
        """
        Get the binary name to be run for this vertex.

        :rtype: str
        """
        raise NotImplementedError

    @abstractmethod
    def get_binary_start_type(self) -> ExecutableType:
        """
        Get the start type of the binary to be run.

        :rtype: ~spinnman.model.enum.ExecutableType
        """
        raise NotImplementedError

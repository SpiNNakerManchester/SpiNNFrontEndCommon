# Copyright (c) 2023 The University of Manchester
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

from typing import Dict, Tuple, List
from spinn_utilities.abstract_base import (
    AbstractBase, abstractmethod)
from pacman.model.graphs.machine.machine_vertex import MachineVertex


class LiveOutputDevice(object, metaclass=AbstractBase):
    """
    Indicates a device that will live-output other vertices, and so has a
    different mapping of keys to atoms.
    """
    __slots__ = ()

    @abstractmethod
    def get_device_output_keys(self) -> Dict[MachineVertex,
                                             List[Tuple[int, int]]]:
        """
        Get the atom key mapping to be output for each machine vertex received
        by the device to be output.  Note that the device may change the keys
        as they pass through it, and this needs to be recognised here.
        """
        raise NotImplementedError

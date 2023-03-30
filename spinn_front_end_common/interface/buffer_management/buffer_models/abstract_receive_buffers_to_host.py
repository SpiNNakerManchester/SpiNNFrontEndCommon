# Copyright (c) 2015 The University of Manchester
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
class AbstractReceiveBuffersToHost(object, metaclass=AbstractBase):
    """
    Indicates that this :py:class:`~pacman.model.graphs.machine.MachineVertex`
    can receive buffers.
    """

    __slots__ = ()

    @abstractmethod
    def get_recorded_region_ids(self):
        """
        Get the recording region IDs that have been recorded using buffering.

        :return: The region numbers that have active recording
        :rtype: iterable(int)
        """

    @abstractmethod
    def get_recording_region_base_address(self, placement):
        """
        Get the recording region base address.

        :param ~pacman.model.placements.Placement placement:
            the placement object of the core to find the address of
        :return: the base address of the recording region
        :rtype: int
        """

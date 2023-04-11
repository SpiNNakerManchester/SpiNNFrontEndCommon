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


@require_subclass(MachineVertex)
class AbstractHasProfileData(object, metaclass=AbstractBase):
    """
    Indicates a
    :py:class:`~pacman.model.graphs.machine.MachineVertex`
    that can record a profile.
    """
    __slots__ = ()

    @abstractmethod
    def get_profile_data(self, placement):
        """
        Get the profile data recorded during simulation.

        :param ~pacman.model.placements.Placement placement:
        :rtype: ~spinn_front_end_common.interface.profiling.ProfileData
        """

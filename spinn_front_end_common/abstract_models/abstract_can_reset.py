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

from spinn_utilities.abstract_base import (
    AbstractBase, abstractmethod)


class AbstractCanReset(object, metaclass=AbstractBase):
    """
    Indicates an object that can be reset to time 0.

    This is used when AbstractSpinnakerBase.reset is called.
    All Vertices and all edges in the original graph
    (the one added to by the user) will be checked and reset.
    """
    __slots__ = []

    @abstractmethod
    def reset_to_first_timestep(self):
        """
        Reset the object to first time step.
        """

# Copyright (c) 2017 The University of Manchester
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
class AbstractRewritesDataSpecification(object, metaclass=AbstractBase):
    """
    Indicates an object that allows data to be changed after run,
    and so can rewrite the data specification.
    """

    __slots__ = []

    @abstractmethod
    def regenerate_data_specification(self, spec, placement):
        """
        Regenerate the data specification, only generating regions that
        have changed and need to be reloaded.

        :param ~data_specification.DataSpecificationGenerator spec:
            Where to write the regenerated spec
        :param ~pacman.model.placements.Placement placement:
            Where are we regenerating for?
        """

    @abstractmethod
    def reload_required(self):
        """
        Return true if any data region needs to be reloaded.

        :rtype: bool
        """

    @abstractmethod
    def set_reload_required(self, new_value):
        """
        Indicate that the regions have been reloaded.

        :param new_value: the new value
        """

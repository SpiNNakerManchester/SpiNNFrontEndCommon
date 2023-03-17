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

from spinn_utilities.abstract_base import AbstractBase, abstractproperty
from spinn_utilities.require_subclass import require_subclass
from pacman.model.graphs.machine import MachineVertex


@require_subclass(MachineVertex)
class AbstractSupportsDatabaseInjection(object, metaclass=AbstractBase):
    """
    Marks a machine vertex as supporting injection of information via a
    database running on the controlling host.
    """

    __slots__ = ()

    @abstractproperty
    def is_in_injection_mode(self):
        """
        Whether this vertex is actually in injection mode.

        :rtype: bool
        """

    @abstractproperty
    def injection_partition_id(self):
        """
        The partition that packets are being injected with.

        :rtype: str
        """

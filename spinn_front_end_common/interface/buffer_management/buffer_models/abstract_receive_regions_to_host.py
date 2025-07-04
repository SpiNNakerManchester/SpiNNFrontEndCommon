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
from typing import Sequence, Tuple
from spinn_utilities.abstract_base import AbstractBase, abstractmethod
from spinn_utilities.require_subclass import require_subclass
from pacman.model.graphs.machine import MachineVertex
from pacman.model.placements import Placement
# mypy: disable-error-code=empty-body


@require_subclass(MachineVertex)
class AbstractReceiveRegionsToHost(object, metaclass=AbstractBase):
    """
    Indicates that this :py:class:`~pacman.model.graphs.machine.MachineVertex`
    has regions that are to be downloaded to the host.
    """

    __slots__ = ()

    @abstractmethod
    def get_download_regions(self, placement: Placement) -> Sequence[
            Tuple[int, int, int]]:
        """
        Get the region IDs that are to be downloaded

        :return: The region number, address and size of the regions to be
                 downloaded
        """
        raise NotImplementedError

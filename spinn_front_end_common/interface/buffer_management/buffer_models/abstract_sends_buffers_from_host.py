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
class AbstractSendsBuffersFromHost(object, metaclass=AbstractBase):
    """
    A vertex that sends buffers of keys to be
    transmitted at given timestamps in the simulation.
    """

    __slots__ = ()

    @abstractmethod
    def buffering_input(self):
        """
        Return True if the input of this vertex is to be buffered.

        :rtype: bool
        """

    @abstractmethod
    def get_regions(self):
        """
        Get the set of regions for which there are keys to be sent.

        :return: Iterable of region IDs
        :rtype: iterable(int)
        """

    @abstractmethod
    def get_region_buffer_size(self, region):
        """
        Get the size of the buffer to be used in SDRAM on the machine
        for the region in bytes.

        :param int region: The region to get the buffer size of
        :return: The size of the buffer space in bytes
        :rtype: int
        """

    @abstractmethod
    def is_next_timestamp(self, region):
        """
        Determine if there is another timestamp with data to be sent.

        :param int region: The region to determine if there is more data for
        :return: Whether there is more data
        :rtype: bool
        """

    @abstractmethod
    def get_next_timestamp(self, region):
        """
        Get the next timestamp at which there are still keys to be sent
        for the given region.

        :param int region: The region to get the timestamp for
        :return: The timestamp of the next available keys
        :rtype: int
        """

    @abstractmethod
    def is_next_key(self, region, timestamp):
        """
        Determine if there are still keys to be sent at the given
        timestamp for the given region.

        :param int region: The region to determine if there are keys for
        :param int timestamp:
            The timestamp to determine if there are more keys for
        :return: Whether there are more keys to send for the parameters
        :rtype: bool
        """

    @abstractmethod
    def get_next_key(self, region):
        """
        Get the next key in the given region.

        :param int region: The region to get the next key from
        :return: The next key, or `None` if there are no more keys
        :rtype: int
        """

    @abstractmethod
    def is_empty(self, region):
        """
        Return true if there are no spikes to be buffered for the
        specified region.

        :param int region: The region to get the next key from
        :return: Whether there are no keys to send for the region
        :rtype: bool
        """

    @abstractmethod
    def rewind(self, region):
        """
        Rewinds the internal buffer in preparation of re-sending the spikes.

        :param int region: The region to rewind
        """

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
from typing import Collection, Dict

from spinn_utilities.abstract_base import abstractmethod
from spinn_utilities.overrides import overrides

from spinn_front_end_common.interface.buffer_management.storage_objects \
    import BufferedSendingRegion
from .abstract_sends_buffers_from_host import AbstractSendsBuffersFromHost

# mypy: disable-error-code=empty-body


class SendsBuffersFromHostPreBufferedImpl(
        AbstractSendsBuffersFromHost,
        allow_derivation=True):  # type: ignore [call-arg]
    """
    Implementation of :py:class:`AbstractReceiveBuffersToHost`
    that uses an existing set of buffers for the details.
    """

    __slots__ = ()

    @property
    @abstractmethod
    def send_buffers(self) -> Dict[int, BufferedSendingRegion]:
        """
        The buffer for each region that has keys to send.
        """
        raise NotImplementedError

    @overrides(AbstractSendsBuffersFromHost.buffering_input)
    def buffering_input(self) -> bool:
        return self.send_buffers is not None

    @overrides(AbstractSendsBuffersFromHost.get_regions)
    def get_regions(self) -> Collection[int]:
        return self.send_buffers.keys()

    @overrides(AbstractSendsBuffersFromHost.is_next_timestamp)
    def is_next_timestamp(self, region: int) -> bool:
        return self.send_buffers[region].is_next_timestamp

    @overrides(AbstractSendsBuffersFromHost.get_next_timestamp)
    def get_next_timestamp(self, region: int) -> int:
        return self.send_buffers[region].next_timestamp or 0

    @overrides(AbstractSendsBuffersFromHost.is_next_key)
    def is_next_key(self, region: int, timestamp: int) -> bool:
        return self.send_buffers[region].is_next_key(timestamp)

    @overrides(AbstractSendsBuffersFromHost.get_next_key)
    def get_next_key(self, region: int) -> int:
        return self.send_buffers[region].next_key()

    @overrides(AbstractSendsBuffersFromHost.is_empty)
    def is_empty(self, region: int) -> bool:
        return len(self.send_buffers[region].timestamps) == 0

    @overrides(AbstractSendsBuffersFromHost.rewind)
    def rewind(self, region: int) -> None:
        self.send_buffers[region].rewind()

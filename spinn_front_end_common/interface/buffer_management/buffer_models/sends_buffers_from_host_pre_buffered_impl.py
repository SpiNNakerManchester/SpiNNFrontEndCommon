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

from spinn_utilities.abstract_base import abstractproperty
from spinn_utilities.overrides import overrides
from .abstract_sends_buffers_from_host import AbstractSendsBuffersFromHost


class SendsBuffersFromHostPreBufferedImpl(
        AbstractSendsBuffersFromHost, allow_derivation=True):
    """
    Implementation of :py:class:`AbstractReceiveBuffersToHost`
    that uses an existing set of buffers for the details.
    """
    # pylint: disable=unsubscriptable-object, no-member

    __slots__ = ()

    @abstractproperty
    def send_buffers(self):
        """
        The buffer for each region that has keys to send.

        :rtype: dict(int,
            ~spinn_front_end_common.interface.buffer_management.storage_objects.BufferedSendingRegion)
        """

    @overrides(AbstractSendsBuffersFromHost.buffering_input)
    def buffering_input(self):
        return self.send_buffers is not None

    @overrides(AbstractSendsBuffersFromHost.get_regions)
    def get_regions(self):
        return self.send_buffers.keys()

    @overrides(AbstractSendsBuffersFromHost.is_next_timestamp)
    def is_next_timestamp(self, region):
        return self.send_buffers[region].is_next_timestamp

    @overrides(AbstractSendsBuffersFromHost.get_next_timestamp)
    def get_next_timestamp(self, region):
        return self.send_buffers[region].next_timestamp

    @overrides(AbstractSendsBuffersFromHost.is_next_key)
    def is_next_key(self, region, timestamp):
        return self.send_buffers[region].is_next_key(timestamp)

    @overrides(AbstractSendsBuffersFromHost.get_next_key)
    def get_next_key(self, region):
        return self.send_buffers[region].next_key

    @overrides(AbstractSendsBuffersFromHost.is_empty)
    def is_empty(self, region):
        return len(self.send_buffers[region].timestamps) == 0

    @overrides(AbstractSendsBuffersFromHost.rewind)
    def rewind(self, region):
        self.send_buffers[region].rewind()

# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
from six import add_metaclass
from spinn_utilities.abstract_base import AbstractBase, abstractproperty
from .abstract_sends_buffers_from_host import AbstractSendsBuffersFromHost
from spinn_utilities.overrides import overrides

logger = logging.getLogger(__name__)


@add_metaclass(AbstractBase)
class SendsBuffersFromHostPreBufferedImpl(AbstractSendsBuffersFromHost):
    """ Implementation of :py:class:`AbstractReceiveBuffersToHost`\
        which uses an existing set of buffers for the details.
    """
    # pylint: disable=unsubscriptable-object, no-member

    __slots__ = ()

    @abstractproperty
    def send_buffers(self):
        """
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

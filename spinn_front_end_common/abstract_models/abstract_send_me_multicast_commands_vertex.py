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

from spinn_utilities.abstract_base import AbstractBase, abstractproperty


class AbstractSendMeMulticastCommandsVertex(object, metaclass=AbstractBase):
    """
    A device that may be a virtual vertex which wants to commands to be
    sent to it as multicast packets at fixed points in the simulation.

    .. note::
        The device might not be a vertex at all. It could instead be
        instantiated entirely host side, in which case these methods will
        never be called.
    """

    __slots__ = ()

    @abstractproperty
    def start_resume_commands(self):
        """
        The commands needed when starting or resuming simulation.

        :rtype:
            iterable(~spinn_front_end_common.utility_models.MultiCastCommand)
        """

    @abstractproperty
    def pause_stop_commands(self):
        """
        The commands needed when pausing or stopping simulation.

        :rtype:
            iterable(~spinn_front_end_common.utility_models.MultiCastCommand)
        """

    @abstractproperty
    def timed_commands(self):
        """
        The commands to be sent at given times in the simulation.

        :rtype:
            iterable(~spinn_front_end_common.utility_models.MultiCastCommand)
        """

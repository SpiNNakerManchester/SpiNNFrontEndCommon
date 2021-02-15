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

from spinn_utilities.abstract_base import AbstractBase, abstractproperty


class AbstractSendMeMulticastCommandsVertex(object, metaclass=AbstractBase):
    """ A device that may be a virtual vertex which wants to commands to be\
        sent to it as multicast packets at fixed points in the simulation.

    .. note::
        The device might not be a vertex at all. It could instead be
        instantiated entirely host side, in which case these methods will
        never be called.
    """

    __slots__ = ()

    @abstractproperty
    def start_resume_commands(self):
        """ The commands needed when starting or resuming simulation

        :rtype:
            iterable(~spinn_front_end_common.utility_models.MultiCastCommand)
        """

    @abstractproperty
    def pause_stop_commands(self):
        """ The commands needed when pausing or stopping simulation

        :rtype:
            iterable(~spinn_front_end_common.utility_models.MultiCastCommand)
        """

    @abstractproperty
    def timed_commands(self):
        """ The commands to be sent at given times in the simulation

        :rtype:
            iterable(~spinn_front_end_common.utility_models.MultiCastCommand)
        """

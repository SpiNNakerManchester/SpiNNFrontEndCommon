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

from six import add_metaclass
from spinn_utilities.abstract_base import (
    AbstractBase, abstractproperty, abstractmethod)


@add_metaclass(AbstractBase)
class SimulatorInterface(object):

    __slots__ = ()

    @abstractmethod
    def add_socket_address(self, socket_address):
        """ Add the address of a socket used in the run notification protocol.

        :param ~spinn_utilities.socket_address.SocketAddress socket_address:
            The address of the socket
        :rtype: None
        """

    @abstractproperty
    def buffer_manager(self):
        """ The buffer manager being used for loading/extracting buffers

        :rtype:
            ~spinn_front_end_common.interface.buffer_management.BufferManager
        """

    @abstractproperty
    def config(self):
        """ Provides access to the configuration for front end interfaces.

        :rtype: ~spinn_front_end_common.interface.ConfigHandler
        """

    @abstractproperty
    def has_ran(self):
        """ Whether the simulation has executed anything at all.

        :rtype: bool
        """

    @abstractmethod
    def verify_not_running(self):
        """ Verify that the simulator is in a state where it can start running.
        """

    @abstractproperty
    def machine(self):
        """ The python machine description object.

        :rtype: ~spinn_machine.Machine
        """

    @abstractproperty
    def machine_time_step(self):
        """ The machine timestep, in microseconds.

        :rtype: int
        """

    @abstractproperty
    def no_machine_time_steps(self):
        """ The number of machine time steps.

        :rtype: int
        """

    @abstractproperty
    def placements(self):
        """ Where machine vertices are placed on the machine.

        :rtype: ~pacman.model.placements.Placements
        """

    @abstractproperty
    def tags(self):
        """
        :rtype: ~pacman.model.tags.Tags
        """

    @abstractproperty
    def time_scale_factor(self):
        """
        :rtype: int
        """

    @abstractmethod
    def run(self, run_time):
        """ Run a simulation for a fixed amount of time

        :param int run_time: the run duration in milliseconds.
        """

    @abstractmethod
    def stop(self):
        """ End running of the simulation.
        """

    @abstractproperty
    def transceiver(self):
        """ How to talk to the machine.

        :rtype: ~spinnman.transceiver.Transceiver
        """

    @abstractproperty
    def use_virtual_board(self):
        """
        :rtype: bool
        """

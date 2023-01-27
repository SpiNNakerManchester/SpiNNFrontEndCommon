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

from spinn_utilities.abstract_base import AbstractBase, abstractmethod
from spinnman.constants import SCP_SCAMP_PORT


class AbstractMachineAllocationController(object, metaclass=AbstractBase):
    """ An object that controls the allocation of a machine
    """

    __slots__ = ()

    @abstractmethod
    def extend_allocation(self, new_total_run_time):
        """ Extend the allocation of the machine from the original run time.

        :param float new_total_run_time:
            The total run time that is now required starting from when the
            machine was first allocated
        """

    @abstractmethod
    def close(self):
        """ Indicate that the use of the machine is complete.
        """

    @abstractmethod
    def where_is_machine(self, chip_x, chip_y):
        """ Locates and returns cabinet, frame, board for a given chip in a\
            machine allocated to this job.

        :param int chip_x: chip x location
        :param int chip_y: chip y location
        :return: (cabinet, frame, board)
        :rtype: tuple(int,int,int)
        """

    @abstractmethod
    def create_transceiver(self):
        """
        Create a transceiver for talking to the allocated machine, and
        make sure everything is ready for use (i.e. boot and discover
        connections if needed).

        :rtype: ~spinnman.transceiver.Transceiver
        """

    @abstractmethod
    def open_sdp_connection(self, chip_x, chip_y, udp_port=SCP_SCAMP_PORT):
        """
        Open a connection to a specific ethernet chip. Caller will have to
        arrange for SpiNNaker to pay attention to the connection.

        :param int chip_x: ethernet chip x location
        :param int chip_y: ethernet chip y location
        :param int udp_port:
            the UDP port on the chip to connect to; connecting to a non-SCP
            port will result in a connection that can't easily be configured.
        :rtype: ~spinnman.connections.udp_packet_connections.SDPConnection
        """

    @abstractmethod
    def open_eieio_connection(self, chip_x, chip_y):
        """
        Open a connection to a specific ethernet chip for EIEIO. Caller will
        have to arrange for SpiNNaker to pay attention to the connection.

        :param int chip_x: ethernet chip x location
        :param int chip_y: ethernet chip y location

        :rtype: ~spinnman.connections.udp_packet_connections.EIEIOConnection
        """

    @abstractmethod
    def open_eieio_listener(self):
        """
        Open an unbound EIEIO connection.

        :rtype: ~spinnman.connections.udp_packet_connections.EIEIOConnection
        """

    @property
    def proxying(self):
        """
        Whether this is a proxying connection. False unless overridden.

        :rtype: bool
        """
        return False

    def make_report(self, filename):
        """
        Asks the controller to make a report of details of allocations.
        By default, this does nothing.
        """

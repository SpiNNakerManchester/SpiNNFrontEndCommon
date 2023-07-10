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
from typing import Optional, Tuple
from spinn_utilities.abstract_base import AbstractBase, abstractmethod
from spinnman.constants import SCP_SCAMP_PORT
from spinnman.transceiver import Transceiver
from spinnman.connections.udp_packet_connections import (
    EIEIOConnection, SDPConnection)
# mypy: disable-error-code=empty-body


class AbstractMachineAllocationController(object, metaclass=AbstractBase):
    """
    An object that controls the allocation of a machine
    """

    __slots__ = ()

    @abstractmethod
    def extend_allocation(self, new_total_run_time: float):
        """
        Extend the allocation of the machine from the original run time.

        :param float new_total_run_time:
            The total run time that is now required starting from when the
            machine was first allocated
        """
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """
        Indicate that the use of the machine is complete.
        """
        raise NotImplementedError

    @abstractmethod
    def where_is_machine(self, chip_x: int, chip_y: int) -> Tuple[
            int, int, int]:
        """
        Locates and returns cabinet, frame, board for a given chip in a
        machine allocated to this job.

        :param int chip_x: chip x location
        :param int chip_y: chip y location
        :return: (cabinet, frame, board)
        :rtype: tuple(int,int,int)
        """
        raise NotImplementedError

    @abstractmethod
    def create_transceiver(self) -> Optional[Transceiver]:
        """
        Create a transceiver for talking to the allocated machine, and
        make sure everything is ready for use (i.e. boot and discover
        connections if needed).

        :return:
            The transceiver, or `None` if the MAC is not controlling a
            machine allocation.
        :rtype: ~spinnman.transceiver.Transceiver
        """
        raise NotImplementedError

    @abstractmethod
    def open_sdp_connection(
            self, chip_x: int, chip_y: int,
            udp_port: int = SCP_SCAMP_PORT) -> Optional[SDPConnection]:
        """
        Open a connection to a specific Ethernet-enabled SpiNNaker chip.
        Caller will have to arrange for SpiNNaker to pay attention to the
        connection.

        The coordinates will be job-relative.

        :param int chip_x: Ethernet-enabled chip X coordinate
        :param int chip_y: Ethernet-enabled chip Y coordinate
        :param int udp_port:
            the UDP port on the chip to connect to; connecting to a non-SCP
            port will result in a connection that can't easily be configured.
        :return:
            The connection, or `None` if the coordinates do not refer to an
            allocated chip.
        :rtype: ~spinnman.connections.udp_packet_connections.SDPConnection
        """
        raise NotImplementedError

    @abstractmethod
    def open_eieio_connection(
            self, chip_x: int, chip_y: int) -> Optional[EIEIOConnection]:
        """
        Open a connection to a specific Ethernet-enabled chip for EIEIO.
        Caller will have to arrange for SpiNNaker to pay attention to the
        connection.

        The coordinates will be job-relative.

        :param int chip_x: Ethernet-enabled chip X coordinate
        :param int chip_y: Ethernet-enabled chip Y coordinate
        :return:
            The connection, or `None` if the coordinates do not refer to an
            allocated chip.
        :rtype: ~spinnman.connections.udp_packet_connections.EIEIOConnection
        """
        raise NotImplementedError

    @abstractmethod
    def open_eieio_listener(self) -> Optional[EIEIOConnection]:
        """
        Open an unbound EIEIO connection. This may be used to communicate with
        any board of the job.

        :rtype: ~spinnman.connections.udp_packet_connections.EIEIOConnection
        """
        raise NotImplementedError

    @property
    def proxying(self) -> bool:
        """
        Whether this is a proxying connection. False unless overridden.

        :rtype: bool
        """
        return False

    def make_report(self, filename: str):
        """
        Asks the controller to make a report of details of allocations.
        By default, this does nothing.
        """

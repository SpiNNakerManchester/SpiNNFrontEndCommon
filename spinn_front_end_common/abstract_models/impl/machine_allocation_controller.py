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

import logging
import sys
from threading import Thread
from typing import Optional, Tuple
from spinn_utilities.log import FormatAdapter
from spinn_utilities.abstract_base import AbstractBase, abstractmethod
from spinnman.constants import SCP_SCAMP_PORT
from spinnman.connections.udp_packet_connections import SCAMPConnection
from spinnman.transceiver import create_transceiver_from_hostname, Transceiver
from spinnman.connections.udp_packet_connections import EIEIOConnection
logger = FormatAdapter(logging.getLogger(__name__))


class MachineAllocationController(object, metaclass=AbstractBase):
    """
    How to manage the allocation of a machine so that it gets cleaned up
    neatly when the script dies.
    """
    __slots__ = (
        #: Boolean flag for telling this thread when the system has ended
        "_exited",
        #: the address of the root board of the allocation
        "__hostname")

    def __init__(self, thread_name: str, hostname: Optional[str] = None):
        """
        :param thread_name: Name for the Thread object
        :param hostname: host to use to create a Transceiver
        :param connection_data: Chip to remote hosts mapping
        """
        thread = Thread(name=thread_name, target=self.__manage_allocation)
        thread.daemon = True
        self._exited = False
        self.__hostname = hostname
        thread.start()

    @abstractmethod
    def extend_allocation(self, new_total_run_time: float) -> None:
        """
        Extend the allocation of the machine from the original run time.

        :param new_total_run_time:
            The total run time that is now required starting from when the
            machine was first allocated
        """
        raise NotImplementedError

    def close(self) -> None:
        """
        Indicate that the use of the machine is complete.
        """
        self._exited = True

    @abstractmethod
    def _wait(self) -> bool:
        """
        Wait for some bounded amount of time for a change in the status
        of the machine allocation.

        :return: Whether the machine is still (believed to be) allocated.
        """
        raise NotImplementedError

    @abstractmethod
    def where_is_machine(
            self, chip_x: int, chip_y: int) -> Tuple[int, int, int]:
        """
        Locates and returns cabinet, frame, board for a given chip in a
        machine allocated to this job.

        :param chip_x: chip x location
        :param chip_y: chip y location
        :return: (cabinet, frame, board)
        """
        raise NotImplementedError

    def _teardown(self) -> None:
        """
        Perform any extra tear-down that the thread requires. Does not
        need to be overridden if no action is desired.
        """

    def __manage_allocation(self) -> None:
        machine_still_allocated = True
        while machine_still_allocated and not self._exited:
            machine_still_allocated = self._wait()
        self._teardown()
        if not self._exited:
            logger.error(
                "The allocated machine has been released before the end of"
                " the script; this script will now exit")
            sys.exit(1)

    def create_transceiver(self) -> Transceiver:
        """
        Create a transceiver for talking to the allocated machine, and
        make sure everything is ready for use (i.e. boot and discover
        connections if needed).

        :returns: Transceiver created using the hostname passed into the init
        """
        if not self.__hostname:
            raise NotImplementedError("Needs a hostname")
        txrx = create_transceiver_from_hostname(self.__hostname)
        txrx.discover_scamp_connections()
        return txrx

    def can_create_transceiver(self) -> bool:
        """
        Detects if a call to create_transceiver could work.

        Does not check if create transceiver will work over the known host.

        :returns: True if there is known hostname
        """
        return self.__hostname is not None

    def open_sdp_connection(
            self, chip_x: int, chip_y: int,
            udp_port: int = SCP_SCAMP_PORT) -> Optional[SCAMPConnection]:
        """
        Open a connection to a specific Ethernet-enabled SpiNNaker chip.
        Caller will have to arrange for SpiNNaker to pay attention to the
        connection.

        The coordinates will be job-relative.

        :param chip_x: Ethernet-enabled chip X coordinate
        :param chip_y: Ethernet-enabled chip Y coordinate
        :param udp_port:
            the UDP port on the chip to connect to; connecting to a non-SCP
            port will result in a connection that can't easily be configured.
        :returns:
           Connection to the Chip with a know host over this port or None
        """
        _ = (chip_x, chip_y, udp_port)
        return None

    def open_eieio_listener(self) -> EIEIOConnection:
        """
        Open an unbound EIEIO connection. This may be used to communicate with
        any board of the job.

        :returns: The new EIEIO connection
        """
        return EIEIOConnection()

    @property
    def proxying(self) -> bool:
        """
        Whether this is a proxying connection. False unless overridden.
        """
        return False

    def add_report(self) -> None:
        """
        Asks the controller to add a report of details of allocations.
        By default, this does nothing.
        """

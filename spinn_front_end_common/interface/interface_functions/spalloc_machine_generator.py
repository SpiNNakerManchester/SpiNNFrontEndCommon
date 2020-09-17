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
from spinn_utilities.log import FormatAdapter
from .machine_generator import MachineGenerator
from .spalloc_allocator import SpallocAllocator
from spinn_machine.exceptions import SpinnMachineCorruptionException

logger = FormatAdapter(logging.getLogger(__name__))


class SpallocMachineGenerator(object):
    """ Combines the SpallocAllocator and MachineGenerator into a single
    function

    :param str spalloc_server:
        The server from which the machine should be requested
    :param str spalloc_user: The user to allocate the machine to
    :param set(tuple(int,int)) downed_chips:
        the chips that are down which SARK thinks are alive
    :param set(tuple(int,int,int)) downed_cores:
        the cores that are down which SARK thinks are alive
    :param set(tuple(int,int,int)) downed_links:
        the links that are down which SARK thinks are alive
    :param iter(str) sick_boards: A hopefully empty collection of ipaddress.
        If a machine exception is found on one of these board a new spalloc
        job will be requested.
    :param n_chips: The number of chips required.
        IGNORED if n_boards is not None
    :type n_chips: int or None
    :param int n_boards: The number of boards required
    :type n_boards: int or None
    :param int spalloc_port: The optional port number to speak to spalloc
    :param str spalloc_machine: The optional spalloc machine to use
    :param max_sdram_size: the maximum SDRAM each chip can say it has
        (mainly used in debugging purposes)
    :type max_sdram_size: int or None
    :param bool repair_machine:
        Flag to set the behaviour if a repairable error is found on the
        machine.
        If `True` will create a machine without the problematic bits.
        (See machine_factory.machine_repair)
        If `False`, get machine will raise an Exception if a problematic
        machine is discovered.
    :param bool ignore_bad_ethernets:
        Flag to say that ip_address information
        on non-ethernet chips should be ignored.
        Non-ethernet chips are defined here as ones that do not report
        themselves their nearest ethernet.
        The bad IP address is always logged.
        If True, the IP address is ignored.
        If False, the chip with the bad IP address is removed.
    :param str default_report_directory:
        Directory to write any reports too.
        If None the current directory will be used.
    :return: Host_ip_address, MachineAllocationController, Transceiver, and
        description of machine it is connected to
    :rtype: tuple(~spinnman.transceiver.Transceiver, ~spinn_machine.Machine)
    :rtype: tuple(str, int, None, bool, bool, None, None,
        MachineAllocationController)
    """

    __slots__ = []

    MAX_RESTART_SIZE_IN_BOARDS = 24

    def __call__(
            self, spalloc_server, spalloc_user, downed_chips, downed_cores,
            downed_links, sick_boards, n_chips=None, n_boards=None,
            spalloc_port=None, spalloc_machine=None, max_sdram_size=None,
            repair_machine=False, ignore_bad_ethernets=True,
            default_report_directory=None):
        """
        :param str spalloc_server:
        :param str spalloc_user:
        :param set(tuple(int,int)) downed_chips:
        :param set(tuple(int,int,int)) downed_cores:
        :param set(tuple(int,int,int)) downed_links:
        :param iter(str) sick_boards:
        :param int n_chips:
        :param int n_boards:
        :param int spalloc_port:
        :param str spalloc_machine:
        :rtype: tuple(str, int, None, bool, bool, None, None,
            MachineAllocationController)
        """

        machine_details = None
        previous_controller = None

        spalloc_allocator = SpallocAllocator()
        machine_generator = MachineGenerator()

        while not machine_details:
            results = spalloc_allocator(
                spalloc_server, spalloc_user, n_chips, n_boards, spalloc_port,
                spalloc_machine)
            hostname, board_version, bmp_details, reset_machine_on_start_up, \
                auto_detect_bmp, scamp_connection_data, boot_port_num, \
                machine_allocation_controller = results

            # Now we have a new job release the older one
            if previous_controller:
                previous_controller.close()

            try:
                machine_details, txrx = machine_generator(
                    hostname, bmp_details, downed_chips, downed_cores,
                    downed_links, board_version, auto_detect_bmp,
                    scamp_connection_data, boot_port_num,
                    reset_machine_on_start_up, max_sdram_size, repair_machine,
                    ignore_bad_ethernets, default_report_directory)
            except SpinnMachineCorruptionException as ex:
                if n_boards and n_boards > self.MAX_RESTART_SIZE_IN_BOARDS:
                    raise
                if n_chips and n_chips > self.MAX_RESTART_SIZE_IN_BOARDS * 48:
                    raise
                machine_generator = MachineGenerator()
                machine_details, txrx = machine_generator(
                    hostname, bmp_details, downed_chips, downed_cores,
                    downed_links, board_version, auto_detect_bmp,
                    scamp_connection_data, boot_port_num,
                    reset_machine_on_start_up,
                    max_sdram_size, repair_machine, ignore_bad_ethernets,
                    default_report_directory)
                known = False
                for sick_ip in sick_boards:
                    if sick_ip in ex.ipaddress:
                        # TODO let splaooc know the exception!
                        previous_controller = machine_allocation_controller
                        known = True
                if not known:
                    raise

        return hostname, machine_allocation_controller, machine_details, txrx

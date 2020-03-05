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

import re
from spinnman.connections import SocketAddressWithChip
from spinnman.transceiver import create_transceiver_from_hostname
from spinnman.model import BMPConnectionData
from spinn_front_end_common.utilities.exceptions import ConfigurationException


class MachineGenerator(object):
    """ Makes a transceiver and a machine object.

    :param str hostname:
        the hostname or IP address of the SpiNNaker machine
    :param str bmp_details: the details of the BMP connections
    :param set(tuple(int,int)) downed_chips:
        the chips that are down which SARK thinks are alive
    :param set(tuple(int,int,int)) downed_cores:
        the cores that are down which SARK thinks are alive
    :param set(tuple(int,int,int)) downed_links:
        the links that are down which SARK thinks are alive
    :param int board_version:
        the version of the boards being used within the machine
        (1, 2, 3, 4 or 5)
    :param bool auto_detect_bmp:
        Whether the BMP should be automatically determined
    :param list(~.SocketAddressWithChip) scamp_connection_data:
        the list of SC&MP connection data or None
    :param int boot_port_num: the port number used for the boot connection
    :param bool reset_machine_on_start_up:
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
    :return: Connection details and Transceiver
    :rtype: tuple(~spinnman.transceiver.Transceiver, ~spinn_machine.Machine)
    """

    __slots__ = []

    def __call__(
            self, hostname, bmp_details, downed_chips, downed_cores,
            downed_links, board_version, auto_detect_bmp,
            scamp_connection_data, boot_port_num, reset_machine_on_start_up,
            max_sdram_size=None, repair_machine=False,
            ignore_bad_ethernets=True, default_report_directory=None):
        """
        :param str hostname:
        :param str bmp_details:
        :param set(tuple(int,int)) downed_chips:
        :param set(tuple(int,int,int)) downed_cores:
        :param set(tuple(int,int,int)) downed_links:
        :param int board_version:
        :param bool auto_detect_bmp:
        :param list(~.SocketAddressWithChip) scamp_connection_data:
        :param int boot_port_num:
        :param bool reset_machine_on_start_up:
        :param max_sdram_size:
        :type max_sdram_size: int or None
        :param bool repair_machine:
        :param bool ignore_bad_ethernets:
        :rtype: tuple(~spinnman.transceiver.Transceiver, \
            ~spinn_machine.Machine)
        """
        # pylint: disable=too-many-arguments

        # if the end user gives you SCAMP data, use it and don't discover them
        if scamp_connection_data is not None:
            scamp_connection_data = [
                self._parse_scamp_connection(piece)
                for piece in scamp_connection_data.split(":")]

        txrx = create_transceiver_from_hostname(
            hostname=hostname,
            bmp_connection_data=self._parse_bmp_details(bmp_details),
            version=board_version, ignore_chips=downed_chips,
            ignore_cores=downed_cores, ignored_links=downed_links,
            auto_detect_bmp=auto_detect_bmp, boot_port_no=boot_port_num,
            scamp_connections=scamp_connection_data,
            max_sdram_size=max_sdram_size,
            repair_machine=repair_machine,
            ignore_bad_ethernets=ignore_bad_ethernets,
            default_report_directory=default_report_directory)

        if reset_machine_on_start_up:
            txrx.power_off_machine()

        # do auto boot if possible
        if board_version is None:
            raise ConfigurationException(
                "Please set a machine version number in the configuration "
                "file (spynnaker.cfg or pacman.cfg)")
        txrx.ensure_board_is_ready()
        txrx.discover_scamp_connections()
        return txrx.get_machine_details(), txrx

    @staticmethod
    def _parse_scamp_connection(scamp_connection):
        """
        :param str scamp_connection:
        :rtype: ~.SocketAddressWithChip
        :raises Exception: If the parse fails
        """
        pieces = scamp_connection.split(",")
        if len(pieces) == 3:
            port_num = None
            hostname, chip_x, chip_y = pieces
        elif len(pieces) == 4:
            hostname, port_num, chip_x, chip_y = pieces
        else:
            raise Exception("bad SC&MP connection descriptor")

        return SocketAddressWithChip(
            hostname=hostname,
            port_num=None if port_num is None else int(port_num),
            chip_x=int(chip_x),
            chip_y=int(chip_y))

    @staticmethod
    def _parse_bmp_cabinet_and_frame(bmp_cabinet_and_frame):
        """
        :param str bmp_cabinet_and_frame:
        :rtype: tuple(int or str, int or str, str, str or None)
        """
        split_string = bmp_cabinet_and_frame.split(";", 2)
        if len(split_string) == 1:
            host = split_string[0].split(",")
            if len(host) == 1:
                return 0, 0, split_string[0], None
            return 0, 0, host[0], host[1]
        if len(split_string) == 2:
            host = split_string[1].split(",")
            if len(host) == 1:
                return 0, split_string[0], host[0], None
            return 0, split_string[0], host[0], host[1]
        host = split_string[2].split(",")
        if len(host) == 1:
            return split_string[0], split_string[1], host[0], None
        return split_string[0], split_string[1], host[0], host[1]

    @staticmethod
    def _parse_bmp_boards(bmp_boards):
        """
        :param str bmp_boards:
        :rtype: list(int)
        """
        # If the string is a range of boards, get the range
        range_match = re.match(r"(\d+)-(\d+)", bmp_boards)
        if range_match is not None:
            return list(range(int(range_match.group(1)),
                              int(range_match.group(2)) + 1))

        # Otherwise, assume a list of boards
        return [int(board) for board in bmp_boards.split(",")]

    def _parse_bmp_connection(self, bmp_detail):
        """ Parses one item of BMP connection data. Maximal format:\
            `cabinet;frame;host,port/boards`
            All parts except host can be omitted. Boards can be a \
            hyphen-separated range or a comma-separated list.

        :param str bmp_detail:
        :rtype: ~.BMPConnectionData
        """
        pieces = bmp_detail.split("/")
        (cabinet, frame, hostname, port_num) = \
            self._parse_bmp_cabinet_and_frame(pieces[0])
        # if there is no split, then assume its one board, located at 0
        boards = [0] if len(pieces) == 1 else self._parse_bmp_boards(pieces[1])
        port_num = None if port_num is None else int(port_num)
        return BMPConnectionData(cabinet, frame, hostname, boards, port_num)

    def _parse_bmp_details(self, bmp_string):
        """ Take a BMP line (a colon-separated list) and split it into the\
            BMP connection data.

        :param str bmp_string: the BMP string to be converted
        :return: the BMP connection data
        :rtype: list(~.BMPConnectionData) or None
        """
        if bmp_string is None or bmp_string == "None":
            return None
        return [self._parse_bmp_connection(bmp_connection)
                for bmp_connection in bmp_string.split(":")]

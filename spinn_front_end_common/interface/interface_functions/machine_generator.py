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

from spinn_utilities.log import FormatAdapter
from spinnman.constants import POWER_CYCLE_WAIT_TIME_IN_SECONDS
from spinnman.transceiver import create_transceiver_from_hostname
from spinnman.model import BMPConnectionData
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.exceptions import ConfigurationException
import time
import logging

logger = FormatAdapter(logging.getLogger(__name__))

POWER_CYCLE_WARNING = (
    "When power-cycling a board, it is recommended that you wait for 30 "
    "seconds before attempting a reboot. Therefore, the tools will now "
    "wait for 30 seconds. If you wish to avoid this wait, please set "
    "reset_machine_on_startup = False in the [Machine] section of the "
    "relevant configuration (cfg) file.")

POWER_CYCLE_FAILURE_WARNING = (
    "The end user requested the power-cycling of the board. But the "
    "tools did not have the required BMP connection to facilitate a "
    "power-cycling, and therefore will not do so. please set the "
    "bmp_names accordingly in the [Machine] section of the relevant "
    "configuration (cfg) file. Or use a machine assess process which "
    "provides the BMP data (such as a spalloc system) or finally set "
    "reset_machine_on_startup = False in the [Machine] section of the "
    "relevant configuration (cfg) file to avoid this warning in future.")


def machine_generator(
        bmp_details, board_version, auto_detect_bmp,
        scamp_connection_data,reset_machine_on_start_up):
    """ Makes a transceiver and a machine object.

    :param str bmp_details: the details of the BMP connections
    :param int board_version:
        the version of the boards being used within the machine
        (1, 2, 3, 4 or 5)
    :param bool auto_detect_bmp:
        Whether the BMP should be automatically determined
    :param scamp_connection_data:
        Job.connection dict,a String SC&MP connection data or None
    :type scamp_connection_data:
        dict((int,int), str) or None
    :param bool reset_machine_on_start_up:
    :return: Transceiver, and description of machine it is connected to
    :rtype: tuple(~spinn_machine.Machine,
        ~spinnman.transceiver.Transceiver)
    """
    # pylint: disable=too-many-arguments

    txrx = create_transceiver_from_hostname(
        hostname=FecDataView.get_ipaddress(),
        bmp_connection_data=_parse_bmp_details(bmp_details),
        version=board_version,
        auto_detect_bmp=auto_detect_bmp)

    if reset_machine_on_start_up:
        success = txrx.power_off_machine()
        if success:
            logger.warning(POWER_CYCLE_WARNING)
            time.sleep(POWER_CYCLE_WAIT_TIME_IN_SECONDS)
            logger.warning("Power cycle wait complete")
        else:
            logger.warning(POWER_CYCLE_FAILURE_WARNING)

    # do auto boot if possible
    if board_version is None:
        raise ConfigurationException(
            "Please set a machine version number in the "
            "corresponding configuration (cfg) file")
    txrx.ensure_board_is_ready()
    if scamp_connection_data:
        txrx.add_scamp_connections(scamp_connection_data)
    else:
        txrx.discover_scamp_connections()
    return txrx.get_machine_details(), txrx


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


def _parse_bmp_connection(bmp_detail):
    """ Parses one item of BMP connection data. Maximal format:\
        `cabinet;frame;host,port/boards`

    All parts except host can be omitted. Boards can be a \
    hyphen-separated range or a comma-separated list.

    :param str bmp_detail:
    :rtype: ~.BMPConnectionData
    """
    pieces = bmp_detail.split("/")
    (cabinet, frame, hostname, port_num) = \
        _parse_bmp_cabinet_and_frame(pieces[0])
    # if there is no split, then assume its one board, located at 0
    boards = [0] if len(pieces) == 1 else _parse_bmp_boards(pieces[1])
    port_num = None if port_num is None else int(port_num)
    return BMPConnectionData(cabinet, frame, hostname, boards, port_num)


def _parse_bmp_details(bmp_string):
    """ Take a BMP line (a colon-separated list) and split it into the\
        BMP connection data.

    :param str bmp_string: the BMP string to be converted
    :return: the BMP connection data
    :rtype: list(~.BMPConnectionData) or None
    """
    if bmp_string is None or bmp_string == "None":
        return None
    return [_parse_bmp_connection(bmp_connection)
            for bmp_connection in bmp_string.split(":")]

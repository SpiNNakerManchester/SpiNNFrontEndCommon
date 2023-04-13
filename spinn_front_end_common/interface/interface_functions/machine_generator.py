# Copyright (c) 2015 The University of Manchester
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
        scamp_connection_data, reset_machine_on_start_up):
    """
    Makes a transceiver and a machine object.

    :param str bmp_details: the details of the BMP connections
    :param int board_version:
        the version of the boards being used within the machine
        (1, 2, 3, 4 or 5)
    :param bool auto_detect_bmp:
        Whether the BMP should be automatically determined
    :param scamp_connection_data:
        Job.connection dict, a String SC&MP connection data or `None`
    :type scamp_connection_data:
        dict((int,int), str) or None
    :param bool reset_machine_on_start_up:
    :param MachineAllocationController allocation_controller:
        The allocation controller; in some cases, we delegate the creation of
        the transceiver to it.
    :return: Transceiver, and description of machine it is connected to
    :rtype: tuple(~spinn_machine.Machine,
        ~spinnman.transceiver.Transceiver)
    """
    # pylint: disable=too-many-arguments
    if FecDataView.has_allocation_controller():
        # If there is an allocation controller and it wants to make a
        # transceiver for us, we let it do so; transceivers obtained that way
        # are already fully configured
        txrx = FecDataView.get_allocation_controller().create_transceiver()
        if txrx:
            return txrx.get_machine_details(), txrx

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
    """
    Parses one item of BMP connection data. Maximal format:
    `cabinet;frame;host,port/boards`

    All parts except host can be omitted. Boards can be a
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
    """
    Take a BMP line (a colon-separated list) and split it into the
    BMP connection data.

    :param str bmp_string: the BMP string to be converted
    :return: the BMP connection data
    :rtype: list(~.BMPConnectionData) or None
    """
    if bmp_string is None or bmp_string == "None":
        return None
    return [_parse_bmp_connection(bmp_connection)
            for bmp_connection in bmp_string.split(":")]

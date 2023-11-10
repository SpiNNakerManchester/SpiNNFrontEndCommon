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

import logging
import re
from typing import Dict, List, Optional, Tuple
from spinn_utilities.log import FormatAdapter
from spinn_utilities.typing.coords import XY
from spinn_machine import Machine
from spinnman.transceiver import create_transceiver_from_hostname, Transceiver
from spinnman.model import BMPConnectionData
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.exceptions import ConfigurationException

logger = FormatAdapter(logging.getLogger(__name__))


def machine_generator(
        bmp_details: Optional[str], board_version: Optional[int],
        auto_detect_bmp: bool, scamp_connection_data: Optional[Dict[XY, str]],
        reset_machine_on_start_up: bool) -> Tuple[Machine, Transceiver]:
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
    :return: Transceiver, and description of machine it is connected to
    :rtype: tuple(~spinn_machine.Machine,
        ~spinnman.transceiver.Transceiver)
    """
    if FecDataView.has_allocation_controller():
        # If there is an allocation controller and it wants to make a
        # transceiver for us, we let it do so; transceivers obtained that way
        # are already fully configured
        if FecDataView.get_allocation_controller().can_create_transceiver():
            txrx = FecDataView.get_allocation_controller().create_transceiver()
            return txrx.get_machine_details(), txrx

    txrx = create_transceiver_from_hostname(
        hostname=FecDataView.get_ipaddress(),
        bmp_connection_data=_parse_bmp_details(bmp_details),
        auto_detect_bmp=auto_detect_bmp,
        power_cycle=reset_machine_on_start_up)

    # do auto boot if possible
    if board_version is None:
        raise ConfigurationException(
            "Please set a machine version number in the "
            "corresponding configuration (cfg) file")

    # do auto boot if possible
    if scamp_connection_data:
        txrx.add_scamp_connections(scamp_connection_data)
    else:
        txrx.discover_scamp_connections()
    return txrx.get_machine_details(), txrx


def _parse_bmp_cabinet_and_frame(bmp_str: str) -> Tuple[str, Optional[str]]:
    """
    :param str bmp_str:
    :rtype: tuple(str, str or None)
    """
    if ";" in bmp_str:
        raise NotImplementedError(
            "cfg bmp_names no longer supports cabinet and frame")
    host = bmp_str.split(",")
    if len(host) == 1:
        return bmp_str, None
    return host[0], host[1]


def _parse_bmp_boards(bmp_boards: str) -> List[int]:
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


def _parse_bmp_connection(bmp_detail: str) -> BMPConnectionData:
    """
    Parses one item of BMP connection data. Maximal format:
    `cabinet;frame;host,port/boards`

    All parts except host can be omitted. Boards can be a
    hyphen-separated range or a comma-separated list.

    :param str bmp_detail:
    :rtype: ~.BMPConnectionData
    """
    pieces = bmp_detail.split("/")
    (hostname, port_num) = _parse_bmp_cabinet_and_frame(pieces[0])
    # if there is no split, then assume its one board, located at 0
    boards = [0] if len(pieces) == 1 else _parse_bmp_boards(pieces[1])
    port = None if port_num is None else int(port_num)
    return BMPConnectionData(hostname, boards, port)


def _parse_bmp_details(
        bmp_string: Optional[str]) -> Optional[BMPConnectionData]:
    """
    Take a BMP line (a colon-separated list) and split it into the
    BMP connection data.

    :param str bmp_string: the BMP string to be converted
    :return: the BMP connection data
    :rtype: ~.BMPConnectionData or None
    """
    if bmp_string is None or bmp_string == "None":
        return None
    if ":" in bmp_string:
        raise NotImplementedError(
            "bmp_names can no longer contain multiple bmps")
    return _parse_bmp_connection(bmp_string)

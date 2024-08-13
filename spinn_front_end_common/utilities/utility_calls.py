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

"""
Utility calls for interpreting bits of the DSG
"""

import io
import os
import threading
from typing import (Optional, Union, TextIO, TypeVar)
from spinn_utilities.config_holder import get_config_bool
from spinn_machine import Chip
from spinnman.connections.udp_packet_connections import SCAMPConnection
from spinnman.utilities.utility_functions import (
    reprogram_tag, reprogram_tag_to_listener)
from spinnman.spalloc import SpallocEIEIOListener, SpallocEIEIOConnection
from pacman.model.placements import Placements
from spinn_front_end_common.utilities.constants import (
    APP_PTR_TABLE_HEADER_BYTE_SIZE, APP_PTR_TABLE_REGION_BYTE_SIZE)
from spinn_front_end_common.data import FecDataView

# used to stop file conflicts
_lock_condition = threading.Condition()
#: :meta private:
T = TypeVar("T")


def _mkdir(directory: str):
    """
    Make a directory if it doesn't exist.

    .. note::
        This code is not intended to be secure against malicious third parties

    :param str directory: The directory to create
    """
    # Guarded to stop us from hitting things twice internally; it's not
    # perfect since other processes could also happen along.
    with _lock_condition:
        try:
            if not os.path.exists(directory):
                os.mkdir(directory)
        except OSError:  # pragma: no cover
            # Assume an external race beat us
            pass


def get_region_base_address_offset(
        app_data_base_address: int, region: int) -> int:
    """
    Find the address of the of a given region for the DSG.

    :param int app_data_base_address: base address for the core
    :param int region: the region ID we're looking for
    """
    return (app_data_base_address +
            APP_PTR_TABLE_HEADER_BYTE_SIZE +
            (region * APP_PTR_TABLE_REGION_BYTE_SIZE))


_DAT_TMPL = "dataSpec_{}_{}_{}.dat"
_RPT_TMPL = "dataSpec_{}_{}_{}.txt"
_RPT_DIR = "data_spec_text_files"


def get_report_writer(
        processor_chip_x: int, processor_chip_y: int,
        processor_id: int, use_run_number: bool = False) -> Optional[TextIO]:
    """
    Check if text reports are needed, and if so initialise the report
    writer to send down to DSG.

    :param int processor_chip_x: X coordinate of the chip
    :param int processor_chip_y: Y coordinate of the chip
    :param int processor_id: The processor ID
    :param bool use_run_number:
        If set the directory will include the run number
    :return: the report_writer_object, or `None` if not reporting
    :rtype: ~io.FileIO or None
    """
    # check if text reports are needed at all
    if not get_config_bool("Reports", "write_text_specs"):
        return None
    # initialise the report writer to send down to DSG
    dir_name = _RPT_DIR
    if use_run_number:
        dir_name += str(FecDataView.get_run_number())
    new_report_directory = os.path.join(
        FecDataView.get_run_dir_path(), dir_name)
    _mkdir(new_report_directory)
    name = os.path.join(new_report_directory, _RPT_TMPL.format(
        processor_chip_x, processor_chip_y, processor_id))
    return io.TextIOWrapper(io.FileIO(name, "w"))


def retarget_tag(
        connection: Union[SpallocEIEIOListener, SpallocEIEIOConnection,
                          SCAMPConnection], x: int, y: int, tag: int,
        ip_address: Optional[str] = None, strip: bool = True):
    """
    Make a tag deliver to the given connection.

    :param connection: The connection to deliver to.
    :type connection:
        ~spinnman.connections.udp_packet_connections.UDPConnection
    :param int x:
        The X coordinate of the Ethernet-enabled chip we are sending the
        message to.
    :param int y:
        The Y coordinate of the Ethernet-enabled chip we are sending the
        message to.
    :param int tag:
        The ID of the tag to retarget.
    :param str ip_address:
        What IP address to send the message to. If ``None``, the connection is
        assumed to be connected to a specific board already.
    :param bool strip:
        Whether the tag should strip the SDP header before sending to the
        connection.
    """
    # If the connection itself knows how, delegate to it
    if isinstance(connection, SpallocEIEIOListener):
        connection.update_tag(x, y, tag)
    elif isinstance(connection, SpallocEIEIOConnection):
        connection.update_tag(tag)
    elif ip_address:
        reprogram_tag_to_listener(connection, x, y, ip_address, tag, strip)
    else:
        reprogram_tag(connection, tag, strip)


def open_scp_connection(
        chip_x: int, chip_y: int, chip_ip_address: str) -> SCAMPConnection:
    """
    Create an SCP connection to the given Ethernet-enabled chip. SpiNNaker will
    not be configured to map that connection to a tag; that is the
    caller's responsibility.

    :param int chip_x:
        X coordinate of the Ethernet-enabled chip to connect to.
    :param int chip_y:
        Y coordinate of the Ethernet-enabled chip to connect to.
    :param str chip_ip_address:
        IP address of the Ethernet-enabled chip to connect to.
    :rtype: ~spinnman.connections.udp_packet_connections.SCAMPConnection
    """
    if FecDataView.has_allocation_controller():
        # See if the allocation controller wants to do it
        conn = FecDataView.get_allocation_controller().open_sdp_connection(
            chip_x, chip_y)
        if conn:
            return conn
    return SCAMPConnection(chip_x, chip_y, remote_host=chip_ip_address)


def pick_core_for_system_placement(
        system_placements: Placements, chip: Chip) -> int:
    """
    Get a core number for use putting a system placement on a chip.

    :param ~pacman.model.placements.Placements system_placements:
        Already-made system placements
    :param ~spinn_machine.Chip chip: Chip of interest
    :return: a core that a system placement could be put on
    :rtype: int
    """
    cores = chip.placable_processors_ids
    return cores[system_placements.n_placements_on_chip(chip)]

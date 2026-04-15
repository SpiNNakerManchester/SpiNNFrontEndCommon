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
from typing import (Optional, Union, TextIO, Tuple, TypeVar)

from urllib.parse import urlparse

from spinn_utilities.config_holder import (
    get_config_bool, get_config_str, get_report_path)

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


def _mkdir(directory: str) -> None:
    """
    Make a directory if it doesn't exist.

    .. note::
        This code is not intended to be secure against malicious third parties

    :param directory: The directory to create
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
    :param app_data_base_address: base address for the core
    :param region: the region ID we're looking for
    :returns: The address of the of a given region for the DSG.
    """
    return (app_data_base_address +
            APP_PTR_TABLE_HEADER_BYTE_SIZE +
            (region * APP_PTR_TABLE_REGION_BYTE_SIZE))


_DAT_TMPL = "dataSpec_{}_{}_{}.dat"
_RPT_TMPL = "dataSpec_{}_{}_{}.txt"


def get_report_writer(
        processor_chip_x: int, processor_chip_y: int,
        processor_id: int, use_run_number: bool = False) -> Optional[TextIO]:
    """
    Check if text reports are needed, and if so initialise the report
    writer to send down to DSG.

    :param processor_chip_x: X coordinate of the chip
    :param processor_chip_y: Y coordinate of the chip
    :param processor_id: The processor ID
    :param use_run_number:
        If set the directory will include the run number
    :return: the report_writer_object, or `None` if not reporting
    """
    # check if text reports are needed at all
    if not get_config_bool("Reports", "write_text_specs"):
        return None
    # initialise the report writer to send down to DSG
    new_report_directory = get_report_path("path_text_specs", is_dir=True)
    if use_run_number:
        new_report_directory += str(FecDataView.get_run_number())
    _mkdir(new_report_directory)
    name = os.path.join(new_report_directory, _RPT_TMPL.format(
        processor_chip_x, processor_chip_y, processor_id))
    return io.TextIOWrapper(io.FileIO(name, "w"))


def parse_old_spalloc(
        spalloc_server: str, spalloc_port: int,
        spalloc_user: str) -> Tuple[str, int, str]:
    """
    Parse a URL to the old-style service. This may take the form:

        spalloc://user@spalloc.host.example.com:22244

    The leading ``spalloc://`` is the mandatory part (as is the actual host
    name). If the port and user are omitted, the defaults given in the other
    arguments are used (or default defaults).

    A bare hostname can be used instead. If that's the case (i.e., there's no
    ``spalloc://`` prefix) then the port and user are definitely used.

    :param spalloc_server: Hostname or URL
    :param spalloc_port: Default port
    :param spalloc_user: Default user
    :return: hostname, port, username
    """
    if spalloc_port is None or spalloc_port == "":
        spalloc_port = 22244
    if spalloc_user is None or spalloc_user == "":
        spalloc_user = "unknown user"
    parsed = urlparse(spalloc_server, "spalloc")
    if parsed.netloc == "" or parsed.hostname is None:
        return spalloc_server, spalloc_port, spalloc_user
    return parsed.hostname, (parsed.port or spalloc_port), \
        (parsed.username or spalloc_user)


def retarget_tag(
        connection: Union[SpallocEIEIOListener, SpallocEIEIOConnection,
                          SCAMPConnection], x: int, y: int, tag: int,
        ip_address: Optional[str] = None, strip: bool = True) -> None:
    """
    Make a tag deliver to the given connection.

    :param connection: The connection to deliver to.
    :param x:
        The X coordinate of the Ethernet-enabled chip we are sending the
        message to.
    :param y:
        The Y coordinate of the Ethernet-enabled chip we are sending the
        message to.
    :param tag:
        The ID of the tag to retarget.
    :param ip_address:
        What IP address to send the message to. If ``None``, the connection is
        assumed to be connected to a specific board already.
    :param strip:
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


def pick_core_for_system_placement(
        system_placements: Placements, chip: Chip) -> int:
    """
    Get a core number for use putting a system placement on a chip.

    :param system_placements:
        Already-made system placements
    :param chip: Chip of interest
    :return: a core that a system placement could be put on
    """
    cores = chip.placable_processors_ids
    return cores[system_placements.n_placements_on_chip(chip)]


def check_file_exists(path: str) -> None:
    """
    Check to see a file that should exist does

    Raises an exception if it does not

    :param path: path to file that should exist
    :raises FileNotFoundError: If the path does not exists
    """
    if os.path.exists(path):
        return

    if FecDataView.is_shutdown():
        mode = get_config_str("Mode", "mode").lower()
        if mode == "production":
            raise FileNotFoundError(
                f"In Mode production many files are deleted on end. "
                f"That may explain missing {path}")
        else:
            raise FileNotFoundError(
                f"end has been been called. "
                f"That may explain missing {path}")
    elif FecDataView.is_reset_last():
        raise FileNotFoundError(
            f"reset has been been called. "
            f"That may explain missing {path}")
    elif FecDataView.is_ran_ever():
        # no clear reason
        raise FileNotFoundError(path)
    else:
        raise FileNotFoundError(
            f"Simulation has never run. "
            f"That may explain missing {path}")

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
import tempfile
import threading
from urllib.parse import urlparse
from spinn_utilities.config_holder import get_config_bool
from spinnman.connections.udp_packet_connections import SCAMPConnection
from spinnman.utilities.utility_functions import (
    reprogram_tag, reprogram_tag_to_listener)
from spinnman.spalloc import SpallocEIEIOListener, SpallocEIEIOConnection
from data_specification.constants import (
    APP_PTR_TABLE_HEADER_BYTE_SIZE, APP_PTR_TABLE_REGION_BYTE_SIZE)
from data_specification.data_specification_generator import (
    DataSpecificationGenerator)
from spinn_front_end_common.data import FecDataView

# used to stop file conflicts
_lock_condition = threading.Condition()


def _mkdir(directory):
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


def get_region_base_address_offset(app_data_base_address, region):
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


def get_data_spec_and_file_writer_filename(
        processor_chip_x, processor_chip_y, processor_id,
        application_run_time_report_folder="TEMP"):
    """
    Encapsulates the creation of the DSG writer and the file paths.

    :param int processor_chip_x: X coordinate of the chip
    :param int processor_chip_y: Y coordinate of the chip
    :param int processor_id: The processor ID
    :param str application_run_time_report_folder:
        The folder to contain the resulting specification files; if ``TEMP``
        then a temporary directory is used.
    :return: the filename of the data writer and the data specification object
    :rtype: tuple(str, ~data_specification.DataSpecificationGenerator)
    """
    # pylint: disable=too-many-arguments
    if application_run_time_report_folder == "TEMP":
        application_run_time_report_folder = tempfile.gettempdir()

    filename = os.path.join(
        application_run_time_report_folder, _DAT_TMPL.format(
            processor_chip_x, processor_chip_y, processor_id))
    data_writer = io.FileIO(filename, "wb")

    # check if text reports are needed and if so initialise the report
    # writer to send down to DSG
    report_writer = get_report_writer(
        processor_chip_x, processor_chip_y, processor_id)

    # build the file writer for the spec
    spec = DataSpecificationGenerator(data_writer, report_writer)

    return filename, spec


def get_report_writer(processor_chip_x, processor_chip_y, processor_id):
    """
    Check if text reports are needed, and if so initialise the report
    writer to send down to DSG.

    :param int processor_chip_x: X coordinate of the chip
    :param int processor_chip_y: Y coordinate of the chip
    :param int processor_id: The processor ID
    :return: the report_writer_object, or `None` if not reporting
    :rtype: ~io.FileIO or None
    """
    # pylint: disable=too-many-arguments

    # check if text reports are needed at all
    if not get_config_bool("Reports", "write_text_specs"):
        return None
    # initialise the report writer to send down to DSG
    new_report_directory = os.path.join(
        FecDataView.get_run_dir_path(), _RPT_DIR)
    _mkdir(new_report_directory)
    name = os.path.join(new_report_directory, _RPT_TMPL.format(
        processor_chip_x, processor_chip_y, processor_id))
    return io.TextIOWrapper(io.FileIO(name, "w"))


def parse_old_spalloc(
        spalloc_server, spalloc_port=22244, spalloc_user="unknown user"):
    """
    Parse a URL to the old-style service. This may take the form:

        spalloc://user@spalloc.host.example.com:22244

    The leading ``spalloc://`` is the mandatory part (as is the actual host
    name). If the port and user are omitted, the defaults given in the other
    arguments are used (or default defaults).

    A bare hostname can be used instead. If that's the case (i.e., there's no
    ``spalloc://`` prefix) then the port and user are definitely used.

    :param str spalloc_server: Hostname or URL
    :param int spalloc_port: Default port
    :param str spalloc_user: Default user
    :return: hostname, port, username
    :rtype: tuple(str,int,str)
    """
    if spalloc_port is None or spalloc_port == "":
        spalloc_port = 22244
    if spalloc_user is None or spalloc_user == "":
        spalloc_user = "unknown user"
    parsed = urlparse(spalloc_server, "spalloc")
    if parsed.netloc == "":
        return spalloc_server, spalloc_port, spalloc_user
    return parsed.hostname, (parsed.port or spalloc_port), \
        (parsed.username or spalloc_user)


def retarget_tag(connection, x, y, tag, ip_address=None, strip=True):
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


def open_scp_connection(chip_x, chip_y, chip_ip_address):
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

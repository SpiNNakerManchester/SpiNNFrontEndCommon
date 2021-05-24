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

""" Utility calls for interpreting bits of the DSG
"""

import io
import os
import tempfile
import threading
from data_specification.constants import APP_PTR_TABLE_HEADER_BYTE_SIZE
from data_specification.data_specification_generator import (
    DataSpecificationGenerator)
from spinn_front_end_common.utilities.globals_variables import (
    report_default_directory)

# used to stop file conflicts
_lock_condition = threading.Condition()


def _mkdir(directory):
    """ Make a directory if it doesn't exist.

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
    """ Find the address of the of a given region for the DSG

    :param int app_data_base_address: base address for the core
    :param int region: the region ID we're looking for
    """
    return (app_data_base_address +
            APP_PTR_TABLE_HEADER_BYTE_SIZE + (region * 4))


_DAT_TMPL = "{}_dataSpec_{}_{}_{}.dat"
_RPT_TMPL = "{}_dataSpec_{}_{}_{}.txt"
_RPT_DIR = "data_spec_text_files"


def get_data_spec_and_file_writer_filename(
        processor_chip_x, processor_chip_y, processor_id,
        hostname, report_directory="TEMP", write_text_specs=False,
        application_run_time_report_folder="TEMP"):
    """ Encapsulates the creation of the DSG writer and the file paths.

    :param int processor_chip_x: x-coordinate of the chip
    :param int processor_chip_y: y-coordinate of the chip
    :param int processor_id: The processor ID
    :param str hostname: The hostname of the SpiNNaker machine
    :param str report_directory: the directory for the reports folder
    :param bool write_text_specs:
        True if a textual version of the specification should be written
    :param str application_run_time_report_folder:
        The folder to contain the resulting specification files; if 'TEMP'
        then a temporary directory is used.
    :return: the filename of the data writer and the data specification object
    :rtype: tuple(str, DataSpecificationGenerator)
    """
    # pylint: disable=too-many-arguments
    if application_run_time_report_folder == "TEMP":
        application_run_time_report_folder = tempfile.gettempdir()

    filename = os.path.join(
        application_run_time_report_folder, _DAT_TMPL.format(
            hostname, processor_chip_x, processor_chip_y, processor_id))
    data_writer = io.FileIO(filename, "wb")

    # check if text reports are needed and if so initialise the report
    # writer to send down to DSG
    report_writer = get_report_writer(
        processor_chip_x, processor_chip_y, processor_id,
        hostname, write_text_specs=write_text_specs)

    # build the file writer for the spec
    spec = DataSpecificationGenerator(data_writer, report_writer)

    return filename, spec


def get_report_writer(
        processor_chip_x, processor_chip_y, processor_id,
        hostname, write_text_specs=False):
    """ Check if text reports are needed, and if so initialise the report\
        writer to send down to DSG.

    :param int processor_chip_x: x-coordinate of the chip
    :param int processor_chip_y: y-coordinate of the chip
    :param int processor_id: The processor ID
    :param str hostname: The hostname of the SpiNNaker machine
    :param bool write_text_specs:
        True if a textual version of the specification should be written
    :return: the report_writer_object, or None if not reporting
    :rtype: ~io.FileIO or None
    """
    # pylint: disable=too-many-arguments

    # check if text reports are needed at all
    if not write_text_specs:
        return None
    # initialise the report writer to send down to DSG
    new_report_directory = os.path.join(report_default_directory(), _RPT_DIR)
    _mkdir(new_report_directory)
    name = os.path.join(new_report_directory, _RPT_TMPL.format(
        hostname, processor_chip_x, processor_chip_y, processor_id))
    return io.TextIOWrapper(io.FileIO(name, "w"))

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

import os
from spinn_front_end_common.utilities.globals_variables import (
    report_default_directory)

_REPORT_FILENAME = "tags_on_machine.txt"


def tags_from_machine_report(transceiver):
    """ Describes what the tags actually present on the machine are.

    :param str report_default_directory:
    :param ~spinnman.transceiver.Transceiver transceiver:
    """
    filename = os.path.join(report_default_directory(), _REPORT_FILENAME)
    tags = _get_tags(transceiver)
    with open(filename, "w", encoding="utf-8") as f:
        f.write("Tags actually read off the machine\n")
        f.write("==================================\n")
        for tag in tags:
            f.write(f"{repr(tag)}\n")


def _get_tags(txrx):
    try:
        return txrx.get_tags()
    except Exception as e:  # pylint: disable=broad-except
        return [e]

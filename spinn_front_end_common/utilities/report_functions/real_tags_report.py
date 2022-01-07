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
from spinn_front_end_common.data import FecDataView

_REPORT_FILENAME = "tags_on_machine.txt"


def tags_from_machine_report():
    """ Describes what the tags actually present on the machine are.

    """
    filename = os.path.join(FecDataView.get_run_dir_path(), _REPORT_FILENAME)
    tags = _get_tags()
    with open(filename, "w") as f:
        f.write("Tags actually read off the machine\n")
        f.write("==================================\n")
        for tag in tags:
            f.write(f"{repr(tag)}\n")


def _get_tags():
    try:
        return FecDataView.get_transceiver().get_tags()
    except Exception as e:  # pylint: disable=broad-except
        return [e]

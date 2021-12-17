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

import json
import os
from spinn_utilities.progress_bar import ProgressBar
from spinn_machine.json_machine import to_json
from pacman.utilities import file_format_schemas
from spinn_front_end_common.data import FecDataView

MACHINE_FILENAME = "machine.json"


def write_json_machine(json_folder=None, progress_bar=True):
    """ Runs the code to write the machine in Java readable JSON.

    .. warning::
         The file in this folder will be overwritten!

    :param str json_folder: the folder to which the JSON are being written
    :param bool progress_bar: Flag if Progress Bar should be shown
    :return: the name of the generated file
    :rtype: str
    """

    if progress_bar:
        # Steps are tojson, validate and writefile
        progress = ProgressBar(3, "Converting to JSON machine")
    else:
        progress = None
    if json_folder is None:
        json_folder = FecDataView().json_dir_path
    file_path = os.path.join(json_folder, MACHINE_FILENAME)
    if not os.path.exists(file_path):
        json_obj = to_json()

        if progress:
            progress.update()

        # validate the schema
        file_format_schemas.validate(json_obj, MACHINE_FILENAME)

        # update and complete progress bar
        if progress:
            progress.end()

        # dump to json file
        with open(file_path, "w") as f:
            json.dump(json_obj, f)

    if progress:
        progress.end()

    return file_path

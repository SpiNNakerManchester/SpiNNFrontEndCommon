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

import json
import os
from spinn_utilities.progress_bar import ProgressBar
from spinn_machine.json_machine import to_json
from pacman.utilities import file_format_schemas
from spinn_front_end_common.data import FecDataView

MACHINE_FILENAME = "machine.json"


def write_json_machine(json_folder=None, progress_bar=True, validate=True):
    """
    Runs the code to write the machine in Java readable JSON.

    .. warning::
         The file in this folder will be overwritten!

    :param str json_folder: the folder to which the JSON are being written
    :param bool progress_bar: Flag if Progress Bar should be shown
    :param bool validate: Flag to disable the validation.
    :return: the name of the generated file
    :rtype: str
    """
    if progress_bar:
        # Steps are tojson, validate and writefile
        progress = ProgressBar(3, "Converting to JSON machine")
    else:
        progress = None
    if json_folder is None:
        json_folder = FecDataView.get_json_dir_path()
    file_path = os.path.join(json_folder, MACHINE_FILENAME)
    if not os.path.exists(file_path):
        json_obj = to_json()

        if progress:
            progress.update()

        if validate:
            # validate the schema
            file_format_schemas.validate(json_obj, MACHINE_FILENAME)

        # update and complete progress bar
        if progress:
            progress.end()

        # dump to json file
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(json_obj, f)

    if progress:
        progress.end()

    return file_path

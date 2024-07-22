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
from typing import Optional
from spinn_utilities.progress_bar import ProgressBar, DummyProgressBar
from spinn_machine.json_machine import to_json
from pacman.utilities import file_format_schemas
from spinn_front_end_common.data import FecDataView

#: The name of the generated JSON machine description file.
#: Also the name of the schema that we validate against.
MACHINE_FILENAME = "machine.json"


def write_json_machine(
        json_folder: Optional[str] = None, progress_bar: bool = True,
        validate: bool = True) -> str:
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
    json_folder = json_folder or FecDataView.get_json_dir_path()
    file_path = os.path.join(json_folder, MACHINE_FILENAME)
    if not os.path.exists(file_path):
        with _progress(progress_bar) as progress:
            # Step 1: generate
            json_obj = to_json()
            progress.update()
            # Step 2: validate against the schema
            if validate:
                file_format_schemas.validate(json_obj, MACHINE_FILENAME)
            progress.update()
            # Step 3: dump to json file
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(json_obj, f)
    return file_path


def _progress(progress_bar: bool) -> ProgressBar:
    # Steps are create json object, validate json and write json to a file
    if progress_bar:
        return ProgressBar(3, "Converting to JSON machine")
    else:
        return DummyProgressBar(3, "Converting to JSON machine")

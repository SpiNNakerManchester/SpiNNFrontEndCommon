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

import logging
import json
import os
from spinn_utilities.log import FormatAdapter
from spinn_utilities.progress_bar import ProgressBar
from pacman.utilities import file_format_schemas
from pacman.utilities.json_utils import placements_to_json
from jsonschema.exceptions import ValidationError
from spinn_front_end_common.data import FecDataView

PLACEMENTS_FILENAME = "placements.json"
logger = FormatAdapter(logging.getLogger(__name__))


def write_json_placements():
    """
    Runs the code to write the placements in JSON.
    """
    # Steps are tojson, validate and writefile
    progress = ProgressBar(3, "Converting to JSON Placements")

    file_path = os.path.join(
        FecDataView.get_json_dir_path(), PLACEMENTS_FILENAME)
    json_obj = placements_to_json()

    # validate the schema
    try:
        file_format_schemas.validate(json_obj, PLACEMENTS_FILENAME)
    except ValidationError as ex:
        logger.error("JSON validation exception: {}\n{}",
                     ex.message, ex.instance)

    # update and complete progress bar
    progress.update()

    # dump to json file
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(json_obj, f)

    progress.end()

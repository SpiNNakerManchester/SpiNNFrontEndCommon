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

from spinn_utilities.config_holder import get_config_bool, get_report_path
from spinn_utilities.log import FormatAdapter
from spinn_utilities.progress_bar import ProgressBar
from pacman.utilities import file_format_schemas
from pacman.utilities.json_utils import placements_to_json

_PLACEMENTS_SCHEMA = "placements.json"
logger = FormatAdapter(logging.getLogger(__name__))


def write_json_placements() -> None:
    """
    Runs the code to write the placements in JSON.
    """
    file_path = get_report_path("path_json_placements")
    # Steps are create json object, validate json and write json to a file
    with ProgressBar(3, "Converting to JSON Placements") as progress:
        json_obj = placements_to_json()
        progress.update()

        if get_config_bool("Mapping", "validate_json"):
            file_format_schemas.validate(json_obj, _PLACEMENTS_SCHEMA)
        progress.update()

        # dump to json file
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(json_obj, f)
        progress.update()

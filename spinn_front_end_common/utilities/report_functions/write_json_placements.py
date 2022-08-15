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
    """ Runs the code to write the placements in JSON.

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

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

PLACEMENTS_FILENAME = "placements.json"
logger = FormatAdapter(logging.getLogger(__name__))


class WriteJsonPlacements(object):
    """ Converter from Placements to JSON.
    """

    def __call__(self, placements, json_folder):
        """ Runs the code to write the placements in JSON.

        :param Placements placements: The placements to write.
        :param str json_folder: The folder to which the JSON are being written.
        :return: The name of the generated file.
        :rtype: str
        """
        # Steps are tojson, validate and writefile
        progress = ProgressBar(3, "Converting to JSON Placements")

        return WriteJsonPlacements.write_json(
            placements, json_folder, progress)

    @staticmethod
    def write_json(placements, json_folder, progress=None):
        """ Runs the code to write the placements in Java readable JSON.

        :param Placements placements: The placements to write
        :param str json_folder: the folder to which the JSON are being written
        :param progress: Progress Bar if one used
        :type progress: ~spinn_utilities.progress_bar.ProgressBar or None
        :return: the name of the generated file
        :rtype: str
        """

        file_path = os.path.join(json_folder, PLACEMENTS_FILENAME)
        json_obj = placements_to_json(placements)

        if progress:
            progress.update()

        # validate the schema
        try:
            file_format_schemas.validate(json_obj, PLACEMENTS_FILENAME)
        except ValidationError as ex:
            logger.error("JSON validation exception: {}\n{}",
                         ex.message, ex.instance)

        # update and complete progress bar
        if progress:
            progress.update()

        # dump to json file
        with open(file_path, "w") as f:
            json.dump(json_obj, f)

        if progress:
            progress.end()

        return file_path

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
from pacman.utilities.json_utils import partition_to_n_keys_map_to_json
from jsonschema.exceptions import ValidationError
from spinn_front_end_common.data import FecDataView

N_KEYS_MAP_FILENAME = "n_keys_map.json"
logger = FormatAdapter(logging.getLogger(__name__))


def write_json_partition_n_keys_map(partition_to_n_keys_map):
    """ Converter from MulticastRoutingTables to JSON.

    :param AbstractMachinePartitionNKeysMap partition_to_n_keys_map:
        The number of keys needed for each partition.
    :param str json_folder: the folder to which the JSON are being written
    :return: the name of the generated file
    :rtype: str
    """
    # Steps are tojson, validate and writefile
    progress = ProgressBar(3, "Converting to JSON partition n key map")

    file_path = os.path.join(FecDataView().json_dir_path, N_KEYS_MAP_FILENAME)
    json_obj = partition_to_n_keys_map_to_json(partition_to_n_keys_map)

    if progress:
        progress.update()

    # validate the schema
    try:
        file_format_schemas.validate(json_obj, N_KEYS_MAP_FILENAME)
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

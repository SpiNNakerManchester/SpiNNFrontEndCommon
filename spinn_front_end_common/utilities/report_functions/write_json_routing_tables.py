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
from pacman.utilities import file_format_schemas
from pacman.model.routing_tables.multicast_routing_tables import to_json
from spinn_front_end_common.data import FecDataView

ROUTING_TABLES_FILENAME = "routing_tables.json"


def write_json_routing_tables(router_tables):
    """
    Runs the code to write the machine in Java readable JSON.

    :param ~pacman.model.routing_tables.MulticastRoutingTables router_tables:
        Routing Tables to convert. Could be uncompressed or compressed
    :param str json_folder: the folder to which the JSON are being written
    """
    # Steps are tojson, validate and writefile
    progress = ProgressBar(3, "Converting to JSON RouterTables")

    file_path = os.path.join(
        FecDataView.get_json_dir_path(), ROUTING_TABLES_FILENAME)
    json_obj = to_json(router_tables)

    if progress:
        progress.update()

    # validate the schema
    file_format_schemas.validate(json_obj, ROUTING_TABLES_FILENAME)

    # update and complete progress bar
    if progress:
        progress.update()

    # dump to json file
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(json_obj, f)

    if progress:
        progress.end()

    return file_path

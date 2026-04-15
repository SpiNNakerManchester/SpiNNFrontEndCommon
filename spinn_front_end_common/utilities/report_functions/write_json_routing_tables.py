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

from spinn_utilities.config_holder import get_config_bool, get_report_path
from spinn_utilities.progress_bar import ProgressBar
from pacman.utilities import file_format_schemas
from pacman.model.routing_tables.multicast_routing_tables import (
    to_json, MulticastRoutingTables)

_ROUTING_TABLES_SCHEMA = "routing_tables.json"


def write_json_routing_tables(router_tables: MulticastRoutingTables) -> str:
    """
    Runs the code to write the machine in Java readable JSON.

    :param router_tables:
        Routing Tables to convert. Could be uncompressed or compressed
    :returns: Path to the json file
    """
    file_path = get_report_path("path_json_routing_tables")
    # Steps are create json object, validate json and write json to a file
    with ProgressBar(3, "Converting to JSON RouterTables") as progress:
        json_obj = to_json(router_tables)
        progress.update()

        if get_config_bool("Mapping", "validate_json"):
            # validate the schema
            file_format_schemas.validate(json_obj, _ROUTING_TABLES_SCHEMA)
        progress.update()

        # dump to json file
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(json_obj, f)
        progress.update()

    return file_path

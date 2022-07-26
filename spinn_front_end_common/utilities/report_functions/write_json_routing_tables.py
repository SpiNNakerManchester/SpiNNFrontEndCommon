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
from pacman.utilities import file_format_schemas
from pacman.model.routing_tables.multicast_routing_tables import to_json
from spinn_front_end_common.data import FecDataView

ROUTING_TABLES_FILENAME = "routing_tables.json"


def write_json_routing_tables(router_tables):
    """ Runs the code to write the machine in Java readable JSON.

    :param MulticastRoutingTables router_tables:
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

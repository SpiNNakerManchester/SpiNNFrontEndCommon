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

ROUTING_TABLES_FILENAME = "routing_tables.json"


class WriteJsonRoutingTables(object):
    """ Converter from MulticastRoutingTables to JSON.
    """

    def __call__(self, router_tables, json_folder):
        """ Runs the code to write the machine in Java readable JSON.

        :param MulticastRoutingTables router_tables:
            Routing Tables to convert
        :param str json_folder: the folder to which the JSON are being written
        :return: the name of the generated file
        :rtype: str
        """
        # Steps are tojson, validate and writefile
        progress = ProgressBar(3, "Converting to JSON RouterTables")

        return WriteJsonRoutingTables.do_convert(
            router_tables, json_folder, progress)

    @staticmethod
    def do_convert(router_tables, json_folder, progress=None):
        """ Runs the code to write the machine in Java readable JSON.

        :param MulticastRoutingTables router_tables:
            Routing Tables to convert
        :param str json_folder:
            the folder to which the JSON files are being written
        :param progress: The progress bar, if any
        :type progress: ~spinn_utilities.progress_bar.ProgressBar or None
        :return: the name of the generated file
        :rtype: str
        """

        file_path = os.path.join(json_folder, ROUTING_TABLES_FILENAME)
        json_obj = to_json(router_tables)

        if progress:
            progress.update()

        # validate the schema
        file_format_schemas.validate(json_obj, ROUTING_TABLES_FILENAME)

        # update and complete progress bar
        if progress:
            progress.update()

        # dump to json file
        with open(file_path, "w") as f:
            json.dump(json_obj, f)

        if progress:
            progress.end()

        return file_path

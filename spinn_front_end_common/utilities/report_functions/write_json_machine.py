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
from spinn_machine.json_machine import to_json
from pacman.utilities import file_format_schemas
from spinn_front_end_common.data import FecDataView

MACHINE_FILENAME = "machine.json"


class WriteJsonMachine(object):
    """ Converter from memory machine to java machine.

    .. note::
        This is no longer the rig machine format!

    """

    def __call__(self, machine, json_folder=None):
        """ Runs the code to write the machine in readable JSON.

        :param ~spinn_machine.Machine machine: Machine to convert
        :param json_folder: The folder (if not the standard one)
        to which the JSON are being (over)written.
        :type json_folder: None or str
        :return: the name of the generated file
        :rtype: str
        """
        # Steps are tojson, validate and writefile
        progress = ProgressBar(3, "Converting to JSON machine")

        return WriteJsonMachine.write_json(machine, progress, json_folder)

    @staticmethod
    def write_json(machine, progress=None, json_folder=None):
        """ Runs the code to write the machine in Java readable JSON.

        :param ~spinn_machine.Machine machine: Machine to convert
        :param progress: Progress Bar if one used
        :type progress: ~spinn_utilities.progress_bar.ProgressBar or None
        :param json_folder: The folder (if not the standard one)
        to which the JSON are being (over)written.
        :type json_folder: None or str
        :return: the name of the generated file
        :rtype: str
        """
        if json_folder is None:
            json_folder = FecDataView().json_dir_path
        file_path = os.path.join(json_folder, MACHINE_FILENAME)
        if not os.path.exists(file_path):
            json_obj = to_json(machine)

            if progress:
                progress.update()

            # validate the schema
            file_format_schemas.validate(json_obj, MACHINE_FILENAME)

            # update and complete progress bar
            if progress:
                progress.end()

            # dump to json file
            with open(file_path, "w") as f:
                json.dump(json_obj, f)

        if progress:
            progress.end()

        return file_path

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

import os
from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.data import FecDataView


def fixed_route_from_machine_report():
    """ Writes the fixed routes from the machine

        :param int app_id: the application ID the fixed routes were loaded with
        """
    file_name = os.path.join(
        FecDataView.get_run_dir_path(), "fixed_route_routers")
    transceiver = FecDataView().transceiver
    machine = FecDataView.get_machine()

    progress = ProgressBar(machine.n_chips, "Writing fixed route report")

    app_id = FecDataView().app_id
    with open(file_name, "w") as f:
        f.write(" x    y       route         [cores][links]\n")
        for chip in progress.over(machine.chips):
            if not chip.virtual:
                fixed_route = transceiver.read_fixed_route(
                    chip.x, chip.y, app_id)
                f.write("{: <3s}:{: <3s} contains route {: <10s} {}\n".format(
                    str(chip.x), str(chip.y),
                    _reduce_route_value(
                        fixed_route.processor_ids, fixed_route.link_ids),
                    _expand_route_value(
                        fixed_route.processor_ids, fixed_route.link_ids)))


def _reduce_route_value(processors_ids, link_ids):
    value = 0
    for link in link_ids:
        value += 1 << link
    for processor in processors_ids:
        value += 1 << (processor + 6)
    return str(value)


def _expand_route_value(processors_ids, link_ids):
    """ Convert a 32-bit route word into a string which lists the target\
        cores and links.
    """

    # Convert processor targets to readable values:
    route_string = "["
    separator = ""
    for processor in processors_ids:
        route_string += separator + str(processor)
        separator = ", "

    route_string += "] ["

    # Convert link targets to readable values:
    link_labels = {0: 'E', 1: 'NE', 2: 'N', 3: 'W', 4: 'SW', 5: 'S'}

    separator = ""
    for link in link_ids:
        route_string += separator + link_labels[link]
        separator = ", "
    route_string += "]"
    return route_string

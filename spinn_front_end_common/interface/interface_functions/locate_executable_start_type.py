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

from spinn_utilities.progress_bar import ProgressBar
from spinn_machine import CoreSubsets
from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary
from spinn_front_end_common.utilities.utility_objs import ExecutableType


def locate_executable_start_type(placements):
    """ Discovers where applications of particular types need to be launched.

    :param ~pacman.model.placements.Placements placements:
    :rtype: dict(ExecutableType,~spinn_machine.CoreSubsets or None)
    """
    binary_start_types = dict()

    progress = ProgressBar(
        placements.n_placements, "Finding executable start types")
    for placement in progress.over(placements.placements):

        if isinstance(placement.vertex, AbstractHasAssociatedBinary):
            bin_type = placement.vertex.get_binary_start_type()
            # update core subset with location of the vertex on the
            # machine
            if bin_type not in binary_start_types:
                binary_start_types[bin_type] = CoreSubsets()

            __add_vertex_to_subset(
                placement, binary_start_types[bin_type])

    # only got apps with no binary, such as external devices.
    # return no app
    if not binary_start_types:
        return {ExecutableType.NO_APPLICATION: None}

    return binary_start_types


def __add_vertex_to_subset(placement, core_subsets):
    """
    :param ~.Placement placement:
    :param ~.CoreSubsets core_subsets:
    """
    core_subsets.add_processor(
        x=placement.x, y=placement.y, processor_id=placement.p)

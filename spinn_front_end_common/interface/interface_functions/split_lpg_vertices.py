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

from spinn_front_end_common.utility_models import LivePacketGather


def split_lpg_vertices(app_graph, machine, system_placements):
    """ Split any LPG vertices found

    :param ApplictiongGraph app_graph: The application graph
    :param ~spinn_machine.Machine machine:
        the SpiNNaker machine as discovered
    :param Placements system_placements:
        exiting placements to be added to
    """
    for vertex in app_graph.vertices:
        if isinstance(vertex, LivePacketGather):
            vertex.splitter.create_vertices(machine, system_placements)

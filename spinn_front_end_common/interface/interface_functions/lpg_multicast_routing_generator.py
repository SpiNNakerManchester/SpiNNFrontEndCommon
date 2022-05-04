# Copyright (c) 2021 The University of Manchester
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
from pacman.utilities.algorithm_utilities.routing_algorithm_utilities import (
    most_direct_route, convert_a_route)
from pacman.operations.router_algorithms.ner_route import targets_by_chip


def lpg_multicast_routing_generator(
        live_packet_gatherer_parameters, placements, lpg_to_vertex, machine,
        routing_tables):

    progress = ProgressBar(
        live_packet_gatherer_parameters, "Routing Live Output")

    lpg_for_m_vertex = dict()

    for lpg_params in progress.over(live_packet_gatherer_parameters):
        # locate vertices to connect to a LPG with these params
        for app_vertex, part_ids in live_packet_gatherer_parameters[
                lpg_params]:
            for part_id in part_ids:
                m_vertices = app_vertex.splitter.get_out_going_vertices(
                    part_id)
                for m_vertex in m_vertices:
                    placement = placements.get_placement_of_vertex(m_vertex)
                    chip = machine.get_chip_at(placement.x, placement.y)
                    x = chip.nearest_ethernet_x
                    y = chip.nearest_ethernet_y
                    lpg = lpg_to_vertex[lpg_params, x, y]
                    lpg_place = placements.get_placement_of_vertex(lpg)
                    route = most_direct_route(
                        placement.chip, lpg_place.chip, machine)
                    targets = targets_by_chip([lpg], placements, machine)
                    convert_a_route(
                        routing_tables, m_vertex, part_id, placement.p, None,
                        route, targets)
                    lpg_for_m_vertex[m_vertex, part_id] = lpg

    return lpg_for_m_vertex

# Copyright (c) 2019-2020 The University of Manchester
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

from pacman.model.graphs.abstract_sdram_partition import AbstractSDRAMPartition
from spinn_utilities.progress_bar import ProgressBar


class SDRAMOutgoingPartitionAllocator(object):

    def __call__(self, machine_graph, transceiver, placements, app_id):

        progress_bar = ProgressBar(
            total_number_of_things_to_do=len(
                machine_graph.outgoing_edge_partitions),
            string_describing_what_being_progressed=(
                "Allocating SDRAM for SDRAM outgoing egde partitions"))

        for outgoing_edge_partition in \
                progress_bar.over(machine_graph.outgoing_edge_partitions):
            if isinstance(outgoing_edge_partition, AbstractSDRAMPartition):
                placement = placements.get_placement_of_vertex(
                    outgoing_edge_partition.pre_vertex)
                sdram_base_address = transceiver.malloc_sdram(
                    placement.x, placement.y,
                    outgoing_edge_partition.total_sdram_requirements(), app_id)
                outgoing_edge_partition.sdram_base_address = sdram_base_address

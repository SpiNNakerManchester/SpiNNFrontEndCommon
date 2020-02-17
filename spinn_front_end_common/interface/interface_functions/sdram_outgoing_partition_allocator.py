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

from spinn_utilities.progress_bar import ProgressBar
from pacman.model.graphs import AbstractSDRAMPartition
from pacman.model.graphs.machine import SourceSegmentedSDRAMMachinePartition
from spinn_front_end_common.utilities.exceptions import SpinnFrontEndException


class SDRAMOutgoingPartitionAllocator(object):

    def __call__(self, machine_graph, transceiver, placements, app_id):

        progress_bar = ProgressBar(
            total_number_of_things_to_do=len(machine_graph.vertices),
            string_describing_what_being_progressed=(
                "Allocating SDRAM for SDRAM outgoing egde partitions"))

        for machine_vertex in machine_graph.vertices:
            partitions = (
                machine_graph.get_costed_edge_partitions_starting_at_vertex(
                    machine_vertex))
            for outgoing_edge_partition in partitions:

                # check right type of costed partition
                if isinstance(outgoing_edge_partition, AbstractSDRAMPartition):

                    # get placement, ones where the src is multiple,
                    # you need to ask for the first pre vertex
                    if isinstance(
                            outgoing_edge_partition,
                            SourceSegmentedSDRAMMachinePartition):
                        placement = placements.get_placement_of_vertex(
                            next(iter(outgoing_edge_partition.pre_vertices)))
                    else:
                        placement = placements.get_placement_of_vertex(
                            outgoing_edge_partition.pre_vertex)

                    # total sdram
                    total_sdram = (
                        outgoing_edge_partition.total_sdram_requirements())

                    # if bust, throw exception
                    if total_sdram == 0:
                        raise SpinnFrontEndException(
                            "cannot allocate sdram size of 0 for "
                            "partition {}".format(outgoing_edge_partition))

                    # allocate
                    sdram_base_address = transceiver.malloc_sdram(
                        placement.x, placement.y, total_sdram, app_id)

                    # update
                    outgoing_edge_partition.sdram_base_address = (
                        sdram_base_address)

            progress_bar.update()
        progress_bar.end()

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
from collections import defaultdict

from pacman.model.graphs.machine import AbstractSDRAMPartition
from spinn_front_end_common.utilities.exceptions import SpinnFrontEndException
from spinn_utilities.progress_bar import ProgressBar


class SDRAMOutgoingPartitionAllocator(object):

    N_SEMAPHORE_TAGS_PER_CHIP = 31

    def __call__(self, machine_graph, transceiver, placements, app_id):

        progress_bar = ProgressBar(
            total_number_of_things_to_do=len(
                machine_graph.vertices) * 2,
            string_describing_what_being_progressed=(
                "Allocating SDRAM for SDRAM outgoing egde partitions"))

        chip_based_partitions = defaultdict(list)

        for machine_vertex in machine_graph.vertices:
            partitions = (
                machine_graph.get_costed_edge_partitions_starting_at_vertex(
                    machine_vertex))
            for outgoing_edge_partition in partitions:

                # check right type of costed partition
                if isinstance(outgoing_edge_partition, AbstractSDRAMPartition):

                    # get placement
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

                    # add to chip tracker
                    if outgoing_edge_partition.needs_semaphore:
                        chip_based_partitions[
                            (placement.x, placement.y)].append(
                                outgoing_edge_partition)

            progress_bar.update()

        for (chip_x, chip_y) in chip_based_partitions:
            # check doable
            if (len(chip_based_partitions[(chip_x, chip_y)]) >
                    self.N_SEMAPHORE_TAGS_PER_CHIP):
                raise SpinnFrontEndException(
                    "not enough semaphores to allocate for this setup")

            # update
            for semaphore_id, partition in enumerate(
                    chip_based_partitions[(chip_x, chip_y)]):
                partition.semaphore_id = semaphore_id
            progress_bar.update()
        progress_bar.end()

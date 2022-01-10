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
from spinn_utilities.progress_bar import ProgressBar
from pacman.model.graphs.machine import SourceSegmentedSDRAMMachinePartition
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.exceptions import SpinnFrontEndException


def sdram_outgoing_partition_allocator():
    view = FecDataView()
    machine_graph = FecDataView.get_runtime_machine_graph()
    placements = view.placements
    if FecDataView.has_transceiver():
        transceiver = FecDataView.get_transceiver()
        virtual_usage = None
    else:
        # Ok if transceiver = None
        transceiver = None
        virtual_usage = defaultdict(int)

    progress_bar = ProgressBar(
        total_number_of_things_to_do=len(machine_graph.vertices),
        string_describing_what_being_progressed=(
            "Allocating SDRAM for SDRAM outgoing egde partitions"))

    for machine_vertex in machine_graph.vertices:
        sdram_partitions = (
            machine_graph.get_sdram_edge_partitions_starting_at_vertex(
                machine_vertex))
        app_id = view.app_id
        for sdram_partition in sdram_partitions:

            # get placement, ones where the src is multiple,
            # you need to ask for the first pre vertex
            if isinstance(
                    sdram_partition, SourceSegmentedSDRAMMachinePartition):
                placement = placements.get_placement_of_vertex(
                    next(iter(sdram_partition.pre_vertices)))
            else:
                placement = placements.get_placement_of_vertex(
                    sdram_partition.pre_vertex)

            # total sdram
            total_sdram = (sdram_partition.total_sdram_requirements())

            # if bust, throw exception
            if total_sdram == 0:
                raise SpinnFrontEndException(
                    "Cannot allocate sdram size of 0 for "
                    "partition {}".format(sdram_partition))

            # allocate
            if transceiver is not None:
                sdram_base_address = transceiver.malloc_sdram(
                    placement.x, placement.y, total_sdram, app_id)
            else:
                sdram_base_address = virtual_usage[
                    placement.x, placement.y]
                virtual_usage[placement.x, placement.y] += total_sdram

            # update
            sdram_partition.sdram_base_address = sdram_base_address

        progress_bar.update()
    progress_bar.end()

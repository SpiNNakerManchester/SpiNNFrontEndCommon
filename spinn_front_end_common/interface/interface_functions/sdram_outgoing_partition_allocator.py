# Copyright (c) 2019 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections import defaultdict
from spinn_utilities.progress_bar import ProgressBar
from pacman.model.graphs.machine import SourceSegmentedSDRAMMachinePartition
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.exceptions import SpinnFrontEndException
from spinn_front_end_common.utilities.constants import SDRAM_EDGE_BASE_TAG


def sdram_outgoing_partition_allocator():
    if FecDataView.has_transceiver():
        transceiver = FecDataView.get_transceiver()
        virtual_usage = None
    else:
        # Ok if transceiver = None
        transceiver = None
        virtual_usage = defaultdict(int)

    progress_bar = ProgressBar(
        total_number_of_things_to_do=FecDataView.get_n_vertices(),
        string_describing_what_being_progressed=(
            "Allocating SDRAM for SDRAM outgoing egde partitions"))

    # Keep track of SDRAM tags used
    next_tag = defaultdict(lambda: SDRAM_EDGE_BASE_TAG)

    for vertex in FecDataView.iterate_vertices():
        sdram_partitions = vertex.splitter.get_internal_sdram_partitions()
        for sdram_partition in sdram_partitions:

            # get placement, ones where the src is multiple,
            # you need to ask for the first pre vertex
            if isinstance(
                    sdram_partition, SourceSegmentedSDRAMMachinePartition):
                placement = FecDataView.get_placement_of_vertex(
                    next(iter(sdram_partition.pre_vertices)))
            else:
                placement = FecDataView.get_placement_of_vertex(
                    sdram_partition.pre_vertex)

            # total sdram
            total_sdram = (sdram_partition.total_sdram_requirements())

            # if bust, throw exception
            if total_sdram == 0:
                raise SpinnFrontEndException(
                    "Cannot allocate SDRAM size of 0 for "
                    f"partition {sdram_partition}")

            # allocate
            if transceiver is not None:
                tag = next_tag[placement.x, placement.y]
                next_tag[placement.x, placement.y] = tag + 1
                sdram_base_address = transceiver.malloc_sdram(
                    placement.x, placement.y, total_sdram,
                    FecDataView.get_app_id(), tag)
            else:
                sdram_base_address = virtual_usage[
                    placement.x, placement.y]
                virtual_usage[placement.x, placement.y] += total_sdram

            # update
            sdram_partition.sdram_base_address = sdram_base_address

        progress_bar.update()
    progress_bar.end()

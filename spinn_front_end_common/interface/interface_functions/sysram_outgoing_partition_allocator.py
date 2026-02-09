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
from typing import Dict, Optional, cast, Tuple, List
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.typing.coords import XY
from spinnman.transceiver import Transceiver
from pacman.model.graphs import AbstractSingleSourcePartition
from pacman.model.graphs.machine import (
    SourceSegmentedSysRAMMachinePartition, AbstractSysRAMPartition)
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.exceptions import SpinnFrontEndException
from spinn_front_end_common.utilities.constants import SYSRAM_EDGE_BASE_TAG


def sysram_outgoing_partition_allocator() -> None:
    """
    Goes through all vertices to see if system RAM has to be allocated.
    """
    virtual_usage: Optional[Dict[XY, int]]
    transceiver: Optional[Transceiver]
    if FecDataView.has_transceiver():
        transceiver = FecDataView.get_transceiver()
        virtual_usage = None
    else:
        # OK if transceiver = None
        transceiver = None
        virtual_usage = defaultdict(int)

    progress_bar = ProgressBar(
        total_number_of_things_to_do=FecDataView.get_n_vertices(),
        string_describing_what_being_progressed=(
            "Allocating System RAM for SysRAM outgoing egde partitions"))

    # Keep track of SDRAM tags used
    next_tag: Dict[XY, int] = defaultdict(lambda: SYSRAM_EDGE_BASE_TAG)

    # Keep the allocations to do them all at once
    allocations: List[Tuple[int, int, int, int, int]] = []
    # Match the above list with the partitions to set to align the results
    partitions_to_set: List[AbstractSysRAMPartition] = []

    for vertex in progress_bar.over(FecDataView.iterate_vertices()):
        splitter = vertex.splitter
        for sysram_partition in splitter.get_internal_sysram_partitions():
            # get placement, ones where the src is multiple,
            # you need to ask for the first pre vertex
            if isinstance(
                    sysram_partition, SourceSegmentedSysRAMMachinePartition):
                placement = FecDataView.get_placement_of_vertex(
                    next(iter(sysram_partition.pre_vertices)))
            else:
                placement = FecDataView.get_placement_of_vertex(
                    # tricky!
                    cast(AbstractSingleSourcePartition,
                         sysram_partition).pre_vertex)

            # total sdram
            total_sysram = sysram_partition.total_sysram_requirements()

            # if bust, throw exception
            if total_sysram == 0:
                raise SpinnFrontEndException(
                    "Cannot allocate SysRAM size of 0 for "
                    f"partition {sysram_partition}")

            # allocate
            if transceiver is not None:
                tag = next_tag[placement.x, placement.y]
                next_tag[placement.x, placement.y] = tag + 1
                allocations.append((
                    placement.x, placement.y, total_sysram,
                    FecDataView.get_app_id(), tag))
                partitions_to_set.append(sysram_partition)
            else:
                assert virtual_usage is not None
                sysram_base_address = virtual_usage[placement.x, placement.y]
                virtual_usage[placement.x, placement.y] += total_sysram
                sysram_partition.sysram_base_address = sysram_base_address

        if transceiver is not None:
            addresses = transceiver.malloc_sysram_multi(allocations)
            for partition, address in zip(partitions_to_set, addresses):
                partition.sysram_base_address = address

# Copyright (c) 2017 The University of Manchester
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

from typing import Dict, cast
from spinn_machine import CoreSubsets
from spinnman.model.enums import ExecutableType
from pacman.model.placements import Placement
from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary
from spinn_front_end_common.data import FecDataView


def locate_executable_start_type() -> Dict[ExecutableType, CoreSubsets]:
    """
    Discovers where applications of particular types need to be launched.

    :returns: Mapping of type to the cores which have that type
    """
    binary_start_types: Dict[ExecutableType, CoreSubsets] = dict()

    for placement in FecDataView.iterate_placements_by_vertex_type(
            AbstractHasAssociatedBinary):
        vertex = cast(AbstractHasAssociatedBinary, placement.vertex)
        bin_type = vertex.get_binary_start_type()
        # update core subset with location of the vertex on the
        # machine
        if bin_type not in binary_start_types:
            binary_start_types[bin_type] = CoreSubsets()

        __add_vertex_to_subset(
            placement, binary_start_types[bin_type])

    # only got apps with no binary, such as external devices.
    # return no app
    if not binary_start_types:
        return {ExecutableType.NO_APPLICATION: CoreSubsets()}

    return binary_start_types


def __add_vertex_to_subset(
        placement: Placement, core_subsets: CoreSubsets) -> None:
    core_subsets.add_processor(
        x=placement.x, y=placement.y, processor_id=placement.p)

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

from typing import cast
from pacman.model.placements import Placements
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utility_models.live_packet_gather import (
    LivePacketGather, _LPGSplitter)


def split_lpg_vertices(system_placements: Placements) -> None:
    """
    Split any LPG vertices found.

    :param system_placements: existing placements to be added to
    """
    for vertex in FecDataView.get_vertices_by_type(LivePacketGather):
        cast(_LPGSplitter, vertex.splitter).create_sys_vertices(
            system_placements)

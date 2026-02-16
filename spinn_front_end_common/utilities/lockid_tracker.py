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
from collections import defaultdict
from typing import Dict, Tuple
from pacman.model.graphs.machine.machine_vertex import MachineVertex
from pacman.model.placements.placement import Placement

_MIN_LOCK_ID = 8
_MAX_LOCK_ID = 31


class LockIdTracker(object):
    """
    A tracker of lock ids per chip to make it easier to allocate new IDs.
    """
    __slots__ = (
        "__next_lock_id",
        "__used_lock_id"
    )

    def __init__(self):
        """
        """
        self.__next_lock_id: Dict[Tuple[int, int], int] = defaultdict(
            lambda: _MIN_LOCK_ID)
        self.__used_lock_id: Dict[Tuple[MachineVertex, str], int] = dict()

    def get_id_for(
            self, vertex: MachineVertex, placement: Placement,
            lock_name: str) -> int:
        """
        Get the lock ID for a given vertex and lock name, allocating a new one
        if needed.

        :param vertex: The vertex to get the lock ID for
        :param placement: The placement of the vertex to get the lock ID for
        :param lock_name: The name of the lock to get the ID for
        :return: The lock ID for the given vertex and lock name
        """
        key = (vertex, lock_name)
        if key not in self.__used_lock_id:
            chip_coords = (placement.x, placement.y)
            lock_id = self.__next_lock_id[chip_coords]
            if lock_id > _MAX_LOCK_ID:
                raise Exception(
                    f"Too many locks allocated on chip {chip_coords}")
            self.__used_lock_id[key] = lock_id
            self.__next_lock_id[chip_coords] += 1
        return self.__used_lock_id[key]

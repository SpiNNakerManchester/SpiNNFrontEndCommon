# Copyright (c) 2014 The University of Manchester
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
from __future__ import annotations
from typing import Iterable, List, Tuple, TYPE_CHECKING
from spinn_utilities.overrides import overrides
from pacman.model.graphs import AbstractVertex
from pacman.model.graphs.application import ApplicationEdge, ApplicationVertex
from pacman.model.graphs.application.abstract import (
    AbstractOneAppOneMachineVertex)
from pacman.model.partitioner_splitters import SplitterOneAppOneMachine
from pacman.model.routing_info import BaseKeyAndMask
from .command_sender_machine_vertex import CommandSenderMachineVertex
if TYPE_CHECKING:
    from spinn_front_end_common.utility_models import MultiCastCommand


class CommandSender(
        AbstractOneAppOneMachineVertex[CommandSenderMachineVertex]):
    """
    A utility for sending commands to a vertex (possibly an external device)
    at fixed times in the simulation or in response to simulation events
    (e.g., starting and stopping).
    """

    def __init__(self, label: str):
        """
        :param label: The label of this vertex
        """
        super().__init__(
            CommandSenderMachineVertex(label, self), label)
        self.splitter = SplitterOneAppOneMachine()

    def add_commands(
            self, start_resume_commands: Iterable[MultiCastCommand],
            pause_stop_commands: Iterable[MultiCastCommand],
            timed_commands: Iterable[MultiCastCommand],
            vertex_to_send_to: AbstractVertex) -> None:
        """
        Add commands to be sent down a given edge.

        :param start_resume_commands:
            The commands to send when the simulation starts or resumes from
            pause
        :param pause_stop_commands:
            The commands to send when the simulation stops or pauses after
            running
        :param timed_commands:
            The commands to send at specific times
        :param vertex_to_send_to:
            The vertex these commands are to be sent to
        """
        self._machine_vertex.add_commands(
            start_resume_commands, pause_stop_commands, timed_commands,
            vertex_to_send_to)

    def edges_and_partitions(self) -> Tuple[List[ApplicationEdge], List[str]]:
        """
        Construct application edges from this vertex to the app vertices
        that this vertex knows how to target (and has keys allocated for).

        :return: edges, partition IDs
        """
        return self._machine_vertex.get_edges_and_partitions(
            self, ApplicationVertex, ApplicationEdge)

    @overrides(AbstractOneAppOneMachineVertex.get_fixed_key_and_mask)
    def get_fixed_key_and_mask(self, partition_id: str) -> BaseKeyAndMask:
        return self._machine_vertex.get_fixed_key_and_mask(partition_id)

# Copyright (c) 2022 The University of Manchester
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
from typing import Dict, Iterable, List, Optional
from spinn_utilities.progress_bar import ProgressBar
from spinn_machine import Chip
from spinn_machine.link_data_objects import AbstractLinkData
from pacman.model.graphs.application import ApplicationVirtualVertex
from pacman.model.placements import Placement, Placements
from spinn_front_end_common.data.fec_data_view import FecDataView
from spinn_front_end_common.abstract_models import (
    AbstractSendMeMulticastCommandsVertex)
from spinn_front_end_common.utility_models import CommandSender
from spinn_front_end_common.utilities.utility_calls import (
    pick_core_for_system_placement)


def add_command_senders(system_placements: Placements) -> List[CommandSender]:
    """
    Add command senders

    :param system_placements:
        Placements to add CommandSender placements to.
    :return: The command senders that were added
    """
    return list(CommandSenderAdder(system_placements).add_command_senders())


class CommandSenderAdder(object):
    """
    Code to add CommandSender vertices and their placements.
    """
    __slots__ = (
        "__command_sender_for_chip",
        "__general_command_sender",
        "__system_placements")

    def __init__(self, system_placements: Placements):
        """
        :param system_placements:
            Placements to add CommandSender placements to.
        """
        self.__system_placements = system_placements

        # Keep track of command senders by which chip they are on
        self.__command_sender_for_chip: Dict[Chip, CommandSender] = dict()
        self.__general_command_sender: Optional[CommandSender] = None

    def add_command_senders(self) -> Iterable[CommandSender]:
        """
        Add the needed command senders.

        :return: The command senders that were added
        """
        progress = ProgressBar(FecDataView.get_n_vertices(), "Adding commands")
        for vertex in progress.over(FecDataView.iterate_vertices()):
            if isinstance(vertex, AbstractSendMeMulticastCommandsVertex):
                machine = FecDataView.get_machine()
                link_data = None

                # See if we need a specific placement for a device
                if isinstance(vertex, ApplicationVirtualVertex):
                    link_data = vertex.get_outgoing_link_data(machine)

                # allow the command sender to create key to partition map
                self.__get_command_sender(link_data).add_commands(
                    vertex.start_resume_commands,
                    vertex.pause_stop_commands,
                    vertex.timed_commands, vertex)

        yield from self.__command_sender_for_chip.values()
        if self.__general_command_sender is not None:
            yield self.__general_command_sender

    def __get_command_sender(
            self, link_data: Optional[AbstractLinkData]) -> CommandSender:
        if link_data is None:
            if self.__general_command_sender is None:
                self.__general_command_sender = CommandSender(
                    "General command sender")
            return self.__general_command_sender

        x, y = link_data.connected_chip_x, link_data.connected_chip_y
        chip = FecDataView.get_chip_at(x, y)

        command_sender = self.__command_sender_for_chip.get(chip)
        if command_sender is None:
            command_sender = CommandSender(f"Command Sender on {x}, {y}")
            self.__command_sender_for_chip[chip] = command_sender
            p = pick_core_for_system_placement(self.__system_placements, chip)
            self.__system_placements.add_placement(
                Placement(command_sender.machine_vertex, x, y, p))
        return command_sender

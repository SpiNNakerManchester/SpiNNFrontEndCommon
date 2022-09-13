# Copyright (c) 2022 The University of Manchester
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
from spinn_front_end_common.data.fec_data_view import FecDataView
from spinn_front_end_common.abstract_models import (
    AbstractSendMeMulticastCommandsVertex)
from spinn_front_end_common.utility_models import CommandSender
from pacman.model.graphs.application import ApplicationVirtualVertex
from pacman.model.placements import Placement
from pacman.model.partitioner_splitters import SplitterOneAppOneMachine
from spinn_utilities.progress_bar import ProgressBar


def add_command_senders(system_placements):
    """ Add command senders
    """
    CommandSenderAdder(system_placements).add_command_senders()


class CommandSenderAdder(object):

    __slots__ = [
        "__command_sender_for_chip",
        "__general_command_sender",
        "__system_placements"
    ]

    def __init__(self, system_placements):
        self.__system_placements = system_placements

        # Keep track of command senders by which chip they are on
        self.__command_sender_for_chip = dict()
        self.__general_command_sender = None

    def add_command_senders(self):
        progress = ProgressBar(FecDataView.get_n_vertices(), "Adding commands")
        for vertex in progress.over(FecDataView.iterate_vertices()):
            if isinstance(vertex, AbstractSendMeMulticastCommandsVertex):
                machine = FecDataView.get_machine()
                link_data = None

                # See if we need a specific placement for a device
                if isinstance(vertex, ApplicationVirtualVertex):
                    link_data = vertex.get_outgoing_link_data(machine)

                command_sender = self.__get_command_sender(link_data)

                # allow the command sender to create key to partition map
                command_sender.add_commands(
                    vertex.start_resume_commands,
                    vertex.pause_stop_commands,
                    vertex.timed_commands, vertex)

        all_command_senders = list(self.__command_sender_for_chip.values())
        if self.__general_command_sender is not None:
            all_command_senders.append(self.__general_command_sender)

        # add the edges from the command senders to the dependent vertices
        for command_sender in all_command_senders:
            FecDataView.add_vertex(command_sender)
            edges, partition_ids = command_sender.edges_and_partitions()
            for edge, partition_id in zip(edges, partition_ids):
                FecDataView.add_edge(edge, partition_id)

    def __cores(self, x, y):
        return [p.processor_id
                for p in FecDataView.get_chip_at(x, y).processors
                if not p.is_monitor]

    def __get_command_sender(self, link_data):
        if link_data is None:
            if self.__general_command_sender is None:
                self.__general_command_sender = self.__new_command_sender(
                    "General command sender")
            return self.__general_command_sender

        x = link_data.connected_chip_x
        y = link_data.connected_chip_y

        command_sender = self.__command_sender_for_chip.get((x, y))
        if command_sender is None:
            command_sender = self.__new_command_sender(
                f"Command Sender on {x}, {y}")
            self.__command_sender_for_chip[(x, y)] = command_sender
            cores = self.__cores(x, y)
            p = cores[self.__system_placements.n_placements_on_chip(x, y)]
            self.__system_placements.add_placement(
                Placement(command_sender.machine_vertex, x, y, p))
        return command_sender

    def __new_command_sender(self, label):
        command_sender = CommandSender(label)
        command_sender.splitter = SplitterOneAppOneMachine()
        return command_sender

# Copyright (c) 2017-2019 The University of Manchester
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

from spinn_utilities.overrides import overrides
from pacman.model.graphs.application import ApplicationEdge, ApplicationVertex
from spinn_front_end_common.abstract_models import (
    AbstractProvidesOutgoingPartitionConstraints, AbstractHasAssociatedBinary,
    AbstractGeneratesDataSpecification)
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from .command_sender_machine_vertex import CommandSenderMachineVertex


class CommandSender(
        ApplicationVertex, AbstractGeneratesDataSpecification,
        AbstractHasAssociatedBinary,
        AbstractProvidesOutgoingPartitionConstraints):
    """ A utility for sending commands to a vertex (possibly an external\
        device) at fixed times in the simulation or in response to \
        simulation events (e.g., starting and stopping).
    """

    def __init__(self, label, constraints):
        """
        :param str label: The label of this vertex
        :param constraints: Any initial constraints to this vertex
        :type constraints:
            iterable(~pacman.model.constraints.AbstractConstraint)
        """

        super(CommandSender, self).__init__(label, constraints, 1)
        self._machine_vertex = CommandSenderMachineVertex(label, constraints)

    def add_commands(
            self, start_resume_commands, pause_stop_commands,
            timed_commands, vertex_to_send_to):
        """ Add commands to be sent down a given edge

        :param iterable(MultiCastCommand) start_resume_commands:
            The commands to send when the simulation starts or resumes from
            pause
        :param iterable(MultiCastCommand) pause_stop_commands:
            The commands to send when the simulation stops or pauses after
            running
        :param iterable(MultiCastCommand) timed_commands:
            The commands to send at specific times
        :param ~pacman.model.graphs.AbstractVertex vertex_to_send_to:
            The vertex these commands are to be sent to
        """
        self._machine_vertex.add_commands(
            start_resume_commands, pause_stop_commands, timed_commands,
            vertex_to_send_to)

    @overrides(AbstractGeneratesDataSpecification.generate_data_specification)
    def generate_data_specification(self, spec, placement):
        # pylint: disable=no-value-for-parameter
        self._machine_vertex.generate_data_specification(spec, placement)

    @overrides(ApplicationVertex.create_machine_vertex)
    def create_machine_vertex(
            self, vertex_slice, resources_required, label=None,
            constraints=None):
        # This application vertex only ever has one machine vertex
        return self._machine_vertex

    @overrides(ApplicationVertex.get_resources_used_by_atoms)
    def get_resources_used_by_atoms(self, vertex_slice):
        return self._machine_vertex.resources_required

    @property
    @overrides(ApplicationVertex.n_atoms)
    def n_atoms(self):
        return 1

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return CommandSenderMachineVertex.BINARY_FILE_NAME

    def edges_and_partitions(self):
        """ Construct application edges from this vertex to the app vertices\
            that this vertex knows how to target (and has keys allocated for).

        :return: edges, partition IDs
        :rtype: tuple(list(~pacman.model.graphs.application.ApplicationEdge),
            list(str))
        """
        return self._machine_vertex._get_edges_and_partitions(
            self, ApplicationVertex, ApplicationEdge)

    @overrides(AbstractProvidesOutgoingPartitionConstraints.
               get_outgoing_partition_constraints)
    def get_outgoing_partition_constraints(self, partition):
        return self._machine_vertex.get_outgoing_partition_constraints(
            partition)

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return ExecutableType.USES_SIMULATION_INTERFACE

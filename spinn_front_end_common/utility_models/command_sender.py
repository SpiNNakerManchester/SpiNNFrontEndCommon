from spinn_utilities.overrides import overrides
from pacman.model.graphs.application import ApplicationEdge
from pacman.model.graphs.application import ApplicationVertex
from spinn_front_end_common.abstract_models import (
    AbstractProvidesOutgoingPartitionConstraints, AbstractHasAssociatedBinary,
    AbstractGeneratesDataSpecification)
from .command_sender_machine_vertex import CommandSenderMachineVertex
from spinn_front_end_common.utilities.utility_objs import ExecutableType


class CommandSender(
        ApplicationVertex, AbstractGeneratesDataSpecification,
        AbstractHasAssociatedBinary,
        AbstractProvidesOutgoingPartitionConstraints):
    """ A utility for sending commands to a vertex (possibly an external\
        device) at fixed times in the simulation
    """

    def __init__(self, label, constraints):

        super(CommandSender, self).__init__(label, constraints, 1)
        self._machine_vertex = CommandSenderMachineVertex(label, constraints)

    def add_commands(
            self, start_resume_commands, pause_stop_commands,
            timed_commands, vertex_to_send_to):
        self._machine_vertex.add_commands(
            start_resume_commands, pause_stop_commands, timed_commands,
            vertex_to_send_to)

    def generate_data_specification(
            self, spec, placement):
        # pylint: disable=too-many-arguments, arguments-differ
        self._machine_vertex.generate_data_specification(spec, placement)

    @overrides(ApplicationVertex.create_machine_vertex)
    def create_machine_vertex(
            self, vertex_slice, resources_required, label=None,
            constraints=None):
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
        return self._machine_vertex.get_edges_and_partitions(
            self, ApplicationEdge)

    @overrides(AbstractProvidesOutgoingPartitionConstraints.
               get_outgoing_partition_constraints)
    def get_outgoing_partition_constraints(self, partition):
        return self._machine_vertex.get_outgoing_partition_constraints(
            partition)

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return ExecutableType.USES_SIMULATION_INTERFACE

# pacman imports
from pacman.model.decorators.overrides import overrides
from pacman.model.graphs.application.application_edge import ApplicationEdge
from pacman.model.constraints.key_allocator_constraints \
    import KeyAllocatorFixedKeyAndMaskConstraint
from pacman.model.graphs.application import ApplicationVertex
from pacman.model.resources import ResourceContainer, SDRAMResource
from pacman.model.routing_info import BaseKeyAndMask
from pacman.executor.injection_decorator import inject_items

# spinn front end common imports
from spinn_front_end_common.abstract_models.\
    abstract_provides_outgoing_partition_constraints import \
    AbstractProvidesOutgoingPartitionConstraints
from spinn_front_end_common.abstract_models.\
    abstract_vertex_with_dependent_vertices import \
    AbstractVertexWithEdgeToDependentVertices
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.abstract_models\
    .abstract_generates_data_specification \
    import AbstractGeneratesDataSpecification
from spinn_front_end_common.abstract_models.abstract_has_associated_binary \
    import AbstractHasAssociatedBinary
from spinn_front_end_common.utility_models.command_sender_machine_vertex \
    import CommandSenderMachineVertex
from spinn_front_end_common.utilities.utility_objs.executable_start_type \
    import ExecutableStartType


class CommandSender(
        ApplicationVertex, AbstractGeneratesDataSpecification,
        AbstractHasAssociatedBinary,
        AbstractProvidesOutgoingPartitionConstraints):
    """ A utility for sending commands to a vertex (possibly an external\
        device) at fixed times in the simulation
    """

    # all commands will use this mask
    _DEFAULT_COMMAND_MASK = 0xFFFFFFFF

    def __init__(self, label, constraints):

        ApplicationVertex.__init__(self, label, constraints, 1)

        self._timed_commands = list()
        self._commands_at_start_resume = list()
        self._commands_at_pause_stop = list()
        self._partition_id_to_keys = dict()
        self._keys_to_partition_id = dict()
        self._edge_partition_id_counter = 0
        self._vertex_to_key_map = dict()

    def add_commands(
            self, start_resume_commands, pause_stop_commands,
            timed_commands, vertex_to_send_to):
        """ Add commands to be sent down a given edge

        :param start_resume_commands: The commands to send when the simulation\
                starts or resumes from pause
        :type start_resume_commands: iterable of\
                :py:class:`spinn_front_end_common.utility_models.multi_cast_command.MultiCastCommand`
        :param pause_stop_commands: the commands to send when the simulation\
                stops or pauses after running
        :type pause_stop_commands: iterable of\
                :py:class:`spinn_front_end_common.utility_models.multi_cast_command.MultiCastCommand`
        :param timed_commands: The commands to send at specific times
        :type timed_commands: iterable of\
                :py:class:`spinn_front_end_common.utility_models.multi_cast_command.MultiCastCommand`
        :param vertex_to_send_to: The vertex these commands are to be sent to
        """

        # container for keys for partition mapping (remove duplicates)
        command_keys = set()
        self._vertex_to_key_map[vertex_to_send_to] = set()

        # update holders
        self._commands_at_start_resume.extend(start_resume_commands)
        self._commands_at_pause_stop.extend(pause_stop_commands)
        self._timed_commands.extend(timed_commands)

        for commands in (
                start_resume_commands, pause_stop_commands, timed_commands):
            for command in commands:
                # track keys
                command_keys.add(command.key)
                self._vertex_to_key_map[vertex_to_send_to].add(command.key)

        # create mapping between keys and partitions via partition constraint
        for key in command_keys:

            partition_id = "COMMANDS{}".format(self._edge_partition_id_counter)
            self._keys_to_partition_id[key] = partition_id
            self._partition_id_to_keys[partition_id] = key
            self._edge_partition_id_counter += 1

    @inject_items({
        "machine_time_step": "MachineTimeStep",
        "time_scale_factor": "TimeScaleFactor",
        "n_machine_time_steps": "RunTimeMachineTimeSteps"
    })
    @overrides(
        AbstractGeneratesDataSpecification.generate_data_specification,
        additional_arguments={
            "machine_time_step", "time_scale_factor", "n_machine_time_steps"
        })
    def generate_data_specification(
            self, spec, placement, machine_time_step, time_scale_factor,
            n_machine_time_steps):
        placement.vertex.generate_data_specification(
            spec, placement, machine_time_step, time_scale_factor,
            n_machine_time_steps)

    @overrides(ApplicationVertex.create_machine_vertex)
    def create_machine_vertex(
            self, vertex_slice, resources_required, label=None,
            constraints=None):
        return CommandSenderMachineVertex(
            constraints, resources_required, label,
            self._commands_at_start_resume, self._commands_at_pause_stop,
            self._timed_commands)

    @overrides(ApplicationVertex.get_resources_used_by_atoms)
    def get_resources_used_by_atoms(self, vertex_slice):

        sdram = (
            CommandSenderMachineVertex.get_timed_commands_bytes(
                self._timed_commands) +
            CommandSenderMachineVertex.get_n_command_bytes(
                self._commands_at_start_resume) +
            CommandSenderMachineVertex.get_n_command_bytes(
                self._commands_at_pause_stop) +
            constants.SYSTEM_BYTES_REQUIREMENT +
            CommandSenderMachineVertex.get_provenance_data_size(0) +
            (CommandSenderMachineVertex.get_number_of_mallocs_used_by_dsg() *
             constants.SARK_PER_MALLOC_SDRAM_USAGE))

        # Return the SDRAM and 1 core
        return ResourceContainer(sdram=SDRAMResource(sdram))

    @property
    @overrides(ApplicationVertex.n_atoms)
    def n_atoms(self):
        return 1

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        """ Return a string representation of the models binary

        """
        return CommandSenderMachineVertex.get_binary_file_name()

    @overrides(AbstractVertexWithEdgeToDependentVertices.dependent_vertices)
    def dependent_vertices(self):
        return self._vertex_to_key_map.keys()

    def edges_and_partitions(self):
        edges = list()
        partition_ids = list()
        keys_added = set()
        for vertex in self._vertex_to_key_map:
            for key in self._vertex_to_key_map[vertex]:
                if key not in keys_added:
                    keys_added.add(key)
                    app_edge = ApplicationEdge(self, vertex)
                    edges.append(app_edge)
                    partition_ids.append(self._keys_to_partition_id[key])
        return edges, partition_ids

    @overrides(AbstractProvidesOutgoingPartitionConstraints.
               get_outgoing_partition_constraints)
    def get_outgoing_partition_constraints(self, partition):
        return [KeyAllocatorFixedKeyAndMaskConstraint([
            BaseKeyAndMask(
                self._partition_id_to_keys[partition.identifier],
                self._DEFAULT_COMMAND_MASK)
        ])]

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return ExecutableStartType.USES_SIMULATION_INTERFACE

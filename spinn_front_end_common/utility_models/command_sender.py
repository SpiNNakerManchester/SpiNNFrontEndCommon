# pacman imports
from pacman.model.decorators.overrides import overrides
from pacman.model.constraints.key_allocator_constraints.\
    key_allocator_fixed_key_and_mask_constraint \
    import KeyAllocatorFixedKeyAndMaskConstraint
from pacman.model.graphs.application.impl.application_vertex import \
    ApplicationVertex
from pacman.model.resources.resource_container import ResourceContainer
from pacman.model.resources.sdram_resource import SDRAMResource
from pacman.model.routing_info.base_key_and_mask import BaseKeyAndMask
from pacman.executor.injection_decorator import inject_items

# spinn front end common imports
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.interface.simulation import simulation_utilities
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
        AbstractHasAssociatedBinary):
    """ A utility for sending commands to a vertex (possibly an external\
        device) at fixed times in the simulation
    """

    # 4 for key, 4 for payload 2 for repeats, 2 for delays
    _COMMAND_WITH_PAYLOAD_SIZE = 12

    # 4 for key, 2 for repeats, 2 for delays
    _COMMAND_WITHOUT_PAYLOAD_SIZE = 8

    # all commands will use this mask
    _DEFAULT_COMMAND_MASK = 0xFFFFFFFF

    def __init__(self, label, constraints):

        ApplicationVertex.__init__(self, label, constraints, 1)

        self._commands_by_partition = dict()
        self._constraints_by_partition = dict()
        self._commands_with_payloads = dict()
        self._commands_without_payloads = dict()
        self._times_with_commands = set()

    def add_commands(self, commands, partitions):
        """ Add commands to be sent down a given edge

        :param commands: The commands to send
        :type commands: iterable of\
                    :py:class:`spinn_front_end_common.utility_models.multi_cast_command.MultiCastCommand`
        :param partitions: The partition down which the commands will be sent
        :raise ConfigurationException:\
            If the edge already has commands or if all the commands masks are\
            not 0xFFFFFFFF and there is no commonality between the\
            command masks
        """

        # Check if the edge already exists
        for partition in partitions:
            if partition in self._commands_by_partition:
                raise exceptions.ConfigurationException(
                    "The partition {} has already got commands")

        # container for keys for partition mapping
        command_keys = list()

        # Go through the commands
        for command in commands:

            # figure which command container to store this command in
            if command.is_payload:
                command_container = self._commands_with_payloads
            else:
                command_container = self._commands_without_payloads

            # check if the command time is already allocated
            if command.time not in command_container:
                command_container[command.time] = list()

            # Add the command to the appropriate dictionary
            command_container[command.time].append(command)

            # Add that there is a command at this time (set removes duplicates)
            self._times_with_commands.add(command.time)

            if command.key not in command_keys:

                # If this command has not been seen before, add it
                command_keys.append(command.key)

        # create mapping between keys and partitions via partition constraint
        for key, partition in zip(command_keys, partitions):
            partition.add_constraint(KeyAllocatorFixedKeyAndMaskConstraint(
                [BaseKeyAndMask(key, self._DEFAULT_COMMAND_MASK)]))

    @inject_items({
        "machine_time_step": "MachineTimeStep",
        "time_scale_factor": "TimeScaleFactor",
        "machine_graph": "MemoryMachineGraph",
        "graph_mapper": "MemoryGraphMapper",
        "routing_infos": "MemoryRoutingInfos",
        "n_machine_time_steps": "TotalMachineTimeSteps"
    })
    @overrides(
        AbstractGeneratesDataSpecification.generate_data_specification,
        additional_arguments={
            "machine_time_step", "time_scale_factor", "machine_graph",
            "graph_mapper", "routing_infos", "n_machine_time_steps"
        })
    def generate_data_specification(
            self, spec, placement, machine_time_step, time_scale_factor,
            machine_graph, graph_mapper, routing_infos, n_machine_time_steps):

        # reserve region - add a word for the region size
        n_command_bytes = self._get_n_command_bytes()
        self._reserve_memory_regions(
            spec, n_command_bytes + 4, placement.vertex)

        # Write system region
        spec.comment("\n*** Spec for multicast source ***\n\n")
        spec.switch_write_focus(CommandSenderMachineVertex.SYSTEM_REGION)
        spec.write_array(simulation_utilities.get_simulation_header_array(
            self.get_binary_file_name(), machine_time_step,
            time_scale_factor))

        # Go through the times and replace negative times with positive ones
        new_times = set()
        for time in self._times_with_commands:
            if time < 0 and n_machine_time_steps is not None:
                real_time = n_machine_time_steps + (time + 1)
                if time in self._commands_with_payloads:
                    if real_time in self._commands_with_payloads:
                        self._commands_with_payloads[real_time].extend(
                            self._commands_with_payloads[time])
                    else:
                        self._commands_with_payloads[real_time] = \
                            self._commands_with_payloads[time]
                    del self._commands_with_payloads[time]
                if time in self._commands_without_payloads:
                    if real_time in self._commands_without_payloads:
                        self._commands_without_payloads[real_time].extend(
                            self._commands_without_payloads[time])
                    else:
                        self._commands_without_payloads[real_time] = \
                            self._commands_without_payloads[time]
                    del self._commands_without_payloads[time]
                new_times.add(real_time)

            # if runtime is infinite, then there's no point storing end of
            # simulation events, as they will never occur
            elif time < 0 and n_machine_time_steps is None:
                if time in self._commands_with_payloads:
                    del self._commands_with_payloads[time]
                if time in self._commands_without_payloads:
                    del self._commands_without_payloads[time]
            else:
                new_times.add(time)

        # write commands
        spec.switch_write_focus(region=CommandSenderMachineVertex.COMMANDS)
        spec.write_value(n_command_bytes)
        for time in sorted(new_times):

            # Gather the different types of commands
            with_payload = list()
            if time in self._commands_with_payloads:
                with_payload = self._commands_with_payloads[time]
            without_payload = list()
            if time in self._commands_without_payloads:
                without_payload = self._commands_without_payloads[time]

            spec.write_value(time)

            spec.write_value(len(with_payload))
            for command in with_payload:
                spec.write_value(command.key)
                spec.write_value(command.payload)
                spec.write_value(command.repeat << 16 |
                                 command.delay_between_repeats)

            spec.write_value(len(without_payload))
            for command in without_payload:
                spec.write_value(command.key)
                spec.write_value(command.repeat << 16 |
                                 command.delay_between_repeats)

        # End-of-Spec:
        spec.end_specification()

    @staticmethod
    def _reserve_memory_regions(spec, command_size, vertex):
        """
        Reserve SDRAM space for memory areas:
        1) Area for information on what data to record
        2) area for start commands
        3) area for end commands
        """
        spec.comment("\nReserving memory space for data regions:\n\n")

        # Reserve memory:
        spec.reserve_memory_region(
            region=CommandSenderMachineVertex.SYSTEM_REGION,
            size=constants.SYSTEM_BYTES_REQUIREMENT,
            label='setup')
        if command_size > 0:
            spec.reserve_memory_region(
                region=CommandSenderMachineVertex.COMMANDS,
                size=command_size, label='commands')
        vertex.reserve_provenance_data_region(spec)

    @overrides(ApplicationVertex.create_machine_vertex)
    def create_machine_vertex(
            self, vertex_slice, resources_required, label=None,
            constraints=None):
        return CommandSenderMachineVertex(
            constraints, resources_required, label)

    @overrides(ApplicationVertex.get_resources_used_by_atoms)
    def get_resources_used_by_atoms(self, vertex_slice):

        sdram = (
            self._get_n_command_bytes() + 4 + 12 +
            CommandSenderMachineVertex.get_provenance_data_size(0)
        )

        # Return the SDRAM and 1 core
        return ResourceContainer(sdram=SDRAMResource(sdram))

    @property
    @overrides(ApplicationVertex.n_atoms)
    def n_atoms(self):
        return 1

    def _get_n_command_bytes(self):
        n_bytes = 0

        for time in self._times_with_commands:

            # Add 3 words for count-with-command, count-without-command
            # and time
            n_bytes += 12

            # Add the size of each command
            if time in self._commands_with_payloads:
                n_bytes += (len(self._commands_with_payloads[time]) *
                            self._COMMAND_WITH_PAYLOAD_SIZE)
            if time in self._commands_without_payloads:
                n_bytes += (len(self._commands_without_payloads[time]) *
                            self._COMMAND_WITHOUT_PAYLOAD_SIZE)

        return n_bytes

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        """ Return a string representation of the models binary

        """
        return 'command_sender_multicast_source.aplx'

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return ExecutableStartType.USES_SIMULATION_INTERFACE

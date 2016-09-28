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
from spinn_front_end_common.interface.simulation import simulation_utilities
from spinn_front_end_common.abstract_models\
    .abstract_generates_data_specification \
    import AbstractGeneratesDataSpecification
from spinn_front_end_common.abstract_models\
    .abstract_binary_uses_simulation_run import AbstractBinaryUsesSimulationRun
from spinn_front_end_common.abstract_models.abstract_has_associated_binary \
    import AbstractHasAssociatedBinary
from spinn_front_end_common.utility_models.command_sender_machine_vertex \
    import CommandSenderMachineVertex
from spinn_front_end_common.utility_models.commands.\
    multi_cast_command_with_payload import \
    MultiCastCommandWithPayload


class CommandSender(
        ApplicationVertex, AbstractGeneratesDataSpecification,
        AbstractHasAssociatedBinary, AbstractBinaryUsesSimulationRun):
    """ A utility for sending commands to a vertex (possibly an external\
        device) at fixed times in the simulation
    """

    # 4 for key, 4 for has payload, 4 for payload 2 for repeats, 2 for delays
    _COMMAND_WITH_PAYLOAD_SIZE = 16

    # 4 for key, 4 for no payload, 2 for repeats, 2 for delays
    _COMMAND_WITHOUT_PAYLOAD_SIZE = 12

    # 4 for the time stamp
    _COMMAND_TIMESTAMP_SIZE = 4

    # 4 for the size of the schedule
    _COMMAND_SIZE_SIZE = 4

    # all commands will use this mask
    _DEFAULT_COMMAND_MASK = 0xFFFFFFFF

    # bool for if the command has a payload
    _HAS_PAYLOAD = 0

    # bool for if the command does not have a payload
    _HAS_NO_PAYLOAD = 1

    def __init__(self, label, constraints):

        ApplicationVertex.__init__(self, label, constraints, 1)

        self._times_with_commands = dict()

    def add_commands(self, commands, partitions):
        """ Add commands to be sent down a given edge

        :param commands: The commands to send
        :type commands: iterable of\
                    :py:class:`spinn_front_end_common.utility_models.multi_cast_command.MultiCastCommand`
        :param partition:
        :param edge: The edge down which the commands will be sent
        :type edge:\
                    :py:class:`pacman.model.graph.application.abstract_application_edge.AbstractApplicationEdge`
        :raise ConfigurationException:\
            If the edge already has commands or if all the commands masks are\
            not 0xFFFFFFFF and there is no commonality between the\
            command masks
        """

        # container for keys for partition mapping
        command_keys = list()

        # Go through the commands
        for command in commands:

            # track times for commands
            if command.time not in self._times_with_commands:
                self._times_with_commands[command.time] = list()
            self._times_with_commands[command.time].append(command)

            # track keys
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
        "n_machine_time_steps": "RunTimeMachineTimeSteps"
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

        # sort out times and messages not to send
        new_times = self._sort_out_timings(n_machine_time_steps)

        # reserve region - add a word for the region size
        n_command_bytes = self._get_n_command_bytes()

        # reverse memory regions
        self._reserve_memory_regions(
            spec,
            n_command_bytes + self._COMMAND_SIZE_SIZE +
            (self._COMMAND_TIMESTAMP_SIZE * len(new_times)),
            placement.vertex)

        # Write system region
        spec.comment("\n*** Spec for multicast source ***\n\n")
        spec.switch_write_focus(CommandSenderMachineVertex.SYSTEM_REGION)
        spec.write_array(simulation_utilities.get_simulation_header_array(
            self.get_binary_file_name(), machine_time_step,
            time_scale_factor))

        # write commands
        spec.switch_write_focus(region=CommandSenderMachineVertex.COMMANDS)

        # write size of the data region
        spec.write_value(n_command_bytes)

        # for each time, write commands
        for time in sorted(new_times):

            spec.write_value(time)

            # write the number of commands to send
            spec.write_value(len(self._times_with_commands[time]))

            # Gather the different types of commands
            for command in self._times_with_commands[time]:
                if isinstance(command, MultiCastCommandWithPayload):

                    spec.write_value(command.key)
                    spec.write_value(self._HAS_PAYLOAD)
                    spec.write_value(command.payload)
                    spec.write_value((command.repeat << 16 |
                                     command.delay_between_repeats))
                else:
                    spec.write_value(command.key)
                    spec.write_value(self._HAS_NO_PAYLOAD)
                    spec.write_value((command.repeat << 16 |
                                     command.delay_between_repeats))

        # End-of-Spec:
        spec.end_specification()

    def _sort_out_timings(self, n_machine_time_steps):
        # Go through the times and replace negative times with positive ones
        new_times = set()
        new_time_commands = dict()
        times_to_delete = list()
        for time in self._times_with_commands:
            if time < 0 and n_machine_time_steps is not None:
                real_time = n_machine_time_steps + (time + 1)
                new_time_commands[real_time] = self._times_with_commands[time]
                times_to_delete.append(time)
                new_times.add(real_time)

            # if runtime is infinite, then there's no point storing end of
            # simulation events, as they will never occur
            elif time < 0 and n_machine_time_steps is None:
                times_to_delete.append(time)
            else:
                new_times.add(time)

        # delete wrong data now
        for time_to_delete in times_to_delete:
            del self._times_with_commands[time_to_delete]

        # add new time data to dict
        self._times_with_commands.update(new_time_commands)
        return new_times

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
            self._get_n_command_bytes() + constants.SYSTEM_BYTES_REQUIREMENT +
            CommandSenderMachineVertex.get_provenance_data_size(0)
        )

        # Return the SDRAM and 1 core
        return ResourceContainer(sdram=SDRAMResource(sdram))

    @property
    @overrides(ApplicationVertex.n_atoms)
    def n_atoms(self):
        return 1

    def _get_n_command_bytes(self):
        """
        :return:
        """
        n_bytes = 0

        for time in self._times_with_commands:
            n_bytes += self._COMMAND_TIMESTAMP_SIZE
            for command in self._times_with_commands[time]:
                if isinstance(command, MultiCastCommandWithPayload):
                    n_bytes += self._COMMAND_WITH_PAYLOAD_SIZE
                else:
                    n_bytes += self._COMMAND_WITHOUT_PAYLOAD_SIZE
        return n_bytes

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        """ Return a string representation of the models binary

        :return:
        """
        return 'command_sender_multicast_source.aplx'

from spinn_front_end_common.interface.provenance\
    .provides_provenance_data_from_machine_impl \
    import ProvidesProvenanceDataFromMachineImpl
from spinn_front_end_common.utilities import exceptions

from pacman.model.constraints.key_allocator_constraints\
    .key_allocator_fixed_mask_constraint import KeyAllocatorFixedMaskConstraint
from pacman.model.decorators.overrides import overrides
from pacman.model.constraints.key_allocator_constraints\
    .key_allocator_fixed_key_and_mask_constraint \
    import KeyAllocatorFixedKeyAndMaskConstraint
from pacman.model.routing_info.base_key_and_mask import BaseKeyAndMask
from pacman.model.graph.machine.abstract_machine_vertex \
    import AbstractMachineVertex


_COMMAND_WITH_PAYLOAD_SIZE = 12

_COMMAND_WITHOUT_PAYLOAD_SIZE = 8


class CommandSenderMachineVertex(
        AbstractMachineVertex, ProvidesProvenanceDataFromMachineImpl):

    SYSTEM_REGION = 0
    COMMANDS = 1
    PROVENANCE_REGION = 2

    def __init__(
            self, machine_time_step, time_scale_factor,
            edge_to_command_map=None):
        ProvidesProvenanceDataFromMachineImpl.__init__(
            self, self.PROVENANCE_REGION, n_additional_data_items=0)

        self._machine_time_step = machine_time_step
        self._time_scale_factor = time_scale_factor

        self._edge_constraints = dict()
        self._command_edge = dict()
        self._times_with_commands = set()
        self._commands_with_payloads = dict()
        self._commands_without_payloads = dict()

        if edge_to_command_map is not None:
            for (edge, commands) in edge_to_command_map.iteritems():
                self.add_commands(commands, edge)

    @overrides(AbstractMachineVertex.resources_required)
    def resources_required(self):
        return self.get_n_command_bytes(
            self._times_with_commands, self._commands_with_payloads,
            self._commands_without_payloads)

    def add_commands(self, commands, edge):
        """ Add commands to be sent down a given edge

        :param commands: The commands to send
        :type commands:\
            iterable of\
            :py:class:`spinn_front_end_common.utility_models.multi_cast_command.MultiCastCommand`
        :param edge: The edge down which the commands will be sent
        :type edge:\
            :py:class:`pacman.model.graph.application.abstract_application_edge.AbstractApplicationEdge`
        :raise ConfigurationException:\
            If the edge already has commands or if all the commands masks are\
            not 0xFFFFFFFF and there is no commonality between the command\
            masks
        """

        # Check if the edge already exists
        if edge in self._edge_constraints:
            raise exceptions.ConfigurationException(
                "The edge has already got commands")

        # Go through the commands
        command_keys = dict()
        command_mask = 0
        for command in commands:

            # Add the command to the appropriate dictionary
            dictionary = None
            if command.is_payload:
                dictionary = self._commands_with_payloads
            else:
                dictionary = self._commands_without_payloads
            if command.time not in dictionary:
                dictionary[command.time] = list()
            dictionary[command.time].append(command)

            # Add that there is a command at this time
            self._times_with_commands.add(command.time)

            # Add the edge associated with the command
            self._command_edge[command] = edge

            if command.key not in command_keys:

                # If this command has not been seen before, add it
                command_keys[command.key] = command.mask
            else:

                # Otherwise merge the current key mask with the current mask
                command_keys[command.key] = (command_keys[command.key] |
                                             command.mask)

            # Keep track of the masks on all the commands
            command_mask |= command.mask

        if command_mask != 0xFFFFFFFF:

            # If the final command mask contains don't cares, use this as a
            # fixed mask
            self._edge_constraints[edge] = list(
                [KeyAllocatorFixedMaskConstraint(command_mask)])
        else:

            # If there is no mask consensus, check that all the masks are
            # actually 0xFFFFFFFF, as otherwise it will not be possible
            # to assign keys to the edge
            for (key, mask) in command_keys:
                if mask != 0xFFFFFFFF:
                    raise exceptions.ConfigurationException(
                        "Command masks are too different to make a mask"
                        " consistent with all the keys.  This can be resolved"
                        " by either specifying a consistent mask, or by using"
                        " the mask 0xFFFFFFFF and providing exact keys")

            # If the keys are all fixed keys, keep them
            self._edge_constraints[edge] = list([
                KeyAllocatorFixedKeyAndMaskConstraint(
                    [BaseKeyAndMask(key, mask)
                     for (key, mask) in command_keys])])

    @staticmethod
    def get_n_command_bytes(
            times_with_commands, commands_with_payloads,
            commands_without_payloads):
        """ Get the number of bytes required by the given commands
        """
        n_bytes = 0

        for time in times_with_commands:

            # Add 3 words for count-with-command, count-without-command
            # and time
            n_bytes += 12

            # Add the size of each command
            if time in commands_with_payloads:
                n_bytes += (len(commands_with_payloads[time]) *
                            _COMMAND_WITH_PAYLOAD_SIZE)
            if time in commands_without_payloads:
                n_bytes += (len(commands_without_payloads[time]) *
                            _COMMAND_WITHOUT_PAYLOAD_SIZE)

        return n_bytes

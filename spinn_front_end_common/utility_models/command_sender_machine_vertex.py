from enum import Enum

from pacman.model.abstract_classes.impl.constrained_object import \
    ConstrainedObject
from pacman.model.decorators.delegates_to import delegates_to
from pacman.model.decorators.overrides import overrides
from pacman.model.graphs.machine.impl.machine_vertex \
    import MachineVertex
from spinn_front_end_common.abstract_models.\
    abstract_binary_uses_simulation_run import \
    AbstractBinaryUsesSimulationRun
from spinn_front_end_common.abstract_models.\
    abstract_has_associated_binary import \
    AbstractHasAssociatedBinary
from spinn_front_end_common.abstract_models.\
    abstract_requires_stop_command import \
    AbstractRequiresStopCommand
from spinn_front_end_common.interface.provenance\
    .provides_provenance_data_from_machine_impl \
    import ProvidesProvenanceDataFromMachineImpl
from spinn_front_end_common.interface.simulation import simulation_utilities
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utility_models.commands.\
    multi_cast_command_with_payload import MultiCastCommandWithPayload


class CommandSenderMachineVertex(
        MachineVertex, ProvidesProvenanceDataFromMachineImpl,
        AbstractRequiresStopCommand, AbstractHasAssociatedBinary,
        AbstractBinaryUsesSimulationRun):

    # Regions for populations
    DATA_REGIONS = Enum(
        value="DATA_REGIONS",
        names=[('SYSTEM_REGION', 0),
               ('COMMANDS_WITH_ARBITRARY_TIMES', 1),
               ('COMMANDS_AT_START_RESUME', 2),
               ('COMMANDS_AT_STOP_PAUSE', 3),
               ('PROVENANCE_REGION', 4)])

    # 4 for key, 4 for has payload, 4 for payload 2 for repeats, 2 for delays
    _COMMAND_WITH_PAYLOAD_SIZE = 16

    # 4 for key, 4 for no payload, 2 for repeats, 2 for delays
    _COMMAND_WITHOUT_PAYLOAD_SIZE = 12

    # 4 for the time stamp
    _COMMAND_TIMESTAMP_SIZE = 4

    # 4 for the size of the schedule
    _COMMAND_SIZE_SIZE = 4

    # 4 for the int to represent the number of commands
    _N_COMMANDS_SIZE = 4

    # bool for if the command has a payload
    _HAS_PAYLOAD = 0

    # bool for if the command does not have a payload
    _HAS_NO_PAYLOAD = 1

    # the number of mallocs used by the dsg
    TOTAL_REQUIRED_MALLOCS = 5

    def __init__(self, constraints, resources_required, label,
                 times_with_commands, commands_at_start_resume,
                 commands_at_pause_stop):
        ProvidesProvenanceDataFromMachineImpl.__init__(
            self, self.DATA_REGIONS.PROVENANCE_REGION.value,
            n_additional_data_items=0)
        AbstractRequiresStopCommand.__init__(self)
        MachineVertex.__init__(self, resources_required, label, constraints)

        # container of different types of command
        self._times_with_commands = times_with_commands
        self._commands_at_start_resume = commands_at_start_resume
        self._commands_at_pause_stop = commands_at_pause_stop

    @delegates_to("_constraints", ConstrainedObject.add_constraints)
    def add_constraints(self, constraints):
        pass

    @delegates_to("_constraints", ConstrainedObject.constraints)
    def constraints(self):
        pass

    @delegates_to("_constraints", ConstrainedObject.add_constraint)
    def add_constraint(self, constraint):
        pass

    def generate_data_specification(
            self, spec, placement, machine_time_step, time_scale_factor,
            n_machine_time_steps):

        timed_commands_size = \
            self.get_timed_commands_bytes(self._times_with_commands)
        start_resume_commands_size = \
            self.get_n_command_bytes(self._commands_at_start_resume)
        pause_stop_commands_size = \
            self.get_n_command_bytes(self._commands_at_pause_stop)

        # reverse memory regions
        self._reserve_memory_regions(
            spec, timed_commands_size, start_resume_commands_size,
            pause_stop_commands_size, placement.vertex)

        # Write system region
        spec.comment("\n*** Spec for multicast source ***\n\n")
        spec.switch_write_focus(
            CommandSenderMachineVertex.DATA_REGIONS.SYSTEM_REGION.value)
        spec.write_array(simulation_utilities.get_simulation_header_array(
            self.get_binary_file_name(), machine_time_step,
            time_scale_factor))

        # write commands
        spec.switch_write_focus(
            region=CommandSenderMachineVertex.DATA_REGIONS.
            COMMANDS_WITH_ARBITRARY_TIMES.value)

        # sort out times and messages not to send
        new_times = self._sort_out_timings(n_machine_time_steps)

        # write commands to spec for timed commands
        self._write_arbitiary_times(new_times, spec, timed_commands_size)

        # write commands fired off during a start or resume
        spec.switch_write_focus(
            region=CommandSenderMachineVertex.DATA_REGIONS.
            COMMANDS_AT_START_RESUME.value)

        self._write_basic_commands(
            self._commands_at_start_resume, start_resume_commands_size, spec)

        # write commands fired off during a pause or end
        spec.switch_write_focus(
            region=CommandSenderMachineVertex.DATA_REGIONS.
            COMMANDS_AT_STOP_PAUSE.value)

        self._write_basic_commands(
            self._commands_at_pause_stop, pause_stop_commands_size, spec)

        # End-of-Spec:
        spec.end_specification()

    def _write_basic_commands(self, commands, commands_size, spec):
        # first size of data region
        spec.write_value(
            commands_size - CommandSenderMachineVertex._COMMAND_SIZE_SIZE)

        # number of commands
        spec.write_value(len(commands))

        # write commands to region
        for command in commands:
            self._write_command(command, spec)

    def _write_arbitiary_times(self, new_times, spec, timed_commands_size):
        # write size of the data region
        spec.write_value(timed_commands_size -
                         CommandSenderMachineVertex._COMMAND_SIZE_SIZE)

        # for each time, write commands
        for time in sorted(new_times):

            # write the time to fire
            spec.write_value(time)

            # write the number of commands to send
            spec.write_value(len(self._times_with_commands[time]))

            # Gather the different types of commands
            for command in self._times_with_commands[time]:
                self._write_command(command, spec)

    @staticmethod
    def _write_command(command, spec):
        if isinstance(command, MultiCastCommandWithPayload):
            spec.write_value(command.key)
            spec.write_value(CommandSenderMachineVertex._HAS_PAYLOAD)
            spec.write_value(command.payload)
            spec.write_value((command.repeat << 16 |
                              command.delay_between_repeats))
        else:
            spec.write_value(command.key)
            spec.write_value(CommandSenderMachineVertex._HAS_NO_PAYLOAD)
            spec.write_value((command.repeat << 16 |
                              command.delay_between_repeats))

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
    def _reserve_memory_regions(
            spec, time_command_size, start_command_size, end_command_size,
            vertex):
        """
        Reserve SDRAM space for memory areas:
        1) Area for information on what data to record
        2) area for start commands
        3) area for end commands
        """
        spec.comment("\nReserving memory space for data regions:\n\n")

        # Reserve memory:
        spec.reserve_memory_region(
            region=CommandSenderMachineVertex.DATA_REGIONS.SYSTEM_REGION.value,
            size=constants.SYSTEM_BYTES_REQUIREMENT, label='setup')

        spec.reserve_memory_region(
            region=CommandSenderMachineVertex.
            DATA_REGIONS.COMMANDS_WITH_ARBITRARY_TIMES.value,
            size=time_command_size, label='commands with arbitrary times')

        spec.reserve_memory_region(
            region=CommandSenderMachineVertex.
            DATA_REGIONS.COMMANDS_AT_START_RESUME.value,
            size=start_command_size, label='commands with start resume times')

        spec.reserve_memory_region(
            region=CommandSenderMachineVertex.
            DATA_REGIONS.COMMANDS_AT_STOP_PAUSE.value,
            size=end_command_size, label='commands with stop pause times')

        vertex.reserve_provenance_data_region(spec)

    @staticmethod
    def get_timed_commands_bytes(times_with_commands):
        n_bytes = CommandSenderMachineVertex._COMMAND_SIZE_SIZE

        # handle timed commands
        for time in times_with_commands:
            n_bytes += CommandSenderMachineVertex._COMMAND_TIMESTAMP_SIZE
            n_bytes += CommandSenderMachineVertex._N_COMMANDS_SIZE
            for command in times_with_commands[time]:
                n_bytes += CommandSenderMachineVertex._get_command_size(command)
        return n_bytes

    @staticmethod
    def get_n_command_bytes(commands):
        """
        :return:
        """
        n_bytes = (CommandSenderMachineVertex._COMMAND_SIZE_SIZE +
                   CommandSenderMachineVertex._N_COMMANDS_SIZE)
        for command in commands:
            n_bytes += CommandSenderMachineVertex._get_command_size(command)
        return n_bytes

    @staticmethod
    def _get_command_size(command):
        if isinstance(command, MultiCastCommandWithPayload):
            return CommandSenderMachineVertex._COMMAND_WITH_PAYLOAD_SIZE
        else:
            return CommandSenderMachineVertex._COMMAND_WITHOUT_PAYLOAD_SIZE

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        """ Return a string representation of the models binary

        :return:
        """
        return 'command_sender_multicast_source.aplx'

    @staticmethod
    def get_number_of_mallocs_used_by_dsg():
        return CommandSenderMachineVertex.TOTAL_REQUIRED_MALLOCS

from enum import Enum
from collections import Counter

from pacman.model.decorators.overrides import overrides
from pacman.model.graphs.machine import MachineVertex
from spinn_front_end_common.abstract_models.\
    abstract_has_associated_binary import \
    AbstractHasAssociatedBinary
from spinn_front_end_common.interface.provenance\
    .provides_provenance_data_from_machine_impl \
    import ProvidesProvenanceDataFromMachineImpl
from spinn_front_end_common.interface.simulation import simulation_utilities
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utilities.utility_objs.executable_start_type\
    import ExecutableStartType


class CommandSenderMachineVertex(
        MachineVertex, ProvidesProvenanceDataFromMachineImpl,
        AbstractHasAssociatedBinary):

    # Regions for populations
    DATA_REGIONS = Enum(
        value="DATA_REGIONS",
        names=[('SYSTEM_REGION', 0),
               ('SETUP', 1),
               ('COMMANDS_WITH_ARBITRARY_TIMES', 2),
               ('COMMANDS_AT_START_RESUME', 3),
               ('COMMANDS_AT_STOP_PAUSE', 4),
               ('PROVENANCE_REGION', 5)])

    # 4 for key, 4 for has payload, 4 for payload 4 for repeats, 4 for delays
    _COMMAND_WITH_PAYLOAD_SIZE = 20

    # 4 for the time stamp
    _COMMAND_TIMESTAMP_SIZE = 4

    # 4 for the int to represent the number of commands
    _N_COMMANDS_SIZE = 4

    # bool for if the command has a payload (true = 1)
    _HAS_PAYLOAD = 1

    # bool for if the command does not have a payload (false = 0)
    _HAS_NO_PAYLOAD = 0

    # Setup data size (one word)
    _SETUP_DATA_SIZE = 4

    # the number of malloc requests used by the dsg
    TOTAL_REQUIRED_MALLOCS = 5

    def __init__(
            self, constraints, resources_required, label,
            commands_at_start_resume, commands_at_pause_stop, timed_commands):
        ProvidesProvenanceDataFromMachineImpl.__init__(self)
        MachineVertex.__init__(self, label, constraints)

        # container of different types of command
        self._timed_commands = timed_commands
        self._commands_at_start_resume = commands_at_start_resume
        self._commands_at_pause_stop = commands_at_pause_stop
        self._resources = resources_required

    @property
    @overrides(ProvidesProvenanceDataFromMachineImpl._provenance_region_id)
    def _provenance_region_id(self):
        return self.DATA_REGIONS.PROVENANCE_REGION.value

    @property
    @overrides(ProvidesProvenanceDataFromMachineImpl._n_additional_data_items)
    def _n_additional_data_items(self):
        return 0

    @property
    @overrides(MachineVertex.resources_required)
    def resources_required(self):
        return self._resources

    def generate_data_specification(
            self, spec, placement, machine_time_step, time_scale_factor,
            n_machine_time_steps):

        timed_commands_size = \
            self.get_timed_commands_bytes(self._timed_commands)
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

        # Write setup region
        # Find the maximum number of commands per timestep
        max_n_commands = 0
        if len(self._timed_commands) > 0:
            counter = Counter(self._timed_commands)
            max_n_commands = counter.most_common(1)[0][1]
        max_n_commands = max([
            max_n_commands, len(self._commands_at_start_resume),
            len(self._commands_at_pause_stop)])
        time_between_commands = 0
        if max_n_commands > 0:
            time_between_commands = (
                (machine_time_step * time_scale_factor / 2) / max_n_commands)
        spec.switch_write_focus(
            CommandSenderMachineVertex.DATA_REGIONS.SETUP.value)
        spec.write_value(time_between_commands)

        # write commands
        spec.switch_write_focus(
            region=CommandSenderMachineVertex.DATA_REGIONS.
            COMMANDS_WITH_ARBITRARY_TIMES.value)

        # write commands to spec for timed commands
        self._write_timed_commands(self._timed_commands, spec)

        # write commands fired off during a start or resume
        spec.switch_write_focus(
            region=CommandSenderMachineVertex.DATA_REGIONS.
            COMMANDS_AT_START_RESUME.value)

        self._write_basic_commands(self._commands_at_start_resume, spec)

        # write commands fired off during a pause or end
        spec.switch_write_focus(
            region=CommandSenderMachineVertex.DATA_REGIONS.
            COMMANDS_AT_STOP_PAUSE.value)

        self._write_basic_commands(self._commands_at_pause_stop, spec)

        # End-of-Spec:
        spec.end_specification()

    def _write_basic_commands(self, commands, spec):

        # number of commands
        spec.write_value(len(commands))

        # write commands to region
        for command in commands:
            self._write_command(command, spec)

    def _write_timed_commands(self, timed_commands, spec):

        spec.write_value(len(timed_commands))

        # write commands
        for command in timed_commands:
            spec.write_value(command.time)
            self._write_command(command, spec)

    @staticmethod
    def _write_command(command, spec):
        spec.write_value(command.key)
        spec.write_value(CommandSenderMachineVertex._HAS_PAYLOAD)
        spec.write_value(command.payload if command.is_payload else 0)
        spec.write_value(command.repeat)
        spec.write_value(command.delay_between_repeats)

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
            size=constants.SYSTEM_BYTES_REQUIREMENT, label='system')

        spec.reserve_memory_region(
            region=CommandSenderMachineVertex.DATA_REGIONS.SETUP.value,
            size=CommandSenderMachineVertex._SETUP_DATA_SIZE, label='setup')

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
    def get_timed_commands_bytes(timed_commands):
        n_bytes = CommandSenderMachineVertex._N_COMMANDS_SIZE
        n_bytes += (
            (CommandSenderMachineVertex._COMMAND_TIMESTAMP_SIZE +
             CommandSenderMachineVertex._COMMAND_WITH_PAYLOAD_SIZE) *
            len(timed_commands)
        )
        return n_bytes

    @staticmethod
    def get_n_command_bytes(commands):
        """
        :return:
        """
        n_bytes = CommandSenderMachineVertex._N_COMMANDS_SIZE
        n_bytes += (
            CommandSenderMachineVertex._COMMAND_WITH_PAYLOAD_SIZE *
            len(commands)
        )
        return n_bytes

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        """ Return a string representation of the models binary

        :return:
        """
        return 'command_sender_multicast_source.aplx'

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return ExecutableStartType.USES_SIMULATION_INTERFACE

    @staticmethod
    def get_number_of_mallocs_used_by_dsg():
        return CommandSenderMachineVertex.TOTAL_REQUIRED_MALLOCS

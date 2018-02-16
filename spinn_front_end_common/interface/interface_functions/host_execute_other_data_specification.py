from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.utility_models.data_speed_up_packet_gatherer_machine_vertex import \
    DataSpeedUpPacketGatherMachineVertex
from spinn_utilities.progress_bar import ProgressBar

import logging
import struct

logger = logging.getLogger(__name__)
_ONE_WORD = struct.Struct("<I")


class HostExecuteOtherDataSpecification(object):
    """ Executes the host based data specification
    """

    __slots__ = []

    def __call__(
            self, transceiver, machine, app_id, dsg_targets,
            uses_advanced_monitors, executable_targets, placements=None,
            extra_monitor_cores=None,
            extra_monitor_to_chip_mapping=None,
            extra_monitor_cores_to_ethernet_connection_map=None,
            processor_to_app_data_base_address=None):
        """

        :param machine: the python representation of the spinnaker machine
        :param transceiver: the spinnman instance
        :param app_id: the application ID of the simulation
        :param dsg_targets: map of placement to file path

        :return: map of placement and dsg data, and loaded data flag.
        """
        if processor_to_app_data_base_address is None:
            processor_to_app_data_base_address = dict()

        # if using extra monitors, set up routing timeouts
        if uses_advanced_monitors:
            DataSpeedUpPacketGatherMachineVertex.set_cores_for_data_streaming(
                transceiver, extra_monitor_cores, placements)

        # create a progress bar for end users
        progress = ProgressBar(
            executable_targets.total_processors + 1 -
            executable_targets.get_n_cores_for_executable_type(
                ExecutableType.SYSTEM),
            "Executing data specifications and loading data for "
            "application vertices")

        # only load executables not of system type.
        executable_types = executable_targets.executable_types_in_binary_set()
        for executable_type in executable_types:
            if executable_type != ExecutableType.SYSTEM:
                for binary in \
                        executable_targets.get_binaries_of_executable_type(
                            executable_type):
                    self._execute_dse_for_binary(
                        binary, executable_targets, transceiver, machine,
                        app_id, progress, processor_to_app_data_base_address,
                        dsg_targets, uses_advanced_monitors,
                        extra_monitor_cores_to_ethernet_connection_map)
        progress.end()

        # reset router timeouts
        if uses_advanced_monitors:
            DataSpeedUpPacketGatherMachineVertex.\
                unset_cores_for_data_streaming(
                    transceiver, extra_monitor_cores, placements)

        return processor_to_app_data_base_address

    @staticmethod
    def _execute_dse_for_binary(
            binary, executable_targets, transceiver, machine, app_id,
            progress, processor_to_app_data_base_address, dsg_targets,
            uses_advanced_monitors,
            extra_monitor_cores_to_ethernet_connection_map):

        core_subsets = executable_targets.get_cores_for_binary(binary)
        for core_subset in core_subsets:
            x = core_subset.x
            y = core_subset.y

            # determine which function to use for writing memory
            write_memory_function = DataSpeedUpPacketGatherMachineVertex.\
                locate_correct_write_data_function_for_chip_location(
                    machine=machine, x=x, y=y, transceiver=transceiver,
                    uses_advanced_monitors=uses_advanced_monitors,
                    extra_monitor_cores_to_ethernet_connection_map=
                    extra_monitor_cores_to_ethernet_connection_map)

            # execute dse, allocate sdram and write to spinnaker via correct
            # write function
            for p in core_subset.processor_ids:
                data = helpful_functions.\
                    execute_dse_allocate_sdram_and_write_to_spinnaker(
                        transceiver, machine, app_id, x, y, p,
                        dsg_targets[(x, y, p)], write_memory_function)
                processor_to_app_data_base_address[x, y, p] = data
                progress.update()

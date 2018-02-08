from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_utilities.progress_bar import ProgressBar

import logging
import struct

logger = logging.getLogger(__name__)
_ONE_WORD = struct.Struct("<I")


class HostExecuteSystemDataSpecification(object):
    """ Executes the host based data specification
    """

    __slots__ = []

    def __call__(
            self, transceiver, machine, app_id, dsg_targets,
            executable_targets):
        """

        :param machine: the python representation of the spinnaker machine
        :param transceiver: the spinnman instance
        :param app_id: the application ID of the simulation
        :param dsg_targets: map of placement to file path
        :param executable_targets: the map between binaries and locations\
         and executable types

        :return: map of placement and dsg data, and loaded data flag.
        """

        processor_to_app_data_base_address = dict()

        # create a progress bar for end users
        progress = ProgressBar(
            executable_targets.get_n_cores_for_executable_type(
                ExecutableType.SYSTEM),
            "Executing data specifications and loading data for system "
            "vertices")

        for binary in executable_targets.get_binaries_of_executable_type(
                ExecutableType.SYSTEM):
            core_subsets = executable_targets.get_cores_for_binary(binary)
            for core_subset in core_subsets:
                x = core_subset.x
                y = core_subset.y
                for p in core_subset.processor_ids:
                    # write information for the memory map report
                    data = helpful_functions.\
                        execute_dse_allocate_sdram_and_write_to_spinnaker(
                            transceiver, machine, app_id, x, y, p,
                            dsg_targets[(x, y, p)],  transceiver.write_memory)
                    processor_to_app_data_base_address[x, y, p] = data
                    progress.update()
        progress.end()
        return processor_to_app_data_base_address

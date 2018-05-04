import logging
import struct
from spinn_front_end_common.utilities.helpful_functions import (
    execute_dse_allocate_sdram_and_write_to_spinnaker)
from spinn_front_end_common.utilities.utility_objs.executable_type import (
    ExecutableType)
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter


logger = FormatAdapter(logging.getLogger(__name__))
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
        :type machine: :py:class:`~spinn_machine.Machine`
        :param transceiver: the spinnman instance
        :type transceiver: :py:class:`~spinnman.Transceiver`
        :param app_id: the application ID of the simulation
        :type app_id: int
        :param dsg_targets: map of placement to file path
        :type dsg_targets: dict(tuple(int,int,int),str)
        :param executable_targets: \
            the map between binaries and locations and executable types
        :type executable_targets: ?
        :return: map of placement and DSG data, and loaded data flag.
        :rtype: dict(tuple(int,int,int),DataWritten)
        """
        # pylint: disable=too-many-arguments

        processor_to_app_data_base_address = dict()

        # create a progress bar for end users
        progress = ProgressBar(
            executable_targets.get_n_cores_for_executable_type(
                SYSTEM),
            "Executing data specifications and loading data for system "
            "vertices")
        self._execute_system_specs(
            transceiver, machine, app_id, executable_targets, dsg_targets,
            processor_to_app_data_base_address, progress)
        progress.end()
        return processor_to_app_data_base_address

    @staticmethod
    def _execute_system_specs(
            txrx, machine, app_id, targets, dsg_targets, base_addresses,
            progress):
        for binary in targets.get_binaries_of_executable_type(ExecutableType.SYSTEM):
            core_subsets = targets.get_cores_for_binary(binary)
            for core_subset in core_subsets:
                x = core_subset.x
                y = core_subset.y
                for p in progress.over(core_subset.processor_ids, False):
                    # write information for the memory map report
                    data = execute_dse_allocate_sdram_and_write_to_spinnaker(
                        txrx, machine, app_id, x, y, p,
                        dsg_targets[x, y, p],  txrx.write_memory)
                    base_addresses[x, y, p] = data

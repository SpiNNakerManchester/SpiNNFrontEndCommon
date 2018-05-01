import os
import logging
import struct
from spinn_front_end_common.utility_models import (
    DataSpeedUpPacketGatherMachineVertex)
from data_specification.data_spec_sender import data_specification_executor
from spinn_utilities.progress_bar import ProgressBar
from spinn_machine import CoreSubsets
from spinnman.model.enums import CPUState
from spinn_front_end_common.utilities.constants import DSE_DATA_STRUCT_SIZE
from spinn_front_end_common.utilities.helpful_functions import (
    write_address_to_user0)


logger = logging.getLogger(__name__)
_FOUR_WORDS = struct.Struct("<4I")


class MachineExecuteOtherDataSpecification(object):
    """ Executes the machine based data specification
    """

    __slots__ = []

    def __call__(
            self, write_memory_map_report, dsg_targets, transceiver, app_id,
            uses_advanced_monitors=False, machine=None,
            extra_monitor_cores_to_ethernet_connection_map=None):
        """
        :param write_memory_map_report: bool for writing memory report
        :param dsg_targets: the mapping between placement and dsg file
        :param transceiver: SpiNNMan instance
        :param app_id: the app id
        :param machine: the SpiNNMachine instance
        :param uses_advanced_monitors: flag for using extra monitors
        :param extra_monitor_cores_to_ethernet_connection_map:\
        extra monitor to ethernet chip map
        """
        return self.spinnaker_based_data_specification_execution(
            write_memory_map_report, dsg_targets, transceiver, app_id,
            uses_advanced_monitors, machine,
            extra_monitor_cores_to_ethernet_connection_map)

    def spinnaker_based_data_specification_execution(
            self, write_memory_map_report, dsg_targets, transceiver, app_id,
            uses_advanced_monitors, machine,
            extra_monitor_cores_to_ethernet_connection_map):
        """
        :param write_memory_map_report: bool for writing memory report
        :param dsg_targets: the mapping between placement and dsg file
        :param transceiver: SpiNNMan instance
        :param app_id: the app id
        :param machine: the SpiNNMachine instance
        :param uses_advanced_monitors: flag for using extra monitors
        :param extra_monitor_cores_to_ethernet_connection_map:\
        extra monitor to ethernet chip map
        :return: True
        :rtype: bool
        """

        dse_app_id, core_subset = self._load_data_specs(
            transceiver, dsg_targets, app_id, write_memory_map_report,
            uses_advanced_monitors, machine,
            extra_monitor_cores_to_ethernet_connection_map)
        # Execute the DSE on all the cores
        logger.info("Loading the Data Specification Executor")
        self._execute_data_specs(transceiver, core_subset, app_id, dse_app_id)
        logger.info("On-chip Data Specification Executor completed")

    @staticmethod
    def _load_data_specs(txrx, dsg_targets, app_id, write_report,
                         uses_advanced_monitors, machine,
                         extra_monitor_cores_to_ethernet_connection_map):
        # pylint: disable=too-many-locals

        # create a progress bar for end users
        progress = ProgressBar(dsg_targets, "Loading data specifications")

        dse_app_id = txrx.app_id_tracker.get_new_id()
        core_subset = CoreSubsets()

        for (x, y, p, label) in progress.over(dsg_targets):
            core_subset.add_processor(x, y, p)
            file_path = dsg_targets[x, y, p, label]
            file_size = os.path.getsize(file_path)

            # data spec file is written at specific address (file_data_addr);
            # this is encapsulated in a structure with four fields:
            #
            # 1 - data specification base address
            # 2 - data specification file size
            # 3 - future application ID
            # 4 - store data for memory map report (True / False)
            #
            # If the memory map report is going to be produced, the
            # address of the structure is returned in user1

            dse_data_struct = txrx.malloc_sdram(
                x, y, DSE_DATA_STRUCT_SIZE, dse_app_id)
            file_data_addr = txrx.malloc_sdram(x, y, file_size, dse_app_id)

            txrx.write_memory(x, y, dse_data_struct, _FOUR_WORDS.pack(
                file_data_addr, file_size, app_id, write_report))

            # determine which function to use for writing large memory
            write_memory_function = DataSpeedUpPacketGatherMachineVertex. \
                locate_correct_write_data_function_for_chip_location(
                    machine=machine, x=x, y=y, transceiver=txrx,
                    uses_advanced_monitors=uses_advanced_monitors,
                    extra_monitor_cores_to_ethernet_connection_map=(
                        extra_monitor_cores_to_ethernet_connection_map))

            write_memory_function(
                x, y, file_data_addr, file_path, is_filename=True)

            write_address_to_user0(txrx, x, y, p, dse_data_struct)

        return dse_app_id, core_subset

    @staticmethod
    def _execute_data_specs(txrx, cores, app_id, dse_app_id):
        dse_executor = data_specification_executor()
        txrx.execute_flood(cores, dse_executor, app_id, is_filename=True)

        logger.info(
            "Waiting for On-chip Data Specification Executor to complete")

        txrx.wait_for_cores_to_be_in_state(cores, app_id, [CPUState.FINISHED])
        txrx.stop_application(dse_app_id)
        txrx.app_id_tracker.free_id(dse_app_id)

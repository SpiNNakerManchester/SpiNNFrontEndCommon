from data_specification.data_spec_sender import data_specification_executor

from spinn_utilities.progress_bar import ProgressBar
from spinn_machine import CoreSubsets

# spinnman imports
from spinnman.model.enums import CPUState

# front end common imports
from spinn_front_end_common.utilities.constants import DSE_DATA_STRUCT_SIZE
from spinn_front_end_common.utilities.helpful_functions \
    import write_address_to_user0

import os
import logging
import struct

logger = logging.getLogger(__name__)
_FOUR_WORDS = struct.Struct("<4I")


class MachineExecuteDataSpecification(object):
    """ Executes the machine based data specification
    """

    __slots__ = []

    def __call__(
            self, write_memory_map_report, dsg_targets, transceiver, app_id):
        """
        :param write_memory_map_report:
        :param dsg_targets:
        :param transceiver:
        :param app_id:
        """
        return self.spinnaker_based_data_specification_execution(
            write_memory_map_report, dsg_targets, transceiver, app_id)

    def spinnaker_based_data_specification_execution(
            self, write_memory_map_report, dsg_targets, transceiver, app_id):
        """
        :param write_memory_map_report:
        :param dsg_targets:
        :param transceiver:
        :param app_id:
        :return: True
        :rtype: bool
        """

        dse_app_id, core_subset = self._load_data_specs(
            transceiver, dsg_targets, app_id, write_memory_map_report)
        # Execute the DSE on all the cores
        logger.info("Loading the Data Specification Executor")
        self._execute_data_specs(transceiver, core_subset, app_id, dse_app_id)
        logger.info("On-chip Data Specification Executor completed")

    def _load_data_specs(self, txrx, dsg_targets, app_id, write_report):
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
            txrx.write_memory(x, y, file_data_addr, file_path,
                              is_filename=True)
            write_address_to_user0(txrx, x, y, p, dse_data_struct)

        return dse_app_id, core_subset

    def _execute_data_specs(self, txrx, cores, app_id, dse_app_id):
        dse_executor = data_specification_executor()
        txrx.execute_flood(cores, dse_executor, app_id, is_filename=True)

        logger.info(
            "Waiting for On-chip Data Specification Executor to complete")

        txrx.wait_for_cores_to_be_in_state(cores, app_id, [CPUState.FINISHED])
        txrx.stop_application(dse_app_id)
        txrx.app_id_tracker.free_id(dse_app_id)

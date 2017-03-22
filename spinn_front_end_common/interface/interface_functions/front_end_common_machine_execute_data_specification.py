from data_specification import data_spec_sender

from spinn_machine.utilities.progress_bar import ProgressBar
from spinn_machine.core_subsets import CoreSubsets

# spinnman imports
from spinnman.model.enums.cpu_state import CPUState

# front end common imports
from spinn_front_end_common.utilities import constants

import os
import logging
import struct

logger = logging.getLogger(__name__)


class FrontEndCommonMachineExecuteDataSpecification(object):
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
        data = self.spinnaker_based_data_specification_execution(
            write_memory_map_report, dsg_targets, transceiver, app_id)
        return data

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

        # create a progress bar for end users
        progress_bar = ProgressBar(
            len(dsg_targets), "Loading data specifications")

        dse_app_id = transceiver.app_id_tracker.get_new_id()

        core_subset = CoreSubsets()
        for (x, y, p, label) in dsg_targets:

            core_subset.add_processor(x, y, p)

            dse_data_struct_address = transceiver.malloc_sdram(
                x, y, constants.DSE_DATA_STRUCT_SIZE, dse_app_id)

            data_spec_file_path = dsg_targets[x, y, p, label]
            data_spec_file_size = os.path.getsize(data_spec_file_path)

            base_address = transceiver.malloc_sdram(
                x, y, data_spec_file_size, dse_app_id)

            dse_data_struct_data = struct.pack(
                "<4I", base_address, data_spec_file_size, app_id,
                write_memory_map_report)

            transceiver.write_memory(
                x, y, dse_data_struct_address, dse_data_struct_data,
                len(dse_data_struct_data))

            transceiver.write_memory(
                x, y, base_address, data_spec_file_path, is_filename=True)

            # data spec file is written at specific address (base_address)
            # this is encapsulated in a structure with four fields:
            # 1 - data specification base address
            # 2 - data specification file size
            # 3 - future application ID
            # 4 - store data for memory map report (True / False)
            # If the memory map report is going to be produced, the
            # address of the structure is returned in user1
            user_0_address = transceiver.\
                get_user_0_register_address_from_core(x, y, p)

            transceiver.write_memory(
                x, y, user_0_address, dse_data_struct_address, 4)

            progress_bar.update()
        progress_bar.end()

        # Execute the DSE on all the cores
        logger.info("Loading the Data Specification Executor")
        dse_exec = os.path.join(
            os.path.dirname(data_spec_sender),
            'data_specification_executor.aplx')
        transceiver.execute_flood(
            core_subset, dse_exec, app_id, is_filename=True)

        logger.info(
            "Waiting for On-chip Data Specification Executor to complete")
        transceiver.wait_for_cores_to_be_in_state(
            core_subset, app_id, [CPUState.FINISHED])

        transceiver.stop_application(dse_app_id)
        transceiver.app_id_tracker.free_id(dse_app_id)
        logger.info("On-chip Data Specification Executor completed")

        return True

# spinn_io_handler imports
from spinn_storage_handlers.file_data_reader import FileDataReader

# data spec imports
import data_specification.data_spec_sender.spec_sender as spec_sender

# pacman imports
from spinn_machine.progress_bar import ProgressBar

# spinnman imports
from spinnman.model.core_subsets import CoreSubsets
from spinnman.model.cpu_state import CPUState

# front end common imports
from spinn_front_end_common.utilities import constants

import os
import logging
import struct
import time
from spinn_front_end_common.utilities import helpful_functions

logger = logging.getLogger(__name__)


class FrontEndCommonPartitionableGraphMachineExecuteDataSpecification(object):
    """ Executes the machine based data specification
    """

    def __call__(
            self, write_memory_map_report, dsg_targets, transceiver,
            dse_app_id, app_id):
        """

        :param hostname:
        :param placements:
        :param graph_mapper:
        :param write_text_specs:
        :param runtime_application_data_folder:
        :param machine:
        :return:
        """

        data = self.spinnaker_based_data_specification_execution(
            write_memory_map_report, dsg_targets, transceiver,
            dse_app_id, app_id)

        return data

    def spinnaker_based_data_specification_execution(
            self, write_memory_map_report, dsg_targets, transceiver,
            dse_app_id, app_id):
        """

        :param hostname:
        :param placements:
        :param graph_mapper:
        :param write_text_specs:
        :param application_data_runtime_folder:
        :param machine:
        :return:
        """

        # create a progress bar for end users
        progress_bar = ProgressBar(
            len(list(dsg_targets)),
            "Loading data specifications")

        number_of_cores_used = 0
        core_subset = CoreSubsets()
        for ((x, y, p), data_spec_file_path) in dsg_targets.iteritems():

            core_subset.add_processor(x, y, p)

            dse_data_struct_addr = transceiver.malloc_sdram(
                x, y, constants.DSE_DATA_STRUCT_SIZE, dse_app_id)

            data_spec_file_path = dsg_targets[x, y, p]
            data_spec_file_size = os.path.getsize(data_spec_file_path)

            application_data_file_reader = FileDataReader(
                data_spec_file_path)

            base_address = transceiver.malloc_sdram(
                x, y, data_spec_file_size, dse_app_id)

            dse_data_struct_data = struct.pack(
                "<IIII", base_address, data_spec_file_size, app_id,
                write_memory_map_report)

            transceiver.write_memory(
                x, y, dse_data_struct_addr, dse_data_struct_data,
                len(dse_data_struct_data))

            transceiver.write_memory(
                x, y, base_address, application_data_file_reader,
                data_spec_file_size)

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
                x, y, user_0_address, dse_data_struct_addr, 4)

            progress_bar.update()
        progress_bar.end()

        # Execute the DSE on all the cores
        logger.info("Loading the Data Specification Executer")
        dse_exec = os.path.join(
            os.path.dirname(spec_sender.__file__),
            'data_specification_executor.aplx')
        file_reader = FileDataReader(dse_exec)
        size = os.stat(dse_exec).st_size
        transceiver.execute_flood(
            core_subset, file_reader, app_id, size)

        logger.info(
            "Waiting for On-chip Data Specification Executer to complete")
        processors_exited = transceiver.get_core_state_count(
            dse_app_id, CPUState.FINISHED)
        while processors_exited < number_of_cores_used:
            processors_errored = transceiver.get_core_state_count(
                dse_app_id, CPUState.RUN_TIME_EXCEPTION)
            if processors_errored > 0:
                error_cores = helpful_functions.get_cores_in_state(
                    core_subset, CPUState, transceiver)
                if len(error_cores) > 0:
                    error = helpful_functions.get_core_status_string(
                        error_cores)
                    raise Exception(
                        "Data Specification Execution has failed: {}".format(
                            error))
            time.sleep(1)
            processors_exited = transceiver.get_core_state_count(
                dse_app_id, CPUState.FINISHED)

        transceiver.stop_application(dse_app_id)
        logger.info("On-chip Data Specification Executer completed")

        return {
            "LoadedApplicationDataToken": True,
            "DSEOnHost": False,
            "DSEOnChip": True}

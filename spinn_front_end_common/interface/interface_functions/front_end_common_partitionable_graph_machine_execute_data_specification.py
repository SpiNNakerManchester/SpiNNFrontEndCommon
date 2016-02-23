# spinn_io_handler imports
from spinn_storage_handlers.file_data_reader import FileDataReader

# data spec imports
import data_specification.data_spec_sender.spec_sender as spec_sender

# pacman imports
from pacman.utilities.utility_objs.progress_bar import ProgressBar

# spinnman imports
from spinnman.model.core_subsets import CoreSubsets
from spinnman.model.cpu_state import CPUState

# front end common imports
from spinn_front_end_common.abstract_models.\
    abstract_data_specable_vertex import \
    AbstractDataSpecableVertex
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utilities import exceptions

import os
import logging
import struct
import time

logger = logging.getLogger(__name__)


class FrontEndCommonPartitionableGraphMachineExecuteDataSpecification(object):
    """ Executes the machine based data specification
    """

    def __call__(
            self, hostname, placements, graph_mapper, report_default_directory,
            report_states, runtime_application_data_folder, machine,
            board_version, dsg_targets, transceiver, dse_app_id, app_id):
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
            hostname, placements, graph_mapper, report_states,
            runtime_application_data_folder, machine, board_version,
            report_default_directory, dsg_targets, transceiver,
            dse_app_id, app_id)

        return data

    def spinnaker_based_data_specification_execution(
            self, hostname, placements, graph_mapper, report_states,
            application_data_runtime_folder, machine, board_version,
            report_default_directory, dsg_targets, transceiver,
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
        mem_map_report = report_states.write_memory_map_report

        # check which cores are in use
        number_of_cores_used = 0
        core_subset = CoreSubsets()
        for placement in placements.placements:
            core_subset.add_processor(placement.x, placement.y, placement.p)
            number_of_cores_used += 1

        # read DSE exec name
        executable_targets = {
            os.path.dirname(spec_sender.__file__) +
            '/data_specification_executor.aplx': core_subset}

        # create a progress bar for end users
        progress_bar = ProgressBar(len(list(placements.placements)),
                                   "Loading data specifications on chip")

        for placement in placements.placements:
            associated_vertex = graph_mapper.get_vertex_from_subvertex(
                placement.subvertex)

            # if the vertex can generate a DSG, call it
            if isinstance(associated_vertex, AbstractDataSpecableVertex):

                x, y, p = placement.x, placement.y, placement.p
                label = associated_vertex.label

                dse_data_struct_addr = transceiver.malloc_sdram(
                    x, y, constants.DSE_DATA_STRUCT_SIZE, dse_app_id)

                data_spec_file_path = dsg_targets[x, y, p, label]
                data_spec_file_size = os.path.getsize(data_spec_file_path)

                application_data_file_reader = FileDataReader(
                    data_spec_file_path)

                base_address = transceiver.malloc_sdram(
                    x, y, data_spec_file_size, dse_app_id)

                dse_data_struct_data = struct.pack(
                    "<IIII", base_address, data_spec_file_size, app_id,
                    mem_map_report)

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

        self._load_executable_images(
            transceiver, executable_targets, dse_app_id,
            app_data_folder=application_data_runtime_folder)

        processors_exited = transceiver.get_core_state_count(
            dse_app_id, CPUState.FINISHED)
        while processors_exited < number_of_cores_used:
            logger.info(
                "Data spec executor on chip not completed, waiting "
                "1 second for it to complete")
            time.sleep(1)
            processors_exited = transceiver.get_core_state_count(
                dse_app_id, CPUState.FINISHED)

        transceiver.stop_application(dse_app_id)
        logger.info("On-chip data spec executor completed")

        return {
            "LoadedApplicationDataToken": True,
            "DSEOnHost": False,
            "DSEOnChip": True}

    def _load_executable_images(self, transceiver, executable_targets, app_id,
                                app_data_folder):
        """ Go through the executable targets and load each binary to \
            everywhere and then send a start request to the cores that \
            actually use it
        """

        progress_bar = ProgressBar(len(executable_targets),
                                   "Loading executables onto the machine")
        for executable_target_key in executable_targets:
            file_reader = FileDataReader(executable_target_key)
            core_subset = executable_targets[executable_target_key]

            statinfo = os.stat(executable_target_key)
            size = statinfo.st_size

            # TODO there is a need to parse the binary and see if its
            # ITCM and DTCM requirements are within acceptable params for
            # operating on spinnaker. Currently there are just a few safety
            # checks which may not be accurate enough.
            if size > constants.MAX_SAFE_BINARY_SIZE:
                logger.warn(
                    "The size of {} is large enough that its"
                    " possible that the binary may be larger than what is"
                    " supported by spinnaker currently. Please reduce the"
                    " binary size if it starts to behave strangely, or goes"
                    " into the WDOG state before starting.".format(
                        executable_target_key))
                if size > constants.MAX_POSSIBLE_BINARY_SIZE:
                    raise exceptions.ConfigurationException(
                        "The size of the binary is too large and therefore"
                        " will very likely cause a WDOG state. Until a more"
                        " precise measurement of ITCM and DTCM can be produced"
                        " this is deemed as an error state. Please reduce the"
                        " size of your binary or circumvent this error check.")

            transceiver.execute_flood(core_subset, file_reader, app_id,
                                      size)

            progress_bar.update()
        progress_bar.end()

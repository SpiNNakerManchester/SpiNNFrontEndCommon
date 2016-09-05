
# data spec imports
from data_specification.data_specification_executor import \
    DataSpecificationExecutor
from data_specification import exceptions

# spinn_storage_handlers import
from spinn_storage_handlers.file_data_reader import FileDataReader
from spinn_storage_handlers.file_data_writer import FileDataWriter

# pacman imports
from spinn_machine.utilities.progress_bar import ProgressBar

import os
import logging
import struct
import tempfile

logger = logging.getLogger(__name__)


class FrontEndCommonHostExecuteDataSpecification(object):
    """ Executes the host based data specification
    """

    __slots__ = []

    def __call__(
            self, hostname, transceiver, report_default_directory,
            write_text_specs, runtime_application_data_folder, machine,
            app_id, dsg_targets):
        """

        :param hostname:
        :param write_text_specs:
        :param runtime_application_data_folder:
        :param machine:
        :return:
        """

        data = self.host_based_data_specification_execution(
            hostname, transceiver, write_text_specs,
            runtime_application_data_folder, machine,
            report_default_directory, app_id, dsg_targets)

        return data

    def host_based_data_specification_execution(
            self, hostname, transceiver, write_text_specs,
            application_data_runtime_folder, machine, report_default_directory,
            app_id, dsg_targets):
        """

        :param hostname:
        :param transceiver:
        :param write_text_specs:
        :param application_data_runtime_folder:
        :param machine:
        :param report_default_directory:
        :param app_id:
        :param dsg_targets:
        :return:
        """
        processor_to_app_data_base_address = dict()

        # create a progress bar for end users
        progress_bar = ProgressBar(
            len(list(dsg_targets)),
            "Executing data specifications and loading data")

        for ((x, y, p), data_spec_file_path) in dsg_targets.iteritems():

            # build specification reader
            data_spec_file_path = dsg_targets[x, y, p]
            data_spec_reader = FileDataReader(data_spec_file_path)

            # build application data writer
            app_data_file_path = self.get_application_data_file_path(
                x, y, p, hostname, application_data_runtime_folder)

            data_writer = FileDataWriter(app_data_file_path)

            # generate a file writer for DSE report (app pointer table)
            report_writer = None
            if write_text_specs:
                new_report_directory = os.path.join(
                    report_default_directory, "data_spec_text_files")

                if not os.path.exists(new_report_directory):
                    os.mkdir(new_report_directory)

                file_name = "{}_DSE_report_for_{}_{}_{}.txt".format(
                    hostname, x, y, p)
                report_file_path = os.path.join(new_report_directory,
                                                file_name)
                report_writer = FileDataWriter(report_file_path)

            # maximum available memory
            # however system updates the memory available
            # independently, so the check on the space available actually
            # happens when memory is allocated
            chip = machine.get_chip_at(x, y)
            memory_available = chip.sdram.size

            # generate data spec executor
            host_based_data_spec_executor = DataSpecificationExecutor(
                data_spec_reader, data_writer, memory_available,
                report_writer)

            # run data spec executor
            try:
                # bytes_used_by_spec, bytes_written_by_spec = \
                host_based_data_spec_executor.execute()
            except exceptions.DataSpecificationException as e:
                logger.error(
                    "Error executing data specification for {}, {}, {}".format(
                        x, y, p))
                raise e

            bytes_used_by_spec = \
                host_based_data_spec_executor.get_constructed_data_size()

            # allocate memory where the app data is going to be written
            # this raises an exception in case there is not enough
            # SDRAM to allocate
            start_address = transceiver.malloc_sdram(
                x, y, bytes_used_by_spec, app_id)

            # the base address address needs to be passed to the DSE to
            # generate the pointer table with absolute addresses
            host_based_data_spec_executor.write_dse_output_file(
                start_address)

            # close the application data file writer
            data_writer.close()

            # the data is written to memory
            file_reader = FileDataReader(app_data_file_path)
            app_data = file_reader.readall()
            bytes_written_by_spec = len(app_data)
            transceiver.write_memory(x, y, start_address, app_data)
            file_reader.close()

            # set user 0 register appropriately to the application data
            user_0_address = \
                transceiver.get_user_0_register_address_from_core(x, y, p)
            start_address_encoded = \
                buffer(struct.pack("<I", start_address))
            transceiver.write_memory(
                x, y, user_0_address, start_address_encoded)

            # write information for the memory map report
            processor_to_app_data_base_address[x, y, p] = {
                'start_address': start_address,
                'memory_used': bytes_used_by_spec,
                'memory_written': bytes_written_by_spec
            }

            # update the progress bar
            progress_bar.update()

        # close the progress bar
        progress_bar.end()
        return processor_to_app_data_base_address, True

    @staticmethod
    def get_application_data_file_path(
            processor_chip_x, processor_chip_y, processor_id, hostname,
            application_run_time_folder):
        """

        :param processor_chip_x:
        :param processor_chip_y:
        :param processor_id:
        :param hostname:
        :param application_run_time_folder:
        :return:
        """

        if application_run_time_folder == "TEMP":
            application_run_time_folder = tempfile.gettempdir()

        application_data_file_name = \
            application_run_time_folder + os.sep + \
            "{}_appData_{}_{}_{}.dat".format(
                hostname, processor_chip_x, processor_chip_y, processor_id)
        return application_data_file_name

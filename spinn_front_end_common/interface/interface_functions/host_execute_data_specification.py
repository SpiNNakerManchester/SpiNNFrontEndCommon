from spinn_utilities.progress_bar import ProgressBar

# data spec imports
from data_specification import DataSpecificationExecutor, constants
from data_specification.exceptions import DataSpecificationException

# spinn_storage_handlers import
from spinn_storage_handlers import FileDataReader

import logging
import struct
import numpy

logger = logging.getLogger(__name__)


class HostExecuteDataSpecification(object):
    """ Executes the host based data specification
    """

    __slots__ = []

    def __call__(self, transceiver, machine, app_id, dsg_targets):
        """

        :param machine: the python representation of the spinnaker machine
        :param transceiver: the spinnman instance
        :param app_id: the application ID of the simulation
        :param dsg_targets: map of placement to file path

        :return: map of placement and dsg data, and loaded data flag.
        """
        processor_to_app_data_base_address = dict()

        # create a progress bar for end users
        progress = ProgressBar(
            dsg_targets, "Executing data specifications and loading data")

        for ((x, y, p), data_spec_file_path) in progress.over(
                dsg_targets.iteritems()):

            # build specification reader
            data_spec_file_path = dsg_targets[x, y, p]
            data_spec_reader = FileDataReader(data_spec_file_path)

            # maximum available memory
            # however system updates the memory available
            # independently, so the check on the space available actually
            # happens when memory is allocated
            chip = machine.get_chip_at(x, y)
            memory_available = chip.sdram.size

            # generate data spec executor
            executor = DataSpecificationExecutor(
                data_spec_reader, memory_available)

            # run data spec executor
            try:
                # bytes_used_by_spec, bytes_written_by_spec = \
                executor.execute()
            except DataSpecificationException as e:
                logger.error(
                    "Error executing data specification for {}, {}, {}".format(
                        x, y, p))
                raise e

            bytes_used_by_spec = executor.get_constructed_data_size()

            # allocate memory where the app data is going to be written
            # this raises an exception in case there is not enough
            # SDRAM to allocate
            start_address = transceiver.malloc_sdram(
                x, y, bytes_used_by_spec, app_id)

            # Write the header and pointer table and load it
            header = executor.get_header()
            pointer_table = executor.get_pointer_table(start_address)
            data_to_write = numpy.concatenate(
                (header, pointer_table)).tostring()
            transceiver.write_memory(x, y, start_address, data_to_write)
            bytes_written_by_spec = len(data_to_write)

            # Write each region
            for region_id in range(constants.MAX_MEM_REGIONS):
                region = executor.get_region(region_id)
                if region is not None:

                    max_pointer = region.max_write_pointer
                    if not region.unfilled and max_pointer > 0:

                        # Get the data up to what has been written
                        data = region.region_data[:max_pointer]

                        # Write the data to the position
                        position = pointer_table[region_id]
                        transceiver.write_memory(x, y, position, data)
                        bytes_written_by_spec += len(data)

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
                'memory_written': bytes_written_by_spec}

        return processor_to_app_data_base_address, True

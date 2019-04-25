from collections import OrderedDict
import logging
import struct
import numpy
from six import iteritems
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter
from data_specification import DataSpecificationExecutor
from data_specification.constants import MAX_MEM_REGIONS
from data_specification.exceptions import DataSpecificationException
from spinn_storage_handlers import FileDataReader
from spinn_front_end_common.utilities.helpful_functions import (
    write_address_to_user0)
from spinn_front_end_common.utilities.utility_objs import (
    ExecutableType, DataWritten)

logger = FormatAdapter(logging.getLogger(__name__))
_ONE_WORD = struct.Struct("<I")
_MEM_REGIONS = range(MAX_MEM_REGIONS)


def system_cores(exec_targets):
    # See https://stackoverflow.com/a/1077205/301832 for why this is
    # backwards and confusing
    return set(
        core
        for binary in exec_targets.get_binaries_of_executable_type(
            ExecutableType.SYSTEM)
        for core in exec_targets.get_cores_for_binary(binary))


def _write_to_spinnaker(txrx, x, y, p, start_address, executor):
    # Write the header and pointer table and load it
    header = executor.get_header()
    pointer_table = executor.get_pointer_table(start_address)
    data_to_write = numpy.concatenate((header, pointer_table)).tostring()
    txrx.write_memory(x, y, start_address, data_to_write)
    bytes_written_by_spec = len(data_to_write)

    # Write each region
    for region_id in _MEM_REGIONS:
        region = executor.get_region(region_id)
        if region is not None:
            max_pointer = region.max_write_pointer
            if not region.unfilled and max_pointer > 0:
                # Get the data up to what has been written
                data = region.region_data[:max_pointer]

                # Write the data to the position
                txrx.write_memory(x, y, pointer_table[region_id], data)
                bytes_written_by_spec += len(data)

    # set user 0 register appropriately to the application data
    write_address_to_user0(txrx, x, y, p, start_address)
    return bytes_written_by_spec


class HostExecuteDataSpecification(object):
    """ Executes the host based data specification.
    """

    __slots__ = []

    def __call__(
            self, transceiver, machine, app_id, dsg_targets,
            processor_to_app_data_base_address=None):
        """ Execute the data specs for all targets.

        :param machine: the python representation of the SpiNNaker machine
        :param transceiver: the spinnman instance
        :param app_id: the application ID of the simulation
        :param dsg_targets: map of placement to file path

        :return: map of placement and DSG data, and loaded data flag.
        """
        # pylint: disable=too-many-arguments
        if processor_to_app_data_base_address is None:
            processor_to_app_data_base_address = dict()

        # create a progress bar for end users
        progress = ProgressBar(
            dsg_targets, "Executing data specifications and loading data")

        for (x, y, p), data_spec_file_path in \
                progress.over(iteritems(dsg_targets)):
            # write information for the memory map report
            processor_to_app_data_base_address[x, y, p] = self._execute(
                transceiver, machine, app_id, x, y, p, data_spec_file_path,
                _write_to_spinnaker)

        return processor_to_app_data_base_address

    def execute_application_data_specs(
            self, transceiver, machine, app_id, dsg_targets,
            uses_advanced_monitors, executable_targets, placements=None,
            extra_monitor_cores=None,
            extra_monitor_to_chip_mapping=None,
            extra_monitor_cores_to_ethernet_connection_map=None,
            processor_to_app_data_base_address=None):
        """ Execute the data specs for all non-system targets.

        :param machine: the python representation of the SpiNNaker machine
        :param transceiver: the spinnman instance
        :param app_id: the application ID of the simulation
        :param dsg_targets: map of placement to file path

        :return: map of placement and DSG data, and loaded data flag.
        """
        # pylint: disable=too-many-arguments
        if processor_to_app_data_base_address is None:
            processor_to_app_data_base_address = dict()

        dsg_targets = self._filter_out_system_executables(
            dsg_targets, executable_targets)

        # create a progress bar for end users
        progress = ProgressBar(
            dsg_targets,
            "Executing data specifications and loading data for "
            "application vertices")

        for (x, y, p), data_spec_file_path in \
                progress.over(iteritems(dsg_targets)):
            # write information for the memory map report
            processor_to_app_data_base_address[x, y, p] = self._execute(
                transceiver, machine, app_id, x, y, p, data_spec_file_path,
                _write_to_spinnaker)

        return processor_to_app_data_base_address

    def execute_system_data_specs(
            self, transceiver, machine, app_id, dsg_targets,
            executable_targets, processor_to_app_data_base_address=None):
        """ Execute the data specs for all system targets.

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
        dsg_targets = self._filter_out_app_executables(
            dsg_targets, executable_targets)

        # create a progress bar for end users
        progress = ProgressBar(
            dsg_targets,
            "Executing data specifications and loading data for system "
            "vertices")

        for (x, y, p), data_spec_file_path in \
                progress.over(iteritems(dsg_targets)):
            # write information for the memory map report
            processor_to_app_data_base_address[x, y, p] = self._execute(
                transceiver, machine, app_id, x, y, p, data_spec_file_path,
                _write_to_spinnaker)
        return processor_to_app_data_base_address

    @staticmethod
    def _execute(txrx, machine, app_id, x, y, p, data_spec_path, writer_func):
        # build specification reader
        reader = FileDataReader(data_spec_path)

        # Maximum available memory.
        # However, system updates the memory available independently, so the
        # space available check actually happens when memory is allocated.
        memory_available = machine.get_chip_at(x, y).sdram.size

        # generate data spec executor
        executor = DataSpecificationExecutor(reader, memory_available)

        # run data spec executor
        try:
            executor.execute()
        except DataSpecificationException:
            logger.error("Error executing data specification for {}, {}, {}",
                         x, y, p)
            raise

        bytes_allocated = executor.get_constructed_data_size()

        # allocate memory where the app data is going to be written; this
        # raises an exception in case there is not enough SDRAM to allocate
        start_address = txrx.malloc_sdram(x, y, bytes_allocated, app_id)

        # Do the actual writing
        bytes_written = writer_func(
            txrx, x, y, p, start_address, executor)

        return DataWritten(start_address, bytes_allocated, bytes_written)

    @staticmethod
    def _filter_out_system_executables(dsg_targets, executable_targets):
        """ Select just the application DSG loading tasks """
        syscores = system_cores(executable_targets)
        return OrderedDict(
            (core, spec) for (core, spec) in iteritems(dsg_targets)
            if core not in syscores)

    @staticmethod
    def _filter_out_app_executables(dsg_targets, executable_targets):
        """ Select just the application DSG loading tasks """
        syscores = system_cores(executable_targets)
        return OrderedDict(
            (core, spec) for (core, spec) in iteritems(dsg_targets)
            if core in syscores)

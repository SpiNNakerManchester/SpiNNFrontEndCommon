import logging
import struct
import numpy
from six import iteritems
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter
from data_specification import DataSpecificationExecutor
from data_specification.constants import MAX_MEM_REGIONS
from data_specification.exceptions import DataSpecificationException
from spinn_front_end_common.interface.ds.ds_write_info import DsWriteInfo
from spinn_front_end_common.utilities.helpful_functions import (
    write_address_to_user0)

logger = FormatAdapter(logging.getLogger(__name__))
_ONE_WORD = struct.Struct("<I")
_MEM_REGIONS = range(MAX_MEM_REGIONS)


class HostExecuteDataSpecification(object):
    """ Executes the host based data specification.
    """

    __slots__ = []

    first = True

    def __call__(
            self, transceiver, machine, app_id, dsg_targets,
            report_folder=None, java_caller=None,
            processor_to_app_data_base_address=None):
        """
        Does the Data Specification Execution and loading

        :param transceiver: the spinnman instance
        :type transceiver: :py:class:`spinnman.transceiver.Transceiver`
        :param machine: the python representation of the SpiNNaker machine
        :type machine: :py:class:`spinn_machine.machine.Machine`
        :param app_id: the application ID of the simulation
        :type app_id: int
        :param dsg_targets: map of placement to file path
        :type dsg_targets: :py:class:`spinn_front_end_common.interface.\
            ds.data_specification_targets.DataSpecificationTargets`
        :param report_folder: The path where
            the SQLite database holding the data will be placed,
            and where any java provenance can be written.
            report_folder can not be None if java_caller is not None.
        :type report_folder: str
        :param java_caller: The support class to run via Java.
            If None pure python is used.
        :type java_caller: :py:class:`spinn_front_end_common.interface.
            java_caller.JavaCaller`
        :param processor_to_app_data_base_address The write info which is a
            dict of cores to a dict of
                'start_address', 'memory_used', 'memory_written
        :return: map of of cores to a dict of
                'start_address', 'memory_used', 'memory_written
            Note: If using python the return type is an actual dict object.
            If using Java the return is a DsWriteInfo
                but this implements the same mapping interface as dict
        :rtype: dict or :py:class:
            `spinn_front_end_common.interface.ds.ds_write_info.DsWriteInfo`
        """
        if java_caller is None:
            return self._python_all_(
                transceiver, machine, app_id, dsg_targets,
                processor_to_app_data_base_address)
        else:
            return self._java_all_(
                machine, app_id, dsg_targets, java_caller,
                report_folder, processor_to_app_data_base_address)

    def _java_all_(
            self, machine, app_id, dsg_targets, java_caller, report_folder,
            processor_to_app_data_base_address):
        """
        Does the Data Specification Execution and loading using Java

        :param machine: the python representation of the SpiNNaker machine
        :type machine: :py:class:`spinn_machine.machine.Machine`
        :param app_id: the application ID of the simulation
        :type app_id: int
        :param dsg_targets: map of placement to file path
        :type dsg_targets: :py:class:`spinn_front_end_common.interface.\
            ds.data_specification_targets.DataSpecificationTargets`
        :param report_folder: The path where
            the SQLite database holding the data will be placed,
            and where any java provenance can be written.
            report_folder can not be None if java_caller is not None.
        :type report_folder: str
        :param java_caller: The support class to run via Java.
            If None pure python is used.
        :type java_caller: :py:class:`spinn_front_end_common.interface.
            java_caller.JavaCaller`
        :param processor_to_app_data_base_address The write info which is a
            dict of cores to a dict of
                'start_address', 'memory_used', 'memory_written
        :return: map of of cores to a dict of
                'start_address', 'memory_used', 'memory_written
        :rtype: spinn_front_end_common.interface.ds.ds_write_info.DsWriteInfo
        """

        # create a progress bar for end users
        progress = ProgressBar(
            3, "Executing data specifications and loading data using Java")

        # Copy data from WriteMemoryIOData to database
        dw_write_info = DsWriteInfo(dsg_targets.get_database())
        dw_write_info.clear_write_info()
        if processor_to_app_data_base_address is not None:
            for core, info in iteritems(processor_to_app_data_base_address):
                dw_write_info[core] = info
        progress.update()
        dsg_targets.set_app_id(app_id)
        java_caller.set_machine(machine)
        java_caller.set_report_folder(report_folder)
        progress.update()
        java_caller.host_execute_data_specification()

        progress.end()
        return dw_write_info

    def _python_all_(
            self, transceiver, machine, app_id, dsg_targets,
            processor_to_app_data_base_address=None):
        """
        Does the Data Specification Execution and loading using python

        :param transceiver: the spinnman instance
        :type transceiver: :py:class:`spinnman.transceiver.Transceiver`
        :param machine: the python representation of the SpiNNaker machine
        :type machine: :py:class:`spinn_machine.machine.Machine`
        :param app_id: the application ID of the simulation
        :type app_id: int
        :param dsg_targets: map of placement to file path
        :type dsg_targets: :py:class:`spinn_front_end_common.interface.\
            ds.data_specification_targets.DataSpecificationTargets`
        :param processor_to_app_data_base_address The write info which is a
            dict of cores to a dict of
                'start_address', 'memory_used', 'memory_written
        :return: dict of cores to a dict of
                'start_address', 'memory_used', 'memory_written
        """
        # While the database supports having the info in it a python bugs does
        # not like iterating over and writing intermingled so using a dict
        if processor_to_app_data_base_address is None:
            processor_to_app_data_base_address = dict()

        # create a progress bar for end users
        progress = ProgressBar(
            dsg_targets.n_targets(),
            "Executing data specifications and loading data")

        for (x, y, p), reader in \
                progress.over(iteritems(dsg_targets)):
            # write information for the memory map report
            info = self._execute(
                transceiver, machine, app_id, x, y, p, reader)
            processor_to_app_data_base_address[x, y, p] = info

        return processor_to_app_data_base_address

    @staticmethod
    def _execute(txrx, machine, app_id, x, y, p, reader):
        # pylint: disable=too-many-arguments, too-many-locals

        # maximum available memory
        # however system updates the memory available
        # independently, so the check on the space available actually
        # happens when memory is allocated

        # generate data spec executor
        executor = DataSpecificationExecutor(
            reader, machine.get_chip_at(x, y).sdram.size)

        # run data spec executor
        try:
            # bytes_used_by_spec, bytes_written_by_spec = \
            executor.execute()
        except DataSpecificationException:
            logger.error("Error executing data specification for {}, {}, {}",
                         x, y, p)
            raise

        bytes_used_by_spec = executor.get_constructed_data_size()

        # allocate memory where the app data is going to be written; this
        # raises an exception in case there is not enough SDRAM to allocate
        start_address = txrx.malloc_sdram(x, y, bytes_used_by_spec, app_id)

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
        return {
            'start_address': start_address,
            'memory_used': bytes_used_by_spec,
            'memory_written': bytes_written_by_spec
        }

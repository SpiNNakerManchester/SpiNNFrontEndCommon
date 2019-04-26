from collections import OrderedDict
import logging
import struct
import numpy
from six import iteritems, itervalues
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


def filter_out_system_executables(dsg_targets, executable_targets):
    """ Select just the application DSG loading tasks """
    syscores = system_cores(executable_targets)
    return OrderedDict(
        (core, spec) for (core, spec) in iteritems(dsg_targets)
        if core not in syscores)


def filter_out_app_executables(dsg_targets, executable_targets):
    """ Select just the application DSG loading tasks """
    syscores = system_cores(executable_targets)
    return OrderedDict(
        (core, spec) for (core, spec) in iteritems(dsg_targets)
        if core in syscores)


class HostExecuteDataSpecification(object):
    """ Executes the host based data specification.
    """

    __slots__ = ["_app_id", "_core_to_conn_map", "_machine", "_monitors",
                 "_placements", "_txrx"]

    def __init__(self):
        self._app_id = None
        self._core_to_conn_map = None
        self._machine = None
        self._monitors = None
        self._placements = None
        self._txrx = None

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
        self._machine = machine
        self._txrx = transceiver
        self._app_id = app_id

        # create a progress bar for end users
        progress = ProgressBar(
            dsg_targets, "Executing data specifications and loading data")

        for core, data_spec_file in progress.over(iteritems(dsg_targets)):
            # write information for the memory map report
            processor_to_app_data_base_address[core] = self.__execute(
                core, data_spec_file, self._txrx.write_memory)

        return processor_to_app_data_base_address

    def execute_application_data_specs(
            self, transceiver, machine, app_id, dsg_targets,
            uses_advanced_monitors, executable_targets, placements=None,
            extra_monitor_cores=None,
            extra_monitor_cores_to_ethernet_connection_map=None,
            processor_to_app_data_base_address=None):
        """ Execute the data specs for all non-system targets.

        :param machine: the python representation of the SpiNNaker machine
        :param transceiver: the spinnman instance
        :param app_id: the application ID of the simulation
        :param dsg_targets: map of placement to file path
        :param uses_advanced_monitors: whether to use fast data in protocol
        :param executable_targets: what core will running what binary
        :param placements: where vertices are located
        :param extra_monitor_cores: the deployed extra monitors, if any
        :param extra_monitor_cores_to_ethernet_connection_map: \
            how to talk to extra monitor cores
        :param processor_to_app_data_base_address: \
            map of placement and DSG data
        :return: map of placement and DSG data
        """
        # pylint: disable=too-many-arguments
        if processor_to_app_data_base_address is None:
            processor_to_app_data_base_address = dict()
        self._machine = machine
        self._txrx = transceiver
        self._app_id = app_id
        self._monitors = extra_monitor_cores
        self._placements = placements
        self._core_to_conn_map = extra_monitor_cores_to_ethernet_connection_map
        dsg_targets = filter_out_system_executables(
            dsg_targets, executable_targets)

        if uses_advanced_monitors:
            receiver = self.__set_router_timeouts()

        # create a progress bar for end users
        progress = ProgressBar(
            dsg_targets,
            "Executing data specifications and loading data for "
            "application vertices")

        for core, data_spec_file in progress.over(iteritems(dsg_targets)):
            x, y, _ = core
            # write information for the memory map report
            processor_to_app_data_base_address[core] = self.__execute(
                core, data_spec_file,
                self.__select_writer(x, y)
                if uses_advanced_monitors else self._txrx.write_memory)

        if uses_advanced_monitors:
            self.__reset_router_timeouts(receiver)
        return processor_to_app_data_base_address

    def __set_router_timeouts(self):
        receiver = next(itervalues(self._core_to_conn_map))
        receiver.set_cores_for_data_streaming(
            self._txrx, self._monitors, self._placements)
        return receiver

    def __reset_router_timeouts(self, receiver):
        # reset router tables
        receiver.set_application_routing_tables(
            self._txrx, self._monitors, self._placements)
        # reset router timeouts
        receiver.unset_cores_for_data_streaming(
            self._txrx, self._monitors, self._placements)

    def __select_writer(self, x, y):
        chip = self._machine.get_chip_at(x, y)
        ethernet_chip = self._machine.get_chip_at(
            chip.nearest_ethernet_x, chip.nearest_ethernet_y)
        gatherer = self._core_to_conn_map[ethernet_chip.x, ethernet_chip.y]
        return gatherer.send_data_into_spinnaker

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

        if processor_to_app_data_base_address is None:
            processor_to_app_data_base_address = dict()
        self._machine = machine
        self._txrx = transceiver
        self._app_id = app_id
        dsg_targets = filter_out_app_executables(
            dsg_targets, executable_targets)

        # create a progress bar for end users
        progress = ProgressBar(
            dsg_targets,
            "Executing data specifications and loading data for system "
            "vertices")

        for core, data_spec_file in progress.over(iteritems(dsg_targets)):
            # write information for the memory map report
            processor_to_app_data_base_address[core] = self.__execute(
                core, data_spec_file, self._txrx.write_memory)
        return processor_to_app_data_base_address

    def __execute(self, core, data_spec_path, writer_func):
        x, y, p = core
        # build specification reader
        reader = FileDataReader(data_spec_path)

        # Maximum available memory.
        # However, system updates the memory available independently, so the
        # space available check actually happens when memory is allocated.
        memory_available = self._machine.get_chip_at(x, y).sdram.size

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
        start_address = self._txrx.malloc_sdram(
            x, y, bytes_allocated, self._app_id)

        # Do the actual writing ------------------------------------

        # Write the header and pointer table
        header = executor.get_header()
        pointer_table = executor.get_pointer_table(start_address)
        data_to_write = numpy.concatenate((header, pointer_table)).tostring()
        # NB: DSE meta-block is always small (i.e., one SDP write)
        self._txrx.write_memory(x, y, start_address, data_to_write)
        bytes_written = len(data_to_write)

        # Write each region
        for region_id in _MEM_REGIONS:
            region = executor.get_region(region_id)
            if region is None:
                continue
            max_pointer = region.max_write_pointer
            if region.unfilled or max_pointer == 0:
                continue

            # Get the data up to what has been written
            data = region.region_data[:max_pointer]

            # Write the data to the position
            writer_func(x, y, pointer_table[region_id], data)
            bytes_written += len(data)

        # set user 0 register appropriately to the application data
        write_address_to_user0(self._txrx, x, y, p, start_address)

        return DataWritten(start_address, bytes_allocated, bytes_written)

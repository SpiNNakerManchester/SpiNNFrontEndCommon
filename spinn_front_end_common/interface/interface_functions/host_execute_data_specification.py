# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from collections import OrderedDict, namedtuple
import logging
import numpy
from spinn_utilities.config_holder import get_config_bool
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter
from spinn_machine import CoreSubsets
from data_specification import DataSpecificationExecutor, MemoryRegionReal
from data_specification.constants import (
    MAX_MEM_REGIONS, APP_PTR_TABLE_BYTE_SIZE)
from data_specification.exceptions import DataSpecificationException
from spinn_front_end_common.interface.ds.ds_write_info import DsWriteInfo
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.helpful_functions import (
    write_address_to_user0)
from spinn_front_end_common.utilities.utility_objs import (
    ExecutableType, DataWritten)
from spinn_front_end_common.utilities.emergency_recovery import (
    emergency_recover_states_from_failure)
from spinn_front_end_common.utilities.constants import CORE_DATA_SDRAM_BASE_TAG

logger = FormatAdapter(logging.getLogger(__name__))
_MEM_REGIONS = range(MAX_MEM_REGIONS)


def system_cores(exec_targets):
    """ Get the subset of cores that are to be used for system operations.

    :param ~spinnman.model.ExecutableTargets exec_targets:
    :rtype: ~spinn_machine.CoreSubsets
    """
    cores = CoreSubsets()
    for binary in exec_targets.get_binaries_of_executable_type(
            ExecutableType.SYSTEM):
        cores.add_core_subsets(exec_targets.get_cores_for_binary(binary))
    return cores


def filter_out_system_executables(dsg_targets, executable_targets):
    """ Select just the application DSG loading tasks

    :param DataSpecificationTargets dsg_tagets:
    :param ~spinnman.model.ExecutableTargets executable_targets:
    :rtype: dict(tuple(int,int,int), ~io.RawIOBase)
    """
    syscores = system_cores(executable_targets)
    return OrderedDict(
        (core, spec) for (core, spec) in dsg_targets.items()
        if core not in syscores)


def filter_out_app_executables(dsg_targets, executable_targets):
    """ Select just the system DSG loading tasks

    :param DataSpecificationTargets dsg_tagets:
    :param ~spinnman.model.ExecutableTargets executable_targets:
    :rtype: dict(tuple(int,int,int), ~io.RawIOBase)
    """
    syscores = system_cores(executable_targets)
    return OrderedDict(
        (core, spec) for (core, spec) in dsg_targets.items()
        if core in syscores)


#: A named tuple for a region that can be referenced
_RegionToRef = namedtuple(
    "__RegionToUse", ["x", "y", "p", "region", "pointer"])


#: A class for regions to be filled in
class _CoreToFill(object):
    __slots__ = [
        "x", "y", "p", "header", "pointer_table", "base_address", "regions"]

    def __init__(self, x, y, p, header, pointer_table, base_address):
        self.x = x
        self.y = y
        self.p = p
        self.header = header
        self.pointer_table = pointer_table
        self.base_address = base_address
        self.regions = []


class _ExecutionContext(object):
    """ A context for executing multiple data specifications with
        cross-references
    """

    def __init__(self):
        self.__references_to_fill = list()
        self.__references_to_use = dict()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Only do the close bit if nothing has gone wrong
        if exc_type is None:
            self.close()
        # Force any exception to be raised
        return False

    def execute(
            self, core, reader, writer_func, base_address, size_allocated):
        """ Execute the data spec for a core
        :param tuple(int,int,int) core:
        :param ~.AbstractDataReader reader:
        :param int base_address:
        :param int size_allocated:
        :rtype: DataWritten
        """
        x, y, p = core

        # Maximum available memory.
        # However, system updates the memory available independently, so the
        # space available check actually happens when memory is allocated.
        memory_available = FecDataView().get_chip_at(x, y).sdram.size

        # generate data spec executor
        executor = DataSpecificationExecutor(reader, memory_available)

        # run data spec executor
        try:
            executor.execute()
        except DataSpecificationException:
            logger.error("Error executing data specification for {}, {}, {}",
                         x, y, p)
            raise

        # Write the header and pointer table
        header = executor.get_header()
        pointer_table = executor.get_pointer_table(base_address)

        # Handle references to the regions from the executor
        self.__handle_new_references(x, y, p, executor, pointer_table)

        # Handle references that need to be filled
        write_header_now = self.__handle_references_to_fill(
            x, y, p, executor, pointer_table, header, base_address)

        # We don't have to write this bit now; we can still to the rest
        if write_header_now:
            # NB: DSE meta-block is always small (i.e., one SDP write)
            to_write = numpy.concatenate((header, pointer_table)).tobytes()
            FecDataView.write_memory(x, y, base_address, to_write)

        # Write each region
        bytes_written = APP_PTR_TABLE_BYTE_SIZE
        for region_id in _MEM_REGIONS:
            region = executor.get_region(region_id)
            if not isinstance(region, MemoryRegionReal):
                continue
            max_pointer = region.max_write_pointer
            if region.unfilled or max_pointer == 0:
                continue

            # Get the data up to what has been written
            data = region.region_data[:max_pointer]

            # Write the data to the position
            writer_func(x, y, pointer_table[region_id], data)
            bytes_written += len(data)

        return DataWritten(base_address, size_allocated, bytes_written)

    def close(self):
        """ Called when finished executing all regions.  Fills in the
            references if possible, and fails if not
        """
        for core_to_fill in self.__references_to_fill:
            pointer_table = core_to_fill.pointer_table
            for ref_region, ref in core_to_fill.regions:
                if ref not in self.__references_to_use:
                    raise ValueError(
                        "Reference {} requested from {} but not found"
                        .format(ref, core_to_fill))
                pointer_table[ref_region] = self.__get_reference(
                    ref, core_to_fill.x, core_to_fill.y, core_to_fill.p,
                    ref_region)
            to_write = numpy.concatenate(
                (core_to_fill.header, pointer_table)).tobytes()
            FecDataView.write_memory(
                core_to_fill.x, core_to_fill.y, core_to_fill.base_address,
                to_write)

    def __handle_new_references(self, x, y, p, executor, pointer_table):
        """ Get references that can be used later

        :param int x: The x-coordinate of the spec being executed
        :param int y: The y-coordinate of the spec being executed
        :param int p: The core of the spec being executed
        :param ~DataSpecificationExecutor executor:
            The execution context
        :param list(int) pointer_table:
            A table of pointers that could be referenced later
        """
        for ref_region in executor.referenceable_regions:
            ref = executor.get_region(ref_region).reference
            if ref in self.__references_to_use:
                ref_to_use = self.__references_to_use[ref]
                raise ValueError(
                    "Reference {} used previously as {} so cannot be used by"
                    " {}, {}, {}, {}".format(
                        ref, ref_to_use, x, y, p, ref_region))
            ptr = pointer_table[ref_region]
            self.__references_to_use[ref] = _RegionToRef(
                x, y, p, ref_region, ptr)

    def __handle_references_to_fill(
            self, x, y, p, executor, pointer_table, header, base_address):
        """ Resolve references

        :param int x: The x-coordinate of the spec being executed
        :param int y: The y-coordinate of the spec being executed
        :param int p: The core of the spec being executed
        :param ~DataSpecificationExecutor executor:
            The execution context
        :param list(int) pointer_table:
            A table of pointers that could be referenced later
        :param header: The Data Specification header bytes
        :param base_address: The base address of the executed spec
        :return: Whether all references were resolved
        """
        # Resolve any references now
        coreToFill = _CoreToFill(x, y, p, header, pointer_table, base_address)
        for ref_region in executor.references_to_fill:
            ref = executor.get_region(ref_region).ref
            # If already been created, use directly
            if ref in self.__references_to_use:
                pointer_table[ref_region] = self.__get_reference(
                    ref, x, y, p, ref_region)
            else:
                coreToFill.regions.append((ref_region, ref))
        if coreToFill.regions:
            self.__references_to_fill.append(coreToFill)
        return not bool(coreToFill.regions)

    def __get_reference(self, ref, x, y, p, ref_region):
        """ Get a reference to a region, doing some extra checks on eligibility

        :param int ref: The reference to the region
        :param int x: The x-coordinate of the executing spec
        :param int y: The y-coordinate of the executing spec
        :param int p: The core of the executing spec
        :param .CoreToFill ref_region: Data related to the reference
        :return: The pointer to use
        :raise ValueError: if the reference cannot be referenced in this
                            context
        """
        ref_to_use = self.__references_to_use[ref]
        if ref_to_use.x != x or ref_to_use.y != y:
            raise ValueError(
                "Reference {} to {} cannot be used by {}, {}, {}, {}"
                " because they are on different chips".format(
                    ref, ref_to_use, x, y, p, ref_region))
        return ref_to_use.pointer


def execute_system_data_specs(
        dsg_targets, region_sizes,
        executable_targets,
        processor_to_app_data_base_address=None):
    """ Execute the data specs for all system targets.

    :param dict(tuple(int,int,int),str) dsg_targets:
        map of placement to file path
    :param dict(tuple(int,int,int),int) region_sizes:
        the coordinates for region sizes for each core
    :param ~spinnman.model.ExecutableTargets executable_targets:
        the map between binaries and locations and executable types
    :param processor_to_app_data_base_address:
    :type processor_to_app_data_base_address:
        dict(tuple(int,int,int),DataWritten)
    :return: map of placement and DSG data, and loaded data flag.
    :rtype: dict(tuple(int,int,int),DataWritten) or DsWriteInfo
    """
    specifier = _HostExecuteDataSpecification(
        processor_to_app_data_base_address)
    return specifier.execute_system_data_specs(
        dsg_targets, region_sizes, executable_targets)


def execute_application_data_specs(
        dsg_targets, executable_targets, region_sizes,
        extra_monitor_cores=None,
        extra_monitor_cores_to_ethernet_connection_map=None,
        processor_to_app_data_base_address=None):
    """ Execute the data specs for all non-system targets.

    :param dict(tuple(int,int,int),int) region_sizes:
        the coord for region sizes for each core
    :param DataSpecificationTargets dsg_targets:
        map of placement to file path
    :param bool uses_advanced_monitors:
        whether to use fast data in protocol
    :param ~spinnman.model.ExecutableTargets executable_targets:
        what core will running what binary
    :param list(ExtraMonitorSupportMachineVertex) extra_monitor_cores:
        the deployed extra monitors, if any
    :param extra_monitor_cores_to_ethernet_connection_map:
        how to talk to extra monitor cores
    :type extra_monitor_cores_to_ethernet_connection_map:
        dict(tuple(int,int), DataSpeedUpPacketGatherMachineVertex)
    :param processor_to_app_data_base_address:
        map of placement and DSG data
    :type processor_to_app_data_base_address:
        dict(tuple(int,int,int), DsWriteInfo)
    :return: map of placement and DSG data
    :rtype: dict(tuple(int,int,int),DataWritten) or DsWriteInfo
    """
    specifier = _HostExecuteDataSpecification(
        processor_to_app_data_base_address)
    return specifier.execute_application_data_specs(
        dsg_targets, executable_targets, region_sizes,
        extra_monitor_cores, extra_monitor_cores_to_ethernet_connection_map)


class _HostExecuteDataSpecification(object):
    """ Executes the host based data specification.
    """

    __slots__ = [
        # the application ID of the simulation
        "_app_id",
        "_core_to_conn_map",
        "_monitors",
        # The write info; a dict of cores to a dict of
        # 'start_address', 'memory_used', 'memory_written'
        "_write_info_map"]

    first = True

    def __init__(self, processor_to_app_data_base_address):
        """
        :param processor_to_app_data_base_address:
            map of placement and DSG data
        """
        self._app_id = FecDataView.get_app_id()
        self._core_to_conn_map = None
        self._monitors = None
        if processor_to_app_data_base_address:
            self._write_info_map = processor_to_app_data_base_address
        else:
            self._write_info_map = dict()

    def __java_database(self, dsg_targets, progress, region_sizes):
        """
        :param DataSpecificationTargets dsg_tagets:
        :param ~spinn_utilities.progress_bar.ProgressBar progress:
        :param dict(tuple(int,int,int)int) region_sizes:
        :rtype: DsWriteInfo
        """
        # Copy data from WriteMemoryIOData to database
        dw_write_info = DsWriteInfo(dsg_targets.get_database())
        dw_write_info.clear_write_info()
        if self._write_info_map is not None:
            for core, info in self._write_info_map.items():
                (x, y, p) = core
                dw_write_info.set_info(x, y, p, info)
                del region_sizes[core]
        for core in region_sizes:
            (x, y, p) = core
            dw_write_info.set_size_info(x, y, p, region_sizes[core])
        progress.update()
        dsg_targets.set_app_id(self._app_id)
        progress.update()
        return dw_write_info

    def __java_all(self, dsg_targets, region_sizes):
        """ Does the Data Specification Execution and loading using Java

        :param DataSpecificationTargets dsg_targets:
            map of placement to file path
        :return: map of of cores to descriptions of what was written
        :rtype: DsWriteInfo
        """
        # create a progress bar for end users
        progress = ProgressBar(
            3, "Executing data specifications and loading data using Java")

        # Copy data from WriteMemoryIOData to database
        dw_write_info = self.__java_database(
            dsg_targets, progress, region_sizes)

        FecDataView.get_java_caller().execute_data_specification()

        progress.end()
        return dw_write_info

    def __python_all(self, dsg_targets, region_sizes):
        """ Does the Data Specification Execution and loading using Python

        :param DataSpecificationTargets dsg_targets:
            map of placement to file path
        :param dict(tuple(int,int,int),int) region_sizes:
            map between vertex and list of region sizes
        :return: dict of cores to descriptions of what was written
        :rtype: dict(tuple(int,int,int), DataWritten)
        """
        # While the database supports having the info in it a python bugs does
        # not like iterating over and writing intermingled so using a dict
        results = self._write_info_map
        if results is None:
            results = dict()

        # create a progress bar for end users
        progress = ProgressBar(
            dsg_targets.n_targets(),
            "Executing data specifications and loading data")

        # allocate and set user 0 before loading data
        base_addresses = dict()
        for core, _ in dsg_targets.items():
            base_addresses[core] = self.__malloc_region_storage(
                core, region_sizes[core])

        with _ExecutionContext() as context:
            transceiver = FecDataView.get_transceiver()
            for core, reader in progress.over(dsg_targets.items()):
                results[core] = context.execute(
                    core, reader, transceiver.write_memory,
                    base_addresses[core], region_sizes[core])

        return results

    def execute_application_data_specs(
            self, dsg_targets,
            executable_targets, region_sizes,
            extra_monitor_cores=None,
            extra_monitor_cores_to_ethernet_connection_map=None):
        """ Execute the data specs for all non-system targets.

        :param dict(tuple(int,int,int),int) region_sizes:
            the coord for region sizes for each core
        :param DataSpecificationTargets dsg_targets:
            map of placement to file path
        :param bool uses_advanced_monitors:
            whether to use fast data in protocol
        :param ~spinnman.model.ExecutableTargets executable_targets:
            what core will running what binary
        :param list(ExtraMonitorSupportMachineVertex) extra_monitor_cores:
            the deployed extra monitors, if any
        :param extra_monitor_cores_to_ethernet_connection_map:
            how to talk to extra monitor cores
        :type extra_monitor_cores_to_ethernet_connection_map:
            dict(tuple(int,int), DataSpeedUpPacketGatherMachineVertex)
        :return: map of placement and DSG data
        :rtype: dict(tuple(int,int,int),DataWritten) or DsWriteInfo
        """
        # pylint: disable=too-many-arguments
        self._monitors = extra_monitor_cores
        self._core_to_conn_map = extra_monitor_cores_to_ethernet_connection_map

        uses_advanced_monitors = get_config_bool(
            "Machine", "enable_advanced_monitor_support")
        # Allow config to override
        if get_config_bool(
                "Machine", "disable_advanced_monitor_usage_for_data_in"):
            uses_advanced_monitors = False

        try:
            if FecDataView.has_java_caller():
                return self.__java_app(dsg_targets, executable_targets,
                                       uses_advanced_monitors, region_sizes)
            else:
                return self.__python_app(dsg_targets, executable_targets,
                                         uses_advanced_monitors, region_sizes)
        except:  # noqa: E722
            if uses_advanced_monitors:
                emergency_recover_states_from_failure(executable_targets)
            raise

    def __set_router_timeouts(self):
        for receiver in self._core_to_conn_map.values():
            receiver.load_system_routing_tables(self._monitors)
            receiver.set_cores_for_data_streaming(self._monitors)

    def __reset_router_timeouts(self):
        # reset router timeouts
        for receiver in self._core_to_conn_map.values():
            receiver.unset_cores_for_data_streaming(
                self._monitors)
            # reset router tables
            receiver.load_application_routing_tables(self._monitors)

    def __select_writer(self, x, y):
        view = FecDataView()
        chip = view.get_chip_at(x, y)
        ethernet_chip = view.get_chip_at(
            chip.nearest_ethernet_x, chip.nearest_ethernet_y)
        gatherer = self._core_to_conn_map[ethernet_chip.x, ethernet_chip.y]
        return gatherer.send_data_into_spinnaker

    def __python_app(
            self, dsg_targets, executable_targets, use_monitors,
            region_sizes):
        """
        :param DataSpecificationTargets dsg_targets:
        :param ~spinnman.model.ExecutableTargets executable_targets:
        :param bool use_monitors:
        :param dict(tuple(int,int,int),int) region_sizes:
        :return: dict of cores to descriptions of what was written
        :rtype: dict(tuple(int,int,int),DataWritten)
        """
        dsg_targets = filter_out_system_executables(
            dsg_targets, executable_targets)

        if use_monitors:
            self.__set_router_timeouts()

        # create a progress bar for end users
        progress = ProgressBar(
            len(dsg_targets) * 2,
            "Executing data specifications and loading data for "
            "application vertices")

        # allocate and set user 0 before loading data
        base_addresses = dict()
        for core, _ in progress.over(dsg_targets.items(), finish_at_end=False):
            base_addresses[core] = self.__malloc_region_storage(
                core, region_sizes[core])

        with _ExecutionContext() as context:
            transceiver = FecDataView.get_transceiver()
            for core, reader in progress.over(dsg_targets.items()):
                x, y, _p = core
                # write information for the memory map report
                self._write_info_map[core] = context.execute(
                    core, reader,
                    self.__select_writer(x, y)
                    if use_monitors else transceiver.write_memory,
                    base_addresses[core], region_sizes[core])

        if use_monitors:
            self.__reset_router_timeouts()
        return self._write_info_map

    def __java_app(
            self, dsg_targets, executable_targets, use_monitors,
            region_sizes):
        """
        :param DataSpecificationTargets dsg_targets:
        :param ~spinnman.model.ExecutableTargets executable_targets:
        :param bool use_monitors:
        :param dict(tuple(int,int,int),int) region_sizes:
        :return: map of cores to descriptions of what was written
        :rtype: DsWriteInfo
        """
        # create a progress bar for end users
        progress = ProgressBar(
            4, "Executing data specifications and loading data for "
            "application vertices using Java")

        dsg_targets.mark_system_cores(system_cores(executable_targets))
        progress.update()

        # Copy data from WriteMemoryIOData to database
        dw_write_info = self.__java_database(
            dsg_targets, progress, region_sizes)
        java_caller = FecDataView.get_java_caller()
        if use_monitors:
            # Method also called with just recording params
            java_caller.set_placements(FecDataView.get_placements())

        java_caller.execute_app_data_specification(use_monitors)

        progress.end()
        return dw_write_info

    def execute_system_data_specs(
            self, dsg_targets, region_sizes,
            executable_targets,
            processor_to_app_data_base_address=None):
        """ Execute the data specs for all system targets.

        :param dict(tuple(int,int,int),str) dsg_targets:
            map of placement to file path
        :param dict(tuple(int,int,int),int) region_sizes:
            the coordinates for region sizes for each core
        :param ~spinnman.model.ExecutableTargets executable_targets:
            the map between binaries and locations and executable types
        :param processor_to_app_data_base_address:
        :type processor_to_app_data_base_address:
            dict(tuple(int,int,int),DataWritten)
        :return: map of placement and DSG data, and loaded data flag.
        :rtype: dict(tuple(int,int,int),DataWritten) or DsWriteInfo
        """
        # pylint: disable=too-many-arguments

        if FecDataView.has_java_caller():
            self.__java_sys(dsg_targets, executable_targets, region_sizes)
        else:
            self.__python_sys(dsg_targets, executable_targets, region_sizes)

    def __java_sys(self, dsg_targets, executable_targets, region_sizes):
        """ Does the Data Specification Execution and loading using Java

        :param DataSpecificationTargets dsg_targets:
            map of placement to file path
        :param ~spinnman.model.ExecutableTargets executable_targets:
            the map between binaries and locations and executable types
        :param dict(tuple(int,int,int),int) region_sizes:
            the coord for region sizes for each core
        :return: map of cores to descriptions of what was written
        :rtype: DsWriteInfo
        """
        # create a progress bar for end users
        progress = ProgressBar(
            4, "Executing data specifications and loading data for system "
            "vertices using Java")

        dsg_targets.mark_system_cores(system_cores(executable_targets))
        progress.update()

        # Copy data from WriteMemoryIOData to database
        dw_write_info = self.__java_database(
            dsg_targets, progress, region_sizes)

        FecDataView.get_java_caller().execute_system_data_specification()

        progress.end()
        return dw_write_info

    def __python_sys(self, dsg_targets, executable_targets, region_sizes):
        """ Does the Data Specification Execution and loading using Python

        :param DataSpecificationTargets dsg_targets:
            map of placement to file path
        :param ~spinnman.model.ExecutableTargets executable_targets:
            the map between binaries and locations and executable types
        :param dict(tuple(int,int,int),int) region_sizes:
            the coord for region sizes for each core
        :return: dict of cores to descriptions of what was written
        :rtype: dict(tuple(int,int,int),DataWritten)
        """
        # While the database supports having the info in it a python bugs does
        # not like iterating over and writing intermingled so using a dict
        sys_targets = filter_out_app_executables(
            dsg_targets, executable_targets)

        # create a progress bar for end users
        progress = ProgressBar(
            len(sys_targets) * 2,
            "Executing data specifications and loading data for "
            "system vertices")

        # allocate and set user 0 before loading data
        base_addresses = dict()
        for core, _ in progress.over(sys_targets.items(), finish_at_end=False):
            base_addresses[core] = self.__malloc_region_storage(
                core, region_sizes[core])

        with _ExecutionContext() as context:
            transceiver = FecDataView.get_transceiver()
            for core, reader in progress.over(sys_targets.items()):
                self._write_info_map[core] = context.execute(
                    core, reader, transceiver.write_memory,
                    base_addresses[core], region_sizes[core])

        return self._write_info_map

    def __malloc_region_storage(self, core, size):
        """ Allocates the storage for all DSG regions on the core and tells \
            the core and our caller where that storage is.

        :param tuple(int,int,int) core: Which core we're talking about.
        :param int size:
            The total size of all storage for regions on that core, including
            for the header metadata.
        :return: address of region header table (not yet filled)
        :rtype: int
        """
        (x, y, p) = core

        # allocate memory where the app data is going to be written; this
        # raises an exception in case there is not enough SDRAM to allocate
        start_address = FecDataView.get_transceiver().malloc_sdram(
            x, y, size, self._app_id, tag=CORE_DATA_SDRAM_BASE_TAG + p)

        # set user 0 register appropriately to the application data
        write_address_to_user0(x, y, p, start_address)

        return start_address

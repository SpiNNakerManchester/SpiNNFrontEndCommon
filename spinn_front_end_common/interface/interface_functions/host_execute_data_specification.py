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

from collections import namedtuple
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
from spinn_front_end_common.utilities.helpful_functions import (
    write_address_to_user0)
from spinn_front_end_common.utilities.utility_objs import ExecutableType
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

    def __init__(self, txrx, machine):
        self.__txrx = txrx
        self.__machine = machine
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
        :param callable(tuple(int,int,int,bytearray),None) writer_func:
        :param int base_address:
        :param int size_allocated:
        :return: base_address, size_allocated, bytes_written
        :rtype: tuple(int, int, int)
        """
        x, y, p = core

        # Maximum available memory.
        # However, system updates the memory available independently, so the
        # space available check actually happens when memory is allocated.
        memory_available = self.__machine.get_chip_at(x, y).sdram.size

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
            self.__txrx.write_memory(x, y, base_address, to_write)

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

        return base_address, size_allocated, bytes_written

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
            self.__txrx.write_memory(core_to_fill.x, core_to_fill.y,
                                     core_to_fill.base_address, to_write)

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
        transceiver, machine, app_id, dsg_targets,
        executable_targets,  java_caller=None):
    """ Execute the data specs for all system targets.

    :param ~spinnman.transceiver.Transceiver transceiver:
        the spinnman instance
    :param ~spinn_machine.Machine machine:
        the python representation of the spinnaker machine
    :param int app_id: the application ID of the simulation
    :param dict(tuple(int,int,int),str) dsg_targets:
        map of placement to file path
    :param ~spinnman.model.ExecutableTargets executable_targets:
        the map between binaries and locations and executable types
    :param JavaCaller java_caller:
    """
    specifier = _HostExecuteDataSpecification(
        transceiver, machine, app_id, java_caller)
    specifier.execute_system_data_specs(dsg_targets, executable_targets)


def execute_application_data_specs(
        transceiver, machine, app_id, dsg_targets,
        executable_targets, placements=None, extra_monitor_cores=None,
        extra_monitor_cores_to_ethernet_connection_map=None,
        java_caller=None):
    """ Execute the data specs for all non-system targets.

    :param ~spinn_machine.Machine machine:
        the python representation of the SpiNNaker machine
    :param ~spinnman.transceiver.Transceiver transceiver:
        the spinnman instance
    :param int app_id: the application ID of the simulation
    :param DataSpecificationTargets dsg_targets:
        map of placement to file path
    :param bool uses_advanced_monitors:
        whether to use fast data in protocol
    :param ~spinnman.model.ExecutableTargets executable_targets:
        what core will running what binary
    :param ~pacman.model.placements.Placements placements:
        where vertices are located
    :param list(ExtraMonitorSupportMachineVertex) extra_monitor_cores:
        the deployed extra monitors, if any
    :param extra_monitor_cores_to_ethernet_connection_map:
        how to talk to extra monitor cores
    :type extra_monitor_cores_to_ethernet_connection_map:
        dict(tuple(int,int), DataSpeedUpPacketGatherMachineVertex)
    """
    specifier = _HostExecuteDataSpecification(
        transceiver, machine, app_id, java_caller)
    specifier.execute_application_data_specs(
        dsg_targets, executable_targets, placements,
        extra_monitor_cores, extra_monitor_cores_to_ethernet_connection_map)


class _HostExecuteDataSpecification(object):
    """ Executes the host based data specification.
    """

    __slots__ = [
        # the application ID of the simulation
        "_app_id",
        "_core_to_conn_map",
        # The support class to run via Java. If None pure python is used.
        "_java",
        # The python representation of the SpiNNaker machine.
        "_machine",
        "_monitors",
        "_placements",
        # The spinnman instance.
        "_txrx"]

    first = True

    def __init__(self, transceiver, machine, app_id, java_caller):
        """
        :param ~spinnman.transceiver.Transceiver transceiver:
            the spinnman instance
        :param ~spinn_machine.Machine machine:
            the python representation of the spinnaker machine
        :param int app_id: the application ID of the simulation
        :param JavaCaller java_caller:
        """
        self._app_id = app_id
        self._core_to_conn_map = None
        self._java = java_caller
        self._machine = machine
        self._monitors = None
        self._placements = None
        self._txrx = transceiver

    def __java_all(self, dsg_targets):
        """ Does the Data Specification Execution and loading using Java

        :param DataSpecificationTargets dsg_targets:
            map of placement to file path
        """
        # create a progress bar for end users
        progress = ProgressBar(
            2, "Executing data specifications and loading data using Java")

        self._java.set_machine(self._machine)
        progress.update()
        self._java.execute_data_specification()

        progress.end()

    def execute_application_data_specs(
            self, dsg_targets, executable_targets,
            placements=None, extra_monitor_cores=None,
            extra_monitor_cores_to_ethernet_connection_map=None):
        """ Execute the data specs for all non-system targets.

        :param DataSpecificationTargets dsg_targets:
            map of placement to file path
        :param bool uses_advanced_monitors:
            whether to use fast data in protocol
        :param ~spinnman.model.ExecutableTargets executable_targets:
            what core will running what binary
        :param ~pacman.model.placements.Placements placements:
            where vertices are located
        :param extra_monitor_cores:
            the deployed extra monitors, if any
        :type extra_monitor_cores:
            dict(tuple(int,int),ExtraMonitorSupportMachineVertex))
        :param extra_monitor_cores_to_ethernet_connection_map:
            how to talk to extra monitor cores
        :type extra_monitor_cores_to_ethernet_connection_map:
            dict(tuple(int,int), DataSpeedUpPacketGatherMachineVertex)
        """
        # pylint: disable=too-many-arguments
        self._monitors = extra_monitor_cores
        self._placements = placements
        self._core_to_conn_map = extra_monitor_cores_to_ethernet_connection_map

        uses_advanced_monitors = get_config_bool(
            "Machine", "enable_advanced_monitor_support")
        # Allow config to override
        if get_config_bool(
                "Machine", "disable_advanced_monitor_usage_for_data_in"):
            uses_advanced_monitors = False

        impl_method = self.__java_app if self._java else self.__python_app
        try:
            impl_method(dsg_targets, uses_advanced_monitors)
        except:  # noqa: E722
            if uses_advanced_monitors:
                emergency_recover_states_from_failure(
                    self._txrx, self._app_id, executable_targets)
            raise

    def __set_router_timeouts(self):
        for receiver in self._core_to_conn_map.values():
            receiver.load_system_routing_tables(
                self._txrx, self._monitors, self._placements)
            receiver.set_cores_for_data_streaming(
                self._txrx, self._monitors, self._placements)

    def __reset_router_timeouts(self):
        # reset router timeouts
        for receiver in self._core_to_conn_map.values():
            receiver.unset_cores_for_data_streaming(
                self._txrx, self._monitors, self._placements)
            # reset router tables
            receiver.load_application_routing_tables(
                self._txrx, self._monitors, self._placements)

    def __select_writer(self, x, y):
        chip = self._machine.get_chip_at(x, y)
        ethernet_chip = self._machine.get_chip_at(
            chip.nearest_ethernet_x, chip.nearest_ethernet_y)
        gatherer = self._core_to_conn_map[ethernet_chip.x, ethernet_chip.y]
        return gatherer.send_data_into_spinnaker

    def __python_app(self, dsg_targets, use_monitors):
        """
        :param DataSpecificationTargets dsg_targets:
        :param bool use_monitors:
        """
        if use_monitors:
            self.__set_router_timeouts()

        # create a progress bar for end users
        progress = ProgressBar(
            dsg_targets.ds_n_app_cores(),
            "Executing data specifications and loading data for "
            "application vertices")

        # allocate and set user 0 before loading data
        base_addresses = dict()

        with _ExecutionContext(self._txrx, self._machine) as context:
            for core, reader, region_size in progress.over(
                    dsg_targets.app_items()):
                x, y, p = core
                base_addresses[core] = self.__malloc_region_storage(
                    core, region_size)
                # write information for the memory map report
                base_address, size_allocated, bytes_written = context.execute(
                    core, reader,
                    self.__select_writer(x, y)
                    if use_monitors else self._txrx.write_memory,
                    base_addresses[core], region_size)
                dsg_targets.set_write_info(
                    x, y, p, base_address, size_allocated, bytes_written)

        if use_monitors:
            self.__reset_router_timeouts()

    def __java_app(self, dsg_targets, use_monitors):
        """
        :param DataSpecificationTargets dsg_targets:
        :param bool use_monitors:
        """
        # create a progress bar for end users
        progress = ProgressBar(
            4, "Executing data specifications and loading data for "
            "application vertices using Java")

        progress.update()

        self._java.set_machine(self._machine)
        progress.update()
        if use_monitors:
            self._java.set_placements(self._placements, self._txrx)

        self._java.execute_app_data_specification(use_monitors)

        progress.end()

    def execute_system_data_specs(self, dsg_targets, executable_targets):
        """ Execute the data specs for all system targets.

        :param dict(tuple(int,int,int),str) dsg_targets:
            map of placement to file path
        :param ~spinnman.model.ExecutableTargets executable_targets:
            the map between binaries and locations and executable types
        """
        # pylint: disable=too-many-arguments

        dsg_targets.mark_system_cores(system_cores(executable_targets))
        impl_method = self.__java_sys if self._java else self.__python_sys
        impl_method(dsg_targets)

    def __java_sys(self, dsg_targets):
        """ Does the Data Specification Execution and loading using Java

        :param DataSpecificationTargets dsg_targets:
            map of placement to file path
        """
        # create a progress bar for end users
        progress = ProgressBar(
            4, "Executing data specifications and loading data for system "
            "vertices using Java")

        progress.update()

        self._java.set_machine(self._machine)
        progress.update()

        self._java.execute_system_data_specification()

        progress.end()

    def __python_sys(self, dsg_targets):
        """ Does the Data Specification Execution and loading using Python

        :param DataSpecificationTargets dsg_targets:
            map of placement to file path
        """
        progress = ProgressBar(
            dsg_targets.ds_n_system_cores(),
            "Executing data specifications and loading data for "
            "system vertices")

        # allocate and set user 0 before loading data
        base_addresses = dict()

        with _ExecutionContext(self._txrx, self._machine) as context:
            for core, reader, region_size in progress.over(
                    dsg_targets.system_items()):
                x, y, p = core
                base_addresses[core] = self.__malloc_region_storage(
                    core, region_size)
                base_address, size_allocated, bytes_written = context.execute(
                    core, reader, self._txrx.write_memory,
                    base_addresses[core], region_size)
                dsg_targets.set_write_info(
                    x, y, p, base_address, size_allocated, bytes_written)

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
        start_address = self._txrx.malloc_sdram(
            x, y, size, self._app_id, tag=CORE_DATA_SDRAM_BASE_TAG + p)

        # set user 0 register appropriately to the application data
        write_address_to_user0(self._txrx, x, y, p, start_address)

        return start_address

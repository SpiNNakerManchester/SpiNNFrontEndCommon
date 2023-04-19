# Copyright (c) 2015 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.helpful_functions import (
    write_address_to_user0)
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.utilities.emergency_recovery import (
    emergency_recover_states_from_failure)
from spinn_front_end_common.utilities.constants import CORE_DATA_SDRAM_BASE_TAG

logger = FormatAdapter(logging.getLogger(__name__))
_MEM_REGIONS = range(MAX_MEM_REGIONS)


def system_cores():
    """
    Get the subset of cores that are to be used for system operations.

    :rtype: ~spinn_machine.CoreSubsets
    """
    cores = CoreSubsets()
    exec_targets = FecDataView.get_executable_targets()
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
    """
    A context for executing multiple data specifications with
    cross-references.
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
        """
        Execute the data spec for a core.

        :param tuple(int,int,int) core:
        :param ~io.RawIOBase reader:
        :param int base_address:
        :param int size_allocated:
        :return: base_address, size_allocated, bytes_written
        :rtype: tuple(int, int, int)
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

            to_write = numpy.concatenate(
                (header, pointer_table.view("uint32"))).tobytes()
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
            writer_func(x, y, pointer_table[region_id]["pointer"], data)
            bytes_written += len(data)

        return base_address, size_allocated, bytes_written

    def close(self):
        """
        Called when finished executing all regions.  Fills in the
        references if possible, and fails if not.
        """
        for core_to_fill in self.__references_to_fill:
            pointer_table = core_to_fill.pointer_table
            for ref_region, ref in core_to_fill.regions:
                if ref not in self.__references_to_use:
                    raise ValueError(
                        f"Reference {ref} requested from {core_to_fill} "
                        "but not found")
                pointer_table[ref_region]["pointer"] = self.__get_reference(
                    ref, core_to_fill.x, core_to_fill.y, core_to_fill.p,
                    ref_region)
            to_write = numpy.concatenate(
                (core_to_fill.header, pointer_table.view("uint32"))).tobytes()
            FecDataView.write_memory(
                core_to_fill.x, core_to_fill.y, core_to_fill.base_address,
                to_write)

    def __handle_new_references(self, x, y, p, executor, pointer_table):
        """
        Get references that can be used later.

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
                    f"Reference {ref} used previously as {ref_to_use} so "
                    f"cannot be used by {x}, {y}, {p}, {ref_region}")
            ptr = pointer_table[ref_region]["pointer"]
            self.__references_to_use[ref] = _RegionToRef(
                x, y, p, ref_region, ptr)

    def __handle_references_to_fill(
            self, x, y, p, executor, pointer_table, header, base_address):
        """
        Resolve references.

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
                pointer_table[ref_region]["pointer"] = self.__get_reference(
                    ref, x, y, p, ref_region)
            else:
                coreToFill.regions.append((ref_region, ref))
        if coreToFill.regions:
            self.__references_to_fill.append(coreToFill)
        return not bool(coreToFill.regions)

    def __get_reference(self, ref, x, y, p, ref_region):
        """
        Get a reference to a region, doing some extra checks on eligibility.

        :param int ref: The reference to the region
        :param int x: The x-coordinate of the executing spec
        :param int y: The y-coordinate of the executing spec
        :param int p: The core of the executing spec
        :param .CoreToFill ref_region: Data related to the reference
        :return: The pointer to use
        :raise ValueError:
            if the reference cannot be referenced in this context
        """
        ref_to_use = self.__references_to_use[ref]
        if ref_to_use.x != x or ref_to_use.y != y:
            raise ValueError(
                f"Reference {ref} to {ref_to_use} cannot be used by "
                f"{x}, {y}, {p}, {ref_region} because they are on "
                "different chips")
        return ref_to_use.pointer


def execute_system_data_specs():
    """
    Execute the data specs for all system targets.
    """
    specifier = _HostExecuteDataSpecification()
    return specifier.execute_system_data_specs()


def execute_application_data_specs():
    """
    Execute the data specs for all non-system targets.
    """
    specifier = _HostExecuteDataSpecification()
    specifier.execute_application_data_specs()


class _HostExecuteDataSpecification(object):
    """
    Executes the host based data specification.
    """

    __slots__ = [
        # the application ID of the simulation
        "_app_id"]

    first = True

    def __init__(self):
        self._app_id = FecDataView.get_app_id()

    def execute_application_data_specs(self):
        """
        Execute the data specs for all non-system targets.
        """

        uses_advanced_monitors = get_config_bool(
            "Machine", "enable_advanced_monitor_support")
        # Allow config to override
        if get_config_bool(
                "Machine", "disable_advanced_monitor_usage_for_data_in"):
            uses_advanced_monitors = False
        try:
            if FecDataView.has_java_caller():
                return self.__java_app(uses_advanced_monitors)
            else:
                return self.__python_app(uses_advanced_monitors)
        except:  # noqa: E722
            if uses_advanced_monitors:
                emergency_recover_states_from_failure()
            raise

    def __set_router_timeouts(self):
        for receiver in FecDataView.iterate_gathers():
            receiver.load_system_routing_tables()
            receiver.set_cores_for_data_streaming()

    def __reset_router_timeouts(self):
        # reset router timeouts
        for receiver in FecDataView.iterate_gathers():
            receiver.unset_cores_for_data_streaming()
            # reset router tables
            receiver.load_application_routing_tables()

    def __select_writer(self, x, y):
        view = FecDataView()
        chip = view.get_chip_at(x, y)
        ethernet_chip = view.get_chip_at(
            chip.nearest_ethernet_x, chip.nearest_ethernet_y)
        gatherer = view.get_gatherer_by_xy(ethernet_chip.x, ethernet_chip.y)
        return gatherer.send_data_into_spinnaker

    def __python_app(self, use_monitors):
        """
        :param bool use_monitors:
        """
        if use_monitors:
            self.__set_router_timeouts()

        dsg_targets = FecDataView.get_dsg_targets()
        # create a progress bar for end users
        progress = ProgressBar(
            dsg_targets.ds_n_app_cores(),
            "Executing data specifications and loading data for "
            "application vertices")

        with _ExecutionContext() as context:
            transceiver = FecDataView.get_transceiver()
            for core, reader, region_size in progress.over(
                    dsg_targets.app_items()):
                x, y, p = core
                base_address = self.__malloc_region_storage(
                    core, region_size)
                base_address, size_allocated, bytes_written = context.execute(
                    core, reader, self.__select_writer(x, y)
                    if use_monitors else transceiver.write_memory,
                    base_address, region_size)
                dsg_targets.set_write_info(
                    x, y, p, base_address, size_allocated, bytes_written)

        if use_monitors:
            self.__reset_router_timeouts()

    def __java_app(self, use_monitors):
        """
        :param bool use_monitors:
        """
        # create a progress bar for end users
        progress = ProgressBar(
            2, "Executing data specifications and loading data for "
            "application vertices using Java")

        java_caller = FecDataView.get_java_caller()
        if use_monitors:
            # Method also called with just recording params
            java_caller.set_placements(FecDataView.iterate_placemements())
        progress.update()

        java_caller.execute_app_data_specification(use_monitors)
        progress.end()

    def execute_system_data_specs(self):
        """
        Execute the data specs for all system targets.
        """
        # pylint: disable=too-many-arguments
        FecDataView.get_dsg_targets().mark_system_cores(system_cores())
        if FecDataView.has_java_caller():
            self.__java_sys()
        else:
            self.__python_sys()

    def __java_sys(self):
        """
        Does the Data Specification Execution and loading using Java.
        """
        # create a progress bar for end users
        progress = ProgressBar(
            1, "Executing data specifications and loading data for system "
            "vertices using Java")
        FecDataView.get_java_caller().execute_system_data_specification()
        progress.end()

    def __python_sys(self):
        """
        Does the Data Specification Execution and loading using Python.
        """

        # create a progress bar for end users
        dsg_targets = FecDataView.get_dsg_targets()
        progress = ProgressBar(
            dsg_targets.ds_n_system_cores(),
            "Executing data specifications and loading data for "
            "system vertices")

        # allocate and set user 0 before loading data

        with _ExecutionContext() as context:
            transceiver = FecDataView.get_transceiver()
            for core, reader, region_size in progress.over(
                    dsg_targets.system_items()):
                x, y, p = core
                base_address = self.__malloc_region_storage(
                    core, region_size)
                base_address, size_allocated, bytes_written = context.execute(
                    core, reader, transceiver.write_memory,
                    base_address, region_size)
                dsg_targets.set_write_info(
                    x, y, p, base_address, size_allocated, bytes_written)

    def __malloc_region_storage(self, core, size):
        """
        Allocates the storage for all DSG regions on the core and tells
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

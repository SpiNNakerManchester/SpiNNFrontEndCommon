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

from collections import OrderedDict
import logging
import struct
import numpy
from six import iteritems, itervalues
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter
from spinn_machine import CoreSubsets
from data_specification import DataSpecificationExecutor
from data_specification.constants import MAX_MEM_REGIONS
from data_specification.exceptions import DataSpecificationException
from spinn_front_end_common.interface.ds.ds_write_info import DsWriteInfo
from spinn_front_end_common.utilities.helpful_functions import (
    write_address_to_user0)
from spinn_front_end_common.utilities.utility_objs import (
    ExecutableType, DataWritten)
from spinn_front_end_common.utilities.helpful_functions import (
    emergency_recover_states_from_failure)

logger = FormatAdapter(logging.getLogger(__name__))
_ONE_WORD = struct.Struct("<I")
_MEM_REGIONS = range(MAX_MEM_REGIONS)


def system_cores(exec_targets):
    cores = CoreSubsets()
    for binary in exec_targets.get_binaries_of_executable_type(
            ExecutableType.SYSTEM):
        cores.add_core_subsets(exec_targets.get_cores_for_binary(binary))
    return cores


def filter_out_system_executables(dsg_targets, executable_targets):
    """ Select just the application DSG loading tasks """
    syscores = system_cores(executable_targets)
    return OrderedDict(
        (core, spec) for (core, spec) in iteritems(dsg_targets)
        if core not in syscores)


def filter_out_app_executables(dsg_targets, executable_targets):
    """ Select just the system DSG loading tasks """
    syscores = system_cores(executable_targets)
    return OrderedDict(
        (core, spec) for (core, spec) in iteritems(dsg_targets)
        if core in syscores)


class HostExecuteDataSpecification(object):
    """ Executes the host based data specification.
    """

    __slots__ = [
        # the application ID of the simulation
        "_app_id",
        "_core_to_conn_map",
        # The path where the SQLite database holding the data will be placed,
        # and where any java provenance can be written.
        "_db_folder",
        # The support class to run via Java. If None pure python is used.
        "_java",
        # The python representation of the SpiNNaker machine.
        "_machine",
        "_monitors",
        "_placements",
        # The spinnman instance.
        "_txrx",
        # The write info; a dict of cores to a dict of
        # 'start_address', 'memory_used', 'memory_written'
        "_write_info_map"]

    first = True

    def __init__(self):
        self._app_id = None
        self._core_to_conn_map = None
        self._db_folder = None
        self._java = None
        self._machine = None
        self._monitors = None
        self._placements = None
        self._txrx = None
        self._write_info_map = None

    # Is this method unused now?
    def __call__(
            self, transceiver, machine, app_id, dsg_targets,
            report_folder=None, java_caller=None,
            processor_to_app_data_base_address=None):
        """ Does the Data Specification Execution and loading

        :param transceiver: the spinnman instance
        :type transceiver: :py:class:`spinnman.transceiver.Transceiver`
        :param machine: the python representation of the SpiNNaker machine
        :type machine: :py:class:`spinn_machine.machine.Machine`
        :param app_id: the application ID of the simulation
        :type app_id: int
        :param dsg_targets: map of placement to file path
        :type dsg_targets: \
            :py:class:`spinn_front_end_common.interface.ds.DataSpecificationTargets`
        :param report_folder: The path where \
            the SQLite database holding the data will be placed, \
            and where any java provenance can be written. \
            report_folder can not be None if java_caller is not None.
        :type report_folder: str
        :param java_caller: The support class to run via Java. \
            If None pure python is used.
        :type java_caller: \
            :py:class:`spinn_front_end_common.interface.java_caller.JavaCaller`
        :param processor_to_app_data_base_address: The write info which is a\
            dict of cores to a dict of
                'start_address', 'memory_used', 'memory_written'
        :return: map of of cores to a dict of \
                'start_address', 'memory_used', 'memory_written'
            Note: If using python the return type is an actual dict object.
            If using Java the return is a DsWriteInfo \
                but this implements the same mapping interface as dict
        :rtype: dict or \
            :py:class:`spinn_front_end_common.interface.ds.ds_write_info.DsWriteInfo`
        """
        # pylint: disable=too-many-arguments
        if processor_to_app_data_base_address is None:
            processor_to_app_data_base_address = dict()
        self._app_id = app_id
        self._db_folder = report_folder
        self._java = java_caller
        self._machine = machine
        self._txrx = transceiver
        self._write_info_map = processor_to_app_data_base_address
        impl_method = self.__java_all if java_caller else self.__python_all
        return impl_method(dsg_targets)

    def __java_all(self, dsg_targets):
        """ Does the Data Specification Execution and loading using Java

        :param dsg_targets: map of placement to file path
        :type dsg_targets: \
            :py:class:`~spinn_front_end_common.interface.ds.DataSpecificationTargets`
        :return: map of of cores to a dict of \
            'start_address', 'memory_used', 'memory_written'
        :rtype: spinn_front_end_common.interface.ds.ds_write_info.DsWriteInfo
        """

        # create a progress bar for end users
        progress = ProgressBar(
            3, "Executing data specifications and loading data using Java")

        # Copy data from WriteMemoryIOData to database
        dw_write_info = DsWriteInfo(dsg_targets.get_database())
        dw_write_info.clear_write_info()
        if self._write_info_map is not None:
            for core, info in iteritems(self._write_info_map):
                dw_write_info[core] = info

        progress.update()

        dsg_targets.set_app_id(self._app_id)
        self._java.set_machine(self._machine)
        self._java.set_report_folder(self._db_folder)

        progress.update()

        self._java.execute_data_specification()

        progress.end()
        return dw_write_info

    def __python_all(self, dsg_targets):
        """ Does the Data Specification Execution and loading using Python

        :param dsg_targets: map of placement to file path
        :type dsg_targets: \
            :py:class:`~spinn_front_end_common.interface.ds.DataSpecificationTargets`
        :return: dict of cores to a dict of\
            'start_address', 'memory_used', 'memory_written
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

        for core, reader in progress.over(iteritems(dsg_targets)):
            results[core] = self.__execute(
                core, reader, self._txrx.write_memory)

        return results

    def execute_application_data_specs(
            self, transceiver, machine, app_id, dsg_targets,
            uses_advanced_monitors, executable_targets,
            placements=None, extra_monitor_cores=None,
            extra_monitor_cores_to_ethernet_connection_map=None,
            report_folder=None, java_caller=None,
            processor_to_app_data_base_address=None,
            disable_advanced_monitor_usage=False):
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
        :param disable_advanced_monitor_usage: \
            whether to avoid using advanced monitors even if they're available
        :return: map of placement and DSG data
        """
        # pylint: disable=too-many-arguments
        if processor_to_app_data_base_address is None:
            processor_to_app_data_base_address = dict()
        self._write_info_map = processor_to_app_data_base_address
        self._db_folder = report_folder
        self._java = java_caller
        self._machine = machine
        self._txrx = transceiver
        self._app_id = app_id
        self._monitors = extra_monitor_cores
        self._placements = placements
        self._core_to_conn_map = extra_monitor_cores_to_ethernet_connection_map

        # Allow override to disable
        if disable_advanced_monitor_usage:
            uses_advanced_monitors = False

        impl_method = self.__java_app if java_caller else self.__python_app
        try:
            return impl_method(
                dsg_targets, executable_targets, uses_advanced_monitors)
        except:  # noqa: E722
            if uses_advanced_monitors:
                emergency_recover_states_from_failure(
                    self._txrx, self._app_id, executable_targets)
            raise

    def __set_router_timeouts(self):
        receiver = next(itervalues(self._core_to_conn_map))
        receiver.load_system_routing_tables(
            self._txrx, self._monitors, self._placements)
        receiver.set_cores_for_data_streaming(
            self._txrx, self._monitors, self._placements)
        return receiver

    def __reset_router_timeouts(self, receiver):
        # reset router tables
        receiver.load_application_routing_tables(
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

    def __python_app(self, dsg_targets, executable_targets, use_monitors):
        dsg_targets = filter_out_system_executables(
            dsg_targets, executable_targets)

        if use_monitors:
            receiver = self.__set_router_timeouts()

        # create a progress bar for end users
        progress = ProgressBar(
            dsg_targets,
            "Executing data specifications and loading data for "
            "application vertices")

        for core, reader in progress.over(iteritems(dsg_targets)):
            x, y, _ = core
            # write information for the memory map report
            self._write_info_map[core] = self.__execute(
                core, reader,
                self.__select_writer(x, y)
                if use_monitors else self._txrx.write_memory)

        if use_monitors:
            self.__reset_router_timeouts(receiver)
        return self._write_info_map

    def __java_app(self, dsg_targets, executable_targets, use_monitors):
        # create a progress bar for end users
        progress = ProgressBar(
            4, "Executing data specifications and loading data for "
            "application vertices using Java")

        dsg_targets.mark_system_cores(system_cores(executable_targets))
        progress.update()

        # Copy data from WriteMemoryIOData to database
        dw_write_info = DsWriteInfo(dsg_targets.get_database())
        dw_write_info.clear_write_info()
        if self._write_info_map is not None:
            for core, info in iteritems(self._write_info_map):
                dw_write_info[core] = info

        progress.update()

        dsg_targets.set_app_id(self._app_id)
        self._java.set_machine(self._machine)
        self._java.set_report_folder(self._db_folder)
        if use_monitors:
            self._java.set_placements(self._placements, self._txrx)

        progress.update()

        self._java.execute_app_data_specification(use_monitors)

        progress.end()
        return dw_write_info

    def execute_system_data_specs(
            self, transceiver, machine, app_id, dsg_targets,
            executable_targets, report_folder=None, java_caller=None,
            processor_to_app_data_base_address=None):
        """ Execute the data specs for all system targets.

        :param machine: the python representation of the spinnaker machine
        :type machine: ~spinn_machine.Machine
        :param transceiver: the spinnman instance
        :type transceiver: ~spinnman.transceiver.Transceiver
        :param app_id: the application ID of the simulation
        :type app_id: int
        :param dsg_targets: map of placement to file path
        :type dsg_targets: dict(tuple(int,int,int),str)
        :param executable_targets: \
            the map between binaries and locations and executable types
        :type executable_targets: ExecutableTargets
        :return: map of placement and DSG data, and loaded data flag.
        :rtype: dict(tuple(int,int,int),\
            ~spinn_front_end_common.utilities.utility_objs.DataWritten)
        """
        # pylint: disable=too-many-arguments

        if processor_to_app_data_base_address is None:
            processor_to_app_data_base_address = dict()
        self._write_info_map = processor_to_app_data_base_address
        self._machine = machine
        self._txrx = transceiver
        self._app_id = app_id
        self._db_folder = report_folder
        self._java = java_caller
        impl_method = self.__java_sys if java_caller else self.__python_sys
        return impl_method(dsg_targets, executable_targets)

    def __java_sys(self, dsg_targets, executable_targets):
        """ Does the Data Specification Execution and loading using Java

        :param dsg_targets: map of placement to file path
        :type dsg_targets: \
            ~spinn_front_end_common.interface.ds.DataSpecificationTargets
        :return: map of cores to \
            :py:class:`~spinn_front_end_common.utilities.utility_objs.DataWritten`
        :rtype: ~spinn_front_end_common.interface.ds.DsWriteInfo
        """

        # create a progress bar for end users
        progress = ProgressBar(
            4, "Executing data specifications and loading data for system "
            "vertices using Java")

        dsg_targets.mark_system_cores(system_cores(executable_targets))
        progress.update()

        # Copy data from WriteMemoryIOData to database
        dw_write_info = DsWriteInfo(dsg_targets.get_database())
        dw_write_info.clear_write_info()
        if self._write_info_map is not None:
            for core, info in iteritems(self._write_info_map):
                dw_write_info[core] = info

        progress.update()

        dsg_targets.set_app_id(self._app_id)
        self._java.set_machine(self._machine)
        self._java.set_report_folder(self._db_folder)

        progress.update()

        self._java.execute_system_data_specification()

        progress.end()
        return dw_write_info

    def __python_sys(self, dsg_targets, executable_targets):
        """ Does the Data Specification Execution and loading using Python

        :param dsg_targets: map of placement to file path
        :type dsg_targets: \
            :py:class:`spinn_front_end_common.interface.ds.DataSpecificationTargets`
        :return: dict of cores to a dict of\
            'start_address', 'memory_used', 'memory_written
        """
        # While the database supports having the info in it a python bugs does
        # not like iterating over and writing intermingled so using a dict
        sys_targets = filter_out_app_executables(
            dsg_targets, executable_targets)

        # create a progress bar for end users
        progress = ProgressBar(
            len(sys_targets), "Executing data specifications and loading data "
            "for system vertices")

        for core, reader in progress.over(iteritems(sys_targets)):
            self._write_info_map[core] = self.__execute(
                core, reader, self._txrx.write_memory)

        return self._write_info_map

    def __execute(self, core, reader, writer_func):
        x, y, p = core

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

# Copyright (c) 2016 The University of Manchester
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
"""
main interface for the SpiNNaker tools
"""
from __future__ import annotations
import logging
import math
import os
import re
import signal
import sys
import threading
import types
from threading import Condition
from typing import (
    Any, Dict, Iterable, Optional, Sequence, Tuple, Type,
    TypeVar, Union, cast, final)
from types import FrameType

from numpy import __version__ as numpy_version

from spinn_utilities import __version__ as spinn_utils_version
from spinn_utilities.config_holder import (
    config_options, config_sections,
    get_config_bool, get_config_int, get_config_str, get_config_str_or_none,
    get_report_path, get_timestamp_path, is_config_none, set_config)
from spinn_utilities.exceptions import DataNotYetAvialable
from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides
from spinn_utilities.typing.coords import XY
from spinn_utilities.progress_bar import ProgressBar

from spinn_machine import __version__ as spinn_machine_version
from spinn_machine import CoreSubsets, Machine

from spinnman import __version__ as spinnman_version
from spinnman.exceptions import (
    SpiNNManCoresNotInStateException)
from spinnman.model.cpu_infos import CPUInfos
from spinnman.model.enums import CPUState, ExecutableType
from spinnman.spalloc import is_server_address
from spinnman.transceiver import (
    create_transceiver_from_hostname, Transceiver, transceiver_generator)

from spalloc_client import (  # type: ignore[import]
    __version__ as spalloc_version)

from pacman import __version__ as pacman_version
from pacman.exceptions import PacmanPlaceException
from pacman.model.graphs.application import ApplicationEdge, ApplicationVertex
from pacman.model.graphs import AbstractVirtual
from pacman.model.resources import AbstractSDRAM
from pacman.model.partitioner_splitters.splitter_reset import splitter_reset
from pacman.model.placements import Placements
from pacman.model.routing_tables import MulticastRoutingTables
from pacman.operations.fixed_route_router import fixed_route_router
from pacman.operations.multi_cast_router_check_functionality.\
    valid_routes_checker import validate_routes
from pacman.operations.partition_algorithms import splitter_partitioner
from pacman.operations.placer_algorithms import place_application_graph
from pacman.operations.router_algorithms import route_application_graph
from pacman.operations.router_compressors import (
    pair_compressor, range_compressor)
from pacman.operations.router_compressors.ordered_covering_router_compressor \
    import ordered_covering_compressor
from pacman.operations.routing_info_allocator_algorithms.\
    zoned_routing_info_allocator import (flexible_allocate, global_allocate)
from pacman.operations.routing_table_generators import (
    basic_routing_table_generator, merged_routing_table_generator)
from pacman.operations.tag_allocator_algorithms import basic_tag_allocator

from spinn_front_end_common import __version__ as fec_version
from spinn_front_end_common import common_model_binaries
from spinn_front_end_common.abstract_models import (
    AbstractVertexWithEdgeToDependentVertices,
    AbstractCanReset)
from spinn_front_end_common.data.fec_data_view import FecDataView
from spinn_front_end_common.interface.buffer_management import BufferManager
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import BufferDatabase
from spinn_front_end_common.interface.config_handler import (
    ConfigHandler)
from spinn_front_end_common.interface.interface_functions import (
    application_finisher, application_runner,
    chip_io_buf_clearer, chip_io_buf_extractor,
    chip_provenance_updater, chip_runtime_updater, compute_energy_used,
    create_notification_protocol, database_interface,
    reload_dsg_regions, energy_provenance_reporter,
    load_application_data_specs, load_system_data_specs,
    graph_binary_gatherer, graph_data_specification_writer,
    graph_provenance_gatherer, hbp_allocator,
    insert_chip_power_monitors_to_graphs,
    insert_extra_monitor_vertices_to_graphs, split_lpg_vertices,
    load_app_images, load_fixed_routes, load_sys_images,
    locate_executable_start_type,
    placements_provenance_gatherer, profile_data_gatherer,
    read_routing_tables_from_machine, router_provenance_gatherer,
    routing_table_loader, sdram_outgoing_partition_allocator,
    spalloc_allocate_job_old,
    system_multicast_routing_generator,
    tags_loader, add_command_senders)
from spinn_front_end_common.interface.interface_functions.\
    host_no_bitfield_router_compression import (
        ordered_covering_compression, pair_compression)
from spinn_front_end_common.interface.provenance import (
    FecTimer, GlobalProvenance, ProvenanceWriter, TimerCategory, TimerWork)
from spinn_front_end_common.interface.splitter_selectors import (
    splitter_selector)
from spinn_front_end_common.interface.java_caller import JavaCaller
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.report_functions import (
    bitfield_compressor_report, board_chip_report, EnergyReport,
    fixed_route_from_machine_report,
    generate_routing_compression_checker_report, memory_map_on_host_report,
    memory_map_on_host_chip_report, network_specification,
    tags_from_machine_report,
    write_json_machine, write_json_placements,
    write_json_routing_tables, drift_report)
from spinn_front_end_common.utilities.iobuf_extractor import IOBufExtractor
from spinn_front_end_common.utility_models import (
    DataSpeedUpPacketGatherMachineVertex)
from spinn_front_end_common.utilities.report_functions.reports import (
    generate_comparison_router_report, partitioner_report,
    placer_reports_with_application_graph,
    router_compressed_summary_report, routing_info_report,
    router_report_from_compressed_router_tables,
    router_report_from_paths,
    router_report_from_router_tables, router_summary_report,
    sdram_usage_report_per_chip,
    tag_allocator_report)
from spinn_front_end_common.data.fec_data_writer import FecDataWriter

try:
    from scipy import __version__ as scipy_version
except ImportError:
    scipy_version = "scipy not installed"

logger = FormatAdapter(logging.getLogger(__name__))
_T = TypeVar("_T")

SHARED_PATH = re.compile(r".*\/shared\/([^\/]+)")
SHARED_GROUP = 1
SHARED_WITH_PATH = re.compile(r".*\/Shared with (all|groups|me)\/([^\/]+)")
SHARED_WITH_GROUP = 2


class AbstractSpinnakerBase(ConfigHandler):
    """
    Main interface into the tools logic flow.
    """

    __slots__ = (
        # Condition object used for waiting for stop
        # Set during init and the used but never new object
        "_state_condition",

        # Set when run_until_complete is specified by the user
        "_run_until_complete",

        #
        "_raise_keyboard_interrupt",

        # original value which is used in exception handling and control c
        "__sys_excepthook",

        # All beyond this point new for no extractor
        # The data is not new but now it is held direct and not via inputs

        # Flag to say is compressed routing tables are on machine
        # TODO remove this when the data change only algorithms are done
        "_multicast_routes_loaded")

    def __init__(
            self, data_writer_cls: Optional[Type[FecDataWriter]] = None):
        """
        :param data_writer_cls: The Global data writer class
        """
        super().__init__(data_writer_cls)

        FecTimer.start_category(TimerCategory.WAITING)
        FecTimer.start_category(TimerCategory.SETTING_UP)

        # output locations of binaries to be searched for end user info
        logger.info(
            "Will search these locations for binaries: {}",
            self._data_writer.get_executable_finder().binary_paths)

        self._multicast_routes_loaded = False

        # holder for timing and running related values
        self._run_until_complete = False
        self._state_condition = Condition()

        # folders
        self._set_up_report_specifics()

        # Setup for signal handling
        self._raise_keyboard_interrupt = False

        self._create_version_provenance()

        self.__sys_excepthook = sys.excepthook

        FecTimer.setup(self)

        self._data_writer.register_binary_search_path(
            os.path.dirname(common_model_binaries.__file__))

        external_binaries = get_config_str_or_none(
            "Mapping", "external_binaries")
        if external_binaries is not None:
            self._data_writer.register_binary_search_path(external_binaries)

        FecTimer.end_category(TimerCategory.SETTING_UP)

    def _hard_reset(self) -> None:
        """
        This clears all data that if no longer valid after a hard reset
        """
        if self._data_writer.has_transceiver():
            self._data_writer.get_transceiver().stop_application(
                self._data_writer.get_app_id())
        self._close_allocation_controller()
        self._reset_remove_data()
        self._data_writer.hard_reset()
        self._multicast_routes_loaded = False

    def _reset_remove_data(self) -> None:
        """
        Removes all data from the report directory user did not ask to keep.
        """
        with FecTimer("Cleanup reports folder based on cfg", TimerWork.REPORT):
            self.__reset_remove_data()

    def __reset_remove_data(self) -> None:
        if not get_config_bool("Reports", "keep_json_files"):
            for section in config_sections():
                for option in config_options(section):
                    if option.startswith("pathjson"):
                        path = get_report_path(option, section=section)
                        if os.path.exists(path):
                            os.remove(path)
                            dir_name = os.path.dirname(path)
                            if not os.listdir(dir_name):
                                os.removedirs(dir_name)

        if not get_config_bool("Reports", "keep_dataspec_database"):
            path = get_report_path("path_dataspec_database")
            if os.path.exists(path):
                os.remove(path)

        if not get_config_bool("Reports", "keep_input_output_database"):
            path = get_report_path("path_input_output_database")
            if os.path.exists(path):
                os.remove(path)

        if not get_config_bool("Reports", "keep_java_log"):
            path = get_report_path("path_java_log")
            if os.path.exists(path):
                os.remove(path)

    def _stop_remove_data(self) -> None:
        with FecTimer("Cleanup reports folder based on cfg", TimerWork.REPORT):
            self.__reset_remove_data()

            if not get_config_bool("Reports", "keep_data_database"):
                path = get_report_path("path_data_database")
                if os.path.exists(path):
                    os.remove(path)

            if not get_config_bool("Reports", "keep_stack_trace"):
                os.remove(get_timestamp_path("tpath_stack_trace"))

    def _setup_java_caller(self) -> None:
        if get_config_bool("Java", "use_java"):
            self._data_writer.set_java_caller(JavaCaller())

    def __signal_handler(
            self, _signal: int, _frame: Optional[FrameType]) -> None:
        """
        Handles closing down of script via keyboard interrupt

        :param _signal: the signal received (ignored)
        :param _frame: frame executed in (ignored)
        """
        # If we are to raise the keyboard interrupt, do so
        if self._raise_keyboard_interrupt:
            raise KeyboardInterrupt

        logger.error("User has cancelled simulation")
        self._shutdown()

    def exception_handler(
            self, exc_type: Type[BaseException], value: BaseException,
            traceback_obj: Optional[types.TracebackType]) -> None:
        """
        Handler of exceptions.

        :param exc_type: the type of exception received
        :param value: the value of the exception
        :param traceback_obj: the trace back stuff
        """
        logger.error("Shutdown on exception")
        self._shutdown()
        return self.__sys_excepthook(exc_type, value, traceback_obj)

    def _should_run(self) -> bool:
        """
        Checks if the simulation should run.

        Will warn the user if there is no need to run

        :return: True if and only if one of the graphs has vertices in it
        :raises ConfigurationException: If the current state does not
            support a new run call
        """
        if self._data_writer.get_n_vertices() > 0:
            return True
        logger.warning(
            "Your graph has no vertices in it. "
            "Therefore the run call will exit immediately.")
        return False

    def run_until_complete(self, n_steps: Optional[int] = None) -> None:
        """
        Run a simulation until it completes.

        :param n_steps:
            If not `None`, this specifies that the simulation should be
            requested to run for the given number of steps.  The host will
            still wait until the simulation itself says it has completed.
        """
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        self._run_until_complete = True
        self._run(n_steps, sync_time=0.0)
        FecTimer.end_category(TimerCategory.RUN_OTHER)

    def run(self, run_time: Optional[float], sync_time: float = 0) -> None:
        """
        Run a simulation for a fixed amount of time.

        :param run_time: the run duration in milliseconds.
        :param sync_time:
            If not 0, this specifies that the simulation should pause after
            this duration.  The continue_simulation() method must then be
            called for the simulation to continue.
        """
        FecTimer.start_category(TimerCategory.RUN_OTHER)
        if self._run_until_complete:
            raise NotImplementedError("run after run_until_complete")
        self._run(run_time, sync_time)
        FecTimer.end_category(TimerCategory.RUN_OTHER)

    def __timesteps(self, time_in_ms: float) -> int:
        """
        Get a number of timesteps for a given time in milliseconds.

        :return: The number of timesteps
        """
        time_step_ms = self._data_writer.get_simulation_time_step_ms()
        n_time_steps = int(math.ceil(time_in_ms / time_step_ms))
        calc_time = n_time_steps * time_step_ms

        # Allow for minor float errors
        if abs(time_in_ms - calc_time) > 0.00001:
            logger.warning(
                "Time of {}ms "
                "is not a multiple of the machine time step of {}ms "
                "and has therefore been rounded up to {}ms",
                time_in_ms, time_step_ms, calc_time)
        return n_time_steps

    def _calc_run_time(self, run_time: Optional[float]) -> Union[
            Tuple[int, float], Tuple[None, None]]:
        """
        Calculates n_machine_time_steps and total_run_time based on run_time
        and machine_time_step.

        This method rounds the run up to the next timestep as discussed in
        https://github.com/SpiNNakerManchester/sPyNNaker/issues/149

        If run_time is `None` (run forever) both values will be `None`

        :param run_time: time user requested to run for in milliseconds
        :return: n_machine_time_steps as a whole int and
            total_run_time in milliseconds
        """
        if run_time is None:
            # TODO does this make sense?
            # https://github.com/SpiNNakerManchester/SpiNNFrontEndCommon/issues/1243
            if FecDataView.has_allocation_controller():
                FecDataView.get_allocation_controller().extend_allocation(0.0)
            self._data_writer.set_plan_n_timesteps(get_config_int(
                "Buffers", "minimum_auto_time_steps"))
            return None, None
        n_machine_time_steps = self.__timesteps(run_time)
        total_run_timesteps = (
            (self._data_writer.get_current_run_timesteps() or 0) +
            n_machine_time_steps)
        total_run_time = (
            total_run_timesteps *
            self._data_writer.get_hardware_time_step_ms())
        if FecDataView.has_allocation_controller():
            FecDataView.get_allocation_controller().extend_allocation(
                total_run_time)

        if get_config_bool("Buffers", "use_auto_pause_and_resume"):
            self._data_writer.set_plan_n_timesteps(
                get_config_int("Buffers", "minimum_auto_time_steps"))
        else:
            self._data_writer.set_plan_n_timesteps(n_machine_time_steps)

        logger.info(
            f"Simulating for {n_machine_time_steps} "
            f"{self._data_writer.get_simulation_time_step_ms()} ms timesteps "
            f"using a hardware timestep of "
            f"{self._data_writer.get_hardware_time_step_us()} us")
        return n_machine_time_steps, total_run_time

    def _run(self, run_time: Optional[float], sync_time: float) -> None:
        self._data_writer.start_run()
        with GlobalProvenance() as db:
            db.insert_run_reset_mapping()
        try:
            self.__run(run_time, sync_time)
            self._data_writer.finish_run()
        except Exception:
            # if in debug mode, do not shut down machine
            if get_config_str("Mode", "mode") != "Debug":
                try:
                    self.stop()
                except Exception as stop_e:
                    logger.exception(f"Error {stop_e} when attempting to stop")
            self._data_writer.shut_down()
            raise

    @staticmethod
    def __is_main_thread() -> bool:
        """
        :return: Whether this is the main thread.
        """
        return threading.get_ident() == threading.main_thread().ident

    def __run_verify(self) -> None:
        # verify that we can keep doing auto pause and resume
        if self._data_writer.is_ran_ever():
            can_keep_running = all(
                executable_type.supports_auto_pause_and_resume
                for executable_type in
                self._data_writer.get_executable_types())
            if not can_keep_running:
                raise NotImplementedError(
                    "Only binaries that use the simulation interface can be"
                    " run more than once")

        # If we have never run before, or the graph has changed,
        # start by performing mapping
        if (self._data_writer.get_requires_mapping() and
                self._data_writer.is_ran_last()):
            self.stop()
            raise NotImplementedError(
                "The network cannot be changed between runs without"
                " resetting")

    def __run_control_c_handler_on(self) -> None:
        # Install the Control-C handler
        if self.__is_main_thread():
            signal.signal(signal.SIGINT, self.__signal_handler)
            self._raise_keyboard_interrupt = True
            sys.excepthook = self.__sys_excepthook

    def __run_control_c_handler_off(self) -> None:
        # Indicate that the signal handler needs to act
        if self.__is_main_thread():
            self._raise_keyboard_interrupt = False
            sys.excepthook = self.exception_handler

    def __run_reset_sync_signal(self) -> None:
        # If we have reset and the graph has changed, stop any running
        # application
        if (self._data_writer.get_requires_data_generation() and
                self._data_writer.has_transceiver()):
            self._data_writer.get_transceiver().stop_application(
                self._data_writer.get_app_id())
            self._data_writer.reset_sync_signal()

    def __run(self, run_time: Optional[float], sync_time: float) -> None:
        """
        The main internal run function.

        :param run_time: the run duration in milliseconds.
        :param sync_time:
            the time in milliseconds between synchronisations, or 0 to disable.
        """
        if not self._should_run():
            return
        logger.info("Starting execution process")
        self.__run_verify()
        self.__run_control_c_handler_on()
        n_machine_time_steps, total_run_time = self._calc_run_time(run_time)
        n_sync_steps = self.__timesteps(sync_time)
        self.__run_reset_sync_signal()

        # build the graphs to modify with system requirements
        if self._data_writer.get_requires_mapping():
            self._do_mapping(total_run_time, n_machine_time_steps)

        if not self._data_writer.is_ran_last():
            self._do_write_metadata()

        # requires data_generation includes never run and requires_mapping
        if self._data_writer.get_requires_data_generation():
            self._do_load()

        # Run for each of the given steps
        if n_machine_time_steps is not None:
            if get_config_bool("Buffers", "use_auto_pause_and_resume"):
                steps = self._generate_steps(n_machine_time_steps)
            else:
                steps = [n_machine_time_steps]
            logger.info("Running for {} steps for a total of {}ms",
                        len(steps), run_time)
            self._data_writer.set_n_run_steps(len(steps))
            for step in steps:
                run_step = self._data_writer.next_run_step()
                logger.info(f"Run {run_step} of {len(steps)}")
                self._do_run(step, n_sync_steps)
            self._data_writer.clear_run_steps()
        elif self._run_until_complete:
            logger.info("Running until complete")
            self._do_run(None, n_sync_steps)
        else:
            if self._data_writer.get_max_run_time_steps() < sys.maxsize:
                logger.warning("Due to recording this simulation "
                               "should not be run longer than {}ms",
                               self._data_writer.get_max_run_time_steps())
            logger.info("Running until stop is called by another thread")
            self._do_run(None, n_sync_steps)
        self.__run_control_c_handler_off()

    @final
    def _add_commands_to_command_sender(
            self, system_placements: Placements) -> None:
        """
        Runs, times and logs the VirtualMachineGenerator if required.

        May set then "machine" value
        """
        with FecTimer("Command Sender Adder", TimerWork.OTHER):
            all_command_senders = add_command_senders(system_placements)
            # add the edges from the command senders to the dependent vertices
            for command_sender in all_command_senders:
                self._data_writer.add_vertex(command_sender)
                edges, partition_ids = command_sender.edges_and_partitions()
                for edge, partition_id in zip(edges, partition_ids):
                    self._data_writer.add_edge(edge, partition_id)

    @final
    def _add_dependent_verts_and_edges_for_application_graph(self) -> None:
        # cache vertices to allow insertion during iteration
        vertices = list(self._data_writer.get_vertices_by_type(
                AbstractVertexWithEdgeToDependentVertices))
        for vertex in vertices:
            v = cast(ApplicationVertex, vertex)
            for dpt_vtx in vertex.dependent_vertices():
                if dpt_vtx.has_been_added_to_graph():
                    continue
                self._data_writer.add_vertex(dpt_vtx)
                edge_partition_ids = vertex.\
                    edge_partition_identifiers_for_dependent_vertex(dpt_vtx)
                for edge_identifier in edge_partition_ids:
                    self._data_writer.add_edge(
                        ApplicationEdge(v, dpt_vtx), edge_identifier)

    @final
    def _deduce_data_n_timesteps(
            self, n_machine_time_steps: Optional[int]) -> None:
        """
        Operates the auto pause and resume functionality by figuring out
        how many timer ticks a simulation can run before SDRAM runs out,
        and breaks simulation into chunks of that long.
        """
        # Go through the placements and find how much SDRAM is used
        # on each chip
        usage_by_chip: Dict[XY, AbstractSDRAM] = dict()

        for place in self._data_writer.iterate_placemements():
            if isinstance(place.vertex, AbstractVirtual):
                continue

            sdram = place.vertex.sdram_required
            if (place.x, place.y) in usage_by_chip:
                usage_by_chip[place.x, place.y] += sdram
            else:
                usage_by_chip[place.x, place.y] = sdram

        # Go through the chips and divide up the remaining SDRAM, finding
        # the minimum number of machine timesteps to assign
        max_time_steps = sys.maxsize
        for (x, y), sdram in usage_by_chip.items():
            size = self._data_writer.get_chip_at(x, y).sdram
            if sdram.fixed > size:
                raise PacmanPlaceException(
                    f"Too much SDRAM has been allocated on chip {x}, {y}: "
                    f"{sdram.fixed} of {size}")
            if sdram.per_timestep:
                max_this_chip = int((size - sdram.fixed) // sdram.per_timestep)
                max_time_steps = min(max_time_steps, max_this_chip)

        if not get_config_bool("Buffers", "use_auto_pause_and_resume"):
            if ((n_machine_time_steps is not None) and
                    (max_time_steps < n_machine_time_steps)):
                raise ConfigurationException(
                    "The SDRAM required by one or more vertices is based on "
                    "the run time, so the run time is limited to "
                    f"{max_time_steps} time steps")

        self._data_writer.set_max_run_time_steps(max_time_steps)

    def _generate_steps(self, n_steps: int) -> Sequence[int]:
        """
        Generates the list of "timer" runs. These are usually in terms of
        time steps, but need not be.

        :param n_steps: the total runtime in machine time steps
        :return: list of time step lengths
        """
        if n_steps == 0:
            return [0]
        n_steps_per_segment = self._data_writer.get_max_run_time_steps()
        n_full_iterations = int(math.floor(n_steps / n_steps_per_segment))
        left_over_steps = n_steps - n_full_iterations * n_steps_per_segment
        steps = [int(n_steps_per_segment)] * n_full_iterations
        if left_over_steps:
            steps.append(int(left_over_steps))
        return steps

    @overrides(ConfigHandler._execute_get_virtual_machine, extend_doc=False)
    def _execute_get_virtual_machine(self) -> Machine:
        with FecTimer("Virtual machine generator", TimerWork.OTHER):
            return super()._execute_get_virtual_machine()

    @overrides(ConfigHandler._do_transceiver_by_remote)
    def _do_transceiver_by_remote(
            self, total_run_time: Optional[float],
            ensure_board_is_ready: bool) -> Transceiver:
        spalloc_server = get_config_str_or_none("Machine", "spalloc_server")
        if spalloc_server:
            if is_server_address(spalloc_server):
                transceiver, _ = self._execute_transceiver_by_spalloc(
                    ensure_board_is_ready)
                return transceiver
            else:
                assert ensure_board_is_ready
                return self._execute_transceiver_by_spalloc_old()
        if not is_config_none("Machine", "remote_spinnaker_url"):
            return self._execute_transceiver_by_hbp(total_run_time)
        raise ConfigurationException(
            "Neither cfg spalloc_server or remote_spinnaker_url set")

    @overrides(ConfigHandler._execute_transceiver_by_spalloc)
    def _execute_transceiver_by_spalloc(
            self, ensure_board_is_ready: bool
            ) -> Tuple[Transceiver, Dict[XY, str]]:
        with (FecTimer("Transceiver by Spalloc", TimerWork.OTHER)):
            transceiver, connections = (
                super()._execute_transceiver_by_spalloc(
                    ensure_board_is_ready))
            with ProvenanceWriter() as db:
                db.insert_board_provenance(connections)
            return (transceiver, connections)

    def _execute_transceiver_by_spalloc_old(self) -> Transceiver:
        with FecTimer("Transceiver by Spalloc Old", TimerWork.OTHER):
            ipaddress, connections, controller = spalloc_allocate_job_old()
            self._data_writer.set_ipaddress(ipaddress)
            with ProvenanceWriter() as db:
                db.insert_board_provenance(connections)
            self._data_writer.set_allocation_controller(controller)
            transceiver = create_transceiver_from_hostname(
                ipaddress, ensure_board_is_ready=True)
            transceiver.discover_scamp_connections()
            self._data_writer.set_transceiver(transceiver)
            return transceiver

    def _execute_transceiver_by_hbp(
            self, total_run_time:  Optional[float]) -> Transceiver:
        with (FecTimer("HBPAllocator", TimerWork.OTHER)):
            # TODO: Would passing the bearer token to this ever make sense?
            ipaddress, bmp_details, controller = hbp_allocator(total_run_time)
            self._data_writer.set_ipaddress(ipaddress)
            self._data_writer.set_allocation_controller(controller)
            transceiver = transceiver_generator(
                bmp_details, auto_detect_bmp=False,
                scamp_connection_data=None, reset_machine_on_start_up=False,
                ensure_board_is_ready=True)
            self._data_writer.set_transceiver(transceiver)
            return transceiver

    @overrides(ConfigHandler._execute_tranceiver_by_name)
    def _execute_tranceiver_by_name(
            self, ensure_board_is_ready: bool = True) -> Transceiver:
        with FecTimer("Machine generator", TimerWork.GET_MACHINE):
            return super()._execute_tranceiver_by_name(
                ensure_board_is_ready=True)

    def get_machine(self) -> Machine:
        """
        Get the Machine. Creating it if necessary.

        This method will make sure that any set called
        before the next run is hard.

        If called after a reset it will return a different Machine
        to the one from the previous run.

        :returns: The Machine now stored in the DataView
        """
        FecTimer.start_category(TimerCategory.GET_MACHINE, True)
        self._data_writer.set_user_accessed_machine()
        if self._data_writer.is_user_mode() and \
                self._data_writer.is_soft_reset():
            self._data_writer.clear_machine()
            # Make the reset hard
            logger.warning(
                "Calling Get machine after a reset force a hard reset and "
                "therefore generate a new machine")
            self._hard_reset()
        machine = self._get_known_machine()
        FecTimer.end_category(TimerCategory.GET_MACHINE)
        return machine

    def _create_version_provenance(self) -> None:
        """
        Add the version information to the provenance data at the start.
        """
        with GlobalProvenance() as db:
            db.insert_version("spinn_utilities_version", spinn_utils_version)
            db.insert_version("spinn_machine_version", spinn_machine_version)
            db.insert_version("spalloc_version", spalloc_version)
            db.insert_version("spinnman_version", spinnman_version)
            db.insert_version("pacman_version", pacman_version)
            db.insert_version("front_end_common_version", fec_version)
            db.insert_version("numpy_version", numpy_version)
            db.insert_version("scipy_version", scipy_version)

    def _do_extra_mapping_algorithms(self) -> None:
        """
        Allows overriding classes to add algorithms.
        """

    def _json_machine(self) -> None:
        """
        Runs, times and logs WriteJsonMachine if required.
        """
        with FecTimer("Json machine", TimerWork.REPORT) as timer:
            if timer.skip_if_cfg_false("Reports", "write_json_machine"):
                return
            write_json_machine()

    def _report_network_specification(self) -> None:
        """
        Runs, times and logs the Network Specification report is requested.
        """
        with FecTimer(
                "Network Specification report", TimerWork.REPORT) as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_network_specification_report"):
                return
            network_specification()

    def _execute_split_lpg_vertices(
            self, system_placements: Placements) -> None:
        """
        Runs, times and logs the SplitLPGVertices if required.
        """
        with FecTimer("Split Live Gather Vertices", TimerWork.OTHER):
            split_lpg_vertices(system_placements)

    def _report_board_chip(self) -> None:
        """
        Runs, times and logs the BoardChipReport is requested.
        """
        with FecTimer("Board chip report", TimerWork.REPORT) as timer:
            if timer.skip_if_cfg_false("Reports", "write_board_chip_report"):
                return
            board_chip_report()
            if FecDataView.has_allocation_controller():
                filename = get_report_path("path_board_chip_report")
                with open(filename, "a", encoding="utf-8") as report:
                    report.write(
                        f"{FecDataView.get_allocation_controller()}\n")

    def _execute_splitter_reset(self) -> None:
        """
        Runs, times and logs the splitter_reset.
        """
        with FecTimer("Splitter reset", TimerWork.OTHER):
            splitter_reset()

    # Overridden by sPyNNaker to choose an extended algorithm
    def _execute_splitter_selector(self) -> None:
        """
        Runs, times and logs the SplitterSelector.
        """
        with FecTimer("Splitter selector", TimerWork.OTHER):
            splitter_selector()

    def _execute_delay_support_adder(self) -> None:
        """
        Stub to allow sPyNNaker to add delay supports.
        """

    # Overridden by sPyNNaker to choose a different algorithm
    def _execute_splitter_partitioner(self) -> None:
        """
        Runs, times and logs the SplitterPartitioner if required.
        """
        if self._data_writer.get_n_vertices() == 0:
            return
        with FecTimer("Splitter partitioner", TimerWork.OTHER):
            self._data_writer.set_n_chips_in_graph(splitter_partitioner())

    def _execute_insert_chip_power_monitors(
            self, system_placements: Placements) -> None:
        """
        Run, time and log the InsertChipPowerMonitorsToGraphs if required.

        """
        with FecTimer("Insert chip power monitors", TimerWork.OTHER) as timer:
            if timer.skip_if_cfg_false("Reports", "write_energy_report"):
                return
            insert_chip_power_monitors_to_graphs(system_placements)

    @final
    def _execute_insert_extra_monitor_vertices(
            self, system_placements: Placements) -> None:
        """
        Run, time and log the InsertExtraMonitorVerticesToGraphs if required.
        """
        with FecTimer(
                "Insert extra monitor vertices", TimerWork.OTHER) as timer:
            if timer.skip_if_cfgs_false(
                    "Machine", "enable_advanced_monitor_support",
                    "enable_reinjection"):
                return
            # inserter checks for None app graph not an empty one
        gather_map, monitor_map = insert_extra_monitor_vertices_to_graphs(
            system_placements)
        self._data_writer.set_gatherer_map(gather_map)
        self._data_writer.set_monitor_map(monitor_map)

    def _report_partitioner(self) -> None:
        """
        Write, times and logs the partitioner_report if needed.
        """
        with FecTimer("Partitioner report", TimerWork.REPORT) as timer:
            if timer.skip_if_cfg_false("Reports", "write_partitioner_reports"):
                return
            partitioner_report()

    @property
    def get_number_of_available_cores_on_machine(self) -> int:
        """
        The number of available cores on the machine after taking
        into account preallocated resources.
        """
        machine = self._get_known_machine()
        # get cores of machine
        cores = machine.total_available_user_cores
        ethernets = len(machine.ethernet_connected_chips)
        cores -= ((machine.n_chips - ethernets) *
                  self._data_writer.get_all_monitor_cores())
        cores -= ethernets * self._data_writer.get_ethernet_monitor_cores()
        return cores

    def _execute_application_placer(
            self, system_placements: Placements) -> None:
        """
        Runs, times and logs the Application Placer.

        Sets the "placements" data

        .. note::
            Calling of this method is based on the configuration placer value
        """
        with FecTimer("Application Placer", TimerWork.OTHER):
            self._data_writer.set_placements(place_application_graph(
                system_placements))

    def _do_placer(self, system_placements: Placements) -> None:
        """
        Runs, times and logs one of the placers.

        Sets the "placements" data

        Which placer is run depends on the configuration placer value

        This method is the entry point for adding a new Placer

        :raise ConfigurationException:
            if the configuration place value is unexpected
        """
        name = get_config_str("Mapping", "placer")
        if name == "ApplicationPlacer":
            return self._execute_application_placer(system_placements)
        if "," in name:
            raise ConfigurationException(
                "Only a single algorithm is supported for placer")
        raise ConfigurationException(
            f"Unexpected cfg setting placer: {name}")

    def _do_write_metadata(self) -> None:
        """
        Do the various functions to write metadata to the SQLite files.
        """
        with FecTimer("Record vertex labels to database", TimerWork.REPORT):
            with BufferDatabase() as db:
                db.store_vertex_labels()

    @final
    def _execute_system_multicast_routing_generator(self) -> None:
        """
        Runs, times and logs the SystemMulticastRoutingGenerator if required.

        May sets the data "data_in_multicast_routing_tables",
        "data_in_multicast_key_to_chip_map" and
        "system_multicast_router_timeout_keys"
        """
        with FecTimer("System multicast routing generator",
                      TimerWork.OTHER) as timer:
            if timer.skip_if_cfgs_false(
                    "Machine", "enable_advanced_monitor_support",
                    "enable_reinjection"):
                return
            data = system_multicast_routing_generator()
            self._data_writer.set_system_multicast_routing_data(data)

    def _report_placements_with_application_graph(self) -> None:
        """
        Writes, times and logs the application graph placer report if
        requested.
        """
        if self._data_writer.get_n_vertices() == 0:
            return
        with FecTimer("Placements with application graph report",
                      TimerWork.REPORT) as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_application_graph_placer_report"):
                return
            placer_reports_with_application_graph()

    def _json_placements(self) -> None:
        """
        Does, times and logs the writing of placements as JSON if requested.
        """
        with FecTimer("Json placements", TimerWork.REPORT) as timer:
            if timer.skip_if_cfg_false("Reports", "write_json_placements"):
                return
            write_json_placements()

    @final
    def _execute_application_router(self) -> None:
        """
        Runs, times and logs the ApplicationRouter.

        Sets the "routing_table_by_partition" data if called

        .. note::
            Calling of this method is based on the configuration router value
        """
        with FecTimer("Application Router", TimerWork.RUNNING):
            self._data_writer.set_routing_table_by_partition(
                route_application_graph())

    @final
    def _do_routing(self) -> None:
        """
        Runs, times and logs one of the routers.

        Sets the "routing_table_by_partition" data

        Which router is run depends on the configuration router value

        This method is the entry point for adding a new Router

        :raise ConfigurationException:
            if the configuration router value is unexpected
        """
        name = get_config_str("Mapping", "router")
        if name == "ApplicationRouter":
            return self._execute_application_router()
        if "," in name:
            raise ConfigurationException(
                "Only a single algorithm is supported for router")
        raise ConfigurationException(
            f"Unexpected cfg setting router: {name}")

    def _execute_basic_tag_allocator(self) -> None:
        """
        Runs, times and logs the Tag Allocator.

        Sets the "tag" data
        """
        with FecTimer("Basic tag allocator", TimerWork.OTHER):
            self._data_writer.set_tags(basic_tag_allocator())

    def _report_tag_allocations(self) -> None:
        """
        Write, times and logs the tag allocator report if requested.
        """
        with FecTimer("Tag allocator report", TimerWork.REPORT) as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_tag_allocation_reports"):
                return
            tag_allocator_report()

    @final
    def _execute_global_allocate(
            self, extra_allocations: Iterable[
                Tuple[ApplicationVertex, str]]) -> None:
        """
        Runs, times and logs the Global Zoned Routing Info Allocator.

        Sets "routing_info" is called

        .. note::
            Calling of this method is based on the configuration
            info_allocator value
        """
        with FecTimer("Global allocate", TimerWork.OTHER):
            self._data_writer.set_routing_infos(
                global_allocate(extra_allocations))

    @final
    def _execute_flexible_allocate(
            self, extra_allocations: Iterable[
                Tuple[ApplicationVertex, str]]) -> None:
        """
        Runs, times and logs the Zoned Routing Info Allocator.

        Sets "routing_info" is called

        .. note::
            Calling of this method is based on the configuration
            info_allocator value
        """
        with FecTimer("Zoned routing info allocator", TimerWork.OTHER):
            self._data_writer.set_routing_infos(
                flexible_allocate(extra_allocations))

    @final
    def _do_info_allocator(self) -> None:
        """
        Runs, times and logs one of the info allocators.

        Sets the "routing_info" data

        Which allocator is run depends on the configuration info_allocator
        value.

        This method is the entry point for adding a new Info Allocator

        :raise ConfigurationException:
            if the configuration info_allocator value is unexpected
        """
        name = get_config_str("Mapping", "info_allocator")
        if name == "GlobalZonedRoutingInfoAllocator":
            return self._execute_global_allocate([])
        if name == "ZonedRoutingInfoAllocator":
            return self._execute_flexible_allocate([])
        if "," in name:
            raise ConfigurationException(
                "Only a single algorithm is supported for info_allocator")
        raise ConfigurationException(
            f"Unexpected cfg setting info_allocator: {name}")

    def _report_router_info(self) -> None:
        """
        Writes, times and logs the router info report if requested.
        """
        with FecTimer("Router info report", TimerWork.REPORT) as timer:
            if timer.skip_if_cfg_false("Reports", "write_router_info_report"):
                return
            routing_info_report([])

    @final
    def _execute_basic_routing_table_generator(self) -> None:
        """
        Runs, times and logs the Routing Table Generator.

        .. note::
            Currently no other Routing Table Generator supported.
            To add an additional Generator copy the pattern of do_placer
        """
        with FecTimer("Basic routing table generator", TimerWork.OTHER):
            self._data_writer.set_uncompressed(basic_routing_table_generator())

    @final
    def _execute_merged_routing_table_generator(self) -> None:
        """
        Runs, times and logs the Routing Table Generator.

        .. note::
            Currently no other Routing Table Generator supported.
            To add an additional Generator copy the pattern of do_placer
        """
        with FecTimer("Merged routing table generator", TimerWork.OTHER):
            self._data_writer.set_uncompressed(
                merged_routing_table_generator())

        # TODO Nuke ZonedRoutingTableGenerator

    @final
    def _do_routing_table_generator(self) -> None:
        """
        Runs, times and logs one of the routing table generators.

        Sets the "routing_info" data

        Which allocator is run depends on the configuration's
        `routing_table_generator` value.

        This method is the entry point for adding a new routing table
        generator.

        :raise ConfigurationException:
            if the configuration's `routing_table_generator` value is
            unexpected
        """
        name = get_config_str("Mapping", "routing_table_generator")
        if name == "BasicRoutingTableGenerator":
            return self._execute_basic_routing_table_generator()
        if name == "MergedRoutingTableGenerator":
            return self._execute_merged_routing_table_generator()
        if "," in name:
            raise ConfigurationException(
                "Only a single algorithm is supported for"
                " routing_table_generator")
        raise ConfigurationException(
            f"Unexpected cfg setting routing_table_generator: {name}")

    def _report_routers(self) -> None:
        """
        Write, times and logs the router report if requested.
        """
        with FecTimer("Router report", TimerWork.REPORT) as timer:
            if timer.skip_if_cfg_false("Reports", "write_router_reports"):
                return
        router_report_from_paths()

    def _report_router_summary(self) -> None:
        """
        Write, times and logs the router summary report if requested.
        """
        with FecTimer("Router summary report", TimerWork.REPORT) as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_router_summary_report"):
                return
            router_summary_report()

    def _json_routing_tables(self) -> None:
        """
        Write, time and log the routing tables as JSON if requested.
        """
        with FecTimer("Json routing tables", TimerWork.REPORT) as timer:
            if timer.skip_if_cfg_false("Reports", "write_json_routing_tables"):
                return
            write_json_routing_tables(self._data_writer.get_uncompressed())
            # Output ignored as never used

    def _report_drift(self, start: bool) -> None:
        """
        Write, time and log the inter-board timer drift.

        :param start: Is this the start or the end
        """
        with FecTimer("Drift report", TimerWork.REPORT) as timer:
            if timer.skip_if_virtual_board():
                return
            if start and timer.skip_if_cfg_false(
                    "Reports", "write_drift_report_start"):
                return
            if not start and timer.skip_if_cfg_false(
                    "Reports", "write_drift_report_end"):
                return
            drift_report()

    @final
    def _execute_locate_executable_start_type(self) -> None:
        """
        Runs, times and logs LocateExecutableStartType if required.

        May set the executable_types data.
        """
        with FecTimer("Locate executable start type", TimerWork.OTHER):
            binary_start_types = locate_executable_start_type()
            self._data_writer.set_executable_types(binary_start_types)
            if get_config_bool("Buffers", "use_auto_pause_and_resume"):
                # Disable auto pause and resume if the binary can't do it
                for executable_type in binary_start_types:
                    if not executable_type.supports_auto_pause_and_resume:
                        logger.warning(
                            "Disabling auto pause resume as graph includes {}",
                            executable_type)
                        set_config("Buffers",
                                   "use_auto_pause_and_resume", "False")
                        break

    @final
    def _execute_buffer_manager_creator(self) -> None:
        """
        Run, times and logs the buffer manager creator if required.

        May set the buffer_manager data
        """
        if self._data_writer.has_buffer_manager():
            return
        with FecTimer("Buffer manager creator", TimerWork.OTHER) as timer:
            if timer.skip_if_virtual_board():
                return

            self._data_writer.set_buffer_manager(BufferManager())

    def _execute_sdram_outgoing_partition_allocator(self) -> None:
        """
        Runs, times and logs the SDRAMOutgoingPartitionAllocator.
        """
        with FecTimer("SDRAM outgoing partition allocator", TimerWork.OTHER):
            sdram_outgoing_partition_allocator()

    def _execute_control_sync(self, do_sync: bool) -> None:
        """
        Control synchronisation on board.

        :param do_sync: Whether to enable synchronisation
        """
        with FecTimer("Control Sync", TimerWork.CONTROL) as timer:
            if timer.skip_if_virtual_board():
                return
            self._data_writer.get_transceiver().control_sync(do_sync)

    def _do_mapping(self, total_run_time: Optional[float],
                    n_machine_time_steps: Optional[int]) -> None:
        """
        Runs, times and logs all the algorithms in the mapping stage.
        """
        FecTimer.start_category(TimerCategory.MAPPING)
        if self._data_writer.is_soft_reset():
            # wipe out stuff associated with past mapping
            self._hard_reset()
        self._add_dependent_verts_and_edges_for_application_graph()

        self._setup_java_caller()
        self._do_extra_mapping_algorithms()
        self._report_network_specification()

        self._execute_splitter_reset()
        self._execute_splitter_selector()
        self._execute_delay_support_adder()

        self._execute_splitter_partitioner()
        self._get_known_machine(total_run_time)
        self._json_machine()
        self._report_board_chip()

        system_placements = Placements()
        self._add_commands_to_command_sender(system_placements)
        self._execute_split_lpg_vertices(system_placements)
        self._execute_insert_chip_power_monitors(system_placements)
        self._execute_insert_extra_monitor_vertices(system_placements)

        self._report_partitioner()
        self._do_placer(system_placements)
        self._report_placements_with_application_graph()
        self._json_placements()

        self._execute_system_multicast_routing_generator()
        self._do_routing()

        self._execute_basic_tag_allocator()
        self._report_tag_allocations()

        self._do_info_allocator()
        self._report_router_info()
        self._do_routing_table_generator()
        self._report_uncompressed_routing_table()
        self._check_uncompressed_routing_table()
        self._report_routers()
        self._report_router_summary()
        self._json_routing_tables()
        self._execute_locate_executable_start_type()
        self._execute_buffer_manager_creator()

        self._deduce_data_n_timesteps(n_machine_time_steps)
        FecTimer.end_category(TimerCategory.MAPPING)

    # Overridden by spy which adds placement_order
    def _execute_graph_data_specification_writer(self) -> None:
        """
        Runs, times, and logs the GraphDataSpecificationWriter.

        Creates and fills the data spec database
        """
        with FecTimer("Graph data specification writer", TimerWork.OTHER):
            self._data_writer.set_ds_database_path(
                graph_data_specification_writer())

    def _do_data_generation(self) -> None:
        """
        Runs, Times and logs the data generation.
        """
        self._execute_sdram_outgoing_partition_allocator()
        self._execute_graph_data_specification_writer()

    def _execute_reset_routing(self) -> None:
        """
        Runs, times and logs the resetting of routing if required.
        """
        if self._multicast_routes_loaded:
            return
        with FecTimer("Reset routing", TimerWork.LOADING) as timer:
            if timer.skip_if_virtual_board():
                return
            progress = ProgressBar(1, "Resetting Routing")
            FecDataView().get_transceiver().reset_routing()
            progress.update()
            progress.end()

    def _execute_graph_binary_gatherer(self) -> None:
        """
        Runs, times and logs the GraphBinaryGatherer if required.
        """
        with FecTimer("Graph binary gatherer", TimerWork.OTHER) as timer:
            try:
                self._data_writer.set_executable_targets(
                    graph_binary_gatherer())
            except KeyError:
                if get_config_bool("Machine", "virtual_board"):
                    # Github actions have no binaries
                    logger.warning(
                        "Ignoring executable not found as using virtual")
                    timer.error("executable not found and virtual board")
                    return
                raise

    @final
    def _execute_ordered_covering_compressor(self) -> MulticastRoutingTables:
        """
        Runs, times and logs the OrderedCoveringCompressor.

        .. note::
            Calling of this method is based on the configuration compressor or
            virtual_compressor value

        :return: Compressed routing tables
        """
        with FecTimer("Ordered covering compressor", TimerWork.OTHER) as timer:
            self._multicast_routes_loaded = False
            precompressed = self._data_writer.get_precompressed()
            if self._compression_skipable(precompressed):
                timer.skip("Tables already small enough")
                return precompressed
            return ordered_covering_compressor()

    @final
    def _execute_ordered_covering_compression(self) -> Optional[
            MulticastRoutingTables]:
        """
        Runs, times and logs the ordered covering compressor on machine.

        .. note::
            Calling of this method is based on the configuration compressor or
            virtual_compressor value
        """
        with FecTimer("Ordered covering compressor",
                      TimerWork.COMPRESSING) as timer:
            if timer.skip_if_virtual_board():
                return None
            precompressed = self._data_writer.get_precompressed()
            if self._compression_skipable(precompressed):
                timer.skip("Tables already small enough")
                self._multicast_routes_loaded = False
                return precompressed
            ordered_covering_compression()
            self._multicast_routes_loaded = True
            return None

    @final
    def _execute_pair_compressor(self) -> MulticastRoutingTables:
        """
        Runs, times and logs the PairCompressor.

        .. note::
            Calling of this method is based on the configuration compressor or
            virtual_compressor value

        :return: Compressed routing table
        """
        with FecTimer("Pair compressor", TimerWork.OTHER) as timer:
            precompressed = self._data_writer.get_precompressed()
            self._multicast_routes_loaded = False
            if self._compression_skipable(precompressed):
                timer.skip("Tables already small enough")
                return precompressed
            return pair_compressor()

    @final
    def _execute_pair_compression(self) -> Optional[MulticastRoutingTables]:
        """
        Runs, times and logs the pair compressor on machine.

        .. note::
            Calling of this method is based on the configuration compressor or
            virtual_compressor value
        """
        with FecTimer("Pair on chip router compression",
                      TimerWork.COMPRESSING) as timer:
            if timer.skip_if_virtual_board():
                return None
            precompressed = self._data_writer.get_precompressed()
            if self._compression_skipable(precompressed):
                timer.skip("Tables already small enough")
                self._multicast_routes_loaded = False
                return precompressed
            pair_compression()
            self._multicast_routes_loaded = True
            return None

    @final
    def _execute_pair_unordered_compressor(self) -> MulticastRoutingTables:
        """
        Runs, times and logs the CheckedUnorderedPairCompressor.

        .. note::
            Calling of this method is based on the configuration compressor or
            virtual_compressor value

        :return: compressed routing tables
        """
        with FecTimer("Pair unordered compressor", TimerWork.OTHER) as timer:
            self._multicast_routes_loaded = False
            precompressed = self._data_writer.get_precompressed()
            if self._compression_skipable(precompressed):
                timer.skip("Tables already small enough")
                return precompressed
            return pair_compressor(ordered=False)

    def _compressor_name(self) -> Tuple[str, bool]:
        if get_config_bool("Machine", "virtual_board"):
            name = get_config_str_or_none("Mapping", "virtual_compressor")
            if name is None:
                logger.info("As no virtual_compressor specified "
                            "using compressor setting")
                name = get_config_str("Mapping", "compressor")
        else:
            name = get_config_str("Mapping", "compressor")
        pre_compress = "BitField" not in name
        return name, pre_compress

    def _compression_skipable(self, tables: MulticastRoutingTables) -> bool:
        if get_config_bool(
                "Mapping", "router_table_compress_as_far_as_possible"):
            return False
        machine = self._get_known_machine()
        return (tables.get_max_number_of_entries()
                <= machine.min_n_router_enteries)

    def _execute_pre_compression(self, pre_compress: bool) -> None:
        name = get_config_str_or_none("Mapping", "precompressor")
        if not pre_compress or name is None:
            # Declare the precompressed data to be the uncompressed data
            self._data_writer.set_precompressed(
                self._data_writer.get_uncompressed())
            return
        elif name != "Ranged":
            raise ConfigurationException(
                f"Unexpected cfg setting precompressor: {name}")

        with FecTimer("Ranged Compressor", TimerWork.OTHER) as timer:
            if self._compression_skipable(
                    self._data_writer.get_uncompressed()):
                timer.skip("Tables already small enough")
                self._data_writer.set_precompressed(
                    self._data_writer.get_uncompressed())
                return
            self._data_writer.set_precompressed(range_compressor())

    def _do_early_compression(self, name: str) -> Optional[
            MulticastRoutingTables]:
        """
        Calls a compressor based on the name provided.

        .. note::
            This method is the entry point for adding a new compressor that
             can or must run early.

        :param name: Name of a compressor
        :return: CompressedRoutingTables (likely to be `None)`,
            RouterCompressorProvenanceItems (may be an empty list)
        :raise ConfigurationException: if the name is not expected
        """
        if name == "OrderedCoveringCompressor":
            return self._execute_ordered_covering_compressor()
        elif name == "OrderedCoveringOnChipRouterCompression":
            return self._execute_ordered_covering_compression()
        elif name == "PairCompressor":
            return self._execute_pair_compressor()
        elif name == "PairOnChipRouterCompression":
            return self._execute_pair_compression()
        elif name == "PairUnorderedCompressor":
            return self._execute_pair_unordered_compressor()

        # delay compression until later
        return None

    @final
    def _execute_load_routing_tables(
            self, compressed: Optional[MulticastRoutingTables]) -> None:
        """
        Runs, times and logs the RoutingTableLoader if required.
        """
        if not compressed:
            return
        with FecTimer("Routing table loader", TimerWork.LOADING) as timer:
            self._multicast_routes_loaded = True
            if timer.skip_if_virtual_board():
                return
            routing_table_loader(compressed)

    def _report_uncompressed_routing_table(self) -> None:
        """
        Runs, times and logs the router report from router tables if requested.
        """
        with FecTimer("Uncompressed routing table report",
                      TimerWork.REPORT) as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_uncompressed"):
                return
            router_report_from_router_tables()

    def _check_uncompressed_routing_table(self) -> None:
        """
        Runs, times and logs the checking of uncompressed table
        """
        with FecTimer("Validating Uncompressed routing table",
                      TimerWork.REPORT) as timer:
            if timer.skip_if_cfg_false(
                   "Mapping", "validate_routes_uncompressed"):
                return
            validate_routes(self._data_writer.get_uncompressed())

    def _report_bit_field_compressor(self) -> None:
        """
        Runs, times and logs the BitFieldCompressorReport if requested.
        """
        with FecTimer("Bitfield compressor report", TimerWork.REPORT) as timer:
            if timer.skip_if_cfg_false(
                    "Reports",  "write_bit_field_compressor_report"):
                return
            # BitFieldSummary output ignored as never used
            bitfield_compressor_report()

    def _execute_fixed_routes(self) -> None:
        """
        Runs, times and logs Load Fixed Routes if required.
        """
        with FecTimer("Fixed routes", TimerWork.LOADING) as timer:
            if timer.skip_if_cfg_false(
                    "Machine", "enable_advanced_monitor_support"):
                return
            if not self._data_writer.has_fixed_routes():
                self._data_writer.set_fixed_routes(fixed_route_router(
                    DataSpeedUpPacketGatherMachineVertex))
            if not get_config_bool("Machine", "virtual_board"):
                load_fixed_routes()
                if get_config_bool("Reports", "write_fixed_routes_report"):
                    fixed_route_from_machine_report()

    def _execute_load_system_data_specification(self) -> None:
        """
        Runs, times and logs the load_system_data_specs if required.
        """
        with FecTimer(
                "Load system data specification", TimerWork.OTHER) as timer:
            if timer.skip_if_virtual_board():
                return
            load_system_data_specs()

    def _execute_load_system_executable_images(self) -> None:
        """
        Runs, times and logs the loading of executable images.
        """
        with FecTimer(
                "Load executable system Images", TimerWork.LOADING) as timer:
            if timer.skip_if_virtual_board():
                return
            load_sys_images()

    def _execute_load_application_data_specification(self) -> None:
        """
        Runs, times and logs :py:meth:`load_application_data_specs`
        if required.
        """
        with FecTimer("Load Application data specification",
                      TimerWork.LOADING_DATA) as timer:
            if timer.skip_if_virtual_board():
                return
            return load_application_data_specs()

    def _execute_tags_from_machine_report(self) -> None:
        """
        Run, times and logs the TagsFromMachineReport if requested.
        """
        with FecTimer(
                "Tags from machine report", TimerWork.EXTRACTING) as timer:
            if timer.skip_if_virtual_board():
                return
            if timer.skip_if_cfg_false(
                    "Reports", "write_tag_allocation_reports"):
                return
            tags_from_machine_report()

    def _execute_load_tags(self) -> None:
        """
        Runs, times and logs the Tags Loader if required.
        """
        # TODO why: if graph_changed or data_changed:
        with FecTimer("Tags Loader", TimerWork.LOADING) as timer:
            if timer.skip_if_virtual_board():
                return
            tags_loader()

    def _do_extra_load_algorithms(self) -> None:
        """
        Runs, times and logs any extra load algorithms.
        """

    def _report_memory_on_host(self) -> None:
        """
        Runs, times and logs MemoryMapOnHostReport if requested.
        """
        with FecTimer("Memory report", TimerWork.REPORT) as timer:
            if timer.skip_if_virtual_board():
                return
            if timer.skip_if_cfg_false(
                    "Reports", "write_memory_map_report"):
                return
            memory_map_on_host_report()

    def _report_memory_on_chip(self) -> None:
        """
        Runs, times and logs MemoryMapOnHostChipReport if requested.
        """
        with FecTimer("Memory report", TimerWork.REPORT) as timer:
            if timer.skip_if_virtual_board():
                return
            if timer.skip_if_cfg_false(
                    "Reports", "write_memory_map_report"):
                return
            memory_map_on_host_chip_report()

    # TODO consider different cfg flags
    def _report_compressed(self, compressed: Optional[
            MulticastRoutingTables]) -> None:
        """
        Runs, times and logs the compressor reports if requested.
        """
        with FecTimer("Compressor report", TimerWork.REPORT) as timer:
            if timer.skip_all_cfgs_false(
                    [("Reports", "write_compressed"),
                     ("Reports", "write_compression_comparison"),
                     ("Reports", "write_compression_summary"),
                     ("Mapping", "run_compression_checker")],
                    "No reports need compressed routing tables"):
                return

            if compressed is None:
                if timer.skip_if_virtual_board():
                    return
                compressed = read_routing_tables_from_machine()

            if get_config_bool("Reports", "write_compressed"):
                router_report_from_compressed_router_tables(compressed)
            if get_config_bool("Reports", "write_compression_comparison"):
                generate_comparison_router_report(compressed)
            if get_config_bool("Reports", "write_compression_summary"):
                router_compressed_summary_report(compressed)
            if get_config_bool("Mapping", "run_compression_checker"):
                routing_tables = self._data_writer.get_uncompressed()
                generate_routing_compression_checker_report(
                    routing_tables, compressed)

    def _execute_application_load_executables(self) -> None:
        """
        Algorithms needed for loading the binaries to the SpiNNaker machine.
        """
        with FecTimer("Load executable app images",
                      TimerWork.LOADING) as timer:
            if timer.skip_if_virtual_board():
                return
            load_app_images()

    def _do_load(self) -> None:
        """
        Runs, times and logs the load algorithms.
        """
        FecTimer.start_category(TimerCategory.LOADING)

        if self._data_writer.get_requires_mapping():
            self._execute_reset_routing()
            self._execute_graph_binary_gatherer()
        # loading_algorithms
        compressor, pre_compress = self._compressor_name()
        self._execute_pre_compression(pre_compress)
        compressed = self._do_early_compression(compressor)

        self._do_data_generation()

        self._execute_control_sync(False)
        if self._data_writer.get_requires_mapping():
            self._execute_fixed_routes()
        self._execute_load_system_data_specification()
        self._execute_load_system_executable_images()
        self._execute_load_tags()
        self._execute_load_application_data_specification()

        self._do_extra_load_algorithms()
        self._execute_load_routing_tables(compressed)
        self._report_bit_field_compressor()

        # TODO Was master correct to run the report first?
        self._execute_tags_from_machine_report()
        if self._data_writer.get_requires_mapping():
            self._report_memory_on_host()
            self._report_memory_on_chip()
            self._report_compressed(compressed)
        self._execute_application_load_executables()
        self._execute_router_provenance_gatherer("Load", TimerWork.LOADING)

        FecTimer.end_category(TimerCategory.LOADING)

    def _report_sdram_usage_per_chip(self) -> None:
        # TODO why in do run
        with FecTimer("Sdram usage per chip report",
                      TimerWork.REPORT) as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_sdram_usage_report_per_chip"):
                return
            sdram_usage_report_per_chip()

    def _execute_dsg_region_reloader(self) -> None:
        """
        Runs, times and logs the DSGRegionReloader if required.

        Reload any parameters over the loaded data if we have already
        run and not using a virtual board and the data hasn't already
        been regenerated
        """
        if not self._data_writer.is_ran_ever():
            return
        if self._data_writer.is_hard_reset():
            return
        with FecTimer("DSG region reloader", TimerWork.LOADING) as timer:
            if timer.skip_if_virtual_board():
                return
            reload_dsg_regions()

    def _execute_graph_provenance_gatherer(self) -> None:
        """
        Runs, times and log the GraphProvenanceGatherer if requested.
        """
        with FecTimer("Graph provenance gatherer", TimerWork.OTHER) as timer:
            if timer.skip_if_cfg_false("Reports",
                                       "read_graph_provenance_data"):
                return
            graph_provenance_gatherer()

    def _execute_placements_provenance_gatherer(self) -> None:
        """
        Runs, times and log the PlacementsProvenanceGatherer if requested.
        """
        with FecTimer(
                "Placements provenance gatherer", TimerWork.OTHER) as timer:
            if timer.skip_if_cfg_false("Reports",
                                       "read_placements_provenance_data"):
                return
            if timer.skip_if_virtual_board():
                return
            try:
                # Also used in recover from error
                placements_provenance_gatherer(
                    self._data_writer.get_n_placements(),
                    self._data_writer.iterate_placemements())
            except DataNotYetAvialable as ex:
                timer.skip(str(ex))
                return

    def _execute_router_provenance_gatherer(
            self, prefix: str, phase: TimerWork) -> None:
        """
        Runs, times and log the RouterProvenanceGatherer if requested.
        """
        with FecTimer(
                "Router provenance gatherer", phase) as timer:
            if timer.skip_if_cfg_false("Reports",
                                       "read_router_provenance_data"):
                return
            if timer.skip_if_virtual_board():
                return
            try:
                router_provenance_gatherer(prefix)
            except DataNotYetAvialable as ex:
                timer.skip(str(ex))
                return

    def _execute_profile_data_gatherer(self) -> None:
        """
        Runs, times and logs the ProfileDataGatherer if requested.
        """
        with FecTimer("Profile data gatherer", TimerWork.EXTRACTING) as timer:
            if timer.skip_if_cfg_false("Reports", "read_profile_data"):
                return
            if timer.skip_if_virtual_board():
                return
            try:
                profile_data_gatherer()
            except DataNotYetAvialable as ex:
                timer.skip(str(ex))
                return

    def _do_read_provenance(self) -> None:
        """
        Runs, times and log the methods that gather provenance.
        """
        self._execute_graph_provenance_gatherer()
        self._execute_placements_provenance_gatherer()
        self._execute_profile_data_gatherer()

    def _report_energy(self) -> None:
        """
        Runs, times and logs the energy report if requested.
        """
        with FecTimer("Energy report", TimerWork.REPORT) as timer:
            if timer.skip_if_cfg_false("Reports", "write_energy_report"):
                return
            if timer.skip_if_virtual_board():
                return

            power_used = compute_energy_used()

            energy_provenance_reporter(power_used)

            # create energy reporter
            energy_reporter = EnergyReport()
            # run energy report
            energy_reporter.write_energy_report(power_used)

    def _do_provenance_reports(self) -> None:
        """
        Runs any reports based on provenance.
        """

    def _execute_clear_router_diagnostic_counters(self) -> None:
        """
        Runs, times and logs the clear_router_diagnostic_counters if required.
        """
        with FecTimer("Clear Router Diagnostic Counters",
                      TimerWork.CONTROL) as timer:
            if timer.skip_if_virtual_board():
                return
            transceiver = FecDataView().get_transceiver()
            transceiver.clear_router_diagnostic_counters()

    def _execute_clear_io_buf(self) -> None:
        """
        Runs, times and logs the ChipIOBufClearer if required.
        """
        if self._data_writer.get_current_run_timesteps() is None:
            return
        with FecTimer("Clear IO buffer", TimerWork.CONTROL) as timer:
            if timer.skip_if_virtual_board():
                return
            # TODO Why check empty_graph is always false??
            if timer.skip_if_cfg_false("Reports", "clear_iobuf_during_run"):
                return
            chip_io_buf_clearer()

    def _execute_runtime_update(self, n_sync_steps: int) -> None:
        """
        Runs, times and logs the runtime updater if required.

        :param n_sync_steps:
            The number of timesteps between synchronisations
        """
        with FecTimer("Runtime Update", TimerWork.LOADING) as timer:
            if timer.skip_if_virtual_board():
                return
            if (ExecutableType.USES_SIMULATION_INTERFACE in
                    self._data_writer.get_executable_types()):
                chip_runtime_updater(n_sync_steps)
            else:
                timer.skip("No Simulation Interface used")

    def _execute_create_database_interface(
            self, run_time: Optional[float]) -> None:
        """
        Runs, times and logs Database Interface Creator.

        Sets the _database_file_path data object

        :param run_time: the run duration in milliseconds.
        """
        with FecTimer("Create database interface", TimerWork.OTHER):
            # Used to used compressed routing tables if available on host
            # TODO consider not saving router tables.
            self._data_writer.set_database_file_path(
                database_interface(run_time))

    def _execute_create_notifiaction_protocol(self) -> None:
        """
        Runs, times and logs the creation of the Notification Protocol.

        Sets the notification_interface data object
        """
        with FecTimer("Create notification protocol", TimerWork.OTHER):
            self._data_writer.set_notification_protocol(
                create_notification_protocol())

    def _execute_runner(
            self, n_sync_steps: int, run_time: Optional[float]) -> None:
        """
        Runs, times and logs the ApplicationRunner.

        :param n_sync_steps:
            The number of timesteps between synchronisations
        :param run_time: the run duration in milliseconds.
        """
        with FecTimer(FecTimer.APPLICATION_RUNNER, TimerWork.RUNNING) as timer:
            if timer.skip_if_virtual_board():
                return
            # Don't timeout if a stepped mode is in operation
            if n_sync_steps:
                time_threshold = None
            else:
                time_threshold = get_config_int(
                    "Machine", "post_simulation_overrun_before_error")
            latest_runtime = application_runner(
                run_time, time_threshold, self._run_until_complete,
                self._state_condition)
            if latest_runtime is not None:
                self._data_writer.set_current_run_timesteps(latest_runtime)

    def _execute_extract_iobuff(self) -> None:
        """
        Runs, times and logs the ChipIOBufExtractor if required.
        """
        with FecTimer("Extract IO buff", TimerWork.EXTRACTING) as timer:
            if timer.skip_if_virtual_board():
                return
            if timer.skip_if_cfg_false("Reports", "extract_iobuf"):
                return
            # ErrorMessages, WarnMessages output ignored as never used!
            chip_io_buf_extractor()

    def _execute_buffer_extractor(self) -> None:
        """
        Runs, times and logs the BufferExtractor if required.
        """
        with FecTimer("Buffer extractor", TimerWork.EXTRACT_DATA) as timer:
            if timer.skip_if_virtual_board():
                return
            bm = self._data_writer.get_buffer_manager()
            bm.extract_data()

    def _do_extract_from_machine(self) -> None:
        """
        Runs, times and logs the steps to extract data from the machine.
        """
        self._execute_router_provenance_gatherer("Run", TimerWork.EXTRACTING)
        self._execute_clear_router_diagnostic_counters()
        self._execute_extract_iobuff()
        self._execute_buffer_extractor()
        self._execute_clear_io_buf()
        self._execute_router_provenance_gatherer(
            "Extract", TimerWork.EXTRACTING)

        self._do_read_provenance()
        self._report_energy()
        self._do_provenance_reports()

    def __do_run(
            self, n_machine_time_steps: Optional[int],
            n_sync_steps: int) -> None:
        """
        Runs, times and logs the do run steps.

        :param n_machine_time_steps: Number of timesteps run
        :param n_sync_steps:
            The number of timesteps between synchronisations
        """
        # TODO virtual board
        FecTimer.start_category(TimerCategory.RUN_LOOP)
        run_time = None
        if n_machine_time_steps is not None:
            run_time = (n_machine_time_steps *
                        self._data_writer.get_simulation_time_step_ms())
        self._data_writer.increment_current_run_timesteps(
            n_machine_time_steps)

        self._report_sdram_usage_per_chip()
        self._report_drift(start=True)
        if self._data_writer.get_requires_mapping():
            self._execute_create_database_interface(run_time)
        self._execute_create_notifiaction_protocol()
        if (self._data_writer.is_ran_ever() and
                not self._data_writer.get_requires_mapping() and
                not self._data_writer.get_requires_data_generation()):
            self._execute_dsg_region_reloader()
        self._execute_runtime_update(n_sync_steps)
        self._execute_runner(n_sync_steps, run_time)
        self._do_extract_from_machine()
        # reset at the end of each do_run cycle
        self._report_drift(start=False)
        self._execute_control_sync(True)
        FecTimer.end_category(TimerCategory.RUN_LOOP)

    def _do_run(
            self, n_machine_time_steps: Optional[int],
            n_sync_steps: int) -> None:
        """
        Runs, times and logs the do run steps.

        :param n_machine_time_steps: Number of timesteps run
        :param n_sync_steps:
            The number of timesteps between synchronisations
        """
        try:
            self.__do_run(n_machine_time_steps, n_sync_steps)
        except KeyboardInterrupt:
            logger.error("User has aborted the simulation")
            self._shutdown()
            sys.exit(1)
        except Exception as run_e:
            self._recover_from_error(run_e)

            # re-raise exception
            raise run_e

    def _recover_from_error(self, exception: Exception) -> None:
        try:
            self.__recover_from_error(exception)
        except Exception as rec_e:
            logger.exception(
                f"Error {rec_e} when attempting to recover from error")

    def __recover_from_error(self, exception: Exception) -> None:
        # if exception has an exception, print to system
        logger.error("An error has occurred during simulation")
        # Print the detail including the traceback
        logger.error(exception)

        logger.info("\n\nAttempting to extract data\n\n")

        # Extract router provenance
        try:
            router_provenance_gatherer()
        except Exception:
            logger.exception("Error reading router provenance")

        # Find the cores that are not in an expected state
        unsuccessful_cores = CPUInfos()
        if isinstance(exception, SpiNNManCoresNotInStateException):
            unsuccessful_cores = exception.failed_core_states()

        # If there are no cores in a bad state, find those not yet in
        # their finished state
        transceiver = self._data_writer.get_transceiver()
        if not unsuccessful_cores:
            for executable_type, core_subsets in \
                    self._data_writer.get_executable_types().items():
                unsuccessful_cores = transceiver.get_cpu_infos(
                    core_subsets, executable_type.end_state, False)

        # Print the details of error cores
        logger.error(unsuccessful_cores.get_status_string())

        # Find the cores that are not in RTE i.e. that can still be read
        non_rte_cores = unsuccessful_cores.infos_not_in_states(
            [CPUState.RUN_TIME_EXCEPTION, CPUState.WATCHDOG])

        # If there are any cores that are not in RTE, extract data from them
        if (non_rte_cores and
                ExecutableType.USES_SIMULATION_INTERFACE in
                self._data_writer.get_executable_types()):
            non_rte_core_subsets = CoreSubsets()
            for (x, y, p) in non_rte_cores:
                non_rte_core_subsets.add_processor(x, y, p)

            # Attempt to force the cores to write provenance and exit
            try:
                chip_provenance_updater(non_rte_core_subsets)
            except Exception:
                logger.exception("Could not update provenance on chip")

            # Extract any written provenance data
            try:
                transceiver = self._data_writer.get_transceiver()
                finished_cores = transceiver.get_cpu_infos(
                    non_rte_core_subsets, CPUState.FINISHED, True)
                finished_placements = Placements()
                for (x, y, p) in finished_cores:
                    try:
                        placement = self._data_writer.\
                            get_placement_on_processor(x, y, p)
                        finished_placements.add_placement(placement)
                    except Exception:   # pylint: disable=broad-except
                        pass  # already recovering from error
                placements_provenance_gatherer(
                    finished_placements.n_placements,
                    finished_placements.placements)
            except Exception as pro_e:
                logger.exception(f"Could not read provenance due to {pro_e}")

        # Read IOBUF where possible (that should be everywhere)
        iobuf = IOBufExtractor()
        try:
            errors, warnings = iobuf.extract_iobuf()
        except Exception:
            logger.exception("Could not get iobuf")
            errors, warnings = [], []

        # Print the IOBUFs
        self._print_iobuf(errors, warnings)

    @staticmethod
    def _print_iobuf(errors: Iterable[str], warnings: Iterable[str]) -> None:
        for warning in warnings:
            logger.warning(warning)
        for error in errors:
            logger.error(error)

    def reset(self) -> None:
        """
        Puts the simulation back at time zero.
        """
        FecTimer.start_category(TimerCategory.RESETTING)
        if not self._data_writer.is_ran_last():
            if not self._data_writer.is_ran_ever():
                logger.error("Ignoring the reset before the run")
            else:
                logger.error("Ignoring the repeated reset call")
            return

        logger.info("Resetting")

        if self._data_writer.get_user_accessed_machine():
            logger.warning(
                "A reset after a get machine call is always hard and "
                "therefore the previous machine is no longer valid")
            self._hard_reset()
        else:
            self._data_writer.soft_reset()

        # rewind the buffers from the buffer manager, to start at the beginning
        # of the simulation again and clear buffered out
        if self._data_writer.has_buffer_manager():
            self._data_writer.get_buffer_manager().reset()

        # Reset the graph off the machine, to set things to time 0
        self.__reset_graph_elements()
        FecTimer.end_category(TimerCategory.RESETTING)

    def __repr__(self) -> str:
        if self._data_writer.has_ipaddress():
            return (f"general front end instance for machine "
                    f"{self._data_writer.get_ipaddress()}")
        else:
            return "general front end instance no machine set"

    def _shutdown(self) -> None:
        # if stopping on machine, clear IP tags and routing table
        self.__clear()

        super()._shutdown()
        self._data_writer.clear_notification_protocol()
        FecTimer.stop_category_timing()

    def __clear(self) -> None:
        if not self._data_writer.has_transceiver():
            return
        transceiver = self._data_writer.get_transceiver()

        if get_config_bool("Machine", "clear_tags"):
            for ip_tag in self._data_writer.get_tags().ip_tags:
                transceiver.clear_ip_tag(
                    ip_tag.tag, board_address=ip_tag.board_address)
            for reverse_ip_tag in self._data_writer.get_tags().reverse_ip_tags:
                transceiver.clear_ip_tag(
                    reverse_ip_tag.tag,
                    board_address=reverse_ip_tag.board_address)

        # if clearing routing table entries, clear
        if get_config_bool("Machine", "clear_routing_tables"):
            transceiver.clear_multicast_routes()

    def stop(self) -> None:
        """
        End running of the simulation.
        """
        self._data_writer.stopping()
        FecTimer.start_category(TimerCategory.SHUTTING_DOWN)
        # If we have run forever, stop the binaries

        try:
            if (self._data_writer.is_ran_ever()
                    and self._data_writer.get_current_run_timesteps() is None
                    and not get_config_bool("Machine", "virtual_board")
                    and not self._run_until_complete):
                self._do_stop_workflow()
            elif get_config_bool("Reports", "read_provenance_data_on_end"):
                self._do_read_provenance()
            self._stop_remove_data()

        except Exception as e:
            self._recover_from_error(e)
            self._data_writer.write_errored_file(str(e))
            raise
        finally:
            # shut down the machine properly
            self._shutdown()

        self._data_writer.write_finished_file()
        # No matching FecTimer.end_category as shutdown stops timer

    def _execute_application_finisher(self) -> None:
        with FecTimer("Application finisher", TimerWork.CONTROL):
            application_finisher()

    def _do_stop_workflow(self) -> None:
        self._execute_application_finisher()
        self._do_extract_from_machine()

    def stop_run(self) -> None:
        """
        Request that the current infinite run stop.

        .. note::
            This will need to be called from another thread as the infinite
            run call is blocking.

        :raises SpiNNUtilsException:
            If the stop_run was not expected in the current state.
        """
        # Do not do start category here
        # as called from a different thread while running
        if self._data_writer.is_stop_already_requested():
            logger.warning("Second Request to stop_run ignored")
            return
        with self._state_condition:
            self._data_writer.request_stop()
            self._state_condition.notify_all()

    def continue_simulation(self) -> None:
        """
        Continue a simulation that has been started in stepped mode.
        """
        sync_signal = self._data_writer.get_next_sync_signal()
        transceiver = self._data_writer.get_transceiver()
        transceiver.send_signal(self._data_writer.get_app_id(), sync_signal)

    @staticmethod
    def __reset_object(obj: Any) -> None:
        # Reset an object if appropriate
        if isinstance(obj, AbstractCanReset):
            obj.reset_to_first_timestep()

    def __reset_graph_elements(self) -> None:
        # Reset any object that can reset
        for vertex in self._data_writer.iterate_vertices():
            self.__reset_object(vertex)
        for p in self._data_writer.iterate_partitions():
            for edge in p.edges:
                self.__reset_object(edge)

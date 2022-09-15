# Copyright (c) 2017-2022 The University of Manchester
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
"""
main interface for the SpiNNaker tools
"""
import logging
import math
import os
import signal
import sys
import threading
from threading import Condition
from numpy import __version__ as numpy_version

from spinn_utilities import __version__ as spinn_utils_version
from spinn_utilities.config_holder import (
    get_config_bool, get_config_int, get_config_str, set_config)
from spinn_utilities.log import FormatAdapter
from spinn_utilities.timer import Timer

from spinn_machine import __version__ as spinn_machine_version
from spinn_machine import CoreSubsets, Machine

from spinnman import __version__ as spinnman_version
from spinnman.exceptions import SpiNNManCoresNotInStateException
from spinnman.model.cpu_infos import CPUInfos
from spinnman.model.enums.cpu_state import CPUState

from data_specification import __version__ as data_spec_version

from spalloc import __version__ as spalloc_version

from pacman import __version__ as pacman_version
from pacman.model.graphs.application import ApplicationEdge
from pacman.model.graphs import AbstractVirtual
from pacman.model.partitioner_splitters.splitter_reset import splitter_reset
from pacman.model.placements import Placements
from pacman.operations.fixed_route_router import fixed_route_router
from pacman.operations.partition_algorithms import splitter_partitioner
from pacman.operations.placer_algorithms import place_application_graph
from pacman.operations.router_algorithms import (
    basic_dijkstra_routing, ner_route, ner_route_traffic_aware,
    route_application_graph)
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
from spinn_front_end_common.data import FecTimer
from spinn_front_end_common.interface.config_handler import ConfigHandler
from spinn_front_end_common.interface.interface_functions import (
    application_finisher, application_runner, buffer_extractor,
    buffer_manager_creator, chip_io_buf_clearer, chip_io_buf_extractor,
    chip_provenance_updater, chip_runtime_updater, compute_energy_used,
    create_notification_protocol, database_interface,
    dsg_region_reloader, energy_provenance_reporter,
    execute_application_data_specs, execute_system_data_specs,
    graph_binary_gatherer, graph_data_specification_writer,
    graph_provenance_gatherer,
    host_based_bit_field_router_compressor, hbp_allocator,
    insert_chip_power_monitors_to_graphs,
    insert_extra_monitor_vertices_to_graphs, split_lpg_vertices,
    load_app_images, load_fixed_routes, load_sys_images,
    local_tdma_builder, locate_executable_start_type,
    machine_generator,
    placements_provenance_gatherer, profile_data_gatherer,
    read_routing_tables_from_machine, router_provenance_gatherer,
    routing_setup, routing_table_loader,
    sdram_outgoing_partition_allocator, spalloc_allocator,
    system_multicast_routing_generator,
    tags_loader, virtual_machine_generator, add_command_senders)
from spinn_front_end_common.interface.interface_functions.\
    machine_bit_field_router_compressor import (
        machine_bit_field_ordered_covering_compressor,
        machine_bit_field_pair_router_compressor)
from spinn_front_end_common.interface.interface_functions.\
    host_no_bitfield_router_compression import (
        ordered_covering_compression, pair_compression)
from spinn_front_end_common.interface.splitter_selectors import (
    splitter_selector)
from spinn_front_end_common.interface.provenance import (
    APPLICATION_RUNNER, DATA_GENERATION, GET_MACHINE, LOADING,
    ProvenanceWriter, MAPPING, RUN_LOOP)
from spinn_front_end_common.interface.java_caller import JavaCaller
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.report_functions import (
    bitfield_compressor_report, board_chip_report, EnergyReport,
    fixed_route_from_machine_report, memory_map_on_host_report,
    memory_map_on_host_chip_report, network_specification,
    router_collision_potential_report,
    routing_table_from_machine_report, tags_from_machine_report,
    write_json_machine, write_json_placements,
    write_json_routing_tables, drift_report)
from spinn_front_end_common.utilities.iobuf_extractor import IOBufExtractor
from spinn_front_end_common.utilities.utility_objs import ExecutableType
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

try:
    from scipy import __version__ as scipy_version
except ImportError:
    scipy_version = "scipy not installed"

logger = FormatAdapter(logging.getLogger(__name__))


class AbstractSpinnakerBase(ConfigHandler):
    """ Main interface into the tools logic flow.
    """
    # pylint: disable=broad-except

    __slots__ = [
        # The IP-address of the SpiNNaker machine

        # the connection to allocted spalloc and HBP machines
        "_machine_allocation_controller",

        # Condition object used for waiting for stop
        # Set during init and the used but never new object
        "_state_condition",

        # Set when run_until_complete is specified by the user
        "_run_until_complete",

        #
        "_raise_keyboard_interrupt",

        # The loop number for the this/next loop in the end_user run
        "_n_loops",

        # A dict of live packet gather params to Application LGP vertices
        "_lpg_vertices",

        # the timer used to log the execute time
        # TODO energy report cleanup
        "_run_timer",

        # Used in exception handling and control c
        "_last_except_hook",

        # All beyond this point new for no extractor
        # The data is not new but now it is held direct and not via inputs

        # Flag to say is compressed routing tables are on machine
        # TODO remove this when the data change only algorithms are done
        "_multicast_routes_loaded"
    ]

    def __init__(self, data_writer_cls=None):
        """
        :param int n_chips_required:
            Overrides the number of chips to allocate from spalloc
        :param int n_boards_required:
            Overrides the number of boards to allocate from spalloc
        :param FecDataWriter data_writer_cls:
            The Global data writer class
        """
        # pylint: disable=too-many-arguments
        super().__init__(data_writer_cls)

        # output locations of binaries to be searched for end user info
        logger.info(
            "Will search these locations for binaries: {}",
            self._data_writer.get_executable_finder().binary_paths)

        # store for Live Packet Gatherers
        self._lpg_vertices = dict()

        self._machine_allocation_controller = None
        self._hard_reset()

        # holder for timing and running related values
        self._run_until_complete = False
        self._state_condition = Condition()
        self._n_loops = None

        # folders
        self._set_up_report_specifics()

        # Setup for signal handling
        self._raise_keyboard_interrupt = False

        self._create_version_provenance()

        self._last_except_hook = sys.excepthook

        FecTimer.setup(self)

        self._data_writer.register_binary_search_path(
            os.path.dirname(common_model_binaries.__file__))

        self._data_writer.set_machine_generator(self._get_machine)
        self._run_timer = None

    def _hard_reset(self):
        """
        This clears all data that if no longer valid after a hard reset

        """
        if self._data_writer.has_transceiver():
            self._data_writer.get_transceiver().stop_application(
                self._data_writer.get_app_id())
            self._data_writer.hard_reset()
        self._multicast_routes_loaded = False
        self.__close_allocation_controller()

    def _machine_clear(self):
        pass

    def check_machine_specifics(self):
        """ Checks machine specifics for the different modes of execution.

        Not this can only be called from a class that sets the config file
        to read this data from.
        """
        n_items_specified = 0
        if get_config_str("Machine", "machine_name"):
            n_items_specified += 1
        if get_config_str("Machine", "spalloc_server"):
            if get_config_str("Machine", "spalloc_user") is None:
                raise Exception(
                    "A spalloc_user must be specified with a spalloc_server")
            n_items_specified += 1
        if get_config_str("Machine", "remote_spinnaker_url"):
            n_items_specified += 1
        if get_config_bool("Machine", "virtual_board"):
            n_items_specified += 1

        if n_items_specified == 0:
            raise ConfigurationException(
                "See http://spinnakermanchester.github.io/spynnaker/"
                "PyNNOnSpinnakerInstall.html Configuration Section")

        if n_items_specified > 1:
            raise Exception(
                "Only one of machineName, spalloc_server, "
                "remote_spinnaker_url and virtual_board should be specified "
                "in your configuration files")

    def _setup_java_caller(self):
        if get_config_bool("Java", "use_java"):
            self._data_writer.set_java_caller(JavaCaller())

    def __signal_handler(self, _signal, _frame):
        """ Handles closing down of script via keyboard interrupt

        :param _signal: the signal received (ignored)
        :param _frame: frame executed in (ignored)
        :return: None
        """
        # If we are to raise the keyboard interrupt, do so
        if self._raise_keyboard_interrupt:
            raise KeyboardInterrupt

        logger.error("User has cancelled simulation")
        self._shutdown()

    def exception_handler(self, exctype, value, traceback_obj):
        """ Handler of exceptions

        :param type exctype: the type of exception received
        :param Exception value: the value of the exception
        :param traceback traceback_obj: the trace back stuff
        """
        logger.error("Shutdown on exception")
        self._shutdown()
        return self._last_except_hook(exctype, value, traceback_obj)

    def _should_run(self):
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
            "Therefor the run call will exit immediately.")
        return False

    def run_until_complete(self, n_steps=None):
        """ Run a simulation until it completes

        :param int n_steps:
            If not None, this specifies that the simulation should be
            requested to run for the given number of steps.  The host will
            still wait until the simulation itself says it has completed
        """
        self._run_until_complete = True
        self._run(n_steps, sync_time=0)

    def run(self, run_time, sync_time=0):
        """ Run a simulation for a fixed amount of time

        :param int run_time: the run duration in milliseconds.
        :param float sync_time:
            If not 0, this specifies that the simulation should pause after
            this duration.  The continue_simulation() method must then be
            called for the simulation to continue.
        """
        if self._run_until_complete:
            raise NotImplementedError("run after run_until_complete")
        self._run(run_time, sync_time)

    def __timesteps(self, time_in_ms):
        """ Get a number of timesteps for a given time in milliseconds.

        :return: The number of timesteps
        :rtype: int
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

    def _calc_run_time(self, run_time):
        """
        Calculates n_machine_time_steps and total_run_time based on run_time\
        and machine_time_step

        This method rounds the run up to the next timestep as discussed in\
        https://github.com/SpiNNakerManchester/sPyNNaker/issues/149

        If run_time is None (run forever) both values will be None

        :param run_time: time user requested to run for in milliseconds
        :type run_time: float or None
        :return: n_machine_time_steps as a whole int and
            total_run_time in milliseconds
        :rtype: tuple(int,float) or tuple(None,None)
        """
        if run_time is None:
            return None, None
        n_machine_time_steps = self.__timesteps(run_time)
        total_run_timesteps = (
            self._data_writer.get_current_run_timesteps() +
            n_machine_time_steps)
        total_run_time = (
            total_run_timesteps *
            self._data_writer.get_hardware_time_step_ms())

        logger.info(
            f"Simulating for {n_machine_time_steps} "
            f"{self._data_writer.get_simulation_time_step_ms()} ms timesteps "
            f"using a hardware timestep of "
            f"{self._data_writer.get_hardware_time_step_us()} us")
        return n_machine_time_steps, total_run_time

    def _run(self, run_time, sync_time):
        self._data_writer.start_run()

        try:
            self.__run(run_time, sync_time)
            self._data_writer.finish_run()
        except Exception:
            self._data_writer.shut_down()
            raise

    def __run(self, run_time, sync_time):
        """ The main internal run function.

        :param int run_time: the run duration in milliseconds.
        :param int sync_time:
            the time in ms between synchronisations, or 0 to disable.
        """
        if not self._should_run():
            return

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

        self._adjust_config(run_time)

        # Install the Control-C handler
        # pylint: disable=protected-access
        if isinstance(threading.current_thread(), threading._MainThread):
            signal.signal(signal.SIGINT, self.__signal_handler)
            self._raise_keyboard_interrupt = True
            sys.excepthook = self._last_except_hook

        logger.info("Starting execution process")

        n_machine_time_steps, total_run_time = self._calc_run_time(run_time)
        if self._machine_allocation_controller is not None:
            self._machine_allocation_controller.extend_allocation(
                total_run_time)

        n_sync_steps = self.__timesteps(sync_time)

        # If we have never run before, or the graph has changed,
        # start by performing mapping
        if (self._data_writer.get_requires_mapping() and
                self._data_writer.is_ran_last()):
            self.stop()
            raise NotImplementedError(
                "The network cannot be changed between runs without"
                " resetting")

        # If we have reset and the graph has changed, stop any running
        # application
        if (self._data_writer.get_requires_data_generation() and
                self._data_writer.has_transceiver()):
            self._data_writer.get_transceiver().stop_application(
                self._data_writer.get_app_id())
            self._data_writer.reset_sync_signal()
        # build the graphs to modify with system requirements
        if self._data_writer.get_requires_mapping():
            if self._data_writer.is_soft_reset():
                # wipe out stuff associated with past mapping
                self._hard_reset()
            FecTimer.setup(self)

            self._add_dependent_verts_and_edges_for_application_graph()

            if get_config_bool("Buffers", "use_auto_pause_and_resume"):
                self._data_writer.set_plan_n_timesteps(get_config_int(
                    "Buffers", "minimum_auto_time_steps"))
            else:
                self._data_writer.set_plan_n_timesteps(n_machine_time_steps)

            self._do_mapping(total_run_time)

        # Check if anything has per-timestep SDRAM usage
        is_per_timestep_sdram = self._is_per_timestep_sdram()

        # Disable auto pause and resume if the binary can't do it
        if not get_config_bool("Machine", "virtual_board"):
            for executable_type in self._data_writer.get_executable_types():
                if not executable_type.supports_auto_pause_and_resume:
                    set_config(
                        "Buffers", "use_auto_pause_and_resume", "False")

        # Work out the maximum run duration given all recordings
        if not self._data_writer.has_max_run_time_steps():
            self._data_writer.set_max_run_time_steps(
                self._deduce_data_n_timesteps())

        # Work out an array of timesteps to perform
        steps = None
        if (not get_config_bool("Buffers", "use_auto_pause_and_resume")
                or not is_per_timestep_sdram):

            # Runs should only be in units of max_run_time_steps at most
            if (is_per_timestep_sdram and
                    (self._data_writer.get_max_run_time_steps()
                        < n_machine_time_steps or
                        n_machine_time_steps is None)):
                raise ConfigurationException(
                    "The SDRAM required by one or more vertices is based on "
                    "the run time, so the run time is limited to "
                    f"{self._data_writer.get_max_run_time_steps()} time steps")

            steps = [n_machine_time_steps]
        elif run_time is not None:

            # With auto pause and resume, any time step is possible but run
            # time more than the first will guarantee that run will be called
            # more than once
            steps = self._generate_steps(n_machine_time_steps)

        # requires data_generation includes never run and requires_mapping
        if self._data_writer.get_requires_data_generation():
            self._do_load()

        # Run for each of the given steps
        if run_time is not None:
            logger.info("Running for {} steps for a total of {}ms",
                        len(steps), run_time)
            for self._n_loops, step in enumerate(steps):
                logger.info("Run {} of {}", self._n_loops + 1, len(steps))
                self._do_run(step, n_sync_steps)
            self._n_loops = None
        elif run_time is None and self._run_until_complete:
            logger.info("Running until complete")
            self._do_run(None, n_sync_steps)
        elif (not get_config_bool(
                "Buffers", "use_auto_pause_and_resume") or
                not is_per_timestep_sdram):
            logger.info("Running forever")
            self._do_run(None, n_sync_steps)
            logger.info("Waiting for stop request")
            with self._state_condition:
                while self._data_writer.is_no_stop_requested():
                    self._state_condition.wait()
        else:
            logger.info("Running forever in steps of {}ms".format(
                self._data_writer.get_max_run_time_steps()))
            self._n_loops = 1
            while self._data_writer.is_no_stop_requested():
                logger.info("Run {}".format(self._n_loops))
                self._do_run(
                    self._data_writer.get_max_run_time_steps(), n_sync_steps)
                self._n_loops += 1

        # Indicate that the signal handler needs to act
        # pylint: disable=protected-access
        if isinstance(threading.current_thread(), threading._MainThread):
            self._raise_keyboard_interrupt = False
            self._last_except_hook = sys.excepthook
            sys.excepthook = self.exception_handler

        self._n_loops = None

    def _is_per_timestep_sdram(self):
        for placement in self._data_writer.iterate_placemements():
            if placement.vertex.sdram_required.per_timestep:
                return True
        return False

    def _add_commands_to_command_sender(self, system_placements):
        """
        Runs, times and logs the VirtualMachineGenerator if required

        May set then "machine" value
        """
        with FecTimer(MAPPING, "Command Sender Adder"):
            all_command_senders = add_command_senders(system_placements)
            # add the edges from the command senders to the dependent vertices
            for command_sender in all_command_senders:
                self._data_writer.add_vertex(command_sender)
                edges, partition_ids = command_sender.edges_and_partitions()
                for edge, partition_id in zip(edges, partition_ids):
                    self._data_writer.add_edge(edge, partition_id)

    def _add_dependent_verts_and_edges_for_application_graph(self):
        # cache vertices to allow insertion during iteration
        vertices = list(self._data_writer.get_vertices_by_type(
                AbstractVertexWithEdgeToDependentVertices))
        for vertex in vertices:
            for dependant_vertex in vertex.dependent_vertices():
                if not vertex.addedToGraph():
                    self._data_writer.add_vertex(dependant_vertex)
                    edge_partition_ids = vertex.\
                        edge_partition_identifiers_for_dependent_vertex(
                            dependant_vertex)
                    for edge_identifier in edge_partition_ids:
                        dependant_edge = ApplicationEdge(
                            pre_vertex=vertex, post_vertex=dependant_vertex)
                        self._data_writer.add_edge(
                            dependant_edge, edge_identifier)

    def _deduce_data_n_timesteps(self):
        """ Operates the auto pause and resume functionality by figuring out\
            how many timer ticks a simulation can run before SDRAM runs out,\
            and breaks simulation into chunks of that long.

        :return: max time a simulation can run.
        """
        # Go through the placements and find how much SDRAM is used
        # on each chip
        usage_by_chip = dict()

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
            size = self._data_writer.get_chip_at(x, y).sdram.size
            if sdram.fixed > size:
                raise Exception(
                    f"Too much SDRAM has been allocated on chip {x}, {y}: "
                    f" {sdram.fixed} of {size}")
            if sdram.per_timestep:
                max_this_chip = int((size - sdram.fixed) // sdram.per_timestep)
                max_time_steps = min(max_time_steps, max_this_chip)

        return max_time_steps

    def _generate_steps(self, n_steps):
        """ Generates the list of "timer" runs. These are usually in terms of\
            time steps, but need not be.

        :param int n_steps: the total runtime in machine time steps
        :return: list of time step lengths
        :rtype: list(int)
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

    def _execute_get_virtual_machine(self):
        """
        Runs, times and logs the VirtualMachineGenerator if required

        May set then "machine" value
        """
        with FecTimer(GET_MACHINE, "Virtual machine generator"):
            self._data_writer.set_machine(virtual_machine_generator())
            self._data_writer.set_ipaddress("virtual")

    def _execute_allocator(self, category, total_run_time):
        """
        Runs, times and logs the SpallocAllocator or HBPAllocator if required

        :param str category: Algorithm category for provenance
        :param total_run_time: The total run time to request
        type total_run_time: int or None
        :return: machine name, machine version, BMP details (if any),
            reset on startup flag, auto-detect BMP, SCAMP connection details,
            boot port, allocation controller
        :rtype: tuple(str, int, object, bool, bool, object, object,
            MachineAllocationController)
        """
        if self._data_writer.has_machine():
            return None
        if get_config_str("Machine", "spalloc_server") is not None:
            with FecTimer(category, "SpallocAllocator"):
                return spalloc_allocator()
        if get_config_str("Machine", "remote_spinnaker_url") is not None:
            with FecTimer(category, "HBPAllocator"):
                return hbp_allocator(total_run_time)

    def _execute_machine_generator(self, category, allocator_data):
        """
        Runs, times and logs the MachineGenerator if required

        May set the "machine" value if not already set

        :param str category: Algorithm category for provenance
        :allocator_data: None or
            (machine name, machine version, BMP details (if any),
            reset on startup flag, auto-detect BMP, SCAMP connection details,
            boot port, allocation controller)
        :type allocator_data: None or
            tuple(str, int, object, bool, bool, object, object,
            MachineAllocationController)
        """
        if self._data_writer.has_machine():
            return
        machine_name = get_config_str("Machine", "machine_name")
        if machine_name is not None:
            self._data_writer.set_ipaddress(machine_name)
            bmp_details = get_config_str("Machine", "bmp_names")
            auto_detect_bmp = get_config_bool(
                "Machine", "auto_detect_bmp")
            scamp_connection_data = None
            reset_machine = get_config_bool(
                "Machine", "reset_machine_on_startup")
            board_version = get_config_int(
                "Machine", "version")

        elif allocator_data:
            (ipaddress, board_version, bmp_details,
             reset_machine, auto_detect_bmp, scamp_connection_data,
             self._machine_allocation_controller
             ) = allocator_data
            self._data_writer.set_ipaddress(ipaddress)
        else:
            return

        with FecTimer(category, "Machine generator"):
            machine, transceiver = machine_generator(
                bmp_details, board_version,
                auto_detect_bmp, scamp_connection_data, reset_machine)
            self._data_writer.set_transceiver(transceiver)
            self._data_writer.set_machine(machine)

    def _get_known_machine(self, total_run_time=0.0):
        """ The python machine description object.

        :param float total_run_time: The total run time to request
        :rtype: ~spinn_machine.Machine
        """
        if not self._data_writer.has_machine():
            if get_config_bool("Machine", "virtual_board"):
                self._execute_get_virtual_machine()
            else:
                allocator_data = self._execute_allocator(
                    GET_MACHINE, total_run_time)
                self._execute_machine_generator(GET_MACHINE, allocator_data)

    def _get_machine(self):
        """ The factory method to get a machine

        :rtype: ~spinn_machine.Machine
        """
        if self._data_writer.is_user_mode() and \
                self._data_writer.is_soft_reset():
            # Make the reset hard
            logger.warning(
                "Calling Get machine after a reset force a hard reset and "
                "therefore generate a new machine")
            self._hard_reset()
        self._get_known_machine()
        if not self._data_writer.has_machine():
            raise ConfigurationException(
                "Not enough information provided to supply a machine")

    def _create_version_provenance(self):
        """ Add the version information to the provenance data at the start.
        """
        with ProvenanceWriter() as db:
            db.insert_version("spinn_utilities_version", spinn_utils_version)
            db.insert_version("spinn_machine_version", spinn_machine_version)
            db.insert_version("spalloc_version", spalloc_version)
            db.insert_version("spinnman_version", spinnman_version)
            db.insert_version("pacman_version", pacman_version)
            db.insert_version("data_specification_version", data_spec_version)
            db.insert_version("front_end_common_version", fec_version)
            db.insert_version("numpy_version", numpy_version)
            db.insert_version("scipy_version", scipy_version)

    def _do_extra_mapping_algorithms(self):
        """
        Allows overriding classes to add algorithms
        """

    def _json_machine(self):
        """
        Runs, times and logs WriteJsonMachine if required

        """
        with FecTimer(MAPPING, "Json machine") as timer:
            if timer.skip_if_cfg_false("Reports", "write_json_machine"):
                return
            write_json_machine()

    def _report_network_specification(self):
        """
        Runs, times and logs the Network Specification report is requested

        """
        with FecTimer(MAPPING, "Network Specification report") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_network_specification_report"):
                return
            network_specification()

    def _execute_split_lpg_vertices(self, system_placements):
        """
        Runs, times and logs the SplitLPGVertices if required
        """
        with FecTimer(MAPPING, "Split Live Gather Vertices"):
            split_lpg_vertices(system_placements)

    def _report_board_chip(self):
        """
        Runs, times and logs the BoardChipReport is requested

        """
        with FecTimer(MAPPING, "Board chip report") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_board_chip_report"):
                return
            board_chip_report()

    def _execute_splitter_reset(self):
        """
        Runs, times and logs the splitter_reset

        """
        with FecTimer(MAPPING, "Splitter reset"):
            splitter_reset()

    # Overriden by spynaker to choose an extended algorithm
    def _execute_splitter_selector(self):
        """
        Runs, times and logs the SplitterSelector
        """
        with FecTimer(MAPPING, "Splitter selector"):
            splitter_selector()

    def _execute_delay_support_adder(self):
        """
        Stub to allow spynakker to add delay supports
        """

    # Overriden by spynaker to choose a different algorithm
    def _execute_splitter_partitioner(self):
        """
        Runs, times and logs the SplitterPartitioner if required
        """
        if self._data_writer.get_n_vertices() == 0:
            return
        with FecTimer(MAPPING, "Splitter partitioner"):
            self._data_writer.set_n_chips_in_graph(splitter_partitioner())

    def _execute_insert_chip_power_monitors(self, system_placements):
        """
        Run, time and log the InsertChipPowerMonitorsToGraphs if required

        """
        with FecTimer(MAPPING, "Insert chip power monitors") as timer:
            if timer.skip_if_cfg_false("Reports", "write_energy_report"):
                return
            insert_chip_power_monitors_to_graphs(system_placements)

    def _execute_insert_extra_monitor_vertices(self, system_placements):
        """
        Run, time and log the InsertExtraMonitorVerticesToGraphs if required

        """
        with FecTimer(MAPPING, "Insert extra monitor vertices") as timer:
            if timer.skip_if_cfgs_false(
                    "Machine", "enable_advanced_monitor_support",
                    "enable_reinjection"):
                return
            # inserter checks for None app graph not an empty one
        gather_map, monitor_map = insert_extra_monitor_vertices_to_graphs(
            system_placements)
        self._data_writer.set_gatherer_map(gather_map)
        self._data_writer.set_monitor_map(monitor_map)

    def _execute_partitioner_report(self):
        """
        Write, times and logs the partitioner_report if needed

        """
        with FecTimer(MAPPING, "Partitioner report") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_partitioner_reports"):
                return
            partitioner_report()

    def _execute_local_tdma_builder(self):
        """
        Runs times and logs the LocalTDMABuilder
        """
        with FecTimer(MAPPING, "Local TDMA builder"):
            local_tdma_builder()

    def _execute_application_placer(self, system_placements):
        """
        Runs, times and logs the Application Placer

        Sets the "placements" data

        .. note::
            Calling of this method is based on the cfg placer value

        """
        with FecTimer(MAPPING, "Application Placer"):
            self._data_writer.set_placements(place_application_graph(
                system_placements))

    def _do_placer(self, system_placements):
        """
        Runs, times and logs one of the placers

        Sets the "placements" data

        Which placer is run depends on the cfg placer value

        This method is the entry point for adding a new Placer

        :raise ConfigurationException: if the cfg place value is unexpected
        """
        name = get_config_str("Mapping", "placer")
        if name == "ApplicationPlacer":
            return self._execute_application_placer(system_placements)
        if "," in name:
            raise ConfigurationException(
                "Only a single algorithm is supported for placer")
        raise ConfigurationException(
            f"Unexpected cfg setting placer: {name}")

    def _execute_system_multicast_routing_generator(self):
        """
        Runs, times and logs the SystemMulticastRoutingGenerator is required

        May sets the data "data_in_multicast_routing_tables",
        "data_in_multicast_key_to_chip_map" and
        "system_multicast_router_timeout_keys"
        """
        with FecTimer(MAPPING, "System multicast routing generator") as timer:
            if timer.skip_if_cfgs_false(
                    "Machine", "enable_advanced_monitor_support",
                    "enable_reinjection"):
                return
            data = system_multicast_routing_generator()
            self._data_writer.set_system_multicast_routing_data(data)

    def _execute_fixed_route_router(self):
        """
        Runs, times and logs the FixedRouteRouter if required

        May set the "fixed_routes" data.
        """
        with FecTimer(MAPPING, "Fixed route router") as timer:
            if timer.skip_if_cfg_false(
                    "Machine", "enable_advanced_monitor_support"):
                return
            self._data_writer.set_fixed_routes(fixed_route_router(
                DataSpeedUpPacketGatherMachineVertex))

    def _report_placements_with_application_graph(self):
        """
        Writes, times and logs the application graph placer report if
        requested
        """
        if self._data_writer.get_n_vertices() == 0:
            return
        with FecTimer(
                MAPPING, "Placements wth application graph report") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_application_graph_placer_report"):
                return
            placer_reports_with_application_graph()

    def _json_placements(self):
        """
        Does, times and logs the writing of placements as json if requested
        :return:
        """
        with FecTimer(MAPPING, "Json placements") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_json_placements"):
                return
            write_json_placements()
            # Output ignored as never used

    def _execute_ner_route_traffic_aware(self):
        """
        Runs, times and logs the NerRouteTrafficAware

        Sets the "routing_table_by_partition" data if called

        .. note::
            Calling of this method is based on the cfg router value
        """
        with FecTimer(MAPPING, "Ner route traffic aware"):
            self._data_writer.set_routing_table_by_partition(
                ner_route_traffic_aware())

    def _execute_ner_route(self):
        """
        Runs, times and logs the NerRoute

        Sets the "routing_table_by_partition" data

        .. note::
            Calling of this method is based on the cfg router value
        """
        with FecTimer(MAPPING, "Ner route"):
            self._data_writer.set_routing_table_by_partition(ner_route())

    def _execute_basic_dijkstra_routing(self):
        """
        Runs, times and logs the BasicDijkstraRouting

        Sets the "routing_table_by_partition" data if called

        .. note::
            Calling of this method is based on the cfg router value
        """
        with FecTimer(MAPPING, "Basic dijkstra routing"):
            self._data_writer.set_routing_table_by_partition(
                basic_dijkstra_routing())

    def _execute_application_router(self):
        """
        Runs, times and logs the ApplicationRouter

        Sets the "routing_table_by_partition" data if called

        .. note::
            Calling of this method is based on the cfg router value
        """
        with FecTimer(MAPPING, "Application Router"):
            self._data_writer.set_routing_table_by_partition(
                route_application_graph())

    def _do_routing(self):
        """
        Runs, times and logs one of the routers

        Sets the "routing_table_by_partition" data

        Which router is run depends on the cfg router value

        This method is the entry point for adding a new Router

        :raise ConfigurationException: if the cfg router value is unexpected
        """
        name = get_config_str("Mapping", "router")
        if name == "BasicDijkstraRouting":
            return self._execute_basic_dijkstra_routing()
        if name == "NerRoute":
            return self._execute_ner_route()
        if name == "NerRouteTrafficAware":
            return self._execute_ner_route_traffic_aware()
        if name == "ApplicationRouter":
            return self._execute_application_router()
        if "," in name:
            raise ConfigurationException(
                "Only a single algorithm is supported for router")
        raise ConfigurationException(
            f"Unexpected cfg setting router: {name}")

    def _execute_basic_tag_allocator(self):
        """
        Runs, times and logs the Tag Allocator

        Sets the "tag" data
        """
        with FecTimer(MAPPING, "Basic tag allocator"):
            self._data_writer.set_tags(
                basic_tag_allocator())

    def _report_tag_allocations(self):
        """
        Write, times and logs the tag allocator report if requested
        """
        with FecTimer(MAPPING, "Tag allocator report") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_tag_allocation_reports"):
                return
            tag_allocator_report()

    def _execute_global_allocate(self, extra_allocations):
        """
        Runs, times and logs the Global Zoned Routing Info Allocator

        Sets "routing_info" is called

        .. note::
            Calling of this method is based on the cfg info_allocator value

        :return:
        """
        with FecTimer(MAPPING, "Global allocate"):
            self._data_writer.set_routing_infos(
                global_allocate(extra_allocations))

    def _execute_flexible_allocate(self, extra_allocations):
        """
        Runs, times and logs the Zoned Routing Info Allocator

        Sets "routing_info" is called

        .. note::
            Calling of this method is based on the cfg info_allocator value

        :return:
        """
        with FecTimer(MAPPING, "Zoned routing info allocator"):
            self._data_writer.set_routing_infos(
                flexible_allocate(extra_allocations))

    def do_info_allocator(self):
        """
        Runs, times and logs one of the info allocaters

        Sets the "routing_info" data

        Which alloactor is run depends on the cfg info_allocator value

        This method is the entry point for adding a new Info Allocator

        :raise ConfigurationException: if the cfg info_allocator value is
            unexpected
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

    def _report_router_info(self):
        """
        Writes, times and logs the router info report if requested
        """
        with FecTimer(MAPPING, "Router info report") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_router_info_report"):
                return
            routing_info_report([])

    def _execute_basic_routing_table_generator(self):
        """
        Runs, times and logs the Routing Table Generator

        .. note::
            Currently no other Routing Table Generator supported.
            To add an additional Generator copy the pattern of do_placer
        """
        with FecTimer(MAPPING, "Basic routing table generator"):
            self._data_writer.set_uncompressed(basic_routing_table_generator())

    def _execute_merged_routing_table_generator(self):
        """
        Runs, times and logs the Routing Table Generator

        .. note::
            Currently no other Routing Table Generator supported.
            To add an additional Generator copy the pattern of do_placer
        """
        with FecTimer(MAPPING, "Merged routing table generator"):
            self._data_writer.set_uncompressed(
                merged_routing_table_generator())

        # TODO Nuke ZonedRoutingTableGenerator

    def _do_routing_table_generator(self):
        """
        Runs, times and logs one of the routing table generators

        Sets the "routing_info" data

        Which alloactor is run depends on the cfg info_allocator value

        This method is the entry point for adding a new Info Allocator

        :raise ConfigurationException: if the cfg info_allocator value is
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

    def _report_routers(self):
        """
        Write, times and logs the router report if requested
        """
        with FecTimer(MAPPING, "Router report") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_router_reports"):
                return
        router_report_from_paths()

    def _report_router_summary(self):
        """
        Write, times and logs the router summary report if requested
        """
        with FecTimer(MAPPING, "Router summary report") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_router_summary_report"):
                return
            router_summary_report()

    def _json_routing_tables(self):
        """
        Write, time and log the routing tables as json if requested
        """
        with FecTimer(MAPPING, "Json routing tables") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_json_routing_tables"):
                return
            write_json_routing_tables(self._data_writer.get_uncompressed())
            # Output ignored as never used

    def _report_router_collision_potential(self):
        """
        Write, time and log the router collision report
        """
        with FecTimer(MAPPING, "Router collision potential report") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_router_collision_potential_report"):
                return
            router_collision_potential_report()

    def _report_drift(self, start):
        """ Write, time and log the drift

        :param bool start: Is this the start or the end
        """
        with FecTimer(MAPPING, "Drift report") as timer:
            if timer.skip_if_virtual_board():
                return
            if start and timer.skip_if_cfg_false(
                    "Reports", "write_drift_report_start"):
                return
            if not start and timer.skip_if_cfg_false(
                    "Reports", "write_drift_report_end"):
                return
            drift_report()

    def _execute_locate_executable_start_type(self):
        """
        Runs, times and logs LocateExecutableStartType if required

        May set the executable_types data.
        """
        with FecTimer(MAPPING, "Locate executable start type"):
            self._data_writer.set_executable_types(
                locate_executable_start_type())

    def _execute_buffer_manager_creator(self):
        """
        Run, times and logs the buffer manager creator if required

        May set the buffer_manager data
        """
        if self._data_writer.has_buffer_manager():
            return
        with FecTimer(MAPPING, "Buffer manager creator") as timer:
            if timer.skip_if_virtual_board():
                return

            self._data_writer.set_buffer_manager(
                buffer_manager_creator())

    def _execute_sdram_outgoing_partition_allocator(self):
        """
        Runs, times and logs the SDRAMOutgoingPartitionAllocator
        """
        with FecTimer(MAPPING, "SDRAM outgoing partition allocator"):
            sdram_outgoing_partition_allocator()

    def _execute_control_sync(self, do_sync):
        """ Control synchronization on board

        :param bool do_sync: Whether to enable synchronization
        """
        with FecTimer(MAPPING, "Control Sync") as timer:
            if timer.skip_if_virtual_board():
                return
            self._data_writer.get_transceiver().control_sync(do_sync)

    def _do_mapping(self, total_run_time):
        """
        Runs, times and logs all the algorithms in the mapping stage

        :param float total_run_time:
        """
        # time the time it takes to do all pacman stuff
        mapping_total_timer = Timer()
        mapping_total_timer.start_timing()

        self._setup_java_caller()
        self._do_extra_mapping_algorithms()
        self._report_network_specification()

        self._execute_splitter_reset()
        self._execute_splitter_selector()
        self._execute_delay_support_adder()

        self._execute_splitter_partitioner()
        allocator_data = self._execute_allocator(MAPPING, total_run_time)
        self._execute_machine_generator(MAPPING, allocator_data)
        self._json_machine()
        self._report_board_chip()

        system_placements = Placements()
        self._add_commands_to_command_sender(system_placements)
        self._execute_split_lpg_vertices(system_placements)
        self._execute_insert_chip_power_monitors(system_placements)
        self._execute_insert_extra_monitor_vertices(system_placements)

        self._execute_partitioner_report()
        self._execute_local_tdma_builder()
        self._do_placer(system_placements)
        self._report_placements_with_application_graph()
        self._json_placements()

        self._execute_system_multicast_routing_generator()
        self._execute_fixed_route_router()
        self._do_routing()

        self._execute_basic_tag_allocator()
        self._report_tag_allocations()

        self.do_info_allocator()
        self._report_router_info()
        self._do_routing_table_generator()
        self._report_uncompressed_routing_table()
        self._report_routers()
        self._report_router_summary()
        self._json_routing_tables()
        # self._report_router_collision_potential()
        self._execute_locate_executable_start_type()
        self._execute_buffer_manager_creator()
        self._execute_sdram_outgoing_partition_allocator()

        with ProvenanceWriter() as db:
            db.insert_category_timing(
                MAPPING, mapping_total_timer.take_sample(), self._n_loops)

    # Overridden by spy which adds placement_order
    def _execute_graph_data_specification_writer(self):
        """
        Runs, times, and logs the GraphDataSpecificationWriter

        Sets the dsg_targets data
        """
        with FecTimer(
                DATA_GENERATION, "Graph data specification writer"):
            self._data_writer.set_dsg_targets(
                graph_data_specification_writer())

    def _do_data_generation(self):
        """
        Runs, Times and logs the data generation
        """
        # set up timing
        data_gen_timer = Timer()
        data_gen_timer.start_timing()

        self._execute_graph_data_specification_writer()

        with ProvenanceWriter() as db:
            db.insert_category_timing(
                DATA_GENERATION, data_gen_timer.take_sample(), self._n_loops)

    def _execute_routing_setup(self,):
        """
        Runs, times and logs the RoutingSetup if required.

        """
        if self._multicast_routes_loaded:
            return
        with FecTimer(LOADING, "Routing setup") as timer:
            if timer.skip_if_virtual_board():
                return
            # Only needs the x and y of chips with routing tables
            routing_setup()

    def _execute_graph_binary_gatherer(self):
        """
        Runs, times and logs the GraphBinaryGatherer if required.

        """
        with FecTimer(LOADING, "Graph binary gatherer") as timer:
            try:
                self._data_writer.set_executable_targets(
                    graph_binary_gatherer())
            except KeyError:
                if get_config_bool("Machine", "virtual_board"):
                    logger.warning(
                        "Ignoring exectable not found as using virtual")
                    timer.error("exectable not found and virtual board")
                    return
                raise

    def _execute_host_bitfield_compressor(self):
        """
        Runs, times and logs the HostBasedBitFieldRouterCompressor

        .. note::
            Calling of this method is based on the cfg compressor or
            virtual_compressor value

        :return: CompressedRoutingTables
        :rtype: MulticastRoutingTables
        """
        with FecTimer(
                LOADING, "Host based bitfield router compressor") as timer:
            if timer.skip_if_virtual_board():
                return None
            self._multicast_routes_loaded = False
            compressed = host_based_bit_field_router_compressor()
            return compressed

    def _execute_machine_bitfield_ordered_covering_compressor(self):
        """
        Runs, times and logs the MachineBitFieldOrderedCoveringCompressor

        .. note::
            Calling of this method is based on the cfg compressor or
            virtual_compressor value

        :return: None
        :rtype: None
        """
        with FecTimer(
                LOADING,
                "Machine bitfield ordered covering compressor") as timer:
            if timer.skip_if_virtual_board():
                return None
            machine_bit_field_ordered_covering_compressor()
            self._multicast_routes_loaded = True
            return None

    def _execute_machine_bitfield_pair_compressor(self):
        """
        Runs, times and logs the MachineBitFieldPairRouterCompressor

        .. note::
            Calling of this method is based on the cfg compressor or
            virtual_compressor value

        :return: None
        :rtype: None
         """
        with FecTimer(
                LOADING, "Machine bitfield pair router compressor") as timer:
            if timer.skip_if_virtual_board():
                return None
            self._multicast_routes_loaded = True
            machine_bit_field_pair_router_compressor()
            return None

    def _execute_ordered_covering_compressor(self):
        """
        Runs, times and logs the OrderedCoveringCompressor

        .. note::
            Calling of this method is based on the cfg compressor or
            virtual_compressor value

        :return: CompressedRoutingTables
        :rtype: MulticastRoutingTables
        """
        with FecTimer(LOADING, "Ordered covering compressor") as timer:
            self._multicast_routes_loaded = False
            precompressed = self._data_writer.get_precompressed()
            if self._compression_skipable(precompressed):
                timer.skip("Tables already small enough")
                return precompressed
            compressed = ordered_covering_compressor()
            return compressed

    def _execute_ordered_covering_compression(self):
        """
        Runs, times and logs the ordered covering compressor on machine

        .. note::
            Calling of this method is based on the cfg compressor or
            virtual_compressor value

        :return: None
        :rtype: None
        """
        with FecTimer(LOADING, "Ordered covering compressor") as timer:
            if timer.skip_if_virtual_board():
                return None, []
            precompressed = self._data_writer.get_precompressed()
            if self._compression_skipable(precompressed):
                timer.skip("Tables already small enough")
                self._multicast_routes_loaded = False
                return precompressed
            ordered_covering_compression()
            self._multicast_routes_loaded = True
            return None

    def _execute_pair_compressor(self):
        """
        Runs, times and logs the PairCompressor

        .. note::
            Calling of this method is based on the cfg compressor or
            virtual_compressor value

        :return: CompressedRoutingTable
        :rtype: MulticastRoutingTables
        """
        with FecTimer(LOADING, "Pair compressor") as timer:
            precompressed = self._data_writer.get_precompressed()
            self._multicast_routes_loaded = False
            if self._compression_skipable(precompressed):
                timer.skip("Tables already small enough")
                return precompressed
            compressed = pair_compressor()
            return compressed

    def _execute_pair_compression(self):
        """
        Runs, times and logs the pair compressor on machine

        .. note::
            Calling of this method is based on the cfg compressor or
            virtual_compressor value

        :return: None
        :rtype: None
        """
        with FecTimer(LOADING, "Pair on chip router compression") as timer:
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

    def _execute_pair_unordered_compressor(self):
        """
        Runs, times and logs the CheckedUnorderedPairCompressor

        .. note::
            Calling of this method is based on the cfg compressor or
            virtual_compressor value

        :return: CompressedRoutingTables
        :rtype: MulticastRoutingTables
        """
        with FecTimer(LOADING, "Pair unordered compressor") as timer:
            self._multicast_routes_loaded = False
            precompressed = self._data_writer.get_precompressed()
            if self._compression_skipable(precompressed):
                timer.skip("Tables already small enough")
                return precompressed
            compressed = pair_compressor(ordered=False)
            return compressed

    def _compressor_name(self):
        if get_config_bool("Machine", "virtual_board"):
            name = get_config_str("Mapping", "virtual_compressor")
            if name is None:
                logger.info("As no virtual_compressor specified "
                            "using compressor setting")
                name = get_config_str("Mapping", "compressor")
        else:
            name = get_config_str("Mapping", "compressor")
        pre_compress = "BitField" not in name
        return name, pre_compress

    def _compression_skipable(self, tables):
        if get_config_bool(
                "Mapping", "router_table_compress_as_far_as_possible"):
            return False
        return tables.max_number_of_entries <= Machine.ROUTER_ENTRIES

    def _execute_pre_compression(self, pre_compress):
        if pre_compress:
            name = get_config_str("Mapping", "precompressor")
            if name is None:
                self._data_writer.set_precompressed(
                    self._data_writer.get_uncompressed())
            elif name == "Ranged":
                with FecTimer(LOADING, "Ranged Compressor") as timer:
                    if self._compression_skipable(
                            self._data_writer.get_uncompressed()):
                        timer.skip("Tables already small enough")
                        self._data_writer.set_precompressed(
                            self._data_writer.get_uncompressed())
                        return
                    self._data_writer.set_precompressed(
                        range_compressor())
            else:
                raise ConfigurationException(
                    f"Unexpected cfg setting precompressor: {name}")
        else:
            self._data_writer.set_precompressed(
                self._data_writer.get_uncompressed())

    def _do_early_compression(self, name):
        """
        Calls a compressor based on the name provided

        .. note::
            This method is the entry point for adding a new compressor that
             can or must run early.

        :param str name: Name of a compressor
        :raise ConfigurationException: if the name is not expected
        :return: CompressedRoutingTables (likely to be None),
            RouterCompressorProvenanceItems (may be an empty list)
        :rtype: tuple(MulticastRoutingTables or None, list(ProvenanceDataItem))
        """
        if name == "MachineBitFieldOrderedCoveringCompressor":
            return \
                self._execute_machine_bitfield_ordered_covering_compressor()
        if name == "MachineBitFieldPairRouterCompressor":
            return self._execute_machine_bitfield_pair_compressor()
        if name == "OrderedCoveringCompressor":
            return self._execute_ordered_covering_compressor()
        if name == "OrderedCoveringOnChipRouterCompression":
            return self._execute_ordered_covering_compression()
        if name == "PairCompressor":
            return self._execute_pair_compressor()
        if name == "PairOnChipRouterCompression":
            return self._execute_pair_compression()
        if name == "PairUnorderedCompressor":
            return self._execute_pair_unordered_compressor()

        # delay compression until later
        return None

    def _do_delayed_compression(self, name, compressed):
        """
        run compression that must be delayed until later

        .. note::
            This method is the entry point for adding a new compressor that
            can not run at the normal place

        :param str name: Name of a compressor
        :raise ConfigurationException: if the name is not expected
        :return: CompressedRoutingTables (likely to be None),
            RouterCompressorProvenanceItems (may be an empty list)
        :rtype: tuple(MulticastRoutingTables or None, list(ProvenanceDataItem))
        """
        if self._multicast_routes_loaded or compressed:
            # Already compressed
            return compressed
        # overridden in spy to handle:
        # SpynnakerMachineBitFieldOrderedCoveringCompressor
        # SpynnakerMachineBitFieldPairRouterCompressor

        if name == "HostBasedBitFieldRouterCompressor":
            return self._execute_host_bitfield_compressor()
        if "," in name:
            raise ConfigurationException(
                "Only a single algorithm is supported for compressor")

        raise ConfigurationException(
            f"Unexpected cfg setting compressor: {name}")

    def _execute_load_routing_tables(self, compressed):
        """
        Runs, times and logs the RoutingTableLoader if required

        :param compressed:
        :type compressed: MulticastRoutingTables or None
        """
        if not compressed:
            return
        with FecTimer(LOADING, "Routing table loader") as timer:
            self._multicast_routes_loaded = True
            if timer.skip_if_virtual_board():
                return
            routing_table_loader(compressed)

    def _report_uncompressed_routing_table(self):
        """
        Runs, times and logs the router report from router tables if requested
        """
        with FecTimer(LOADING, "Uncompressed routing table report") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_routing_table_reports"):
                return
            router_report_from_router_tables()

    def _report_bit_field_compressor(self):
        """
        Runs, times and logs the BitFieldCompressorReport if requested
        """
        with FecTimer(LOADING, "Bitfield compressor report") as timer:
            if timer.skip_if_cfg_false(
                    "Reports",  "write_bit_field_compressor_report"):
                return
            # BitFieldSummary output ignored as never used
            bitfield_compressor_report()

    def _execute_load_fixed_routes(self):
        """
        Runs, times and logs Load Fixed Routes is required
        """
        with FecTimer(LOADING, "Load fixed routes") as timer:
            if timer.skip_if_cfg_false(
                    "Machine", "enable_advanced_monitor_support"):
                return
            if timer.skip_if_virtual_board():
                return
            load_fixed_routes()

    def _execute_system_data_specification(self):
        """
        Runs, times and logs the execute_system_data_specs if required

        """
        with FecTimer(LOADING, "Execute system data specification") \
                as timer:
            if timer.skip_if_virtual_board():
                return None
            execute_system_data_specs()

    def _execute_load_system_executable_images(self):
        """
        Runs, times and logs the loading of exectuable images
        """
        with FecTimer(LOADING, "Load executable system Images") as timer:
            if timer.skip_if_virtual_board():
                return
            load_sys_images()

    def _execute_application_data_specification(self):
        """
        Runs, times and logs the execute_application_data_specs if required

        :return: map of placement and DSG data, and loaded data flag.
        :rtype: dict(tuple(int,int,int),DataWritten) or DsWriteInfo
        """
        with FecTimer(LOADING, "Host data specification") as timer:
            if timer.skip_if_virtual_board():
                return
            return execute_application_data_specs()

    def _execute_tags_from_machine_report(self):
        """
        Run, times and logs the TagsFromMachineReport if requested
        :return:
        """
        with FecTimer(LOADING, "Tags from machine report") as timer:
            if timer.skip_if_virtual_board():
                return
            if timer.skip_if_cfg_false(
                    "Reports", "write_tag_allocation_reports"):
                return
            tags_from_machine_report()

    def _execute_load_tags(self):
        """
        Runs, times and logs the Tags Loader if required
        """
        # TODO why: if graph_changed or data_changed:
        with FecTimer(LOADING, "Tags Loader") as timer:
            if timer.skip_if_virtual_board():
                return
            tags_loader()

    def _do_extra_load_algorithms(self):
        """
        Runs, times and logs any extra load algorithms

        """

    def _report_memory_on_host(self):
        """
        Runs, times and logs MemoryMapOnHostReport is requested

        """
        with FecTimer(LOADING, "Memory report") as timer:
            if timer.skip_if_virtual_board():
                return
            if timer.skip_if_cfg_false(
                    "Reports", "write_memory_map_report"):
                return
            memory_map_on_host_report()

    def _report_memory_on_chip(self):
        """
        Runs, times and logs MemoryMapOnHostChipReport is requested

        """
        with FecTimer(LOADING, "Memory report") as timer:
            if timer.skip_if_virtual_board():
                return
            if timer.skip_if_cfg_false(
                    "Reports", "write_memory_map_report"):
                return

            memory_map_on_host_chip_report()

    # TODO consider different cfg flags
    def _report_compressed(self, compressed):
        """
        Runs, times and logs the compressor reports if requested

        :param compressed:
        :type compressed: MulticastRoutingTables or None
        """
        with FecTimer(LOADING, "Compressor report") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_routing_table_reports"):
                return
            if timer.skip_if_cfg_false(
                    "Reports", "write_routing_tables_from_machine_reports"):
                return

            if compressed is None:
                if timer.skip_if_virtual_board():
                    return
                compressed = read_routing_tables_from_machine()

            router_report_from_compressed_router_tables(compressed)

            generate_comparison_router_report(compressed)

            router_compressed_summary_report(compressed)

            routing_table_from_machine_report(compressed)

    def _report_fixed_routes(self):
        """
        Runs, times and logs the FixedRouteFromMachineReport is requested
        """
        with FecTimer(LOADING, "Fixed route report") as timer:
            if timer.skip_if_virtual_board():
                return
            if timer.skip_if_cfg_false(
                    "Machine", "enable_advanced_monitor_support"):
                return
            # TODO at the same time as LoadFixedRoutes?
            fixed_route_from_machine_report()

    def _execute_application_load_executables(self):
        """ algorithms needed for loading the binaries to the SpiNNaker machine

        :return:
        """
        with FecTimer(LOADING, "Load executable app images") as timer:
            if timer.skip_if_virtual_board():
                return
            load_app_images()

    def _do_load(self):
        """
        Runs, times and logs the load algotithms

        """
        # set up timing
        load_timer = Timer()
        load_timer.start_timing()

        if self._data_writer.get_requires_mapping():
            self._execute_routing_setup()
            self._execute_graph_binary_gatherer()
        # loading_algorithms
        compressor, pre_compress = self._compressor_name()
        self._execute_pre_compression(pre_compress)
        compressed = self._do_early_compression(compressor)

        self._do_data_generation()

        self._execute_control_sync(False)
        if self._data_writer.get_requires_mapping():
            self._execute_load_fixed_routes()
        self._execute_system_data_specification()
        self._execute_load_system_executable_images()
        self._execute_load_tags()
        self._execute_application_data_specification()

        self._do_extra_load_algorithms()
        compressed = self._do_delayed_compression(compressor, compressed)
        self._execute_load_routing_tables(compressed)
        self._report_bit_field_compressor()

        # TODO Was master correct to run the report first?
        self._execute_tags_from_machine_report()
        if self._data_writer.get_requires_mapping():
            self._report_memory_on_host()
            self._report_memory_on_chip()
            self._report_compressed(compressed)
            self._report_fixed_routes()
        self._execute_application_load_executables()

        with ProvenanceWriter() as db:
            db.insert_category_timing(
                LOADING, load_timer.take_sample(), self._n_loops)

    def _execute_sdram_usage_report_per_chip(self):
        # TODO why in do run
        with FecTimer(RUN_LOOP, "Sdram usage per chip report") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_sdram_usage_report_per_chip"):
                return
            sdram_usage_report_per_chip()

    def _execute_dsg_region_reloader(self):
        """
            Runs, times and logs the DSGRegionReloader if required

            Reload any parameters over the loaded data if we have already
            run and not using a virtual board and the data hasn't already
            been regenerated

        """
        if not self._data_writer.is_ran_ever():
            return
        if self._data_writer.is_hard_reset():
            return
        with FecTimer(RUN_LOOP, "DSG region reloader") as timer:
            if timer.skip_if_virtual_board():
                return
            dsg_region_reloader()

    def _execute_graph_provenance_gatherer(self):
        """
        Runs, times and log the GraphProvenanceGatherer if requested

        """
        with FecTimer(RUN_LOOP, "Graph provenance gatherer") as timer:
            if timer.skip_if_cfg_false("Reports", "read_provenance_data"):
                return []
            graph_provenance_gatherer()

    def _execute_placements_provenance_gatherer(self):
        """
        Runs, times and log the PlacementsProvenanceGatherer if requested
        """
        with FecTimer(RUN_LOOP, "Placements provenance gatherer") as timer:
            if timer.skip_if_cfg_false("Reports", "read_provenance_data"):
                return []
            if timer.skip_if_virtual_board():
                return []
            # Also used in recover from error where is is not all placements
            placements_provenance_gatherer(
                self._data_writer.get_n_placements(),
                self._data_writer.iterate_placemements())

    def _execute_router_provenance_gatherer(self):
        """
        Runs, times and log the RouterProvenanceGatherer if requested
        """
        with FecTimer(RUN_LOOP, "Router provenance gatherer") as timer:
            if timer.skip_if_cfg_false("Reports", "read_provenance_data"):
                return []
            if timer.skip_if_virtual_board():
                return []
            router_provenance_gatherer()

    def _execute_profile_data_gatherer(self):
        """
        Runs, times and logs the ProfileDataGatherer if requested
        """
        with FecTimer(RUN_LOOP, "Profile data gatherer") as timer:
            if timer.skip_if_cfg_false("Reports", "read_provenance_data"):
                return
            if timer.skip_if_virtual_board():
                return
            profile_data_gatherer()

    def _do_read_provenance(self):
        """
        Runs, times and log the methods that gather provenance

        :rtype: list(ProvenanceDataItem)
        """
        self._execute_graph_provenance_gatherer()
        self._execute_placements_provenance_gatherer()
        self._execute_router_provenance_gatherer()
        self._execute_profile_data_gatherer()

    def _report_energy(self):
        """
        Runs, times and logs the energy report if requested

        """
        with FecTimer(RUN_LOOP, "Energy report") as timer:
            if timer.skip_if_cfg_false("Reports", "write_energy_report"):
                return []
            if timer.skip_if_virtual_board():
                return []

            # TODO runtime is None
            power_used = compute_energy_used(
                self._machine_allocation_controller)

            energy_provenance_reporter(power_used)

            # create energy reporter
            energy_reporter = EnergyReport()

            # run energy report
            energy_reporter.write_energy_report(power_used)

    def _do_provenance_reports(self):
        """
        Runs any reports based on provenance

        """

    def _execute_clear_io_buf(self):
        """
        Runs, times and logs the ChipIOBufClearer if required

        """
        if self._data_writer.get_current_run_timesteps() is None:
            return
        with FecTimer(RUN_LOOP, "Clear IO buffer") as timer:
            if timer.skip_if_virtual_board():
                return
            # TODO Why check empty_graph is always false??
            if timer.skip_if_cfg_false("Reports", "clear_iobuf_during_run"):
                return
            chip_io_buf_clearer()

    def _execute_runtime_update(self, n_sync_steps):
        """
        Runs, times and logs the runtime updater if required

        :param int n_sync_steps:
            The number of timesteps between synchronisations
        """
        with FecTimer(RUN_LOOP, "Runtime Update") as timer:
            if timer.skip_if_virtual_board():
                return
            if (ExecutableType.USES_SIMULATION_INTERFACE in
                    self._data_writer.get_executable_types()):
                chip_runtime_updater(n_sync_steps)
            else:
                timer.skip("No Simulation Interface used")

    def _execute_create_database_interface(self, run_time):
        """
        Runs, times and logs Database Interface Creater

        Sets the _database_file_path data object

        :param int run_time: the run duration in milliseconds.
        """
        with FecTimer(RUN_LOOP, "Create database interface"):
            # Used to used compressed routing tables if available on host
            # TODO consider not saving router tabes.
            self._data_writer.set_database_file_path(
                database_interface(run_time))

    def _execute_create_notifiaction_protocol(self):
        """
        Runs, times and logs the creation of the Notification Protocol

        Sets the notification_interface data object
        """
        with FecTimer(RUN_LOOP, "Create notification protocol"):
            self._data_writer.set_notification_protocol(
                create_notification_protocol())

    def _execute_runner(self, n_sync_steps, run_time):
        """
        Runs, times and logs the ApplicationRunner

        :param int n_sync_steps:
            The number of timesteps between synchronisations
        :param int run_time: the run duration in milliseconds.
        :return:
        """
        with FecTimer(RUN_LOOP, APPLICATION_RUNNER) as timer:
            if timer.skip_if_virtual_board():
                return
            # Don't timeout if a stepped mode is in operation
            if n_sync_steps:
                time_threshold = None
            else:
                time_threshold = get_config_int(
                    "Machine", "post_simulation_overrun_before_error")
            application_runner(
                run_time, time_threshold, self._run_until_complete)

    def _execute_extract_iobuff(self):
        """
        Runs, times and logs the ChipIOBufExtractor if required
        """
        with FecTimer(RUN_LOOP, "Extract IO buff") as timer:
            if timer.skip_if_virtual_board():
                return
            if timer.skip_if_cfg_false(
                    "Reports", "extract_iobuf"):
                return
            # ErrorMessages, WarnMessages output ignored as never used!
            chip_io_buf_extractor()

    def _execute_buffer_extractor(self):
        """
        Runs, times and logs the BufferExtractor if required
        """
        with FecTimer(RUN_LOOP, "Buffer extractor") as timer:
            if timer.skip_if_virtual_board():
                return
            buffer_extractor()

    def _do_extract_from_machine(self):
        """
        Runs, times and logs the steps to extract data from the machine

        :param run_time: the run duration in milliseconds.
        :type run_time: int or None
        """
        self._execute_extract_iobuff()
        self._execute_buffer_extractor()
        self._execute_clear_io_buf()

        # FinaliseTimingData never needed as just pushed self._ to inputs
        self._do_read_provenance()
        with ProvenanceWriter() as db:
            db.insert_category_timing(
                RUN_LOOP, self._run_timer.take_sample(), self._n_loops)
        self._report_energy()
        self._do_provenance_reports()

    def __do_run(self, n_machine_time_steps, n_sync_steps):
        """
        Runs, times and logs the do run steps.

        :param n_machine_time_steps: Number of timesteps run
        :type n_machine_time_steps: int or None
        :param int n_sync_steps:
            The number of timesteps between synchronisations
        """
        # TODO virtual board
        self._run_timer = Timer()
        self._run_timer.start_timing()
        run_time = None
        if n_machine_time_steps is not None:
            run_time = (n_machine_time_steps *
                        self._data_writer.get_simulation_time_step_ms())
        self._data_writer.increment_current_run_timesteps(
            n_machine_time_steps)

        self._execute_sdram_usage_report_per_chip()
        self._report_drift(start=True)
        if self._data_writer.get_requires_mapping():
            self._execute_create_database_interface(run_time)
        self._execute_create_notifiaction_protocol()
        if (self._data_writer.is_ran_ever() and
                not self._data_writer.get_requires_mapping()):
            self._execute_dsg_region_reloader()
        self._execute_runtime_update(n_sync_steps)
        self._execute_runner(n_sync_steps, run_time)
        if n_machine_time_steps is not None or self._run_until_complete:
            self._do_extract_from_machine()
        # reset at the end of each do_run cycle
        self._report_drift(start=False)
        self._execute_control_sync(True)

    def _do_run(self, n_machine_time_steps, n_sync_steps):
        """
        Runs, times and logs the do run steps.

        :param n_machine_time_steps: Number of timesteps run
        :type n_machine_time_steps: int or None
        :param int n_sync_steps:
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

            # if in debug mode, do not shut down machine
            if get_config_str("Mode", "mode") != "Debug":
                try:
                    self.stop()
                except Exception as stop_e:
                    logger.exception(f"Error {stop_e} when attempting to stop")

            # reraise exception
            raise run_e

    def _recover_from_error(self, exception):
        """
        :param Exception exception:
        """
        try:
            self.__recover_from_error(exception)
        except Exception as rec_e:
            logger.exception(
                f"Error {rec_e} when attempting to recover from error")

    def __recover_from_error(self, exception):
        """
        :param Exception exception:
        """
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
                failed_cores = transceiver.get_cores_not_in_state(
                    core_subsets, executable_type.end_state)
                for (x, y, p) in failed_cores:
                    unsuccessful_cores.add_processor(
                        x, y, p, failed_cores.get_cpu_info(x, y, p))

        # Print the details of error cores
        logger.error(transceiver.get_core_status_string(unsuccessful_cores))

        # Find the cores that are not in RTE i.e. that can still be read
        non_rte_cores = [
            (x, y, p)
            for (x, y, p), core_info in unsuccessful_cores.items()
            if (core_info.state != CPUState.RUN_TIME_EXCEPTION and
                core_info.state != CPUState.WATCHDOG)]

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
                finished_cores = transceiver.get_cores_in_state(
                    non_rte_core_subsets, CPUState.FINISHED)
                finished_placements = Placements()
                placements = self._data_writer.get_placements()
                for (x, y, p) in finished_cores:
                    finished_placements.add_placement(
                        placements.get_placement_on_processor(x, y, p))
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
    def _print_iobuf(errors, warnings):
        """
        :param list(str) errors:
        :param list(str) warnings:
        """
        for warning in warnings:
            logger.warning(warning)
        for error in errors:
            logger.error(error)

    def reset(self):
        """ Code that puts the simulation back at time zero
        """
        if not self._data_writer.is_ran_last():
            if not self._data_writer.is_ran_ever():
                logger.error("Ignoring the reset before the run")
            else:
                logger.error("Ignoring the repeated reset call")
            return

        logger.info("Resetting")

        # rewind the buffers from the buffer manager, to start at the beginning
        # of the simulation again and clear buffered out
        if self._data_writer.has_buffer_manager():
            self._data_writer.get_buffer_manager().reset()

        if self._data_writer.get_user_accessed_machine():
            logger.warning(
                "A reset after a get machine call is always hard and "
                "therefore the previous machine is no longer valid")
            self._hard_reset()
        else:
            self._data_writer.soft_reset()

        # Reset the graph off the machine, to set things to time 0
        self.__reset_graph_elements()

    @property
    def n_loops(self):
        """
        The number for this or the net loop within an end_user run

        :rtype: int or None
        """
        return self._n_loops

    def __repr__(self):
        if self._data_writer.has_ipaddress():
            return f"general front end instance for machine " \
                   f"{self._data_writer.get_ipaddress()}"
        else:
            return "general front end instance no machine set"

    def _shutdown(self):

        # if stopping on machine, clear IP tags and routing table
        self.__clear()

        # stop the transceiver and allocation controller
        if self._data_writer.has_transceiver():
            transceiver = self._data_writer.get_transceiver()
            transceiver.stop_application(self._data_writer.get_app_id())

        self.__close_allocation_controller()
        self._data_writer.clear_notification_protocol()

    def __clear(self):
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
            machine = self._data_writer.get_machine()
            for router_table in self._data_writer.get_uncompressed():
                if not machine.get_chip_at(
                        router_table.x, router_table.y).virtual:
                    transceiver.clear_multicast_routes(
                        router_table.x, router_table.y)

    def __close_allocation_controller(self):
        if self._machine_allocation_controller is not None:
            self._machine_allocation_controller.close()
            self._machine_allocation_controller = None

    def stop(self):
        """
        End running of the simulation.

        """
        self._data_writer.stopping()
        # If we have run forever, stop the binaries

        try:
            if (self._data_writer.is_ran_ever()
                    and self._data_writer.get_current_run_timesteps() is None
                    and not get_config_bool("Machine", "virtual_board")
                    and not self._run_until_complete):
                self._do_stop_workflow()
            elif (get_config_bool("Reports", "read_provenance_data_on_end") and
                  not get_config_bool("Reports", "read_provenance_data")):
                set_config("Reports", "read_provenance_data", "True")
                self._do_read_provenance()

        except Exception as e:
            self._recover_from_error(e)
            self.write_errored_file()
            raise
        finally:
            # shut down the machine properly
            self._shutdown()

        self.write_finished_file()
        self._data_writer.shut_down()

    def _execute_application_finisher(self):
        with FecTimer(RUN_LOOP, "Application finisher"):
            application_finisher()

    def _do_stop_workflow(self):
        """
        :rtype: ~.PACMANAlgorithmExecutor
        """
        self._execute_application_finisher()
        self._do_extract_from_machine()

    @property
    def get_number_of_available_cores_on_machine(self):
        """ The number of available cores on the machine after taking\
            into account preallocated resources.

        :return: number of available cores
        :rtype: int
        """
        machine = self._data_writer.get_machine()
        # get cores of machine
        cores = machine.total_available_user_cores
        take_into_account_chip_power_monitor = get_config_bool(
            "Reports", "write_energy_report")
        if take_into_account_chip_power_monitor:
            cores -= machine.n_chips
        take_into_account_extra_monitor_cores = (get_config_bool(
            "Machine", "enable_advanced_monitor_support") or
                get_config_bool("Machine", "enable_reinjection"))
        if take_into_account_extra_monitor_cores:
            cores -= machine.n_chips
            cores -= len(machine.ethernet_connected_chips)
        return cores

    def stop_run(self):
        """ Request that the current infinite run stop.

        .. note::
            This will need to be called from another thread as the infinite \
            run call is blocking.

        raises SpiNNUtilsException:
            If the stop_run was not expected in the current state.
        """
        if self._data_writer.is_stop_already_requested():
            logger.warning(
                "Second Request to stop_run ignored")
            return
        with self._state_condition:
            self._data_writer.request_stop()
            self._state_condition.notify_all()

    def continue_simulation(self):
        """ Continue a simulation that has been started in stepped mode
        """
        sync_signal = self._data_writer.get_next_sync_signal()
        transceiver = self._data_writer.get_transceiver()
        transceiver.send_signal(self._data_writer.get_app_id(), sync_signal)

    @staticmethod
    def __reset_object(obj):
        # Reset an object if appropriate
        if isinstance(obj, AbstractCanReset):
            obj.reset_to_first_timestep()

    def __reset_graph_elements(self):
        # Reset any object that can reset
        for vertex in self._data_writer.iterate_vertices():
            self.__reset_object(vertex)
        for p in self._data_writer.iterate_partitions():
            for edge in p.edges:
                self.__reset_object(edge)

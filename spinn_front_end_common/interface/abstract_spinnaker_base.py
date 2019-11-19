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

"""
main interface for the SpiNNaker tools
"""
from collections import defaultdict
import logging
import math
import os
import signal
import sys
import time
import threading
from threading import Condition
from six import iteritems, reraise
from numpy import __version__ as numpy_version
from spinn_utilities.timer import Timer
from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides
from spinn_utilities import __version__ as spinn_utils_version
from spinn_machine import CoreSubsets
from spinn_machine import __version__ as spinn_machine_version
from spinn_machine.ignores import IgnoreChip, IgnoreCore, IgnoreLink
from spinnman.model.enums.cpu_state import CPUState
from spinnman import __version__ as spinnman_version
from spinnman.exceptions import SpiNNManCoresNotInStateException
from spinnman.model.cpu_infos import CPUInfos
from spinn_storage_handlers import __version__ as spinn_storage_version
from data_specification import __version__ as data_spec_version
from spalloc import __version__ as spalloc_version
from pacman.model.graphs.common import GraphMapper
from pacman.model.placements import Placements
from pacman.executor import PACMANAlgorithmExecutor
from pacman.exceptions import PacmanAlgorithmFailedToCompleteException
from pacman.model.graphs.application import (
    ApplicationGraph, ApplicationEdge, ApplicationVertex)
from pacman.model.graphs.machine import MachineGraph, MachineVertex
from pacman.model.resources import (PreAllocatedResourceContainer)
from pacman import __version__ as pacman_version
from spinn_front_end_common.abstract_models import (
    AbstractSendMeMulticastCommandsVertex,
    AbstractVertexWithEdgeToDependentVertices, AbstractChangableAfterRun,
    AbstractCanReset)
from spinn_front_end_common.utilities import (
    globals_variables, SimulatorInterface)
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.function_list import (
    get_front_end_common_pacman_xml_paths)
from spinn_front_end_common.utilities.helpful_functions import (
    convert_time_diff_to_total_milliseconds)
from spinn_front_end_common.utilities.report_functions import EnergyReport
from spinn_front_end_common.utilities.utility_objs import (
    ExecutableType, ProvenanceDataItem)
from spinn_front_end_common.utility_models import (
    CommandSender, CommandSenderMachineVertex,
    DataSpeedUpPacketGatherMachineVertex)
from spinn_front_end_common.interface.java_caller import JavaCaller
from spinn_front_end_common.interface.config_handler import ConfigHandler
from spinn_front_end_common.interface.provenance import (
    PacmanProvenanceExtractor)
from spinn_front_end_common.interface.simulator_state import Simulator_State
from spinn_front_end_common.interface.interface_functions import (
    ProvenanceXMLWriter, ProvenanceJSONWriter, ChipProvenanceUpdater,
    PlacementsProvenanceGatherer, RouterProvenanceGatherer, ChipIOBufExtractor)
from spinn_front_end_common import __version__ as fec_version
try:
    from scipy import __version__ as scipy_version
except ImportError:
    scipy_version = "scipy not installed"

logger = FormatAdapter(logging.getLogger(__name__))

#: Number of cores to be used when using a Virtual Machine and not specified
DEFAULT_N_VIRTUAL_CORES = 16

#: The minimum time a board is kept in the off state, in seconds
MINIMUM_OFF_STATE_TIME = 20

# 0-15 are reserved for system use (per lplana)
ALANS_DEFAULT_RANDOM_APP_ID = 16


class AbstractSpinnakerBase(ConfigHandler, SimulatorInterface):
    """ Main interface into the tools logic flow
    """
    # pylint: disable=broad-except

    __slots__ = [
        # the object that contains a set of file paths, which should encompass
        # all locations where binaries are for this simulation.
        "_executable_finder",

        # the number of chips required for this simulation to run, mainly tied
        # to the spalloc system
        "_n_chips_required",

        # the number of boards required for this simulation to run, mainly tied
        # to the spalloc system
        "_n_boards_required",

        # The IP-address of the SpiNNaker machine
        "_hostname",

        # the ip_address of the spalloc server
        "_spalloc_server",

        # the URL for the HBP platform interface
        "_remote_spinnaker_url",

        # the algorithm used for allocating machines from the HBP platform
        #  interface
        "_machine_allocation_controller",

        # the human readable label for the application graph.
        "_graph_label",

        # the pacman application graph, used to hold vertices which need to be
        # split to core sizes
        "_application_graph",

        # the end user application graph, used to hold vertices which need to
        # be split to core sizes
        "_original_application_graph",

        # the pacman machine graph, used to hold vertices which represent cores
        "_machine_graph",

        # the end user pacman machine graph, used to hold vertices which
        # represent cores.
        "_original_machine_graph",

        # the mapping interface between application and machine graphs.
        "_graph_mapper",

        # The holder for where machine graph vertices are placed.
        "_placements",

        # The holder for the routing table entries for all used routers in this
        # simulation
        "_router_tables",

        # the holder for the keys used by the machine vertices for
        # communication
        "_routing_infos",

        # the holder for the fixed routes generated, if there are any
        "_fixed_routes",

        # The holder for the IP tags and reverse IP tags used by the simulation
        "_tags",

        # The python representation of the SpiNNaker machine that this
        # simulation is going to run on
        "_machine",

        # The SpiNNMan interface instance.
        "_txrx",

        # The manager of streaming buffered data in and out of the SpiNNaker
        # machine
        "_buffer_manager",

        # Handler for keep all the calls to Java in a single space.
        # May be null is configs request not to use Java
        "_java_caller",

        #
        "_ip_address",

        #
        "_machine_outputs",

        #
        "_machine_tokens",

        #
        "_mapping_outputs",

        #
        "_mapping_tokens",

        #
        "_load_outputs",

        #
        "_load_tokens",

        #
        "_last_run_outputs",

        #
        "_last_run_tokens",

        #
        "_pacman_provenance",

        #
        "_xml_paths",

        #
        "_extra_mapping_algorithms",

        #
        "_extra_mapping_inputs",

        #
        "_extra_inputs",

        #
        "_extra_pre_run_algorithms",

        #
        "_extra_post_run_algorithms",

        #
        "_extra_load_algorithms",

        #
        "_dsg_algorithm",

        #
        "_none_labelled_edge_count",

        #
        "_database_socket_addresses",

        #
        "_database_interface",

        #
        "_create_database",

        #
        "_has_ran",

        #
        "_state",

        #
        "_state_condition",

        #
        "_has_reset_last",

        #
        "_current_run_timesteps",

        #
        "_no_sync_changes",

        #
        "_max_run_time_steps",

        #
        "_no_machine_time_steps",

        # The lowest values auto pause resume may use as steps
        "_minimum_auto_time_steps",

        #
        "_app_id",

        #
        "_do_timings",

        #
        "_print_timings",

        #
        "_provenance_format",

        #
        "_raise_keyboard_interrupt",

        #
        "_n_calls_to_run",

        #
        "_command_sender",

        # iobuf cores
        "_cores_to_read_iobuf",

        #
        "_all_provenance_items",

        #
        "_executable_types",

        # mapping between parameters and the vertices which need to talk to
        # them
        "_live_packet_recorder_params",

        # place holder for checking the vertices being added to the recorders
        # tracker are all of the same vertex type.
        "_live_packet_recorders_associated_vertex_type",

        # the time the process takes to do mapping
        "_mapping_time",

        # the time the process takes to do load
        "_load_time",

        # the time takes to execute the simulation
        "_execute_time",

        # time takes to do data generation
        "_dsg_time",

        # time taken by the front end extracting things
        "_extraction_time",

        # power save mode. time board turned off or None if not turned off
        "_machine_is_turned_off",

        # Version information from the front end
        "_front_end_versions",

        "_last_except_hook",

        "_vertices_or_edges_added",

        # Version provenance
        "_version_provenance"
    ]

    def __init__(
            self, configfile, executable_finder, graph_label=None,
            database_socket_addresses=None, extra_algorithm_xml_paths=None,
            n_chips_required=None, n_boards_required=None,
            default_config_paths=None,
            validation_cfg=None, front_end_versions=None):
        """
        :param configfile: What the configuration file is called
        :type configfile: str
        :param executable_finder: How to find APLX files to deploy to SpiNNaker
        :type executable_finder: \
            ~spinn_utilities.executable_finder.ExecutableFinder
        :param graph_label: A label for the overall application graph
        :type graph_label: str
        :param database_socket_addresses: How to talk to notification databases
        :type database_socket_addresses: \
            iterable(~spinn_utilities.socket_address.SocketAddress)
        :param extra_algorithm_xml_paths: \
            Where to load definitions of extra algorithms from
        :type extra_algorithm_xml_paths: iterable(str)
        :param n_chips_required: \
            Overrides the number of chips to allocate from spalloc
        :type n_chips_required: int
        :param n_boards_required: \
            Overrides the number of boards to allocate from spalloc
        :type n_boards_required: int
        :param default_config_paths: Directories to load configurations from
        :type default_config_paths: list(str)
        :param validation_cfg: How to validate configuration files
        :type validation_cfg: str
        :param front_end_versions: information about what software is in use
        :type front_end_versions: list(tuple(str,str))
        """
        # pylint: disable=too-many-arguments
        ConfigHandler.__init__(
            self, configfile, default_config_paths, validation_cfg)

        # timings
        self._mapping_time = 0.0
        self._load_time = 0.0
        self._execute_time = 0.0
        self._dsg_time = 0.0
        self._extraction_time = 0.0

        self._executable_finder = executable_finder

        # output locations of binaries to be searched for end user info
        logger.info(
            "Will search these locations for binaries: {}",
            self._executable_finder.binary_paths)

        if n_chips_required is None or n_boards_required is None:
            self._n_chips_required = n_chips_required
            self._n_boards_required = n_boards_required
        else:
            raise ConfigurationException(
                "Please use at most one of n_chips_required or "
                "n_boards_required")
        self._hostname = None
        self._spalloc_server = None
        self._remote_spinnaker_url = None
        self._machine_allocation_controller = None

        # command sender vertex
        self._command_sender = None

        # store for Live Packet Gatherers
        self._live_packet_recorder_params = defaultdict(list)
        self._live_packet_recorders_associated_vertex_type = None

        # update graph label if needed
        if graph_label is None:
            self._graph_label = "Application_graph"
        else:
            self._graph_label = graph_label

        # pacman objects
        self._original_application_graph = \
            ApplicationGraph(label=self._graph_label)
        self._original_machine_graph = MachineGraph(label=self._graph_label)

        self._graph_mapper = None
        self._placements = None
        self._router_tables = None
        self._routing_infos = None
        self._fixed_routes = None
        self._application_graph = None
        self._machine_graph = None
        self._tags = None
        self._machine = None
        self._txrx = None
        self._buffer_manager = None
        self._java_caller = None
        self._ip_address = None
        self._executable_types = None

        # pacman executor objects
        self._machine_outputs = None
        self._machine_tokens = None
        self._mapping_outputs = None
        self._mapping_tokens = None
        self._load_outputs = None
        self._load_tokens = None
        self._last_run_outputs = None
        self._last_run_tokens = None
        self._pacman_provenance = PacmanProvenanceExtractor()
        self._all_provenance_items = list()
        self._version_provenance = list()
        self._xml_paths = self._create_xml_paths(extra_algorithm_xml_paths)

        # extra algorithms and inputs for runs, should disappear in future
        #  releases
        self._extra_mapping_algorithms = list()
        self._extra_mapping_inputs = dict()
        self._extra_inputs = dict()
        self._extra_pre_run_algorithms = list()
        self._extra_post_run_algorithms = list()
        self._extra_load_algorithms = list()

        self._dsg_algorithm = "GraphDataSpecificationWriter"

        # vertex label safety (used by reports mainly)
        self._none_labelled_edge_count = 0

        # database objects
        self._database_socket_addresses = set()
        if database_socket_addresses is not None:
            self._database_socket_addresses.update(database_socket_addresses)
        self._database_interface = None
        self._create_database = None

        # holder for timing related values
        self._has_ran = False
        self._state = Simulator_State.INIT
        self._state_condition = Condition()
        self._has_reset_last = False
        self._n_calls_to_run = 1
        self._current_run_timesteps = 0
        self._no_sync_changes = 0
        self._max_run_time_steps = None
        self._no_machine_time_steps = None
        self._minimum_auto_time_steps = self._config.getint(
                "Buffers", "minimum_auto_time_steps")

        self._app_id = self._read_config_int("Machine", "app_id")

        # folders
        self._pacman_executor_provenance_path = None
        self._set_up_output_folders(self._n_calls_to_run)

        # timing provenance elements
        self._do_timings = self._config.getboolean(
            "Reports", "write_algorithm_timings")
        self._print_timings = self._config.getboolean(
            "Reports", "display_algorithm_timings")
        self._provenance_format = self._config.get(
            "Reports", "provenance_format")
        if self._provenance_format not in ["xml", "json"]:
            raise Exception("Unknown provenance format: {}".format(
                self._provenance_format))

        # Setup for signal handling
        self._raise_keyboard_interrupt = False

        # By default board is kept on once started later
        self._machine_is_turned_off = None

        globals_variables.set_simulator(self)

        # Front End version information
        self._front_end_versions = front_end_versions

        self._last_except_hook = sys.excepthook
        self._vertices_or_edges_added = False

    def set_n_boards_required(self, n_boards_required):
        """
        Sets the machine requirements.

        Warning: This method should not be called after the machine
        requirements have be computed based on the graph.

        :param n_boards_required: The number of boards required
        :raises: ConfigurationException
            If any machine requirements have already been set
        """
        # Catch the unchanged case including leaving it None
        if n_boards_required == self._n_boards_required:
            return
        if self._n_boards_required is not None:
            raise ConfigurationException(
                "Illegal attempt to change previously set value.")
        if self._n_chips_required is not None:
            raise ConfigurationException(
                "Clash with n_chips_required.")
        self._n_boards_required = n_boards_required

    def update_extra_mapping_inputs(self, extra_mapping_inputs):
        """ Supply extra inputs to the mapping algorithms. Mappings are from\
            known names (the logical type names) to the values to bind to them.

        :param extra_inputs: The additional inputs to provide
        :type extra_inputs: dict(str,any)
        """
        if self.has_ran:
            raise ConfigurationException(
                "Changing mapping inputs is not supported after run")
        if extra_mapping_inputs is not None:
            self._extra_mapping_inputs.update(extra_mapping_inputs)

    def update_extra_inputs(self, extra_inputs):
        """ Supply extra inputs to the runtime algorithms. Mappings are from\
            known names (the logical type names) to the values to bind to them.

        :param extra_inputs: The additional inputs to provide
        :type extra_inputs: dict(str,any)
        """
        if self.has_ran:
            raise ConfigurationException(
                "Changing inputs is not supported after run")
        if extra_inputs is not None:
            self._extra_inputs.update(extra_inputs)

    def extend_extra_mapping_algorithms(self, extra_mapping_algorithms):
        """ Add custom mapping algorithms to the end of the sequence of \
            mapping algorithms to be run.

        :param extra_mapping_algorithms: Algorithms to add
        :type extra_mapping_algorithms: list
        """
        if self.has_ran:
            raise ConfigurationException(
                "Changing algorithms is not supported after run")
        if extra_mapping_algorithms is not None:
            self._extra_mapping_algorithms.extend(extra_mapping_algorithms)

    def prepend_extra_pre_run_algorithms(self, extra_pre_run_algorithms):
        """ Add custom pre-execution algorithms to the front of the sequence \
            of algorithms to be run.

        :param extra_pre_run_algorithms: Algorithms to add
        :type extra_pre_run_algorithms: list
        """
        if self.has_ran:
            raise ConfigurationException(
                "Changing algorithms is not supported after run")
        if extra_pre_run_algorithms is not None:
            self._extra_pre_run_algorithms[0:0] = extra_pre_run_algorithms

    def extend_extra_post_run_algorithms(self, extra_post_run_algorithms):
        """ Add custom post-execution algorithms to the sequence of \
            such algorithms to be run.

        :param extra_post_run_algorithms: Algorithms to add
        :type extra_post_run_algorithms: list
        """
        if self.has_ran:
            raise ConfigurationException(
                "Changing algorithms is not supported after run")
        if extra_post_run_algorithms is not None:
            self._extra_post_run_algorithms.extend(extra_post_run_algorithms)

    def extend_extra_load_algorithms(self, extra_load_algorithms):
        """ Add custom data-loading algorithms to the sequence of \
            such algorithms to be run.

        :param extra_load_algorithms: Algorithms to add
        :type extra_load_algorithms: list
        """
        if self.has_ran:
            raise ConfigurationException(
                "Changing algorithms is not supported after run")
        if extra_load_algorithms is not None:
            self._extra_load_algorithms.extend(extra_load_algorithms)

    def add_extraction_timing(self, timing):
        """ Record the time taken for doing data extraction.
        """
        ms = convert_time_diff_to_total_milliseconds(timing)
        self._extraction_time += ms

    def add_live_packet_gatherer_parameters(
            self, live_packet_gatherer_params, vertex_to_record_from,
            partition_ids):
        """ Adds params for a new LPG if needed, or adds to the tracker for\
            same params.

        :param live_packet_gatherer_params: params to look for a LPG
        :param vertex_to_record_from: \
            the vertex that needs to send to a given LPG
        :param partition_ids: \
            the IDs of the partitions to connect from the vertex
        :rtype: None
        """
        self._live_packet_recorder_params[live_packet_gatherer_params].append(
            (vertex_to_record_from, partition_ids))

        # verify that the vertices being added are of one vertex type.
        if self._live_packet_recorders_associated_vertex_type is None:
            if isinstance(vertex_to_record_from, ApplicationVertex):
                self._live_packet_recorders_associated_vertex_type = \
                    ApplicationVertex
            else:
                self._live_packet_recorders_associated_vertex_type = \
                    MachineVertex
        elif not isinstance(
                vertex_to_record_from,
                self._live_packet_recorders_associated_vertex_type):
            raise ConfigurationException(
                "Only one type of graph can be used during live output. "
                "Please fix and try again")

    # options names are all lower without _ inside config
    _DEBUG_ENABLE_OPTS = frozenset([
        "reportsenabled",
        "clear_iobuf_during_run", "extract_iobuf", "extract_iobuf_during_run"])
    _REPORT_DISABLE_OPTS = frozenset([
        "clear_iobuf_during_run", "extract_iobuf", "extract_iobuf_during_run"])

    def set_up_machine_specifics(self, hostname):
        """ Adds machine specifics for the different modes of execution

        :param hostname: machine name
        :type hostname: str
        :rtype: None
        """
        if hostname is not None:
            self._hostname = hostname
            logger.warning("The machine name from setup call is overriding "
                           "the machine name defined in the config file")
        else:
            self._hostname = self._read_config("Machine", "machine_name")
            self._spalloc_server = self._read_config(
                "Machine", "spalloc_server")
            self._remote_spinnaker_url = self._read_config(
                "Machine", "remote_spinnaker_url")

        if (self._hostname is None and self._spalloc_server is None and
                self._remote_spinnaker_url is None and
                not self._use_virtual_board):
            raise Exception(
                "A SpiNNaker machine must be specified your configuration"
                " file")

        n_items_specified = sum([
            1 if item is not None else 0
            for item in [
                self._hostname, self._spalloc_server,
                self._remote_spinnaker_url]])

        if (n_items_specified > 1 or
                (n_items_specified == 1 and self._use_virtual_board)):
            raise Exception(
                "Only one of machineName, spalloc_server, "
                "remote_spinnaker_url and virtual_board should be specified "
                "in your configuration files")

        if self._spalloc_server is not None:
            if self._read_config("Machine", "spalloc_user") is None:
                raise Exception(
                    "A spalloc_user must be specified with a spalloc_server")

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

        :param exctype:  the type of execution received
        :param value: the value of the exception
        :param traceback_obj: the trace back stuff
        """
        logger.error("Shutdown on exception")
        self._shutdown()
        return self._last_except_hook(exctype, value, traceback_obj)

    @overrides(SimulatorInterface.verify_not_running)
    def verify_not_running(self):
        if self._state in [Simulator_State.IN_RUN,
                           Simulator_State.RUN_FOREVER]:
            raise ConfigurationException(
                "Illegal call while a simulation is already running")
        if self._state in [Simulator_State.SHUTDOWN]:
            raise ConfigurationException(
                "Illegal call after simulation is shutdown")

    def run_until_complete(self):
        """ Run a simulation until it completes
        """
        self._run(None, run_until_complete=True)

    @overrides(SimulatorInterface.run)
    def run(self, run_time):
        """ Run a simulation for a fixed amount of time

        :param run_time: the run duration in milliseconds.
        """
        self._run(run_time)

    def _build_graphs_for_usage(self):
        # sort out app graph
        self._application_graph = ApplicationGraph(
            label=self._original_application_graph.label)
        for vertex in self._original_application_graph.vertices:
            self._application_graph.add_vertex(vertex)
        for outgoing_partition in \
                self._original_application_graph.outgoing_edge_partitions:
            for edge in outgoing_partition.edges:
                self._application_graph.add_edge(
                    edge, outgoing_partition.identifier)

        # sort out machine graph
        self._machine_graph = MachineGraph(
            label=self._original_machine_graph.label)
        for vertex in self._original_machine_graph.vertices:
            self._machine_graph.add_vertex(vertex)
        for outgoing_partition in \
                self._original_machine_graph.outgoing_edge_partitions:
            self._machine_graph.add_outgoing_edge_partition(outgoing_partition)
            for edge in outgoing_partition.edges:
                self._machine_graph.add_edge(
                    edge, outgoing_partition.identifier)

    def _run(self, run_time, run_until_complete=False):
        """ The main internal run function

        :param run_time: the run duration in milliseconds.
        """
        self.verify_not_running()

        # verify that we can keep doing auto pause and resume
        if self._has_ran:
            can_keep_running = all(
                executable_type.supports_auto_pause_and_resume
                for executable_type in self._executable_types)
            if not can_keep_running:
                raise NotImplementedError(
                    "Only binaries that use the simulation interface can be"
                    " run more than once")

        self._state = Simulator_State.IN_RUN

        self._adjust_config(
            run_time, self._DEBUG_ENABLE_OPTS, self._REPORT_DISABLE_OPTS)

        # Install the Control-C handler
        if isinstance(threading.current_thread(), threading._MainThread):
            signal.signal(signal.SIGINT, self.__signal_handler)
            self._raise_keyboard_interrupt = True
            sys.excepthook = self._last_except_hook

        logger.info("Starting execution process")

        n_machine_time_steps = None
        total_run_time = None
        if run_time is not None:
            n_machine_time_steps = int(
                (run_time * 1000.0) / self.machine_time_step)
            total_run_timesteps = (
                self._current_run_timesteps + n_machine_time_steps)
            total_run_time = (
                total_run_timesteps *
                (float(self.machine_time_step) / 1000.0) *
                self.time_scale_factor)
        if self._machine_allocation_controller is not None:
            self._machine_allocation_controller.extend_allocation(
                total_run_time)

        # If we have never run before, or the graph has changed,
        # start by performing mapping
        graph_changed, data_changed = self._detect_if_graph_has_changed(True)
        if graph_changed and self._has_ran and not self._has_reset_last:
            self.stop()
            raise NotImplementedError(
                "The network cannot be changed between runs without"
                " resetting")

        # If we have reset and the graph has changed, stop any running
        # application
        if (graph_changed or data_changed) and self._has_ran:
            if self._txrx is not None:
                self._txrx.stop_application(self._app_id)

            # change number of resets as loading the binary again resets the
            # sync to 0
            self._no_sync_changes = 0

            # create new sub-folder for reporting data
            self._set_up_output_folders(self._n_calls_to_run)

        # build the graphs to modify with system requirements
        if not self._has_ran or graph_changed:
            self._build_graphs_for_usage()
            self._add_dependent_verts_and_edges_for_application_graph()
            self._add_commands_to_command_sender()

            # Reset the machine graph if there is an application graph
            if self._application_graph.n_vertices:
                self._machine_graph = MachineGraph(self._graph_label)
                self._graph_mapper = None

            # Reset the machine if the graph has changed
            if not self._use_virtual_board and self._n_calls_to_run > 1:

                # wipe out stuff associated with a given machine, as these need
                # to be rebuilt.
                self._machine = None
                self._buffer_manager = None
                self._java_caller = None
                if self._txrx is not None:
                    self._txrx.close()
                    self._app_id = None
                if self._machine_allocation_controller is not None:
                    self._machine_allocation_controller.close()
                self._max_run_time_steps = None

            if self._machine is None:
                self._get_machine(total_run_time, n_machine_time_steps)
            self._do_mapping(run_time, total_run_time)

        # Check if anything has per-timestep SDRAM usage
        is_per_timestep_sdram = self._is_per_timestep_sdram()

        # Disable auto pause and resume if the binary can't do it
        for executable_type in self._executable_types:
            if not executable_type.supports_auto_pause_and_resume:
                self._config.set("Buffers",
                                 "use_auto_pause_and_resume", "False")

        # Work out the maximum run duration given all recordings
        if self._max_run_time_steps is None:
            self._max_run_time_steps = self._deduce_data_n_timesteps()

        # Work out an array of timesteps to perform
        steps = None
        if (not self._config.getboolean("Buffers", "use_auto_pause_and_resume")
                or not is_per_timestep_sdram):

            # Runs should only be in units of max_run_time_steps at most
            if (is_per_timestep_sdram and
                    (self._max_run_time_steps < n_machine_time_steps or
                        n_machine_time_steps is None)):
                self._state = Simulator_State.FINISHED
                raise ConfigurationException(
                    "The SDRAM required by one or more vertices is based on"
                    " the run time, so the run time is limited to"
                    " {} time steps".format(self._max_run_time_steps))

            steps = [n_machine_time_steps]
        elif run_time is not None:

            # With auto pause and resume, any time step is possible but run
            # time more than the first will guarantee that run will be called
            # more than once
            steps = self._generate_steps(
                n_machine_time_steps, self._max_run_time_steps)

        # If we have never run before, or the graph has changed, or data has
        # been changed, generate and load the data
        if not self._has_ran or graph_changed or data_changed:
            self._do_data_generation(self._max_run_time_steps)

            # If we are using a virtual board, don't load
            if not self._use_virtual_board:
                self._do_load(graph_changed)

        # Run for each of the given steps
        if run_time is not None:
            logger.info("Running for {} steps for a total of {}ms",
                        len(steps), run_time)
            for i, step in enumerate(steps):
                logger.info("Run {} of {}", i + 1, len(steps))
                self._do_run(step, graph_changed, run_until_complete)
        elif run_time is None and run_until_complete:
            logger.info("Running until complete")
            self._do_run(None, graph_changed, True)
        elif (not self._config.getboolean(
                "Buffers", "use_auto_pause_and_resume") or
                not is_per_timestep_sdram):
            logger.info("Running forever")
            self._do_run(None, graph_changed, run_until_complete)
            logger.info("Waiting for stop request")
            with self._state_condition:
                while self._state != Simulator_State.STOP_REQUESTED:
                    self._state_condition.wait()
        else:
            logger.info("Running forever in steps of {}ms".format(
                self._max_run_time_steps))
            i = 0
            while self._state != Simulator_State.STOP_REQUESTED:
                logger.info("Run {}".format(i + 1))
                self._do_run(
                    self._max_run_time_steps, graph_changed,
                    run_until_complete)
                i += 1

        # Indicate that the signal handler needs to act
        if isinstance(threading.current_thread(), threading._MainThread):
            self._raise_keyboard_interrupt = False
            self._last_except_hook = sys.excepthook
            sys.excepthook = self.exception_handler

        # update counter for runs (used by reports and app data)
        self._n_calls_to_run += 1
        if run_time is not None:
            self._state = Simulator_State.FINISHED
        else:
            self._state = Simulator_State.RUN_FOREVER

    def _is_per_timestep_sdram(self):
        for placement in self._placements.placements:
            if placement.vertex.resources_required.sdram.per_timestep:
                return True
        return False

    def _add_commands_to_command_sender(self):
        vertices = self._application_graph.vertices
        graph = self._application_graph
        command_sender_vertex = CommandSender
        if len(vertices) == 0:
            vertices = self._machine_graph.vertices
            graph = self._machine_graph
            command_sender_vertex = CommandSenderMachineVertex
        for vertex in vertices:
            if isinstance(vertex, AbstractSendMeMulticastCommandsVertex):
                # if there's no command sender yet, build one
                if self._command_sender is None:
                    self._command_sender = command_sender_vertex(
                        "auto_added_command_sender", None)
                    graph.add_vertex(self._command_sender)

                # allow the command sender to create key to partition map
                self._command_sender.add_commands(
                    vertex.start_resume_commands,
                    vertex.pause_stop_commands,
                    vertex.timed_commands, vertex)

        # add the edges from the command sender to the dependent vertices
        if self._command_sender is not None:
            edges, partition_ids = self._command_sender.edges_and_partitions()
            for edge, partition_id in zip(edges, partition_ids):
                graph.add_edge(edge, partition_id)

    def _add_dependent_verts_and_edges_for_application_graph(self):
        for vertex in self._application_graph.vertices:
            # add any dependent edges and vertices if needed
            if isinstance(vertex, AbstractVertexWithEdgeToDependentVertices):
                for dependant_vertex in vertex.dependent_vertices():
                    self._application_graph.add_vertex(dependant_vertex)
                    edge_partition_ids = vertex.\
                        edge_partition_identifiers_for_dependent_vertex(
                            dependant_vertex)
                    for edge_identifier in edge_partition_ids:
                        dependant_edge = ApplicationEdge(
                            pre_vertex=vertex,
                            post_vertex=dependant_vertex)
                        self._application_graph.add_edge(
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

        for placement in self._placements.placements:
            sdram_required = placement.vertex.resources_required.sdram
            if (placement.x, placement.y) in usage_by_chip:
                usage_by_chip[placement.x, placement.y] += sdram_required
            else:
                usage_by_chip[placement.x, placement.y] = sdram_required

        # Go through the chips and divide up the remaining SDRAM, finding
        # the minimum number of machine timesteps to assign
        max_time_steps = sys.maxsize
        for (x, y), sdram in usage_by_chip.items():
            size = self._machine.get_chip_at(x, y).sdram.size
            if sdram.per_timestep:
                max_this_chip = int((size - sdram.fixed) // sdram.per_timestep)
                max_time_steps = min(max_time_steps, max_this_chip)

        return max_time_steps

    @staticmethod
    def _generate_steps(n_steps, n_steps_per_segment):
        """ Generates the list of "timer" runs. These are usually in terms of\
            time steps, but need not be.

        :param n_steps: the total runtime in machine time steps
        :type n_steps: int
        :param n_steps_per_segment: the minimum allowed per chunk
        :type n_steps_per_segment: int
        :return: list of time steps
        """
        if n_steps == 0:
            return [0]
        n_full_iterations = int(math.floor(n_steps / n_steps_per_segment))
        left_over_steps = n_steps - n_full_iterations * n_steps_per_segment
        steps = [int(n_steps_per_segment)] * n_full_iterations
        if left_over_steps:
            steps.append(int(left_over_steps))
        return steps

    def _calculate_number_of_machine_time_steps(self, next_run_timesteps):
        if next_run_timesteps is not None:
            total_timesteps = next_run_timesteps + self._current_run_timesteps
            self._no_machine_time_steps = total_timesteps
            return total_timesteps

        self._no_machine_time_steps = None
        return None

    def _run_algorithms(
            self, inputs, algorithms, outputs, tokens, required_tokens,
            provenance_name, optional_algorithms=None):
        """ Runs getting a SpiNNaker machine logic

        :param inputs: the inputs
        :param algorithms: algorithms to call
        :param outputs: outputs to get
        :param tokens: The tokens to start with
        :param required_tokens: The tokens that must be generated
        :param optional_algorithms: optional algorithms to use
        :param provenance_name: the name for provenance
        :return: None
        """
        # pylint: disable=too-many-arguments
        optional = optional_algorithms
        if optional is None:
            optional = []

        # Execute the algorithms
        executor = PACMANAlgorithmExecutor(
            algorithms=algorithms, optional_algorithms=optional,
            inputs=inputs, tokens=tokens,
            required_output_tokens=required_tokens, xml_paths=self._xml_paths,
            required_outputs=outputs, do_timings=self._do_timings,
            print_timings=self._print_timings,
            provenance_name=provenance_name,
            provenance_path=self._pacman_executor_provenance_path)

        try:
            executor.execute_mapping()
            self._pacman_provenance.extract_provenance(executor)
            return executor
        except Exception:
            self._txrx = executor.get_item("MemoryTransceiver")
            self._machine_allocation_controller = executor.get_item(
                "MachineAllocationController")
            exc_info = sys.exc_info()
            try:
                self._shutdown()
                self.write_finished_file()
            except Exception:
                logger.warning("problem when shutting down", exc_info=True)
            reraise(*exc_info)

    def _get_machine(self, total_run_time=0.0, n_machine_time_steps=None):
        if self._machine is not None:
            return self._machine

        # If we are using a directly connected machine, add the details to get
        # the machine and transceiver
        if self._hostname is not None:
            self._machine_by_hostname(n_machine_time_steps, total_run_time)

        elif self._use_virtual_board:
            self._machine_by_virtual(n_machine_time_steps, total_run_time)
        else:
            # must be remote due to set_up_machine_specifics()
            self._machine_by_remote(n_machine_time_steps, total_run_time)

        if self._app_id is None:
            if self._txrx is None:
                self._app_id = ALANS_DEFAULT_RANDOM_APP_ID
            else:
                self._app_id = self._txrx.app_id_tracker.get_new_id()

        self._turn_off_on_board_to_save_power("turn_off_board_after_discovery")

        if self._n_chips_required:
            if self._machine.n_chips < self._n_chips_required:
                raise ConfigurationException(
                    "Failure to detect machine of with {} chips as requested. "
                    "Only found {}".format(self._n_chips_required,
                                           self._machine))
        if self._n_boards_required:
            if len(self._machine.ethernet_connected_chips) \
                    < self._n_boards_required:
                raise ConfigurationException(
                    "Failure to detect machine with {} boards as requested. "
                    "Only found {}".format(self._n_boards_required,
                                           self._machine))

        return self._machine

    def _machine_by_hostname(self, n_machine_time_steps, total_run_time):
        inputs, algorithms = self._get_machine_common(
            n_machine_time_steps, total_run_time)
        outputs = list()
        inputs["IPAddress"] = self._hostname
        inputs["BMPDetails"] = self._read_config("Machine", "bmp_names")
        inputs["AutoDetectBMPFlag"] = self._config.getboolean(
            "Machine", "auto_detect_bmp")
        inputs["ScampConnectionData"] = self._read_config(
            "Machine", "scamp_connections_data")
        inputs['ReportFolder'] = self._report_default_directory
        algorithms.append("MachineGenerator")

        outputs.append("MemoryMachine")
        outputs.append("MemoryTransceiver")

        executor = self._run_algorithms(
            inputs, algorithms, outputs, [], [], "machine_generation")
        self._machine = executor.get_item("MemoryMachine")
        self._txrx = executor.get_item("MemoryTransceiver")
        self._machine_outputs = executor.get_items()
        self._machine_tokens = executor.get_completed_tokens()

    def _machine_by_virtual(self, n_machine_time_steps, total_run_time):
        inputs, algorithms = self._get_machine_common(
            n_machine_time_steps, total_run_time)
        outputs = list()

        inputs["IPAddress"] = "virtual"
        inputs["NumberOfBoards"] = self._read_config_int(
            "Machine", "number_of_boards")
        inputs["MachineWidth"] = self._read_config_int(
            "Machine", "width")
        inputs["MachineHeight"] = self._read_config_int(
            "Machine", "height")
        inputs["MachineJsonPath"] = self._read_config(
            "Machine", "json_path")
        inputs["BMPDetails"] = None
        inputs["AutoDetectBMPFlag"] = False
        inputs["ScampConnectionData"] = None
        inputs["RouterTableEntriesPerRouter"] = \
            self._read_config_int("Machine", "RouterTableEntriesPerRouter")

        algorithms.append("VirtualMachineGenerator")

        outputs.append("MemoryMachine")

        executor = self._run_algorithms(
            inputs, algorithms, outputs, [], [], "machine_generation")
        self._machine_outputs = executor.get_items()
        self._machine_tokens = executor.get_completed_tokens()
        self._machine = executor.get_item("MemoryMachine")

    def _machine_by_remote(self, n_machine_time_steps, total_run_time):
        """
        Gets a machine when we know one of self._spalloc_server or\
            self._remote_spinnaker_url is defined
        """
        inputs, algorithms = self._get_machine_common(
            n_machine_time_steps, total_run_time)
        outputs = list()

        do_partitioning = self._machine_by_size(inputs, algorithms, outputs)
        inputs['ReportFolder'] = self._report_default_directory

        # if using spalloc system
        if self._spalloc_server is not None:
            inputs["SpallocServer"] = self._spalloc_server
            inputs["SpallocPort"] = self._read_config_int(
                "Machine", "spalloc_port")
            inputs["SpallocUser"] = self._read_config(
                "Machine", "spalloc_user")
            inputs["SpallocMachine"] = self._read_config(
                "Machine", "spalloc_machine")
        else:
            # must be using HBP server system
            inputs["RemoteSpinnakerUrl"] = self._remote_spinnaker_url

        if self._spalloc_server is not None:
            algorithms.append("SpallocAllocator")
        elif self._remote_spinnaker_url is not None:
            algorithms.append("HBPAllocator")

        algorithms.append("MachineGenerator")

        outputs.append("MemoryMachine")
        outputs.append("IPAddress")
        outputs.append("MemoryTransceiver")
        outputs.append("MachineAllocationController")

        executor = self._run_algorithms(
            inputs, algorithms, outputs, [], [], "machine_generation")

        self._machine_outputs = executor.get_items()
        self._machine_tokens = executor.get_completed_tokens()
        self._machine = executor.get_item("MemoryMachine")
        self._ip_address = executor.get_item("IPAddress")
        self._txrx = executor.get_item("MemoryTransceiver")
        self._machine_allocation_controller = executor.get_item(
            "MachineAllocationController")

        if do_partitioning:
            self._machine_graph = executor.get_item(
                "MemoryMachineGraph")
            self._graph_mapper = executor.get_item(
                "MemoryGraphMapper")

    def _machine_by_size(self, inputs, algorithms, outputs):
        """
        Checks if we can get a remote machine by size of if we have to use a\
        virtual machine to get the size

        Adds the requires info to inputs, algorithms, outputs

        :param inputs: Data to go into executor
        :param algorithms: Algorithms to execute
        :param outputs: Data needed after execution
        :return: True if and only if the required steps included partitioning
        """
        # If we are using an allocation server but have been told how
        # many chips to use, just use that as an input
        if self._n_chips_required:
            inputs["NChipsRequired"] = self._n_chips_required
            return False
        if self._n_boards_required:
            inputs["NBoardsRequired"] = self._n_boards_required
            return False

        # only add machine graph is it has vertices.
        if (self._machine_graph is not None and
                self._machine_graph.n_vertices != 0):
            inputs["MemoryMachineGraph"] = self._machine_graph
            algorithms.append("GraphMeasurer")
            do_partitioning = False
        # If we are using an allocation server, and we need a virtual
        # board, we need to use the virtual board to get the number of
        # chips to be allocated either by partitioning, or by measuring
        # the graph
        elif (self._application_graph is not None and
                self._application_graph.n_vertices > 0):
            inputs["MemoryApplicationGraph"] = self._application_graph
            algorithms.extend(self._config.get(
                "Mapping",
                "application_to_machine_graph_algorithms").split(","))
            outputs.append("MemoryMachineGraph")
            outputs.append("MemoryGraphMapper")
            do_partitioning = True
        else:
            # No way to decided size so default to one board
            logger.warning(
                "Your graph has no vertices in it. "
                "Will default to a machine with 1 board.")
            inputs["NBoardsRequired"] = 1
            return False

        # Ok we do need a virtual machine
        if self._spalloc_server is not None:
            algorithms.append("SpallocMaxMachineGenerator")
        else:
            algorithms.append("HBPMaxMachineGenerator")

        return do_partitioning

    def _get_machine_common(self, n_machine_time_steps, total_run_time):
        inputs = dict(self._extra_inputs)
        algorithms = list()

        self._create_version_provenance()
        inputs["UsingAdvancedMonitorSupport"] = self._config.getboolean(
            "Machine", "enable_advanced_monitor_support")
        inputs["DisableAdvancedMonitorUsageForDataIn"] = \
            self._config.getboolean(
                "Machine", "disable_advanced_monitor_usage_for_data_in")

        if (self._config.getboolean("Buffers", "use_auto_pause_and_resume")):
            inputs["PlanNTimeSteps"] = self._minimum_auto_time_steps
        else:
            inputs["PlanNTimeSteps"] = n_machine_time_steps

        # add max SDRAM size and n_cores which we're going to allow
        # (debug purposes)
        inputs["MaxSDRAMSize"] = self._read_config_int(
            "Machine", "max_sdram_allowed_per_chip")
        # Set the total run time
        inputs["TotalRunTime"] = total_run_time
        inputs["MaxMachineCoreReduction"] = self._read_config_int(
            "Machine", "max_machine_core_reduction")
        inputs["MachineTimeStep"] = self.machine_time_step
        inputs["TimeScaleFactor"] = self.time_scale_factor

        inputs["DownedChipsDetails"] = IgnoreChip.parse_string(
            self._config.get("Machine", "down_chips"))
        inputs["DownedCoresDetails"] = IgnoreCore.parse_string(
            self._config.get("Machine", "down_cores"))
        inputs["DownedLinksDetails"] = IgnoreLink.parse_string(
            self._config.get("Machine", "down_links"))
        inputs["BoardVersion"] = self._read_config_int(
            "Machine", "version")
        inputs["ResetMachineOnStartupFlag"] = self._config.getboolean(
            "Machine", "reset_machine_on_startup")
        inputs["BootPortNum"] = self._read_config_int(
            "Machine", "boot_connection_port_num")
        inputs["RepairMachine"] = self._config.getboolean(
            "Machine", "repair_machine")
        inputs["IgnoreBadEthernets"] = self._config.getboolean(
            "Machine", "ignore_bad_ethernets")

        # add algorithms for handling LPG placement and edge insertion
        if self._live_packet_recorder_params:
            algorithms.append("PreAllocateResourcesForLivePacketGatherers")
            inputs['LivePacketRecorderParameters'] = \
                self._live_packet_recorder_params

        if self._config.getboolean("Reports", "write_energy_report"):
            algorithms.append("PreAllocateResourcesForChipPowerMonitor")
            inputs['MemorySamplingFrequency'] = self._config.getint(
                "EnergyMonitor", "sampling_frequency")
            inputs['MemoryNumberSamplesPerRecordingEntry'] = \
                self._config.getint(
                    "EnergyMonitor", "n_samples_per_recording_entry")

        # add algorithms for handling extra monitor code
        if (self._config.getboolean("Machine",
                                    "enable_advanced_monitor_support") or
                self._config.getboolean("Machine", "enable_reinjection")):
            algorithms.append("PreAllocateResourcesForExtraMonitorSupport")

        # add the application and machine graphs as needed
        if (self._application_graph is not None and
                self._application_graph.n_vertices > 0):
            inputs["MemoryApplicationGraph"] = self._application_graph
        elif (self._machine_graph is not None and
                self._machine_graph.n_vertices > 0):
            inputs["MemoryMachineGraph"] = self._machine_graph

        return inputs, algorithms

    def _create_version_provenance(self):
        # Add the version information to the provenance data at the start
        version_provenance = list()
        version_provenance.append(ProvenanceDataItem(
            ["version_data", "spinn_utilities_version"], spinn_utils_version))
        version_provenance.append(ProvenanceDataItem(
            ["version_data", "spinn_machine_version"], spinn_machine_version))
        version_provenance.append(ProvenanceDataItem(
            ["version_data", "spinn_storage_handlers_version"],
            spinn_storage_version))
        version_provenance.append(ProvenanceDataItem(
            ["version_data", "spalloc_version"], spalloc_version))
        version_provenance.append(ProvenanceDataItem(
            ["version_data", "spinnman_version"], spinnman_version))
        version_provenance.append(ProvenanceDataItem(
            ["version_data", "pacman_version"], pacman_version))
        version_provenance.append(ProvenanceDataItem(
            ["version_data", "data_specification_version"], data_spec_version))
        version_provenance.append(ProvenanceDataItem(
            ["version_data", "front_end_common_version"], fec_version))
        version_provenance.append(ProvenanceDataItem(
            ["version_data", "numpy_version"], numpy_version))
        version_provenance.append(ProvenanceDataItem(
            ["version_data", "scipy_version"], scipy_version))
        if self._front_end_versions is not None:
            for name, value in self._front_end_versions:
                version_provenance.append(ProvenanceDataItem(
                    names=["version_data", name], value=value))
        self._version_provenance = version_provenance

    def generate_file_machine(self):
        """ Generates a machine JSON file
        """
        inputs = {
            "MemoryMachine": self.machine,
            "FileMachineFilePath": os.path.join(
                self._json_folder, "machine.json")
        }
        outputs = ["FileMachine"]
        executor = PACMANAlgorithmExecutor(
            algorithms=[], optional_algorithms=[], inputs=inputs, tokens=[],
            xml_paths=self._xml_paths,
            required_outputs=outputs, required_output_tokens=[],
            do_timings=self._do_timings, print_timings=self._print_timings,
            provenance_path=self._pacman_executor_provenance_path)
        executor.execute_mapping()

    def _do_mapping(self, run_time, total_run_time):

        # time the time it takes to do all pacman stuff
        mapping_total_timer = Timer()
        mapping_total_timer.start_timing()

        # update inputs with extra mapping inputs if required
        inputs = dict(self._machine_outputs)
        tokens = list(self._machine_tokens)
        if self._extra_mapping_inputs is not None:
            inputs.update(self._extra_mapping_inputs)

        inputs["RunTime"] = run_time
        inputs["TotalRunTime"] = total_run_time

        inputs["PostSimulationOverrunBeforeError"] = self._config.getint(
            "Machine", "post_simulation_overrun_before_error")

        # handle graph additions
        if (self._application_graph.n_vertices > 0 and
                self._graph_mapper is None):
            inputs["MemoryApplicationGraph"] = self._application_graph
        elif self._machine_graph.n_vertices > 0:
            inputs['MemoryMachineGraph'] = self._machine_graph
            if self._graph_mapper is not None:
                inputs["MemoryGraphMapper"] = self._graph_mapper
        else:
            logger.warning(
                "Your graph has no vertices in it.")
            inputs["MemoryApplicationGraph"] = self._application_graph
            inputs["MemoryGraphMapper"] = GraphMapper()
            inputs['MemoryMachineGraph'] = self._machine_graph

        inputs['ReportFolder'] = self._report_default_directory
        inputs["ApplicationDataFolder"] = self._app_data_runtime_folder
        inputs["ProvenanceFilePath"] = self._provenance_file_path
        inputs["AppProvenanceFilePath"] = self._app_provenance_file_path
        inputs["SystemProvenanceFilePath"] = self._system_provenance_file_path
        inputs["APPID"] = self._app_id
        inputs["TimeScaleFactor"] = self.time_scale_factor
        inputs["MachineTimeStep"] = self.machine_time_step
        inputs["DatabaseSocketAddresses"] = self._database_socket_addresses
        inputs["DatabaseWaitOnConfirmationFlag"] = self._config.getboolean(
            "Database", "wait_on_confirmation")
        inputs["WriteCheckerFlag"] = self._config.getboolean(
            "Mode", "verify_writes")
        inputs["WriteTextSpecsFlag"] = self._config.getboolean(
            "Reports", "write_text_specs")
        inputs["ExecutableFinder"] = self._executable_finder
        inputs["UserCreateDatabaseFlag"] = self._config.get(
            "Database", "create_database")
        inputs["SendStartNotifications"] = True
        inputs["SendStopNotifications"] = True
        inputs["WriteDataSpeedUpReportsFlag"] = self._config.getboolean(
            "Reports", "write_data_speed_up_reports")

        algorithms = list()

        if self._live_packet_recorder_params:
            algorithms.append(
                "InsertLivePacketGatherersToGraphs")
            algorithms.append("InsertEdgesToLivePacketGatherers")
            inputs['LivePacketRecorderParameters'] = \
                self._live_packet_recorder_params

        if self._config.getboolean("Reports", "write_energy_report"):
            algorithms.append(
                "InsertChipPowerMonitorsToGraphs")
            inputs['MemorySamplingFrequency'] = self._config.getint(
                "EnergyMonitor", "sampling_frequency")
            inputs['MemoryNumberSamplesPerRecordingEntry'] = \
                self._config.getint(
                    "EnergyMonitor", "n_samples_per_recording_entry")

        # handle extra monitor functionality
        add_data_speed_up = (self._config.getboolean(
            "Machine", "enable_advanced_monitor_support") or
            self._config.getboolean("Machine", "enable_reinjection"))
        if add_data_speed_up:
            algorithms.append("InsertExtraMonitorVerticesToGraphs")
            algorithms.append("InsertEdgesToExtraMonitorFunctionality")
            algorithms.append("DataInMulticastRoutingGenerator")
            algorithms.append("FixedRouteRouter")
            inputs['FixedRouteDestinationClass'] = \
                DataSpeedUpPacketGatherMachineVertex

        # handle extra mapping algorithms if required
        if self._extra_mapping_algorithms is not None:
            algorithms.extend(self._extra_mapping_algorithms)

        optional_algorithms = list()

        # Add reports
        if self._config.getboolean("Reports", "reports_enabled"):
            if self._config.getboolean("Reports",
                                       "write_tag_allocation_reports"):
                algorithms.append("TagReport")
            if self._config.getboolean("Reports", "write_router_info_report"):
                algorithms.append("routingInfoReports")
            if self._config.getboolean("Reports", "write_router_reports"):
                algorithms.append("RouterReports")
            if self._config.getboolean(
                    "Reports", "write_router_summary_report"):
                algorithms.append("RouterSummaryReport")
            if self._config.getboolean(
                   "Reports", "write_compressed_router_summary_report") and \
                    self.use_virtual_board:
                algorithms.append("CompressedRouterSummaryReport")
            if self._config.getboolean("Reports",
                                       "write_routing_table_reports"):
                optional_algorithms.append("unCompressedRoutingTableReports")
                optional_algorithms.append("compressedRoutingTableReports")
                optional_algorithms.append("comparisonOfRoutingTablesReport")
            if self._config.getboolean(
                    "Reports", "write_routing_tables_from_machine_report"):
                optional_algorithms.append(
                    "RoutingTableFromMachineReport")

            # only add board chip report if requested
            if self._config.getboolean("Reports", "write_board_chip_report"):
                algorithms.append("BoardChipReport")

            # only add partitioner report if using an application graph
            if (self._config.getboolean(
                    "Reports", "write_partitioner_reports") and
                    self._application_graph.n_vertices != 0):
                algorithms.append("PartitionerReport")

            # only add write placer report with application graph when
            # there's application vertices
            if (self._config.getboolean(
                    "Reports", "write_application_graph_placer_report") and
                    self._application_graph.n_vertices != 0):
                algorithms.append("PlacerReportWithApplicationGraph")

            if self._config.getboolean(
                    "Reports", "write_machine_graph_placer_report"):
                algorithms.append("PlacerReportWithoutApplicationGraph")

            # only add network specification report if there's
            # application vertices.
            if (self._config.getboolean(
                    "Reports", "write_network_specification_report")):
                algorithms.append("NetworkSpecificationReport")

        # only add the partitioner if there isn't already a machine graph
        algorithms.append("MallocBasedChipIDAllocator")
        if (self._application_graph.n_vertices and
                not self._machine_graph.n_vertices):
            full = self._config.get(
                "Mapping", "application_to_machine_graph_algorithms")
            algorithms.extend(full.replace(" ", "").split(","))
            inputs['MemoryPreviousAllocatedResources'] = \
                PreAllocatedResourceContainer()

        if self._use_virtual_board:
            full = self._config.get(
                "Mapping", "machine_graph_to_virtual_machine_algorithms")
        else:
            full = self._config.get(
                "Mapping", "machine_graph_to_machine_algorithms")
        algorithms.extend(full.replace(" ", "").split(","))

        # add check for algorithm start type
        algorithms.append("LocateExecutableStartType")

        # handle outputs
        outputs = [
            "MemoryPlacements", "MemoryRoutingTables",
            "MemoryTags", "MemoryRoutingInfos",
            "MemoryMachineGraph", "ExecutableTypes"
        ]

        if add_data_speed_up:
            outputs.append("MemoryFixedRoutes")

        if self._application_graph.n_vertices > 0:
            outputs.append("MemoryGraphMapper")

        # Create a buffer manager if there isn't one already
        if not self._use_virtual_board:
            if self._buffer_manager is None:
                algorithms.append("BufferManagerCreator")
                outputs.append("BufferManager")
            else:
                inputs["BufferManager"] = self._buffer_manager
            if self._java_caller is None:
                if self._config.getboolean("Java", "use_java"):
                    java_call = self._config.get("Java", "java_call")
                    java_spinnaker_path = self._config.get_str(
                        "Java", "java_spinnaker_path")
                    java_properties = self._config.get_str(
                        "Java", "java_properties")
                    self._java_caller = JavaCaller(
                        self._json_folder, java_call, java_spinnaker_path,
                        java_properties)
            inputs["JavaCaller"] = self._java_caller

        # Execute the mapping algorithms
        executor = self._run_algorithms(
            inputs, algorithms, outputs, tokens, [], "mapping",
            optional_algorithms)

        # get result objects from the pacman executor
        self._mapping_outputs = executor.get_items()
        self._mapping_tokens = executor.get_completed_tokens()

        # Get the outputs needed
        self._placements = executor.get_item("MemoryPlacements")
        self._router_tables = executor.get_item("MemoryRoutingTables")
        self._tags = executor.get_item("MemoryTags")
        self._routing_infos = executor.get_item("MemoryRoutingInfos")
        self._graph_mapper = executor.get_item("MemoryGraphMapper")
        self._machine_graph = executor.get_item("MemoryMachineGraph")
        self._executable_types = executor.get_item("ExecutableTypes")

        if add_data_speed_up:
            self._fixed_routes = executor.get_item("MemoryFixedRoutes")

        if not self._use_virtual_board:
            self._buffer_manager = executor.get_item("BufferManager")

        self._mapping_time += convert_time_diff_to_total_milliseconds(
            mapping_total_timer.take_sample())

    def _do_data_generation(self, n_machine_time_steps):

        # set up timing
        data_gen_timer = Timer()
        data_gen_timer.start_timing()

        # The initial inputs are the mapping outputs
        inputs = dict(self._mapping_outputs)
        tokens = list(self._mapping_tokens)
        inputs["RunUntilTimeSteps"] = n_machine_time_steps

        inputs["FirstMachineTimeStep"] = self._current_run_timesteps
        inputs["RunTimeMachineTimeSteps"] = n_machine_time_steps
        inputs["DataNTimeSteps"] = self._max_run_time_steps

        # Run the data generation algorithms
        outputs = []
        algorithms = [self._dsg_algorithm]

        executor = self._run_algorithms(
            inputs, algorithms, outputs, tokens, [], "data_generation")
        self._mapping_outputs = executor.get_items()
        self._mapping_tokens = executor.get_completed_tokens()

        self._dsg_time += convert_time_diff_to_total_milliseconds(
            data_gen_timer.take_sample())

    def _do_load(self, graph_changed):
        # set up timing
        load_timer = Timer()
        load_timer.start_timing()

        self._turn_on_board_if_saving_power()

        # The initial inputs are the mapping outputs
        inputs = dict(self._mapping_outputs)
        tokens = list(self._mapping_tokens)
        inputs["WriteMemoryMapReportFlag"] = (
            self._config.getboolean("Reports", "write_memory_map_report") and
            graph_changed
        )

        if not graph_changed and self._has_ran:
            inputs["ExecutableTargets"] = self._last_run_outputs[
                "ExecutableTargets"]

        algorithms = list()

        # add report for extracting routing table from machine report if needed
        # Add algorithm to clear routing tables and set up routing
        if not self._use_virtual_board and graph_changed:
            algorithms.append("RoutingSetup")
            # Get the executable targets
            algorithms.append("GraphBinaryGatherer")

        loading_algorithm = self._read_config("Mapping", "loading_algorithms")
        if loading_algorithm is not None and graph_changed:
            algorithms.extend(loading_algorithm.split(","))
        algorithms.extend(self._extra_load_algorithms)

        write_memory_report = self._config.getboolean(
            "Reports", "write_memory_map_report")
        if write_memory_report and graph_changed:
            algorithms.append("MemoryMapOnHostReport")
            algorithms.append("MemoryMapOnHostChipReport")

        # Add reports that depend on compression
        routing_tables_needed = False
        if graph_changed:
            if self._config.getboolean("Reports",
                                       "write_routing_table_reports"):
                routing_tables_needed = True
                algorithms.append("unCompressedRoutingTableReports")
                algorithms.append("compressedRoutingTableReports")
                algorithms.append("comparisonOfRoutingTablesReport")
            if self._config.getboolean(
                    "Reports", "write_routing_compression_checker_report"):
                routing_tables_needed = True
                algorithms.append("routingCompressionCheckerReport")

        # handle extra monitor functionality
        enable_advanced_monitor = self._config.getboolean(
            "Machine", "enable_advanced_monitor_support")
        if enable_advanced_monitor and (graph_changed or not self._has_ran):
            algorithms.append("LoadFixedRoutes")
            algorithms.append("FixedRouteFromMachineReport")

        # add optional algorithms
        optional_algorithms = list()
        optional_algorithms.append("RoutingTableLoader")
        optional_algorithms.append("TagsLoader")
        optional_algorithms.append("WriteMemoryIOData")
        optional_algorithms.append("HostExecuteApplicationDataSpecification")

        # Get the executable targets
        optional_algorithms.append("GraphBinaryGatherer")

        # algorithms needed for loading the binaries to the SpiNNaker machine
        optional_algorithms.append("LoadApplicationExecutableImages")
        algorithms.append("HostExecuteSystemDataSpecification")
        algorithms.append("LoadSystemExecutableImages")

        # Something probably a report needs the routing tables
        # This report is one way to get them if done on machine
        if routing_tables_needed:
            optional_algorithms.append("RoutingTableFromMachineReport")

        # Decide what needs to be done
        required_tokens = ["DataLoaded", "BinariesLoaded"]

        executor = self._run_algorithms(
            inputs, algorithms, [], tokens, required_tokens, "loading",
            optional_algorithms)
        self._load_outputs = executor.get_items()
        self._load_tokens = executor.get_completed_tokens()

        self._load_time += convert_time_diff_to_total_milliseconds(
            load_timer.take_sample())

    def _do_run(self, n_machine_time_steps, graph_changed, run_until_complete):
        # start timer
        run_timer = Timer()
        run_timer.start_timing()

        run_complete = False
        executor, self._current_run_timesteps = self._create_execute_workflow(
            n_machine_time_steps, graph_changed, run_until_complete)
        try:
            executor.execute_mapping()
            self._pacman_provenance.extract_provenance(executor)
            run_complete = True

            # write provenance to file if necessary
            if (self._config.getboolean("Reports", "write_provenance_data") and
                    n_machine_time_steps is not None):
                prov_items = list()
                if self._version_provenance is not None:
                    prov_items.extend(self._version_provenance)
                if self._pacman_provenance is not None:
                    if self._pacman_provenance.data_items is not None:
                        prov_items.extend(self._pacman_provenance.data_items)
                prov_item = executor.get_item("GraphProvenanceItems")
                if prov_item is not None:
                    prov_items.extend(prov_item)
                prov_item = executor.get_item("PlacementsProvenanceItems")
                if prov_item is not None:
                    prov_items.extend(prov_item)
                prov_item = executor.get_item("RouterProvenanceItems")
                if prov_item is not None:
                    prov_items.extend(prov_item)
                self._pacman_provenance.clear()
                self._version_provenance = list()
                self._write_provenance(prov_items)
                self._all_provenance_items.append(prov_items)

            # move data around
            self._last_run_outputs = executor.get_items()
            self._last_run_tokens = executor.get_completed_tokens()
            self._no_sync_changes = executor.get_item("NoSyncChanges")
            self._has_reset_last = False
            self._has_ran = True

            self._execute_time += convert_time_diff_to_total_milliseconds(
                run_timer.take_sample())

        except KeyboardInterrupt:
            logger.error("User has aborted the simulation")
            self._shutdown()
            sys.exit(1)
        except Exception as e:
            e_inf = sys.exc_info()

            # If an exception occurs during a run, attempt to get
            # information out of the simulation before shutting down
            try:
                if executor is not None:
                    # Only do this if the error occurred in the run
                    if not run_complete and not self._use_virtual_board:
                        self._last_run_outputs = executor.get_items()
                        self._last_run_tokens = executor.get_completed_tokens()
                        self._recover_from_error(
                            e, e_inf, executor.get_item("ExecutableTargets"))
                else:
                    logger.error(
                        "The PACMAN executor crashing during initialisation,"
                        " please read previous error message to locate its"
                        " error")
            except Exception:
                logger.exception("Error when attempting to recover from error")

            # if in debug mode, do not shut down machine
            if self._config.get("Mode", "mode") != "Debug":
                try:
                    self.stop(
                        turn_off_machine=False, clear_routing_tables=False,
                        clear_tags=False)
                except Exception:
                    logger.exception("Error when attempting to stop")

            # reraise exception
            reraise(*e_inf)

    def _create_execute_workflow(
            self, n_machine_time_steps, graph_changed, run_until_complete):
        # calculate number of machine time steps
        run_until_timesteps = self._calculate_number_of_machine_time_steps(
            n_machine_time_steps)
        run_time = None
        if n_machine_time_steps is not None:
            run_time = n_machine_time_steps * self.machine_time_step / 1000.0

        # if running again, load the outputs from last load or last mapping
        if self._load_outputs is not None:
            inputs = dict(self._load_outputs)
            tokens = list(self._load_tokens)
        else:
            inputs = dict(self._mapping_outputs)
            tokens = list(self._mapping_tokens)

        inputs["RanToken"] = self._has_ran
        inputs["NoSyncChanges"] = self._no_sync_changes
        inputs["RunTimeMachineTimeSteps"] = n_machine_time_steps
        inputs["RunUntilTimeSteps"] = run_until_timesteps
        inputs["RunTime"] = run_time
        inputs["FirstMachineTimeStep"] = self._current_run_timesteps
        if run_until_complete:
            inputs["RunUntilCompleteFlag"] = True

        inputs["ExtractIobufFromCores"] = self._config.get(
            "Reports", "extract_iobuf_from_cores")
        inputs["ExtractIobufFromBinaryTypes"] = self._config.get(
            "Reports", "extract_iobuf_from_binary_types")

        # update algorithm list with extra pre algorithms if needed
        if self._extra_pre_run_algorithms is not None:
            algorithms = list(self._extra_pre_run_algorithms)
        else:
            algorithms = list()

        if self._config.getboolean(
                "Reports", "write_sdram_usage_report_per_chip"):
            algorithms.append("SdramUsageReportPerChip")

        # clear iobuf if were in multirun mode
        if (self._has_ran and not graph_changed and
                not self._use_virtual_board and
                self._config.getboolean("Reports", "clear_iobuf_during_run")):
            algorithms.append("ChipIOBufClearer")

        # Reload any parameters over the loaded data if we have already
        # run and not using a virtual board and the data hasn't already
        # been regenerated
        if self._has_ran and not self._use_virtual_board and not graph_changed:
            algorithms.append("DSGRegionReloader")

        # Update the run time if not using a virtual board
        if (not self._use_virtual_board and
                ExecutableType.USES_SIMULATION_INTERFACE in
                self._executable_types):
            algorithms.append("ChipRuntimeUpdater")

        # Add the database writer in case it is needed
        if not self._has_ran or graph_changed:
            algorithms.append("DatabaseInterface")
        else:
            inputs["DatabaseFilePath"] = (
                self._last_run_outputs["DatabaseFilePath"])
        if not self._use_virtual_board:
            algorithms.append("NotificationProtocol")

        outputs = [
            "NoSyncChanges"
        ]

        if self._use_virtual_board:
            logger.warning(
                "Application will not actually be run as on a virtual board")
        elif (len(self._executable_types) == 1 and
                ExecutableType.NO_APPLICATION in self._executable_types):
            logger.warning(
                "Application will not actually be run as there is nothing to "
                "actually run")
        else:
            algorithms.append("ApplicationRunner")

        # ensure we exploit the parallel of data extraction by running it at\
        # end regardless of multirun, but only run if using a real machine
        if (not self._use_virtual_board and
                (run_until_complete or n_machine_time_steps is not None)):
            algorithms.append("BufferExtractor")

        if self._config.getboolean("Reports", "write_provenance_data"):
            algorithms.append("GraphProvenanceGatherer")

        # add any extra post algorithms as needed
        if self._extra_post_run_algorithms is not None:
            algorithms += self._extra_post_run_algorithms

        # add extractor of iobuf if needed
        if (self._config.getboolean("Reports", "extract_iobuf") and
                self._config.getboolean(
                    "Reports", "extract_iobuf_during_run") and
                not self._use_virtual_board and
                n_machine_time_steps is not None):
            algorithms.append("ChipIOBufExtractor")

        # add extractor of provenance if needed
        if (self._config.getboolean("Reports", "write_provenance_data") and
                not self._use_virtual_board and
                n_machine_time_steps is not None):
            algorithms.append("PlacementsProvenanceGatherer")
            algorithms.append("RouterProvenanceGatherer")
            algorithms.append("ProfileDataGatherer")

        # Decide what needs done
        required_tokens = []
        if not self._use_virtual_board:
            required_tokens = ["ApplicationRun"]

        return PACMANAlgorithmExecutor(
            algorithms=algorithms, optional_algorithms=[], inputs=inputs,
            tokens=tokens, required_output_tokens=required_tokens,
            xml_paths=self._xml_paths, required_outputs=outputs,
            do_timings=self._do_timings, print_timings=self._print_timings,
            provenance_path=self._pacman_executor_provenance_path,
            provenance_name="Execution"), run_until_timesteps

    def _write_provenance(self, provenance_data_items):
        """ Write provenance to disk
        """
        writer = None
        if self._provenance_format == "xml":
            writer = ProvenanceXMLWriter()
        elif self._provenance_format == "json":
            writer = ProvenanceJSONWriter()
        writer(provenance_data_items, self._provenance_file_path)

    def _recover_from_error(self, exception, exc_info, executable_targets):
        # if exception has an exception, print to system
        logger.error("An error has occurred during simulation")
        # Print the detail including the traceback
        real_exception = exception
        if isinstance(exception, PacmanAlgorithmFailedToCompleteException):
            logger.error(exception.exception, exc_info=exc_info)
            real_exception = exception.exception
        else:
            logger.error(exception, exc_info=exc_info)

        logger.info("\n\nAttempting to extract data\n\n")

        # Extract router provenance
        extra_monitor_vertices = None
        prov_items = list()
        try:
            if (self._config.getboolean("Machine",
                                        "enable_advanced_monitor_support") or
                    self._config.getboolean("Machine", "enable_reinjection")):
                extra_monitor_vertices = self._last_run_outputs[
                    "MemoryExtraMonitorVertices"]
            router_provenance = RouterProvenanceGatherer()
            prov_item = router_provenance(
                transceiver=self._txrx, machine=self._machine,
                router_tables=self._router_tables,
                extra_monitor_vertices=extra_monitor_vertices,
                placements=self._placements)
            if prov_item is not None:
                prov_items.extend(prov_item)
        except Exception:
            logger.exception("Error reading router provenance")

        # Find the cores that are not in an expected state
        unsuccessful_cores = CPUInfos()
        if isinstance(real_exception, SpiNNManCoresNotInStateException):
            unsuccessful_cores = real_exception.failed_core_states()

        # If there are no cores in a bad state, find those not yet in
        # their finished state
        if not unsuccessful_cores:
            for executable_type in self._executable_types:
                failed_cores = self._txrx.get_cores_not_in_state(
                    self._executable_types[executable_type],
                    executable_type.end_state)
                for (x, y, p) in failed_cores:
                    unsuccessful_cores.add_processor(
                        x, y, p, failed_cores.get_cpu_info(x, y, p))

        # Print the details of error cores
        for (x, y, p), core_info in iteritems(unsuccessful_cores):
            state = core_info.state
            rte_state = ""
            if state == CPUState.RUN_TIME_EXCEPTION:
                rte_state = " ({})".format(core_info.run_time_error.name)
            logger.error("{}, {}, {}: {}{} {}".format(
                x, y, p, state.name, rte_state, core_info.application_name))
            if core_info.state == CPUState.RUN_TIME_EXCEPTION:
                logger.error(
                    "r0=0x{:08X} r1=0x{:08X} r2=0x{:08X} r3=0x{:08X}".format(
                        core_info.registers[0], core_info.registers[1],
                        core_info.registers[2], core_info.registers[3]))
                logger.error(
                    "r4=0x{:08X} r5=0x{:08X} r6=0x{:08X} r7=0x{:08X}".format(
                        core_info.registers[4], core_info.registers[5],
                        core_info.registers[6], core_info.registers[7]))
                logger.error("PSR=0x{:08X} SR=0x{:08X} LR=0x{:08X}".format(
                    core_info.processor_state_register,
                    core_info.stack_pointer, core_info.link_register))

        # Find the cores that are not in RTE i.e. that can still be read
        non_rte_cores = [
            (x, y, p)
            for (x, y, p), core_info in iteritems(unsuccessful_cores)
            if (core_info.state != CPUState.RUN_TIME_EXCEPTION and
                core_info.state != CPUState.WATCHDOG)]

        # If there are any cores that are not in RTE, extract data from them
        if (non_rte_cores and
                ExecutableType.USES_SIMULATION_INTERFACE in
                self._executable_types):
            placements = Placements()
            non_rte_core_subsets = CoreSubsets()
            for (x, y, p) in non_rte_cores:
                vertex = self._placements.get_vertex_on_processor(x, y, p)
                placements.add_placement(
                    self._placements.get_placement_of_vertex(vertex))
                non_rte_core_subsets.add_processor(x, y, p)

            # Attempt to force the cores to write provenance and exit
            try:
                updater = ChipProvenanceUpdater()
                updater(self._txrx, self._app_id, non_rte_core_subsets)
            except Exception:
                logger.exception("Could not update provenance on chip")

            # Extract any written provenance data
            try:
                extractor = PlacementsProvenanceGatherer()
                prov_item = extractor(self._txrx, placements)
                if prov_item is not None:
                    prov_items.extend(prov_item)
            except Exception:
                logger.exception("Could not read provenance")

        # Finish getting the provenance
        if self._pacman_provenance is not None:
            if self._pacman_provenance.data_items is not None:
                prov_items.extend(self._pacman_provenance.data_items)
        self._pacman_provenance.clear()
        self._write_provenance(prov_items)
        self._all_provenance_items.append(prov_items)

        # Read IOBUF where possible (that should be everywhere)
        iobuf = ChipIOBufExtractor()
        try:
            errors, warnings = iobuf(
                self._txrx, executable_targets, self._executable_finder,
                self._app_provenance_file_path,
                self._system_provenance_file_path,
                self._mapping_outputs["BinaryToExecutableType"],
                self._config.get("Reports", "extract_iobuf_from_cores"),
                self._config.get("Reports", "extract_iobuf_from_binary_types")
            )
        except Exception:
            logger.exception("Could not get iobuf")
            errors, warnings = [], []

        # Print the IOBUFs
        self._print_iobuf(errors, warnings)

    @staticmethod
    def _print_iobuf(errors, warnings):
        for warning in warnings:
            logger.warning(warning)
        for error in errors:
            logger.error(error)

    def reset(self):
        """ Code that puts the simulation back at time zero
        """

        logger.info("Resetting")

        # rewind the buffers from the buffer manager, to start at the beginning
        # of the simulation again and clear buffered out
        if self._buffer_manager is not None:
            self._buffer_manager.reset()

        # reset the current count of how many milliseconds the application
        # has ran for over multiple calls to run
        self._current_run_timesteps = 0

        # sets the reset last flag to true, so that when run occurs, the tools
        # know to update the vertices which need to know a reset has occurred
        self._has_reset_last = True

        # Reset the graph off the machine, to set things to time 0
        self.__reset_graph_elements()

    def _create_xml_paths(self, extra_algorithm_xml_paths):
        # add the extra xml files from the config file
        xml_paths = self._config.get("Mapping", "extra_xmls_paths")
        if xml_paths == "None":
            xml_paths = list()
        else:
            xml_paths = xml_paths.split(",")

        xml_paths.extend(get_front_end_common_pacman_xml_paths())

        if extra_algorithm_xml_paths is not None:
            xml_paths.extend(extra_algorithm_xml_paths)

        return xml_paths

    def _detect_if_graph_has_changed(self, reset_flags=True):
        """ Iterates though the original graphs and look for changes
        """
        changed = False
        data_changed = False
        if self._vertices_or_edges_added:
            self._vertices_or_edges_added = False
            # Set changed - note that we can't return yet as we still have to
            # mark vertices as not changed, otherwise they will keep reporting
            # that they have changed when they haven't
            changed = True

        # if application graph is filled, check their changes
        if self._original_application_graph.n_vertices:
            for vertex in self._original_application_graph.vertices:
                if isinstance(vertex, AbstractChangableAfterRun):
                    if vertex.requires_mapping:
                        changed = True
                    if vertex.requires_data_generation:
                        data_changed = True
                    if reset_flags:
                        vertex.mark_no_changes()
            for partition in \
                    self._original_application_graph.outgoing_edge_partitions:
                for edge in partition.edges:
                    if isinstance(edge, AbstractChangableAfterRun):
                        if edge.requires_mapping:
                            changed = True
                        if edge.requires_data_generation:
                            data_changed = True
                        if reset_flags:
                            edge.mark_no_changes()

        # if no application, but a machine graph, check for changes there
        elif self._original_machine_graph.n_vertices:
            for machine_vertex in self._original_machine_graph.vertices:
                if isinstance(machine_vertex, AbstractChangableAfterRun):
                    if machine_vertex.requires_mapping:
                        changed = True
                    if machine_vertex.requires_data_generation:
                        data_changed = True
                    if reset_flags:
                        machine_vertex.mark_no_changes()
            for partition in \
                    self._original_machine_graph.outgoing_edge_partitions:
                for machine_edge in partition.edges:
                    if isinstance(machine_edge, AbstractChangableAfterRun):
                        if machine_edge.requires_mapping:
                            changed = True
                        if machine_edge.requires_data_generation:
                            data_changed = True
                        if reset_flags:
                            machine_edge.mark_no_changes()
        return changed, data_changed

    @property
    @overrides(SimulatorInterface.has_ran)
    def has_ran(self):
        return self._has_ran

    @property
    @overrides(SimulatorInterface.machine)
    def machine(self):
        return self._get_machine()

    @property
    @overrides(SimulatorInterface.no_machine_time_steps)
    def no_machine_time_steps(self):
        return self._no_machine_time_steps

    @property
    def timescale_factor(self):
        return self._read_config_int("Machine", "time_scale_factor")

    @property
    def machine_graph(self):
        return self._machine_graph

    @property
    def original_machine_graph(self):
        return self._original_machine_graph

    @property
    def original_application_graph(self):
        return self._original_application_graph

    @property
    def application_graph(self):
        """ The application graph used to derive the runtime machine \
            configuration.
        """
        return self._application_graph

    @property
    def routing_infos(self):
        return self._routing_infos

    @property
    def fixed_routes(self):
        return self._fixed_routes

    @property
    def placements(self):
        return self._placements

    @property
    @overrides(SimulatorInterface.transceiver)
    def transceiver(self):
        return self._txrx

    @property
    def graph_mapper(self):
        return self._graph_mapper

    @property
    def tags(self):
        return self._tags

    @property
    @overrides(SimulatorInterface.buffer_manager)
    def buffer_manager(self):
        return self._buffer_manager

    @property
    def dsg_algorithm(self):
        """ The DSG algorithm used by the tools
        """
        return self._dsg_algorithm

    @dsg_algorithm.setter
    def dsg_algorithm(self, new_dsg_algorithm):
        """ Set the DSG algorithm to be used by the tools

        :param new_dsg_algorithm: the new DSG algorithm name
        :rtype: None
        """
        self._dsg_algorithm = new_dsg_algorithm

    @property
    def none_labelled_edge_count(self):
        """ The number of times edges have not been labelled.
        """
        return self._none_labelled_edge_count

    def increment_none_labelled_edge_count(self):
        """ Increment the number of new edges which have not been labelled.
        """
        self._none_labelled_edge_count += 1

    @property
    def use_virtual_board(self):
        """ True if this run is using a virtual machine
        """
        return self._use_virtual_board

    def get_current_time(self):
        """ Get the current simulation time.

        :rtype: float
        """
        if self._has_ran:
            return (
                float(self._current_run_timesteps) *
                (self.machine_time_step / 1000.0))
        return 0.0

    def get_generated_output(self, name_of_variable):
        """ Get the value of an inter-algorithm variable.

        :param name_of_variable: The variable to retrieve
        :type name_of_variable: str
        :return: The value (of arbitrary type), or None if the variable is \
            not found.
        """
        if self._has_ran:
            if name_of_variable in self._last_run_outputs:
                return self._last_run_outputs[name_of_variable]
            return None
        raise ConfigurationException(
            "Cannot call this function until after a simulation has ran.")

    def __repr__(self):
        return "general front end instance for machine {}".format(
            self._hostname)

    def add_application_vertex(self, vertex):
        """
        :param vertex: the vertex to add to the graph
        :type: ApplicationVertex
        :rtype: None
        :raises ConfigurationException: when both graphs contain vertices
        :raises PacmanConfigurationException:
            If there is an attempt to add the same vertex more than once
        """
        if (self._original_machine_graph.n_vertices > 0 and
                self._graph_mapper is None):
            raise ConfigurationException(
                "Cannot add vertices to both the machine and application"
                " graphs")
        self._original_application_graph.add_vertex(vertex)
        self._vertices_or_edges_added = True

    def add_machine_vertex(self, vertex):
        """
        :param vertex: the vertex to add to the graph
        :type: MachineVertex
        :rtype: None
        :raises ConfigurationException: when both graphs contain vertices
        :raises PacmanConfigurationException:
            If there is an attempt to add the same vertex more than once
        """
        # check that there's no application vertices added so far
        if self._original_application_graph.n_vertices > 0:
            raise ConfigurationException(
                "Cannot add vertices to both the machine and application"
                " graphs")
        self._original_machine_graph.add_vertex(vertex)
        self._vertices_or_edges_added = True

    def add_application_edge(self, edge_to_add, partition_identifier):
        """
        :param edge_to_add:
        :type: ApplicationEdge
        :param partition_identifier: \
            the partition identifier for the outgoing edge partition
        :type partition_identifier: str
        :rtype: None
        """
        self._original_application_graph.add_edge(
            edge_to_add, partition_identifier)
        self._vertices_or_edges_added = True

    def add_machine_edge(self, edge, partition_id):
        """
        :param edge: the edge to add to the graph
        :type: MachineEdge
        :param partition_id: \
            the partition identifier for the outgoing edge partition
        :type partition_id: str
        :rtype: None
        """
        self._original_machine_graph.add_edge(edge, partition_id)
        self._vertices_or_edges_added = True

    def _shutdown(
            self, turn_off_machine=None, clear_routing_tables=None,
            clear_tags=None):
        self._state = Simulator_State.SHUTDOWN

        # if on a virtual machine then shut down not needed
        if self._use_virtual_board:
            return

        if self._machine_is_turned_off is not None:
            logger.info("Shutdown skipped as board is off for power save")
            return

        if turn_off_machine is None:
            turn_off_machine = self._config.getboolean(
                "Machine", "turn_off_machine")

        if clear_routing_tables is None:
            clear_routing_tables = self._config.getboolean(
                "Machine", "clear_routing_tables")

        if clear_tags is None:
            clear_tags = self._config.getboolean("Machine", "clear_tags")

        if self._txrx is not None:
            # if stopping on machine, clear IP tags and routing table
            self.__clear(clear_tags, clear_routing_tables)

        # Fully stop the application
        self.__stop_app()

        # stop the transceiver and allocation controller
        self.__close_transceiver(turn_off_machine)
        self.__close_allocation_controller()
        self._state = Simulator_State.SHUTDOWN

    def __clear(self, clear_tags, clear_routing_tables):
        # if stopping on machine, clear IP tags and
        if clear_tags:
            for ip_tag in self._tags.ip_tags:
                self._txrx.clear_ip_tag(
                    ip_tag.tag, board_address=ip_tag.board_address)
            for reverse_ip_tag in self._tags.reverse_ip_tags:
                self._txrx.clear_ip_tag(
                    reverse_ip_tag.tag,
                    board_address=reverse_ip_tag.board_address)

        # if clearing routing table entries, clear
        if clear_routing_tables:
            for router_table in self._router_tables.routing_tables:
                if not self._machine.get_chip_at(
                        router_table.x, router_table.y).virtual:
                    self._txrx.clear_multicast_routes(
                        router_table.x, router_table.y)

        # clear values
        self._no_sync_changes = 0

    def __stop_app(self):
        if self._txrx is not None and self._app_id is not None:
            self._txrx.stop_application(self._app_id)

    def __close_transceiver(self, turn_off_machine):
        if self._txrx is not None:
            if turn_off_machine:
                logger.info("Turning off machine")

            self._txrx.close(power_off_machine=turn_off_machine)
            self._txrx = None

    def __close_allocation_controller(self):
        if self._machine_allocation_controller is not None:
            self._machine_allocation_controller.close()
            self._machine_allocation_controller = None

    @overrides(SimulatorInterface.stop,
               extend_defaults=True, additional_arguments=(
                   "turn_off_machine", "clear_routing_tables", "clear_tags"))
    def stop(self, turn_off_machine=None,  # pylint: disable=arguments-differ
             clear_routing_tables=None, clear_tags=None):
        """
        :param turn_off_machine: decides if the machine should be powered down\
            after running the execution. Note that this powers down all boards\
            connected to the BMP connections given to the transceiver
        :type turn_off_machine: bool
        :param clear_routing_tables: informs the tool chain if it\
            should turn off the clearing of the routing tables
        :type clear_routing_tables: bool
        :param clear_tags: informs the tool chain if it should clear the tags\
            off the machine at stop
        :type clear_tags: boolean
        :rtype: None
        """
        if self._state in [Simulator_State.SHUTDOWN]:
            raise ConfigurationException("Simulator has already been shutdown")
        self._state = Simulator_State.SHUTDOWN

        # Keep track of any exception to be re-raised
        exc_info = None

        # If we have run forever, stop the binaries
        if (self._has_ran and self._current_run_timesteps is None and
                not self._use_virtual_board):
            executor = self._create_stop_workflow()
            run_complete = False
            try:
                executor.execute_mapping()
                self._pacman_provenance.extract_provenance(executor)
                run_complete = True

                # write provenance to file if necessary
                if self._config.getboolean("Reports", "write_provenance_data"):
                    prov_items = list()
                    if self._version_provenance is not None:
                        prov_items.extend(self._version_provenance)
                    if self._pacman_provenance is not None:
                        if self._pacman_provenance.data_items is not None:
                            prov_items.extend(
                                self._pacman_provenance.data_items)
                    prov_item = executor.get_item("GraphProvenanceItems")
                    if prov_item is not None:
                        prov_items.extend(prov_item)
                    prov_item = executor.get_item("PlacementsProvenanceItems")
                    if prov_item is not None:
                        prov_items.extend(prov_item)
                    prov_item = executor.get_item("RouterProvenanceItems")
                    if prov_item is not None:
                        prov_items.extend(prov_item)
                    self._pacman_provenance.clear()
                    self._version_provenance = list()
                    self._write_provenance(prov_items)
                    self._all_provenance_items.append(prov_items)
            except Exception as e:
                exc_info = sys.exc_info()

                # If an exception occurs during a run, attempt to get
                # information out of the simulation before shutting down
                try:
                    # Only do this if the error occurred in the run
                    if not run_complete and not self._use_virtual_board:
                        self._recover_from_error(
                            e, exc_info[2], executor.get_item(
                                "ExecutableTargets"))
                except Exception:
                    logger.exception(
                        "Error when attempting to recover from error")

        if not self._use_virtual_board:
            if self._config.getboolean("Reports", "write_energy_report"):
                self._do_energy_report()

            # handle iobuf extraction
            if self._config.getboolean("Reports", "extract_iobuf"):
                self._extract_iobufs()

        # shut down the machine properly
        self._shutdown(turn_off_machine, clear_routing_tables, clear_tags)

        # display any provenance data gathered
        for i, provenance_items in enumerate(self._all_provenance_items):
            message = None
            if len(self._all_provenance_items) > 1:
                message = "Provenance from run {}".format(i)
            self._check_provenance(provenance_items, message)

            # Reset provenance
            self._all_provenance_items = list()

        self.write_finished_file()

        if exc_info is not None:
            reraise(*exc_info)

    def _create_stop_workflow(self):
        inputs = self._last_run_outputs
        tokens = self._last_run_tokens
        algorithms = []
        outputs = []

        # stop any binaries that need to be notified of the simulation
        # stopping if in infinite run
        if ExecutableType.USES_SIMULATION_INTERFACE in self._executable_types:
            algorithms.append("ApplicationFinisher")

        # Add the buffer extractor just in case
        algorithms.append("BufferExtractor")

        # add extractor of iobuf if needed
        if self._config.getboolean("Reports", "extract_iobuf") and \
                self._config.getboolean("Reports", "extract_iobuf_during_run"):
            algorithms.append("ChipIOBufExtractor")

        # add extractor of provenance if needed
        if self._config.getboolean("Reports", "writeProvenanceData"):
            algorithms.append("PlacementsProvenanceGatherer")
            algorithms.append("RouterProvenanceGatherer")
            algorithms.append("ProfileDataGatherer")

        # Assemble how to run the algorithms
        return PACMANAlgorithmExecutor(
            algorithms=algorithms, optional_algorithms=[], inputs=inputs,
            tokens=tokens, required_output_tokens=[],
            xml_paths=self._xml_paths,
            required_outputs=outputs, do_timings=self._do_timings,
            print_timings=self._print_timings,
            provenance_path=self._pacman_executor_provenance_path,
            provenance_name="stopping")

    def _do_energy_report(self):
        if self._buffer_manager is None or self._last_run_outputs is None:
            return

        # create energy report
        energy_report = EnergyReport()

        # acquire provenance items
        router_provenance = self._last_run_outputs.get(
            "RouterProvenanceItems", None)
        if router_provenance is None:
            return
        pacman_provenance = self._pacman_provenance.data_items

        # run energy report
        energy_report(
            self._placements, self._machine,
            self._report_default_directory,
            self._read_config_int("Machine", "version"),
            self._spalloc_server, self._remote_spinnaker_url,
            self.time_scale_factor, self.machine_time_step,
            pacman_provenance, router_provenance, self._machine_graph,
            self._current_run_timesteps, self._buffer_manager,
            self._mapping_time, self._load_time, self._execute_time,
            self._dsg_time, self._extraction_time,
            self._machine_allocation_controller)

    def _extract_iobufs(self):
        if self._config.getboolean("Reports", "extract_iobuf_during_run"):
            return
        if self._config.getboolean("Reports", "clear_iobuf_during_run"):
            return
        extractor = ChipIOBufExtractor()
        extractor(
            transceiver=self._txrx,
            executable_targets=self._last_run_outputs["ExecutableTargets"],
            executable_finder=self._executable_finder,
            app_provenance_file_path=self._app_provenance_file_path,
            system_provenance_file_path=self._system_provenance_file_path,
            binary_executable_types=(
                self._mapping_outputs["BinaryToExecutableType"]))

    @overrides(SimulatorInterface.add_socket_address)
    def add_socket_address(self, socket_address):
        """
        :param socket_address: The address of the database socket
        :type socket_address: ~spinn_utilities.socket_address.SocketAddress
        :rtype: None
        """
        self._database_socket_addresses.add(socket_address)

    @staticmethod
    def _check_provenance(items, initial_message=None):
        """ Display any errors from provenance data.
        """
        initial_message_printed = False
        for item in items:
            if item.report:
                if not initial_message_printed and initial_message is not None:
                    print(initial_message)
                    initial_message_printed = True
                logger.warning(item.message)

    def _turn_off_on_board_to_save_power(self, config_flag):
        """ Executes the power saving mode of either on or off of the\
            SpiNNaker machine.

        :param config_flag: Flag read from the configuration file
        :type config_flag: str
        :rtype: None
        """
        # check if machine should be turned off
        turn_off = self._read_config_boolean("EnergySavings", config_flag)
        if turn_off is None:
            return

        # if a mode is set, execute
        if turn_off:
            if self._turn_off_board_to_save_power():
                logger.info("Board turned off based on: {}", config_flag)
        else:
            if self._turn_on_board_if_saving_power():
                logger.info("Board turned on based on: {}", config_flag)

    def _turn_off_board_to_save_power(self):
        """ Executes the power saving mode of turning off the SpiNNaker\
            machine.

        :return: true when successful, false otherwise
        :rtype: bool
        """
        # already off or no machine to turn off
        if self._machine_is_turned_off is not None or self._use_virtual_board:
            return False

        if self._machine_allocation_controller is not None:
            # switch power state if needed
            if self._machine_allocation_controller.power:
                self._machine_allocation_controller.set_power(False)
        else:
            self._txrx.power_off_machine()

        self._machine_is_turned_off = time.time()
        return True

    def _turn_on_board_if_saving_power(self):
        # Only required if previously turned off which never happens
        # on virtual machine
        if self._machine_is_turned_off is None:
            return False

        # Ensure the machine is completely powered down and
        # all residual electrons have gone
        already_off = time.time() - self._machine_is_turned_off
        if already_off < MINIMUM_OFF_STATE_TIME:
            delay = MINIMUM_OFF_STATE_TIME - already_off
            logger.warning(
                "Delaying turning machine back on for {} seconds. Consider "
                "disabling turn_off_board_after_discovery for scripts that "
                "have short preparation time.".format(delay))
            time.sleep(delay)

        if self._machine_allocation_controller is not None:
            # switch power state if needed
            if not self._machine_allocation_controller.power:
                self._machine_allocation_controller.set_power(True)
        else:
            self._txrx.power_on_machine()

        self._txrx.ensure_board_is_ready()
        self._machine_is_turned_off = None
        return True

    @property
    def has_reset_last(self):
        return self._has_reset_last

    @property
    @overrides(SimulatorInterface.config)
    def config(self):
        return self._config

    @property
    def get_number_of_available_cores_on_machine(self):
        """ The number of available cores on the machine after taking\
            into account preallocated resources.

        :return: number of available cores
        :rtype: int
        """
        # get machine if not got already
        if self._machine is None:
            self._get_machine()

        # get cores of machine
        cores = self._machine.total_available_user_cores
        take_into_account_chip_power_monitor = self._read_config_boolean(
            "Reports", "write_energy_report")
        if take_into_account_chip_power_monitor:
            cores -= self._machine.n_chips
        take_into_account_extra_monitor_cores = (self._config.getboolean(
            "Machine", "enable_advanced_monitor_support") or
                self._config.getboolean("Machine", "enable_reinjection"))
        if take_into_account_extra_monitor_cores:
            cores -= self._machine.n_chips
            cores -= len(self._machine.ethernet_connected_chips)
        return cores

    def stop_run(self):
        """ Request that the current infinite run stop.

        .. note::
            This will need to be called from another thread as the infinite \
            run call is blocking.
        """
        if self._state is not Simulator_State.IN_RUN:
            return
        with self._state_condition:
            self._state = Simulator_State.STOP_REQUESTED
            self._state_condition.notify_all()

    @staticmethod
    def __reset_object(obj):
        # Reset an object if appropriate
        if isinstance(obj, AbstractCanReset):
            obj.reset_to_first_timestep()

    def __reset_graph_elements(self):
        # Reset any object that can reset
        if self._original_application_graph.n_vertices:
            for vertex in self._original_application_graph.vertices:
                self.__reset_object(vertex)
            for p in self._original_application_graph.outgoing_edge_partitions:
                for edge in p.edges:
                    self.__reset_object(edge)
        elif self._original_machine_graph.n_vertices:
            for machine_vertex in self._original_machine_graph.vertices:
                self.__reset_object(machine_vertex)
            for p in self._original_machine_graph.outgoing_edge_partitions:
                for machine_edge in p.edges:
                    self.__reset_object(machine_edge)

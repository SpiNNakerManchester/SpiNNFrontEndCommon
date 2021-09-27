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
import signal
import sys
import threading
from threading import Condition
from numpy import __version__ as numpy_version
from spinn_utilities.timer import Timer
from spinn_utilities.log import FormatAdapter
from spinn_utilities import __version__ as spinn_utils_version
from spinn_machine import CoreSubsets
from spinn_machine import __version__ as spinn_machine_version
from spinnman.model.enums.cpu_state import CPUState
from spinnman import __version__ as spinnman_version
from spinnman.exceptions import SpiNNManCoresNotInStateException
from spinnman.model.cpu_infos import CPUInfos
from spinnman.messages.scp.enums.signal import Signal
from data_specification import __version__ as data_spec_version
from spalloc import __version__ as spalloc_version
from pacman.model.placements import Placements
from pacman.executor.injection_decorator import (
    clear_injectables, provide_injectables, do_injection)
from pacman.model.graphs.application import (
    ApplicationGraph, ApplicationGraphView, ApplicationEdge, ApplicationVertex)
from pacman.model.graphs.machine import (
    MachineGraph, MachineGraphView, MachineVertex)
from pacman.model.resources import (
    ConstantSDRAM, PreAllocatedResourceContainer)
from pacman import __version__ as pacman_version
from pacman.model.partitioner_splitters.splitter_reset import splitter_reset
from pacman.operations.chip_id_allocator_algorithms import (
    MallocBasedChipIdAllocator)
from pacman.operations.fixed_route_router import FixedRouteRouter
from pacman.operations.partition_algorithms import SplitterPartitioner
from pacman.operations.placer_algorithms import (
    ConnectiveBasedPlacer, OneToOnePlacer, RadialPlacer, SpreaderPlacer)
from pacman.operations.router_algorithms import (
    BasicDijkstraRouting, NerRoute, NerRouteTrafficAware)
from pacman.operations.router_compressors.ordered_covering_router_compressor \
    import OrderedCoveringCompressor
from pacman.operations.router_compressors.checked_unordered_pair_compressor \
    import CheckedUnorderedPairCompressor
from pacman.operations.router_compressors import PairCompressor
from pacman.operations.routing_info_allocator_algorithms.\
    malloc_based_routing_allocator import MallocBasedRoutingInfoAllocator
from pacman.operations.routing_info_allocator_algorithms.\
    zoned_routing_info_allocator import (flexible_allocate, global_allocate)
from pacman.operations.routing_table_generators import (
    BasicRoutingTableGenerator)
from pacman.operations.tag_allocator_algorithms import BasicTagAllocator
from spinn_utilities.config_holder import (
    get_config_bool, get_config_int, get_config_str, set_config)
from spinn_front_end_common.abstract_models import (
    AbstractSendMeMulticastCommandsVertex,
    AbstractVertexWithEdgeToDependentVertices, AbstractChangableAfterRun,
    AbstractCanReset)
from spinn_front_end_common.interface.java_caller import JavaCaller
from spinn_front_end_common.interface.interface_functions import (
    ApplicationFinisher, ApplicationRunner,  BufferExtractor,
    BufferManagerCreator, ChipIOBufClearer, ChipIOBufExtractor,
    ChipProvenanceUpdater, ChipRuntimeUpdater, ComputeEnergyUsed,
    CreateNotificationProtocol, DatabaseInterface,
    DSGRegionReloader, EdgeToNKeysMapper, EnergyProvenanceReporter,
    GraphBinaryGatherer, GraphDataSpecificationWriter,
    GraphMeasurer, GraphProvenanceGatherer,  HostBasedBitFieldRouterCompressor,
    HostExecuteDataSpecification, HBPAllocator, HBPMaxMachineGenerator,
    InsertChipPowerMonitorsToGraphs,
    InsertEdgesToExtraMonitorFunctionality, InsertExtraMonitorVerticesToGraphs,
    LoadExecutableImages, LoadFixedRoutes,
    LocalTDMABuilder, LocateExecutableStartType, MachineGenerator,
    PreAllocateResourcesForChipPowerMonitor,
    PreAllocateResourcesForLivePacketGatherers,
    PreAllocateResourcesForExtraMonitorSupport,
    PlacementsProvenanceGatherer,
    ProfileDataGatherer, ProcessPartitionConstraints,
    ProvenanceJSONWriter, ProvenanceSQLWriter, ProvenanceXMLWriter,
    ReadRoutingTablesFromMachine,
    RouterProvenanceGatherer, RoutingSetup, RoutingTableLoader,
    SDRAMOutgoingPartitionAllocator, SpallocAllocator,
    SpallocMaxMachineGenerator,
    SystemMulticastRoutingGenerator,
    TagsLoader, VirtualMachineGenerator)
from spinn_front_end_common.interface.interface_functions.\
    machine_bit_field_router_compressor import (
        MachineBitFieldOrderedCoveringCompressor,
        MachineBitFieldPairRouterCompressor)
from spinn_front_end_common.interface.interface_functions.\
    host_no_bitfield_router_compression import (
        ordered_covering_compression, pair_compression)
from spinn_front_end_common.interface.splitter_selectors import (
    SplitterSelector)
from spinn_front_end_common.utilities import globals_variables
from spinn_front_end_common.utilities.constants import (
    SARK_PER_MALLOC_SDRAM_USAGE)
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.helpful_functions import (
    convert_time_diff_to_total_milliseconds)
from spinn_front_end_common.utilities.report_functions import (
    BitFieldCompressorReport, BoardChipReport, EnergyReport,
    FixedRouteFromMachineReport, MemoryMapOnHostReport,
    MemoryMapOnHostChipReport, NetworkSpecification,
    RouterCollisionPotentialReport,
    RoutingTableFromMachineReport, TagsFromMachineReport,
    WriteJsonMachine, WriteJsonPartitionNKeysMap, WriteJsonPlacements,
    WriteJsonRoutingTables)
from spinn_front_end_common.utilities.utility_objs import (
    ExecutableType, ProvenanceDataItem)
from spinn_front_end_common.utility_models import (
    CommandSender, CommandSenderMachineVertex,
    DataSpeedUpPacketGatherMachineVertex)
from spinn_front_end_common.utilities import IOBufExtractor
from spinn_front_end_common.interface.config_handler import ConfigHandler
from spinn_front_end_common.interface.simulator_status import (
    RUNNING_STATUS, SHUTDOWN_STATUS, Simulator_Status)
from spinn_front_end_common.utilities import FecTimer
from spinn_front_end_common.utilities.report_functions.reports import (
    generate_comparison_router_report, partitioner_report,
    placer_reports_with_application_graph,
    placer_reports_without_application_graph,
    router_compressed_summary_report, routing_info_report,
    router_report_from_compressed_router_tables,
    router_report_from_paths,
    router_report_from_router_tables, router_summary_report,
    sdram_usage_report_per_chip,
    tag_allocator_report)
from spinn_front_end_common import __version__ as fec_version
try:
    from scipy import __version__ as scipy_version
except ImportError:
    scipy_version = "scipy not installed"

logger = FormatAdapter(logging.getLogger(__name__))

# 0-15 are reserved for system use (per lplana)
ALANS_DEFAULT_RANDOM_APP_ID = 16

# Number of provenace items before auto changes to sql format
PROVENANCE_TYPE_CUTOFF = 20000


class AbstractSpinnakerBase(ConfigHandler):
    """ Main interface into the tools logic flow.
    """
    # pylint: disable=broad-except

    __slots__ = [
        # the object that contains a set of file paths, which should encompass
        # all locations where binaries are for this simulation.
        # init param and never changed
        "_executable_finder",

        # the number of boards requested by the user during setup
        # init param and never changed
        "_n_boards_required",

        # the number of chips requested by the user during setup.
        # init param and never changed
        "_n_chips_required",

        # The IP-address of the SpiNNaker machine
        # provided during init and never changed
        # init or cfg param and never changed
        "_hostname",

        # the ip_address of the spalloc server
        # provided during init and never changed
        # cfg param and never changed
        "_spalloc_server",

        # the URL for the HBP platform interface
        # cfg param and never changed
        "_remote_spinnaker_url",

        # the connection to allocted spalloc and HBP machines
        "_machine_allocation_controller",

        # the pacman application graph, used to hold vertices which need to be
        # split to core sizes
        "_application_graph",

        # the end user application graph, used to hold vertices which need to
        # be split to core sizes
        # Object created by init. Added to but never new object
        "_original_application_graph",

        # the pacman machine graph, used to hold vertices which represent cores
        "_machine_graph",

        # the end user pacman machine graph, used to hold vertices which
        # represent cores.
        # Object created by init. Added to but never new object
        "_original_machine_graph",

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

        # vertex label count used to ensure unique names of edges
        "_none_labelled_edge_count",

        # Set of addresses.
        # Set created at init. Added to but never new object
        "_database_socket_addresses",

        # status flag
        "_has_ran",

        # Status enum
        "_status",

        # Condition object used for waiting for stop
        # Set during init and the used but never new object
        "_state_condition",

        # status flag
        "_has_reset_last",

        # count of time from previous runs since setup/reset
        # During do_run points to the end timestep of that cycle
        "_current_run_timesteps",

        # change number of resets as loading the binary again resets the
        # sync to 0
        "_no_sync_changes",

        # max time the run can take without running out of memory
        "_max_run_time_steps",

        # Set when run_until_complete is specified by the user
        "_run_until_complete",

        # id for the application from the cfg or the tranceiver
        # TODO check after related PR
        "_app_id",

        # set to true it the current thread is not the main thread
        "_raise_keyboard_interrupt",

        # The run number for the this/next end_user call to run
        "_n_calls_to_run",

        # TODO should this be at this scope
        "_command_sender",

        # dict of exucutable types to cores
        "_executable_types",

        # mapping between parameters and the vertices which need to talk to
        # them
        # Created during init. Added to but never new object
        "_live_packet_recorder_params",

        # place holder for checking the vertices being added to the recorders
        # tracker are all of the same vertex type.
        "_live_packet_recorders_associated_vertex_type",

        # the time the process takes to do mapping
        # TODO energy report cleanup
        "_mapping_time",

        # the time the process takes to do load
        # TODO energy report cleanup
        "_load_time",

        # the time takes to execute the simulation
        # TODO energy report cleanup
        "_execute_time",

        # the timer used to log the execute time
        # TODO energy report cleanup
        "_run_timer",

        # time takes to do data generation
        # TODO energy report cleanup
        "_dsg_time",

        # time taken by the front end extracting things
        # TODO energy report cleanup
        "_extraction_time",

        # Version information from the front end
        # TODO provenance cleanup
        "_front_end_versions",

        # Used in exception handling and control c
        "_last_except_hook",

        # status flag
        "_vertices_or_edges_added",

        # Version provenance
        # TODO provenance cleanup
        "_version_provenance",

        # All beyond this point new for no extractor
        # The data is not new but now it is held direct and not via inputs

        # Path of the notification interface database
        "_database_file_path",

        # Binaries to run
        "_executable_targets",

        # version of the board to requested or discovered
        "_board_version",

        # vertices added to support Buffer Extractor
        "_extra_monitor_vertices",

        # Start timestep of a do_run cycle
        # Set by data generation and do_run cleared by do_run
        "_first_machine_time_step",

        # Mapping for partitions to how many keys they need
        "_machine_partition_n_keys_map",

        # system routing timout keys
        "_system_multicast_router_timeout_keys",

        # DSG to be written to the machine
        "_dsg_targets",

        # Sizes of dsg regions
        "_region_sizes",

        # Mapping for vertice to extra monitors
        "_vertex_to_ethernet_connected_chip_mapping",

        # Reinjection routing tables
        "_data_in_multicast_routing_tables",

        # Maps injector keys to chips
        "_data_in_multicast_key_to_chip_map",

        # Number of timesteps to consider when doing partitioning and placement
        "_plan_n_timesteps",

        # TODO provenance cleanup
        "_compressor_provenance",

        # Routing tables
        "_routing_table_by_partition",

        # Flag to say is compressed routing tables are on machine
        # TODO remove this when the data change only algorithms are done
        "_multicast_routes_loaded",

        # Extra monitors per chip
        "_extra_monitor_to_chip_mapping",

        # Flag to say if current machine is a temporary max machine
        # the temp /max machine is held in the "machine" slot
        "_max_machine",

        # Number of chips computed to be needed
        "_n_chips_needed",

        # Notification interface if needed
        "_notification_interface",
    ]

    def __init__(
            self, executable_finder, graph_label=None,
            database_socket_addresses=None, n_chips_required=None,
            n_boards_required=None, front_end_versions=None):
        """
        :param executable_finder: How to find APLX files to deploy to SpiNNaker
        :type executable_finder:
            ~spinn_utilities.executable_finder.ExecutableFinder
        :param str graph_label: A label for the overall application graph
        :param database_socket_addresses: How to talk to notification databases
        :type database_socket_addresses:
            iterable(~spinn_utilities.socket_address.SocketAddress) or None
        :param int n_chips_required:
            Overrides the number of chips to allocate from spalloc
        :param int n_boards_required:
            Overrides the number of boards to allocate from spalloc
        :param list(tuple(str,str)) front_end_versions:
            Information about what software is in use
        """
        # pylint: disable=too-many-arguments
        super().__init__()

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

        # command sender vertex
        self._command_sender = None

        # store for Live Packet Gatherers
        self._live_packet_recorder_params = defaultdict(list)
        self._live_packet_recorders_associated_vertex_type = None

        # update graph label if needed
        if graph_label is None:
            graph_label = "Application_graph"
        else:
            graph_label = graph_label

        # pacman objects
        self._original_application_graph = ApplicationGraph(label=graph_label)
        self._original_machine_graph = MachineGraph(
            label=graph_label,
            application_graph=self._original_application_graph)

        self._machine_allocation_controller = None
        self._txrx = None
        self._new_run_clear()

        # pacman executor objects
        self._version_provenance = list()

        self._none_labelled_edge_count = 0

        # database objects
        self._database_socket_addresses = set()
        if database_socket_addresses is not None:
            self._database_socket_addresses.update(database_socket_addresses)

        # holder for timing and running related values
        self._run_until_complete = False
        self._has_ran = False
        self._status = Simulator_Status.INIT
        self._state_condition = Condition()
        self._has_reset_last = False
        self._n_calls_to_run = 1
        self._current_run_timesteps = 0
        self._no_sync_changes = 0

        self._app_id = get_config_int("Machine", "app_id")

        # folders
        self._set_up_output_folders(self._n_calls_to_run)

        # Setup for signal handling
        self._raise_keyboard_interrupt = False

        globals_variables.set_simulator(self)

        # Front End version information
        self._front_end_versions = front_end_versions

        self._last_except_hook = sys.excepthook
        self._vertices_or_edges_added = False
        self._first_machine_time_step = None
        self._compressor_provenance = None

        FecTimer.setup(self)

        # Safety in case a previous run left a bad state
        clear_injectables()

    def _new_run_clear(self):
        """
        This clears all data that if no longer valid after a hard reset

        """
        self.__close_allocation_controller()
        self._application_graph = None
        self._board_version = None
        self._buffer_manager = None
        self._database_file_path = None
        self._notification_interface = None
        self._data_in_multicast_key_to_chip_map = None
        self._data_in_multicast_routing_tables = None
        self._dsg_targets = None
        self._executable_targets = None
        self._executable_types = None
        self._extra_monitor_to_chip_mapping = None
        self._extra_monitor_vertices = None
        self._fixed_routes = None
        self._java_caller = None
        self._machine = None
        self._machine_graph = None
        self._machine_partition_n_keys_map = None
        self._max_machine = False
        self._max_run_time_steps = None
        self._multicast_routes_loaded = False
        self._n_chips_needed = None
        self._placements = None
        self._plan_n_timesteps = None
        self._region_sizes = None
        self._router_tables = None
        self._routing_table_by_partition = None
        self._routing_infos = None
        self._system_multicast_router_timeout_keys = None
        self._tags = None
        if self._txrx is not None:
            self._txrx.close()
            self._app_id = None
        self._txrx = None
        self._vertex_to_ethernet_connected_chip_mapping = None

    def __getitem__(self, item):
        """
        Provides dict style access to the key data.

        Allow ASB to be passed into the do_injection method

        Values exposed this way are limited to the ones needed for injection

        :param str item: key to object wanted
        :return: Object asked for
        :rtype: Object
        :raise KeyError: the error message will say if the item is not known
            now or not provided
        """
        value = self._unchecked_gettiem(item)
        if value or value == 0:
            return value
        if value is None:
            raise KeyError(f"Item {item} is currently not set")

    def __contains__(self, item):
        """
        Provides dict style in checks to the key data.

        Keys check this way are limited to the ones needed for injection

        :param str item:
        :return: True if the items is currently know
        :rtype: bool
        """
        if self._unchecked_gettiem(item) is not None:
            return True
        return False

    def items(self):
        """
        Lists the keys of the data currently available.

        Keys exposed this way are limited to the ones needed for injection

        :return: List of the keys for which there is data
        :rtype: list(str)
        :raise KeyError:  Amethod this call depends on could raise this
            exception, but that indicates a programming mismatch
        """
        results = []
        for key in ["APPID", "ApplicationGraph", "DataInMulticastKeyToChipMap",
                    "DataInMulticastRoutingTables", "DataNTimeSteps",
                    "ExtendedMachine", "FirstMachineTimeStep", "MachineGraph",
                    "MachinePartitionNKeysMap", "Placements", "RoutingInfos",
                    "RunUntilTimeSteps", "SystemMulticastRouterTimeoutKeys",
                    "Tags"]:
            item = self._unchecked_gettiem(key)
            if item is not None:
                results.append((key, item))
        return results

    def _unchecked_gettiem(self, item):
        """
        Returns the data for this item or None if currently unknown.

        Values exposed this way are limited to the ones needed for injection

        :param str item:
        :return: The value for this item or None is currently unkwon
        :rtype: Object or None
        :raise KeyError: It the item is one that is never provided
        """
        if item == "APPID":
            return self._app_id
        if item == "ApplicationGraph":
            return self._application_graph
        if item == "DataInMulticastKeyToChipMap":
            return self._data_in_multicast_key_to_chip_map
        if item == "DataInMulticastRoutingTables":
            return self._data_in_multicast_routing_tables
        if item == "DataNTimeSteps":
            return self._max_run_time_steps
        if item == "DataNSteps":
            return self._max_run_time_steps
        if item == "ExtendedMachine":
            return self._machine
        if item == "FirstMachineTimeStep":
            return self._first_machine_time_step
        if item == "MachineGraph":
            return self.machine_graph
        if item == "MachinePartitionNKeysMap":
            return self._machine_partition_n_keys_map
        if item == "Placements":
            return self._placements
        if item == "RoutingInfos":
            return self._routing_infos
        if item == "RunUntilTimeSteps":
            return self._current_run_timesteps
        if item == "SystemMulticastRouterTimeoutKeys":
            return self._system_multicast_router_timeout_keys
        if item == "Tags":
            return self._tags
        raise KeyError(f"Unexpected Item {item}")

    def set_n_boards_required(self, n_boards_required):
        """ Sets the machine requirements.

        .. warning::

            This method should not be called after the machine
            requirements have be computed based on the graph.

        :param int n_boards_required: The number of boards required
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

    def add_extraction_timing(self, timing):
        """ Record the time taken for doing data extraction.

        :param ~datetime.timedelta timing:
        """
        ms = convert_time_diff_to_total_milliseconds(timing)
        self._extraction_time += ms

    def add_live_packet_gatherer_parameters(
            self, live_packet_gatherer_params, vertex_to_record_from,
            partition_ids):
        """ Adds parameters for a new LPG if needed, or adds to the tracker \
            for parameters. Note that LPGs can be inserted to track behaviour \
            either at the application graph level or at the machine graph \
            level, but not both at the same time.

        :param LivePacketGatherParameters live_packet_gatherer_params:
            params to look for a LPG
        :param ~pacman.model.graphs.AbstractVertex vertex_to_record_from:
            the vertex that needs to send to a given LPG
        :param list(str) partition_ids:
            the IDs of the partitions to connect from the vertex
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

    def set_up_machine_specifics(self, hostname):
        """ Adds machine specifics for the different modes of execution.

        :param str hostname: machine name
        """
        if hostname is not None:
            self._hostname = hostname
            logger.warning("The machine name from setup call is overriding "
                           "the machine name defined in the config file")
        else:
            self._hostname = get_config_str("Machine", "machine_name")
            self._spalloc_server = get_config_str(
                "Machine", "spalloc_server")
            self._remote_spinnaker_url = get_config_str(
                "Machine", "remote_spinnaker_url")

        if (self._hostname is None and self._spalloc_server is None and
                self._remote_spinnaker_url is None and
                not self._use_virtual_board):
            raise Exception(
                "A SpiNNaker machine must be specified your configuration"
                " file")

        n_items_specified = sum(
            item is not None
            for item in [
                self._hostname, self._spalloc_server,
                self._remote_spinnaker_url])

        if (n_items_specified > 1 or
                (n_items_specified == 1 and self._use_virtual_board)):
            raise Exception(
                "Only one of machineName, spalloc_server, "
                "remote_spinnaker_url and virtual_board should be specified "
                "in your configuration files")

        if self._spalloc_server is not None:
            if get_config_str("Machine", "spalloc_user") is None:
                raise Exception(
                    "A spalloc_user must be specified with a spalloc_server")

    def _setup_java_caller(self):
        if get_config_bool("Java", "use_java"):
            java_call = get_config_str("Java", "java_call")
            java_spinnaker_path = get_config_str(
                "Java", "java_spinnaker_path")
            java_jar_path = get_config_str(
                "Java", "java_jar_path")
            java_properties = get_config_str(
                "Java", "java_properties")
            self._java_caller = JavaCaller(
                self._json_folder, java_call, java_spinnaker_path,
                java_properties, java_jar_path)

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

    def verify_not_running(self):
        """ Verify that the simulator is in a state where it can start running.
        """
        if self._status in RUNNING_STATUS:
            raise ConfigurationException(
                "Illegal call while a simulation is already running")
        if self._status in SHUTDOWN_STATUS:
            raise ConfigurationException(
                "Illegal call after simulation is shutdown")

    def _should_run(self):
        """
        Checks if the simulation should run.

        Will warn the user if there is no need to run

        :return: True if and only if one of the graphs has vertices in it
        :raises ConfigurationException: If the current state does not
            support a new run call
        """
        self.verify_not_running()

        if self._original_application_graph.n_vertices:
            return True
        if self._original_machine_graph.n_vertices:
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
        self._run(run_time, sync_time)

    def _build_graphs_for_usage(self):
        if self._original_application_graph.n_vertices:
            if self._original_machine_graph.n_vertices:
                raise ConfigurationException(
                    "Illegal state where both original_application and "
                    "original machine graph have vertices in them")

        self._application_graph = self._original_application_graph.clone()
        self._machine_graph = self._original_machine_graph.clone()

    def __timesteps(self, time_in_ms):
        """ Get a number of timesteps for a given time in milliseconds.

        :return: The number of timesteps
        :rtype: int
        """
        n_time_steps = int(math.ceil(time_in_ms / self.machine_time_step_ms))
        calc_time = n_time_steps * self.machine_time_step_ms

        # Allow for minor float errors
        if abs(time_in_ms - calc_time) > 0.00001:
            logger.warning(
                "Time of {}ms "
                "is not a multiple of the machine time step of {}ms "
                "and has therefore been rounded up to {}ms",
                time_in_ms, self.machine_time_step_ms, calc_time)
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
            self._current_run_timesteps + n_machine_time_steps)
        total_run_time = (
            total_run_timesteps * self.machine_time_step_ms *
            self.time_scale_factor)

        # Convert dt into microseconds and multiply by
        # scale factor to get hardware timestep
        hardware_timestep_us = (
                self.machine_time_step * self.time_scale_factor)

        logger.info(
            f"Simulating for {n_machine_time_steps} "
            f"{self.machine_time_step_ms}ms timesteps using a "
            f"hardware timestep of {hardware_timestep_us}us")

        return n_machine_time_steps, total_run_time

    def _run(self, run_time, sync_time):
        """ The main internal run function.

        :param int run_time: the run duration in milliseconds.
        :param int sync_time:
            the time in ms between synchronisations, or 0 to disable.
        """
        if not self._should_run():
            return

        # verify that we can keep doing auto pause and resume
        if self._has_ran and not self._use_virtual_board:
            can_keep_running = all(
                executable_type.supports_auto_pause_and_resume
                for executable_type in self._executable_types)
            if not can_keep_running:
                raise NotImplementedError(
                    "Only binaries that use the simulation interface can be"
                    " run more than once")

        self._status = Simulator_Status.IN_RUN

        self._adjust_config(run_time)

        # Install the Control-C handler
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

            self._no_sync_changes = 0

        # build the graphs to modify with system requirements
        if not self._has_ran or graph_changed:
            if self._has_ran:
                # create new sub-folder for reporting data
                self._set_up_output_folders(self._n_calls_to_run)

            self._build_graphs_for_usage()
            self._add_dependent_verts_and_edges_for_application_graph()
            self._add_commands_to_command_sender()

            # Reset the machine if the graph has changed
            if not self._use_virtual_board and self._n_calls_to_run > 1:

                # wipe out stuff associated with a given machine, as these need
                # to be rebuilt.
                self._new_run_clear()

            if get_config_bool("Buffers", "use_auto_pause_and_resume"):
                self._plan_n_timesteps = get_config_int(
                    "Buffers", "minimum_auto_time_steps")
            else:
                self._plan_n_timesteps = n_machine_time_steps

            if self._machine is None:
                self._get_machine(total_run_time)
            self._do_mapping(total_run_time)

        # Check if anything has per-timestep SDRAM usage
        provide_injectables(self)
        is_per_timestep_sdram = self._is_per_timestep_sdram()

        # Disable auto pause and resume if the binary can't do it
        if not self._use_virtual_board:
            for executable_type in self._executable_types:
                if not executable_type.supports_auto_pause_and_resume:
                    set_config(
                        "Buffers", "use_auto_pause_and_resume", "False")

        # Work out the maximum run duration given all recordings
        if self._max_run_time_steps is None:
            self._max_run_time_steps = self._deduce_data_n_timesteps(
                self._machine_graph)
        clear_injectables()

        # Work out an array of timesteps to perform
        steps = None
        if (not get_config_bool("Buffers", "use_auto_pause_and_resume")
                or not is_per_timestep_sdram):

            # Runs should only be in units of max_run_time_steps at most
            if (is_per_timestep_sdram and
                    (self._max_run_time_steps < n_machine_time_steps or
                        n_machine_time_steps is None)):
                self._status = Simulator_Status.FINISHED
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
            self._do_data_generation()

            self._do_load(graph_changed)

        # Run for each of the given steps
        if run_time is not None:
            logger.info("Running for {} steps for a total of {}ms",
                        len(steps), run_time)
            for i, step in enumerate(steps):
                logger.info("Run {} of {}", i + 1, len(steps))
                self._do_run(step, graph_changed, n_sync_steps)
        elif run_time is None and self._run_until_complete:
            logger.info("Running until complete")
            self._do_run(None, graph_changed, n_sync_steps)
        elif (not get_config_bool(
                "Buffers", "use_auto_pause_and_resume") or
                not is_per_timestep_sdram):
            logger.info("Running forever")
            self._do_run(None, graph_changed, n_sync_steps)
            logger.info("Waiting for stop request")
            with self._state_condition:
                while self._status != Simulator_Status.STOP_REQUESTED:
                    self._state_condition.wait()
        else:
            logger.info("Running forever in steps of {}ms".format(
                self._max_run_time_steps))
            i = 0
            while self._status != Simulator_Status.STOP_REQUESTED:
                logger.info("Run {}".format(i + 1))
                self._do_run(
                    self._max_run_time_steps, graph_changed, n_sync_steps)
                i += 1

        # Indicate that the signal handler needs to act
        if isinstance(threading.current_thread(), threading._MainThread):
            self._raise_keyboard_interrupt = False
            self._last_except_hook = sys.excepthook
            sys.excepthook = self.exception_handler

        # update counter for runs (used by reports and app data)
        self._n_calls_to_run += 1
        self._status = Simulator_Status.FINISHED

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
                            pre_vertex=vertex, post_vertex=dependant_vertex)
                        self._application_graph.add_edge(
                            dependant_edge, edge_identifier)

    def _deduce_data_n_timesteps(self, machine_graph):
        """ Operates the auto pause and resume functionality by figuring out\
            how many timer ticks a simulation can run before SDRAM runs out,\
            and breaks simulation into chunks of that long.

        :param ~.MachineGraph machine_graph:
        :return: max time a simulation can run.
        """
        # Go through the placements and find how much SDRAM is used
        # on each chip
        usage_by_chip = dict()
        seen_partitions = set()

        for placement in self._placements.placements:
            sdram_required = placement.vertex.resources_required.sdram
            if (placement.x, placement.y) in usage_by_chip:
                usage_by_chip[placement.x, placement.y] += sdram_required
            else:
                usage_by_chip[placement.x, placement.y] = sdram_required

            # add sdram partitions
            sdram_partitions = (
                machine_graph.get_sdram_edge_partitions_starting_at_vertex(
                    placement.vertex))
            for partition in sdram_partitions:
                if partition not in seen_partitions:
                    usage_by_chip[placement.x, placement.y] += (
                        ConstantSDRAM(
                            partition.total_sdram_requirements() +
                            SARK_PER_MALLOC_SDRAM_USAGE))
                    seen_partitions.add(partition)

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

        :param int n_steps: the total runtime in machine time steps
        :param int n_steps_per_segment: the minimum allowed per chunk
        :return: list of time step lengths
        :rtype: list(int)
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
            return total_timesteps

        return None

    def _execute_get_virtual_machine(self):
        """
        Runs, times and logs the VirtualMachineGenerator if required

        May set then "machine" value
        """
        with FecTimer("Execute Virtual Machine Generator") as timer:
            if timer.skip_if_value_already_set(self._machine, "machine"):
                return
            if timer.skip_if_value_false(
                    self._use_virtual_board, "use_virtual_board"):
                return
            generator = VirtualMachineGenerator()
            # TODO fix params
            self._machine = generator(get_config_int("Machine", "version"))

    def _execute_allocator(self, total_run_time):
        """
        Runs, times and logs the SpallocAllocator or HBPAllocator if required

        :param total_run_time: The total run time to request
        type total_run_time: int or None
        :return: machine name, machine version, BMP details (if any),
            reset on startup flag, auto-detect BMP, SCAMP connection details,
            boot port, allocation controller
        :rtype: tuple(str, int, object, bool, bool, object, object,
            MachineAllocationController)
        """
        with FecTimer("Execute Allocator") as timer:
            self._max_machine = False
            if timer.skip_if_value_already_set(self._machine, "machine"):
                return None
            if timer.skip_if_value_not_none(self._hostname, "hostname"):
                return None
            if self._n_chips_needed:
                n_chips_required = self._n_chips_needed
            else:
                n_chips_required = self._n_chips_required
            if n_chips_required is None and self._n_boards_required is None:
                timer.skip("Size of required machine not yet known")
                return None
            if self._spalloc_server is not None:
                allocator = SpallocAllocator()
                return allocator(
                    self._spalloc_server, n_chips_required,
                    self._n_boards_required)
            else:
                allocator = HBPAllocator()
                return allocator(
                    self._remote_spinnaker_url, total_run_time,
                    n_chips_required, self._n_boards_required)

    def _execute_machine_generator(self, allocator_data):
        """
        Runs, times and logs the MachineGenerator if required

        May set the "machine" value if not already set

        :allocator_data: None or
            (machine name, machine version, BMP details (if any),
            reset on startup flag, auto-detect BMP, SCAMP connection details,
            boot port, allocation controller)
        :type allocator_data: None or
            tuple(str, int, object, bool, bool, object, object,
            MachineAllocationController)
        """
        with FecTimer("Execute Machine Generator") as timer:
            if timer.skip_if_value_already_set(self._machine, "machine"):
                return
            if self._hostname:
                bmp_details = get_config_str("Machine", "bmp_names")
                auto_detect_bmp = get_config_bool(
                    "Machine", "auto_detect_bmp")
                scamp_connection_data = get_config_str(
                    "Machine", "scamp_connections_data")
                boot_port_num = get_config_int(
                    "Machine", "boot_connection_port_num")
                reset_machine = get_config_bool(
                    "Machine", "reset_machine_on_startup")
                self._board_version = get_config_int(
                    "Machine", "version")

            elif allocator_data:
                (self._hostname, self._board_version, bmp_details,
                 reset_machine, auto_detect_bmp, scamp_connection_data,
                 boot_port_num, self._machine_allocation_controller
                 ) = allocator_data
            else:
                timer.skip("Size of required machine not yet known")
                return

            generator = MachineGenerator()
            self._machine, self._txrx = generator(
                self._hostname, bmp_details, self._board_version,
                auto_detect_bmp, scamp_connection_data, boot_port_num,
                reset_machine)

    def _execute_get_max_machine(self, total_run_time):
        """
        Runs, times and logs the MachineGenerator if required

        Will set the "machine" value if not already set

        Sets the _max_machine to True if the "machine" value is a temporary
        max machine.

        :param total_run_time: The total run time to request
        :type total_run_time: int or None
        """
        with FecTimer("Execute Max Machine Generator") as timer:
            if timer.skip_if_value_already_set(self._machine, "machine"):
                # Leave _max_machine as is a may be true from an earlier call
                return self._machine

            self._max_machine = True
            if self._spalloc_server:
                generator = SpallocMaxMachineGenerator()
                # TODO fix params
                self._machine = generator(
                    self._spalloc_server,
                    max_machine_core_reduction=get_config_int(
                        "Machine", "max_machine_core_reduction"))

            elif self._remote_spinnaker_url:
                generator = HBPMaxMachineGenerator()
                self._machine = generator(
                    self._remote_spinnaker_url, total_run_time,
                    get_config_int("Machine", "max_machine_core_reduction"))

            else:
                raise NotImplementedError("No machine generataion possible")

    def _get_machine(self, total_run_time=0.0):
        """ The python machine description object.

        :param total_run_time: The total run time to request
        :param n_machine_time_steps:
        :rtype: ~spinn_machine.Machine
        """
        if self._app_id is None:
            if self._txrx is None:
                self._app_id = ALANS_DEFAULT_RANDOM_APP_ID
            else:
                self._app_id = self._txrx.app_id_tracker.get_new_id()

        self._execute_get_virtual_machine()
        allocator_data = self._execute_allocator(total_run_time)
        self._execute_machine_generator(allocator_data)
        self._execute_get_max_machine(total_run_time)
        return self._machine

    def _create_version_provenance(self):
        """ Add the version information to the provenance data at the start.
        """
        version_provenance = [
            ProvenanceDataItem(
                ["version_data", "spinn_utilities_version"],
                spinn_utils_version),
            ProvenanceDataItem(
                ["version_data", "spinn_machine_version"],
                spinn_machine_version),
            ProvenanceDataItem(
                ["version_data", "spalloc_version"], spalloc_version),
            ProvenanceDataItem(
                ["version_data", "spinnman_version"], spinnman_version),
            ProvenanceDataItem(
                ["version_data", "pacman_version"], pacman_version),
            ProvenanceDataItem(
                ["version_data", "data_specification_version"],
                data_spec_version),
            ProvenanceDataItem(
                ["version_data", "front_end_common_version"], fec_version),
            ProvenanceDataItem(
                ["version_data", "numpy_version"], numpy_version),
            ProvenanceDataItem(
                ["version_data", "scipy_version"], scipy_version)]
        if self._front_end_versions is not None:
            version_provenance.extend(
                ProvenanceDataItem(names=["version_data", name], value=value)
                for name, value in self._front_end_versions)
        self._version_provenance = version_provenance

    def _do_extra_mapping_algorithms(self):
        """
        Allows overriding classes to add algorithms
        """

    def _write_json_machine(self):
        """
        Runs, times and logs WriteJsonMachine if required

        """
        with FecTimer("Write Json Machine") as timer:
            if timer.skip_if_cfg_false("Reports", "write_json_machine"):
                return
            writer = WriteJsonMachine()
            writer(self._machine, self._json_folder)
            # TODO output ignored as never used

    def _report_network_specification(self):
        """
        Runs, times and logs the Network Specification report is requested

        """
        with FecTimer("Report network_specification") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_network_specification_report"):
                return
            if self._application_graph is None:
                graph = self._machine_graph
            else:
                graph = self._application_graph
            report = NetworkSpecification()
            report(graph)

    def _execute_chip_id_allocator(self):
        """
        Runs, times and logs the ChipIdAllocator

        """
        with FecTimer("Execute Chip Id Allocator"):
            allocator = MallocBasedChipIdAllocator()
            if self._application_graph is None:
                graph = self._machine_graph
            else:
                graph = self._application_graph
            allocator(self._machine, graph)
            # return ignored as changes done inside original machine object

    def _report_board_chip(self):
        """
        Runs, times and logs the BoardChipReport is requested

        """
        with FecTimer("Report Write Board Chip Report") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_board_chip_report"):
                return
            report = BoardChipReport()
            report(self._machine)

    def _execute_splitter_reset(self):
        """
        Runs, times and logs the splitter_reset

        """
        with FecTimer("Execute Splitter Reset"):
            splitter_reset(self._application_graph)

    # Overriden by spynaker to choose a different algorithm
    def _execute_splitter_selector(self):
        """
        Runs, times and logs the SplitterSelector
        """
        with FecTimer("Execute Splitter Selector"):
            selector = SplitterSelector()
            selector(self._application_graph)

    def _execute_delay_support_adder(self):
        """
        Stub to allow spynakker to add delay supports
        """

    def _execute_preallocate_for_live_packet_gatherer(
            self, pre_allocated_resources):
        """
        Runs, times and logs the PreAllocateResourcesForLivePacketGatherers if\
        required

        :param pre_allocated_resources: other preallocated resources
        :type pre_allocated_resources:
            ~pacman.model.resources.PreAllocatedResourceContainer
        """
        with FecTimer("Execute PreAllocate For LivePacketGatherer") as timer:
            if timer.skip_if_empty(self._live_packet_recorder_params,
                                   "live_packet_recorder_params"):
                return
            pre_allocator = PreAllocateResourcesForLivePacketGatherers()
            # No need to get the output as same object as input
            pre_allocator(self._live_packet_recorder_params,
                          self._machine, pre_allocated_resources)

    def _execute_preallocate_for_chip_power_monitor(
            self, pre_allocated_resources):
        """
        Runs, times and logs the PreAllocateResourcesForChipPowerMonitor if\
        required

        :param pre_allocated_resources: other preallocated resources
        :type pre_allocated_resources:
            ~pacman.model.resources.PreAllocatedResourceContainer
        """
        with FecTimer(
                "Execute PreAllocate For Chip Power Monitor") as timer:
            if timer.skip_if_cfg_false("Reports", "write_energy_report"):
                return
            pre_allocator = PreAllocateResourcesForChipPowerMonitor()
            # No need to get the output as same object as input
            pre_allocator(
                self._machine,
                get_config_int("EnergyMonitor", "sampling_frequency"),
                pre_allocated_resources)

    def _execute_preallocate_for_extra_monitor_support(
            self, pre_allocated_resources):
        """
        Runs, times and logs the PreAllocateResourcesForExtraMonitorSupport if\
        required

        :param pre_allocated_resources: other preallocated resources
        :type pre_allocated_resources:
            ~pacman.model.resources.PreAllocatedResourceContainer
        """
        with FecTimer("Execute PreAllocate For Extra Monitor Support") \
                as timer:
            if timer.skip_if_cfgs_false(
                    "Machine", "enable_advanced_monitor_support",
                    "enable_reinjection"):
                return
            pre_allocator = PreAllocateResourcesForExtraMonitorSupport()
            # TODO n_cores_to_allocate param
            # No need to get the output as same object as input
            pre_allocator(self._machine, pre_allocated_resources)

    # Overriden by spynaker to choose a different algorithm
    def _execute_splitter_partitioner(self, pre_allocated_resources):
        """
        Runs, times and logs the SplitterPartitioner if\
        required

        :param pre_allocated_resources: other preallocated resources
        :type pre_allocated_resources:
            ~pacman.model.resources.PreAllocatedResourceContainer
        """
        with FecTimer("Execute Splitter Partitioner") as timer:
            if timer.skip_if_application_graph_empty():
                return
            partitioner = SplitterPartitioner()
            self._machine_graph, self._n_chips_needed = partitioner(
                self._application_graph, self._machine, self._plan_n_timesteps,
                pre_allocated_resources)

    def _execute_graph_measurer(self):
        """
        Runs, times and logs GraphMeasurer is required

        Sets self._n_chips_needed if no machine exists

        Warning if the users has specified a machine size he gets what he
        asks for and if it is too small the placer will tell him.

        :return:
        """
        with FecTimer("Execute Graph Measurer") as timer:
            if not self._max_machine:
                if timer.skip_if_value_already_set(self._machine, "machine"):
                    return
            measurer = GraphMeasurer()
            self._n_chips_needed = measurer(
                self._machine_graph, self._machine, self._plan_n_timesteps)

    def _execute_insert_chip_power_monitors(self):
        """
        Run, time and log the InsertChipPowerMonitorsToGraphs if required

        """
        with FecTimer("Execute Insert Chip Power Monitors") as timer:
            if timer.skip_if_cfg_false("Reports", "write_energy_report"):
                return
            inserter = InsertChipPowerMonitorsToGraphs()
            inserter(
                self._machine, self._machine_graph,
                get_config_int("EnergyMonitor", "sampling_frequency"),
                self._application_graph)

    def _execute_insert_extra_monitor_vertices(self):
        """
        Run, time and log the InsertChipPowerMonitorsToGraphs if required

        """
        with FecTimer("Execute Insert Extra Monitor Vertices") as timer:
            if timer.skip_if_cfgs_false(
                    "Machine", "enable_advanced_monitor_support",
                    "enable_reinjection"):
                return
            inserter = InsertExtraMonitorVerticesToGraphs()
            # inserter checks for None app graph not an empty one
            if self._application_graph.n_vertices > 0:
                app_graph = self._application_graph
            else:
                app_graph = None
        (self._vertex_to_ethernet_connected_chip_mapping,
         self._extra_monitor_vertices,
         self._extra_monitor_to_chip_mapping) = inserter(
            self._machine, self._machine_graph, app_graph)

    def _execute_partitioner_report(self):
        """
        Write, times and logs the partitioner_report if needed

        """
        with FecTimer("Execute Partitioner Report") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_partitioner_reports"):
                return
            partitioner_report(self._hostname, self._application_graph)

    def _execute_edge_to_n_keys_mapper(self):
        """
        Runs, times and logs the EdgeToNKeysMapper

        Sets the "machine_partition_n_keys_map" data
        """
        with FecTimer("Execute Edge To N Keys Mapper"):
            mapper = EdgeToNKeysMapper()
            self._machine_partition_n_keys_map = mapper(self._machine_graph)

    def _execute_local_tdma_builder(self):
        """
        Runs times and logs the LocalTDMABuilder
        """
        with FecTimer("Execute Local TDMA Builder"):
            builder = LocalTDMABuilder()
            builder(self._machine_graph, self._machine_partition_n_keys_map,
                    self._application_graph)

    def _json_partition_n_keys_map(self):
        """
        Writes, times and logs the machine_partition_n_keys_map if required
        """
        with FecTimer("Json Partition NKeys Map") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_json_partition_n_keys_map"):
                return
            writer = WriteJsonPartitionNKeysMap()
            writer(self._machine_partition_n_keys_map, self._json_folder)
            # Output ignored as never used

    def _execute_connective_based_placer(self):
        """
        Runs, times and logs the ConnectiveBasedPlacer

        Sets the "placements" data

        .. note::
            Calling of this method is based on the cfg placer value

        """
        with FecTimer("Execute Connective Based Placer"):
            placer = ConnectiveBasedPlacer()
            self._placements = placer(
                self._machine_graph, self._machine, self._plan_n_timesteps)

    def _execute_one_to_one_placer(self):
        """
        Runs, times and logs the OneToOnePlacer

        Sets the "placements" data

        .. note::
            Calling of this method is based on the cfg placer value

        """
        with FecTimer("Execute One To One Placer"):
            placer = OneToOnePlacer()
            self._placements = placer(
                self._machine_graph, self._machine, self._plan_n_timesteps)

    def _execute_radial_placer(self):
        """
        Runs, times and logs the RadialPlacer

        Sets the "placements" data

        .. note::
            Calling of this method is based on the cfg placer value

        """
        with FecTimer("Execute Radial Placer"):
            placer = RadialPlacer()
            self._placements = placer(
                self._machine_graph, self._machine, self._plan_n_timesteps)

    def _execute_speader_placer(self):
        """
        Runs, times and logs the SpreaderPlacer

        Sets the "placements" data

        .. note::
            Calling of this method is based on the cfg placer value

        """
        with FecTimer("Execute Spreader Placer"):
            placer = SpreaderPlacer()
            self._placements = placer(
                self._machine_graph, self._machine,
                self._machine_partition_n_keys_map, self._plan_n_timesteps)

    def _do_placer(self):
        """
        Runs, times and logs one of the placers

        Sets the "placements" data

        Which placer is run depends on the cfg placer value

        This method is the entry point for adding a new Placer

        :raise ConfigurationException: if the cfg place value is unexpected
        """
        name = get_config_str("Mapping", "placer")
        if name == "ConnectiveBasedPlacer":
            return self._execute_connective_based_placer()
        if name == "OneToOnePlacer":
            return self._execute_one_to_one_placer()
        if name == "RadialPlacer":
            return self._execute_radial_placer()
        if name == "SpreaderPlacer":
            return self._execute_speader_placer()
        if "," in name:
            raise ConfigurationException(
                "Only a single algorithm is supported for placer")
        raise ConfigurationException(
            f"Unexpected cfg setting placer: {name}")

    def _execute_insert_edges_to_extra_monitor(self):
        """
        Runs times and logs the InsertEdgesToExtraMonitor is required
        """
        with FecTimer("Execute Insert Edges To Extra Monitor") as timer:
            if timer.skip_if_cfgs_false(
                    "Machine", "enable_advanced_monitor_support",
                    "enable_reinjection"):
                return
            # inserter checks for None app graph not an empty one
            if self._application_graph.n_vertices > 0:
                app_graph = self._application_graph
            else:
                app_graph = None
            inserter = InsertEdgesToExtraMonitorFunctionality()
            inserter(self._machine_graph, self._placements, self._machine,
                     self._vertex_to_ethernet_connected_chip_mapping,
                     app_graph)

    def _execute_system_multicast_routing_generator(self):
        """
        Runs, times and logs the SystemMulticastRoutingGenerator is required

        May sets the data "data_in_multicast_routing_tables",
        "data_in_multicast_key_to_chip_map" and
        "system_multicast_router_timeout_keys"
        """
        with FecTimer("Execute System Multicast Routing Generator") as timer:
            if timer.skip_if_cfgs_false(
                    "Machine", "enable_advanced_monitor_support",
                    "enable_reinjection"):
                return
            generator = SystemMulticastRoutingGenerator()
            (self._data_in_multicast_routing_tables,
             self._data_in_multicast_key_to_chip_map,
             self._system_multicast_router_timeout_keys) = generator(
                self._machine, self._extra_monitor_to_chip_mapping,
                self._placements)

    def _execute_fixed_route_router(self):
        """
        Runs, times and logs the FixedRouteRouter if required

        May set the "fixed_routes" data.
        """
        with FecTimer("Execute Fixed Route Router") as timer:
            if timer.skip_if_cfg_false(
                    "Machine", "enable_advanced_monitor_support"):
                return
            router = FixedRouteRouter()
            self._fixed_routes = router(
                self._machine, self._placements,
                DataSpeedUpPacketGatherMachineVertex)

    def _report_placements_with_application_graph(self):
        """
        Writes, times and logs the application graph placer report if
        requested
        """
        with FecTimer("Report Placements With Application Graph") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_application_graph_placer_report"):
                return
            if timer.skip_if_application_graph_empty():
                return
            placer_reports_with_application_graph(
                self._hostname, self._application_graph, self._placements,
                self._machine)

    def _report_placements_with_machine_graph(self):
        """
        Writes, times and logs the machine graph placer report if
        requested
        """
        with FecTimer("Report Placements With Machine Graph") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_machine_graph_placer_report"):
                return
            placer_reports_without_application_graph(
                self._hostname, self._machine_graph, self._placements,
                self._machine)

    def _write_json_placements(self):
        """
        Does, times and logs the writing of placements as json if requested
        :return:
        """
        with FecTimer("Write Json Placements") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_json_placements"):
                return
            writer = WriteJsonPlacements()
            writer(self._placements, self._json_folder)
            # Output ignored as never used

    def _execute_ner_route_traffic_aware(self):
        """
        Runs, times and logs the NerRouteTrafficAware

        Sets the "routing_table_by_partition" data if called

        .. note::
            Calling of this method is based on the cfg router value
        """
        with FecTimer("Execute Ner Route Traffic Aware"):
            router = NerRouteTrafficAware()
            self._routing_table_by_partition = router(
                self._machine_graph, self._machine, self._placements)

    def _execute_ner_route(self):
        """
        Runs, times and logs the NerRoute

        Sets the "routing_table_by_partition" data

        .. note::
            Calling of this method is based on the cfg router value
        """
        with FecTimer("Execute Ner Route"):
            router = NerRoute()
            self._routing_table_by_partition = router(
                self._machine_graph, self._machine, self._placements)

    def _execute_basic_dijkstra_routing(self):
        """
        Runs, times and logs the BasicDijkstraRouting

        Sets the "routing_table_by_partition" data if called

        .. note::
            Calling of this method is based on the cfg router value
        """
        with FecTimer("Execute Basic Dijkstra Routing"):
            router = BasicDijkstraRouting()
            self._routing_table_by_partition = router(
                self._machine_graph, self._machine, self._placements)

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
        with FecTimer("Execute Basic Tag Allocator"):
            allocator = BasicTagAllocator()
            self._tags = allocator(
                self._machine, self._plan_n_timesteps, self._placements)

    def _report_tag_allocations(self):
        """
        Write, times and logs the tag allocator report if requested
        """
        with FecTimer("Report Tag Allocations") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_tag_allocation_reports"):
                return
            tag_allocator_report(self._tags)

    def _execute_process_partition_constraints(self):
        """
        Runs, times and logs the ProcessPartitionConstraints
        """
        with FecTimer("Execute Process Partition Constraints"):
            processor = ProcessPartitionConstraints()
            processor(self._machine_graph)

    def _execute_global_allocate(self):
        """
        Runs, times and logs the Global Zoned Routing Info Allocator

        Sets "routing_info" is called

        .. note::
            Calling of this method is based on the cfg info_allocator value

        :return:
        """
        with FecTimer("Execute Global Zoned Routing Info Allocator"):
            self._routing_infos = global_allocate(
                self._machine_graph, self._machine_partition_n_keys_map)

    def _execute_flexible_allocate(self):
        """
        Runs, times and logs the Zoned Routing Info Allocator

        Sets "routing_info" is called

        .. note::
            Calling of this method is based on the cfg info_allocator value

        :return:
        """
        with FecTimer("Execute Zoned Routing Info Allocator"):
            self._routing_infos = flexible_allocate(
                self._machine_graph, self._machine_partition_n_keys_map)

    def _execute_malloc_based_routing_info_allocator(self):
        """
        Runs, times and logs the Malloc Based Routing Info Allocator

        Sets "routing_info" is called

        .. note::
            Calling of this method is based on the cfg info_allocator value

        :return:
        """
        with FecTimer("Execute Malloc Based Routing Info Allocator"):
            allocator = MallocBasedRoutingInfoAllocator()
            self._routing_infos = allocator(
                self._machine_graph, self._machine_partition_n_keys_map)

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
        if name == "GlobalZonedRoutingInfoAllocator ":
            return self._execute_global_allocate()
        if name == "MallocBasedRoutingInfoAllocator":
            return self._execute_malloc_based_routing_info_allocator()
        if name == "ZonedRoutingInfoAllocator":
            return self._execute_flexible_allocate()
        if "," in name:
            raise ConfigurationException(
                "Only a single algorithm is supported for info_allocator")
        raise ConfigurationException(
            f"Unexpected cfg setting info_allocator: {name}")

    def _report_router_info(self):
        """
        Writes, times and logs the router iinfo report if requested
        """
        with FecTimer("Report Router Info") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_router_info_report"):
                return
            routing_info_report(self._machine_graph, self._routing_infos)

    def _execute_basic_routing_table_generator(self):
        """
        Runs, times and logs the Routing Table Generator

        .. note::
            Currently no other Routing Table Generator supported.
            To add an additional Generator copy the pattern of do_placer
        """
        with FecTimer("Execute Basic Routing Table Generator"):
            generator = BasicRoutingTableGenerator()
            self._router_tables = generator(
                self._routing_infos, self._routing_table_by_partition,
                self._machine)
        # TODO Nuke ZonedRoutingTableGenerator

    def _report_routers(self):
        """
        Write, times and logs the router report if requested
        """
        with FecTimer("Report Router") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_router_reports"):
                return
        router_report_from_paths(
            self._router_tables, self._routing_infos, self._hostname,
            self._machine_graph, self._placements, self._machine)

    def _report_router_summary(self):
        """
        Write, times and logs the router summary report if requested
        """
        with FecTimer("Report Router Summary") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_router_summary_report"):
                return
            router_summary_report(
                self._router_tables,  self._hostname, self._machine)

    def _json_routing_tables(self):
        """
        Write, time and log the routing tables as json if requested
        """
        with FecTimer("Write Json Routing Tables") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_json_routing_tables"):
                return
            writer = WriteJsonRoutingTables()
            writer(self._router_tables, self._json_folder)
            # Output ignored as never used

    def _report_router_collision_potential(self):
        """
        Write, time and log the router collision report
        """
        with FecTimer("Report Router Collision Potential"):
            # TODO cfg flag!
            report = RouterCollisionPotentialReport()
            report(self._routing_table_by_partition,
                   self._machine_partition_n_keys_map, self._machine)

    def _execute_locate_executable_start_type(self):
        """
        Runs, times and logs LocateExecutableStartType if required

        May set the executable_types data.
        """
        with FecTimer("Execute Locate Executable Start Type") as timer:
            # TODO why skip if virtual ?
            if timer.skip_if_virtual_board():
                return
            locator = LocateExecutableStartType()
            self._executable_types = locator(
                self._machine_graph, self._placements)

    def _execute_buffer_manager_creator(self):
        """
        Run, times and logs the buffer manager creator if required

        May set the buffer_manager data
        """
        with FecTimer("Execute Buffer Manager Creator") as timer:
            if timer.skip_if_virtual_board():
                return
            if timer.skip_if_value_already_set(
                    self._buffer_manager, "Buffer Manager"):
                return

            creator = BufferManagerCreator()
            self._buffer_manager = creator(
                self._placements, self._tags, self._txrx,
                self._extra_monitor_vertices,
                self._extra_monitor_to_chip_mapping,
                self._vertex_to_ethernet_connected_chip_mapping,
                self._machine, self._fixed_routes, self._java_caller)

    def _execute_sdram_outgoing_partition_allocator(self):
        """
        Runs, times and logs the SDRAMOutgoingPartitionAllocator
        """
        with FecTimer("Execute SDRAM Outgoing Partition Allocator"):
            allocator = SDRAMOutgoingPartitionAllocator()
            # Ok if transceiver = None
            allocator(
                self._machine_graph, self._placements, self._app_id,
                self._txrx)

    def _do_mapping(self, total_run_time):
        """
        Runs, times and logs all the algorithms in the mapping stage

        :param float total_run_time:
        """
        # time the time it takes to do all pacman stuff
        mapping_total_timer = Timer()
        mapping_total_timer.start_timing()
        provide_injectables(self)

        self._setup_java_caller()
        self._do_extra_mapping_algorithms()
        self._report_network_specification()
        self._execute_splitter_reset()
        self._execute_splitter_selector()
        self._execute_delay_support_adder()
        pre_allocated_resources = PreAllocatedResourceContainer()
        self._execute_preallocate_for_live_packet_gatherer(
            pre_allocated_resources)
        self._execute_preallocate_for_chip_power_monitor(
            pre_allocated_resources)
        self._execute_preallocate_for_extra_monitor_support(
            pre_allocated_resources)
        self._execute_splitter_partitioner(pre_allocated_resources)
        self._execute_graph_measurer()
        allocator_data = self._execute_allocator(total_run_time)
        self._execute_machine_generator(allocator_data)
        assert(self._machine)
        self._write_json_machine()
        self._execute_chip_id_allocator()
        self._report_board_chip()
        self._execute_insert_chip_power_monitors()
        self._execute_insert_extra_monitor_vertices()
        self._execute_partitioner_report()
        self._execute_edge_to_n_keys_mapper()
        self._execute_local_tdma_builder()
        self._json_partition_n_keys_map()
        self._do_placer()
        self._execute_system_multicast_routing_generator()
        self._execute_fixed_route_router()
        self._report_placements_with_application_graph()
        self._report_placements_with_machine_graph()
        self._write_json_placements()
        self._do_routing()
        self._execute_basic_tag_allocator()
        self._report_tag_allocations()
        self._execute_process_partition_constraints()
        self.do_info_allocator()
        self._report_router_info()
        self._execute_basic_routing_table_generator()
        self._report_routers()
        self._report_router_summary()
        self._json_routing_tables()
        self._report_router_collision_potential()
        self._execute_locate_executable_start_type()
        self._execute_buffer_manager_creator()
        self._execute_sdram_outgoing_partition_allocator()

        clear_injectables()
        self._mapping_time += convert_time_diff_to_total_milliseconds(
            mapping_total_timer.take_sample())

    # Overridden by spy which adds placement_order
    def _execute_graph_data_specification_writer(self):
        """
        Runs, times, and logs the GraphDataSpecificationWriter

        Sets the dsg_targets data
        """
        with FecTimer("Execute Graph Data Specification Writer"):
            writer = GraphDataSpecificationWriter()
            self._dsg_targets, self._region_sizes = writer(
                self._placements, self._hostname, self._machine,
                self._max_run_time_steps)

    def _do_data_generation(self):
        """
        Runs, Times and logs the data generation
        """
        # set up timing
        data_gen_timer = Timer()
        data_gen_timer.start_timing()

        self._first_machine_time_step = self._current_run_timesteps

        provide_injectables(self)
        self._execute_graph_data_specification_writer()
        clear_injectables()

        self._dsg_time += convert_time_diff_to_total_milliseconds(
            data_gen_timer.take_sample())

    def _execute_routing_setup(self, graph_changed):
        """
        Runs, times and logs the RoutingSetup if required.

        :param bool graph_changed: Flag to say the graph changed,
        """
        with FecTimer("Execute Routing Setup") as timer:
            if timer.skip_if_virtual_board():
                return
            if timer.skip_if_value_false(graph_changed, "graph_changed"):
                return
            if self._multicast_routes_loaded:
                timer.skip("Routing tables already loaded")
                return
            setup = RoutingSetup()
            # Only needs the x and y of chips with routing tables
            setup(self._router_tables, self._app_id, self._txrx, self._machine)

    def _execute_graph_binary_gatherer(self, graph_changed):
        """
        Runs, times and logs the GraphBinaryGatherer if required.

        :param bool graph_changed: Flag to say the graph changed,
        """
        with FecTimer("Execute Graph Binary Gatherer") as timer:
            if timer.skip_if_value_false(graph_changed, "graph_changed"):
                return
            try:
                gather = GraphBinaryGatherer()
                self._executable_targets = gather(
                    self._placements, self._machine_graph,
                    self._executable_finder)
            except KeyError:
                if self.use_virtual_board:
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

        :return: CompressedRoutingTables and an empty list
        :rtype: tuple(MulticastRoutingTables, List)
        """
        with FecTimer("Execute HostBasedBitFieldRouterCompressor") as timer:
            if timer.skip_if_virtual_board():
                return None, []
            self._multicast_routes_loaded = False
            compressor = HostBasedBitFieldRouterCompressor()
            return compressor(
                self._router_tables, self._machine, self._placements,
                self._txrx, self._machine_graph, self._routing_infos)

    def _execute_machine_bitfield_ordered_covering_compressor(self):
        """
        Runs, times and logs the MachineBitFieldOrderedCoveringCompressor

        .. note::
            Calling of this method is based on the cfg compressor or
            virtual_compressor value

        :return: None and the provenance list
        :rtype: tuple(None, list(ProvenanceDataItem))
        """
        with FecTimer(
                "Execute MachineBitFieldOrderedCoveringCompressor") as timer:
            if timer.skip_if_virtual_board():
                return None, []
            compressor = MachineBitFieldOrderedCoveringCompressor()
            _, provenance = compressor(
                self._router_tables, self._txrx, self._machine, self._app_id,
                self._machine_graph, self._placements, self._executable_finder,
                self._routing_infos, self._executable_targets)
            self._multicast_routes_loaded = True
            return None, provenance

    def _execute_machine_bitfield_pair_compressor(self):
        """
        Runs, times and logs the MachineBitFieldPairRouterCompressor

        .. note::
            Calling of this method is based on the cfg compressor or
            virtual_compressor value

        :return: None and the provenance list
        :rtype: tuple(None, list(ProvenanceDataItem))
         """
        with FecTimer("Execute MachineBitFieldPairRouterCompressor") as timer:
            if timer.skip_if_virtual_board():
                return None, []
            self._multicast_routes_loaded = True
            compressor = MachineBitFieldPairRouterCompressor()
            _, provenance = compressor(
                self._router_tables, self._txrx, self._machine, self._app_id,
                self._machine_graph, self._placements, self._executable_finder,
                self._routing_infos, self._executable_targets)
            return None, provenance

    def _execute_ordered_covering_compressor(self):
        """
        Runs, times and logs the OrderedCoveringCompressor

        .. note::
            Calling of this method is based on the cfg compressor or
            virtual_compressor value

        :return: CompressedRoutingTables and an empty list
        :rtype: tuple(MulticastRoutingTables, List)
        """
        with FecTimer("Execute OrderedCoveringCompressor"):
            self._multicast_routes_loaded = False
            compressor = OrderedCoveringCompressor()
            compressed = compressor(self._router_tables)
            return compressed, []

    def _execute_ordered_covering_compression(self):
        """
        Runs, times and logs the ordered covering compressor on machine

        .. note::
            Calling of this method is based on the cfg compressor or
            virtual_compressor value

        :return: None and an empty list
        :rtype: tuple(None, List)
        """
        with FecTimer("Execute OrderedCoveringCompressor") as timer:
            if timer.skip_if_virtual_board():
                return None, []
            ordered_covering_compression(
                self._router_tables, self._txrx, self._executable_finder,
                self._machine, self._app_id)
            self._multicast_routes_loaded = True
            return None, []

    def _execute_pair_compressor(self):
        """
        Runs, times and logs the PairCompressor

        .. note::
            Calling of this method is based on the cfg compressor or
            virtual_compressor value

        :return: CompressedRoutingTables and an empty list
        :rtype: tuple(MulticastRoutingTables, List)
        """
        with FecTimer("Execute PairCompressor"):
            compressor = PairCompressor()
            compressed = compressor(self._router_tables)
            self._multicast_routes_loaded = False
            return compressed, []

    def _execute_pair_compression(self):
        """
        Runs, times and logs the pair compressor on machine

        .. note::
            Calling of this method is based on the cfg compressor or
            virtual_compressor value

        :return: None and an empty list
        :rtype: tuple(None, List)
        """
        with FecTimer("Execute PairOnChipRouterCompression") as timer:
            if timer.skip_if_virtual_board():
                return None, []
            pair_compression(
                self._router_tables, self._txrx, self._executable_finder,
                self._machine, self._app_id)
            self._multicast_routes_loaded = True
            return None, []

    def _execute_pair_unordered_compressor(self):
        """
        Runs, times and logs the CheckedUnorderedPairCompressor

        .. note::
            Calling of this method is based on the cfg compressor or
            virtual_compressor value

        :return: CompressedRoutingTables and an empty list
        :rtype: tuple(MulticastRoutingTables, List)
        """
        with FecTimer("Execute PairUnorderedCompressor"):
            compressor = CheckedUnorderedPairCompressor()
            compressed = compressor(self._router_tables)
            self._multicast_routes_loaded = False
            return compressed, []

    def _do_compression(self):
        """
        Attempts to run a compressor based on the cfg compressor setting.

        If using a virtual machine it will looks for the
        cfg virtual_compressor value, otherwise use the compressor value.

        May return on host compressed routing tables

        Will set the multicast_routes_loaded flag if during compression the
        routing tables have been loaded

        Only some compressors provide provenance

        :return: CompressedRoutingTables (likely to be None),
            RouterCompressorProvenanceItems (may be an empty list)
        :rtype: tuple(MulticastRoutingTables or None, list(ProvenanceDataItem))
        """
        if self.use_virtual_board:
            name = get_config_str("Mapping", "virtual_compressor")
            if name is None:
                logger.info("As no virtual_compressor specified "
                            "using compressor setting")
                name = get_config_str("Mapping", "compressor")
        else:
            name = get_config_str("Mapping", "compressor")

        # Calling a seperate method which can be overidden
        return self._do_compression_by_name(name)

    def _do_compression_by_name(self, name):
        """
        Calls a compressor based on the name provided

        .. note::
            This method is the entry point for adding a new compressor

        :param str name: Name of a compressor
        :raise ConfigurationException: if the name is not expected
        :return: CompressedRoutingTables (likely to be None),
            RouterCompressorProvenanceItems (may be an empty list)
        :rtype: tuple(MulticastRoutingTables or None, list(ProvenanceDataItem))
        """
        if name == "HostBasedBitFieldRouterCompressor":
            return self._execute_host_bitfield_compressor()
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

        # overridden in spy to handle:
        # SpynnakerMachineBitFieldOrderedCoveringCompressor
        # SpynnakerMachineBitFieldPairRouterCompressor

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
        with FecTimer("Execute Routing Table Loader") as timer:
            if timer.skip_if_virtual_board():
                return
            if compressed:
                loader = RoutingTableLoader()
                loader(compressed, self._app_id, self._txrx, self._machine)
                self._multicast_routes_loaded = True
            else:
                timer.skip("Tables loaded by compressor")

    def _report_uncompressed_routing_table(self):
        """
        Runs, times and logs the router report from router tables if requested
        """
        # TODO why not during mapping?
        with FecTimer("Report Uncompressed RoutingTable") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_routing_table_reports"):
                return
            router_report_from_router_tables(self._router_tables)

    def _report_bit_field_compressor(self):
        """
        Runs, times and logs the BitFieldCompressorReport if requested
        """
        with FecTimer("Report BitField Compressor") as timer:
            if timer.skip_if_cfg_false(
                    "Reports",  "write_bit_field_compressor_report"):
                return
            report = BitFieldCompressorReport()
            # BitFieldSummary output ignored as never used
            report(self._machine_graph, self._placements,
                   self._compressor_provenance)
            # TODO get provenance out of report.

    def _execute_load_fixed_routes(self, graph_changed):
        """
        Runs, times and logs Load Fixed Routes is required

        :param bool graph_changed: Flag to say the graph changed,
        """
        with FecTimer("Execute Load Fixed Routes") as timer:
            if timer.skip_if_cfg_false(
                    "Machine", "enable_advanced_monitor_support"):
                return
            if timer.skip_if_virtual_board():
                return
            if graph_changed or not self._has_ran:
                loader = LoadFixedRoutes()
                loader(self._fixed_routes, self._txrx, self._app_id)
            else:
                timer.skip("Graph not changed since last run")

    def _execute_system_data_specification(self):
        """
        Runs, times and logs the execute_system_data_specs if required

        :return: map of placement and DSG data, and loaded data flag.
        :rtype: dict(tuple(int,int,int),DataWritten) or DsWriteInfo
        """
        with FecTimer("Execute System Data Specification") \
                as timer:
            if timer.skip_if_virtual_board():
                return None
            specifier = HostExecuteDataSpecification()
            return specifier.execute_system_data_specs(
                self._txrx, self._machine, self._app_id, self._dsg_targets,
                self._region_sizes, self._executable_targets,
                self._java_caller)

    def _execute_load_system_executable_images(self):
        """
        Runs, times and logs the loading of exectuable images
        """
        with FecTimer("Execute Load Executable System Images") as timer:
            if timer.skip_if_virtual_board():
                return
            loader = LoadExecutableImages()
            loader.load_sys_images(
                self._executable_targets, self._app_id, self._txrx)

    def _execute_application_data_specification(
            self, processor_to_app_data_base_address):
        """
        Runs, times and logs the execute_application_data_specs if required

        :return: map of placement and DSG data, and loaded data flag.
        :rtype: dict(tuple(int,int,int),DataWritten) or DsWriteInfo
        """
        with FecTimer("Execute Host Data Specification") as timer:
            if timer.skip_if_virtual_board():
                return processor_to_app_data_base_address
            specifier = HostExecuteDataSpecification()
            return specifier.execute_application_data_specs(
                self._txrx, self._machine, self._app_id, self._dsg_targets,
                self._executable_targets, self._region_sizes, self._placements,
                self._extra_monitor_vertices,
                self._vertex_to_ethernet_connected_chip_mapping,
                self._java_caller, processor_to_app_data_base_address)

    def _execute_tags_from_machine_report(self):
        """
        Run, times and logs the TagsFromMachineReport if requested
        :return:
        """
        with FecTimer("Execute Tags From Machine Report") as timer:
            if timer.skip_if_virtual_board():
                return
            if timer.skip_if_cfg_false(
                    "Reports", "write_tag_allocation_reports"):
                return
            report = TagsFromMachineReport()
            report(self._txrx)

    def _execute_load_tags(self):
        """
        Runs, times and logs the Tags Loader if required
        """
        # TODO why: if graph_changed or data_changed:
        with FecTimer("Execute Tags Loader") as timer:
            if timer.skip_if_virtual_board():
                return
            loader = TagsLoader()
            loader(self._txrx, self._tags)

    def _do_extra_load_algorithms(self):
        """
        Runs, times and logs any extra load algorithms

        :param bool graph_changed: Flag to say the graph changed,
        """
        pass

    def _report_memory_on_host(
            self, graph_changed, processor_to_app_data_base_address):
        """
        Runs, times and logs MemoryMapOnHostReport is requested

        :param bool graph_changed: Flag to say the graph changed,
        """
        with FecTimer("Execute Memory Report") as timer:
            if timer.skip_if_virtual_board():
                return
            if timer.skip_if_value_false(graph_changed, "graph_changed"):
                return
            if timer.skip_if_cfg_false(
                    "Reports", "write_memory_map_report"):
                return
            report = MemoryMapOnHostReport()
            report(processor_to_app_data_base_address)

    def _report_memory_on_chip(self, graph_changed):
        """
        Runs, times and logs MemoryMapOnHostChipReport is requested

        :param bool graph_changed: Flag to say the graph changed,
        """
        with FecTimer("Execute Memory Report") as timer:
            if timer.skip_if_virtual_board():
                return
            if timer.skip_if_value_false(graph_changed, "graph_changed"):
                return
            if timer.skip_if_cfg_false(
                    "Reports", "write_memory_map_report"):
                return

            report = MemoryMapOnHostChipReport()
            report(self._dsg_targets, self._txrx)

    # TODO consider different cfg flags
    def _execute_compressed_reports(self, graph_changed, compressed):
        """
        Runs, times and logs the compressor reports if requested

        :param bool graph_changed: Flag to say the graph changed,
        :param compressed:
        :type compressed: MulticastRoutingTables or None
        """
        with FecTimer("Execute Compressor Report") as timer:
            if timer.skip_if_value_false(graph_changed, "graph_changed"):
                return
            if timer.skip_if_cfg_false(
                    "Reports", "write_routing_table_reports"):
                return
            if timer.skip_if_cfg_false(
                    "Reports", "write_routing_tables_from_machine_reports"):
                return

            if compressed is None:
                if timer.skip_if_virtual_board():
                    return
                reader = ReadRoutingTablesFromMachine()
                compressed = reader(self._txrx, self._router_tables,
                                    self._app_id)

            router_report_from_compressed_router_tables(compressed)

            generate_comparison_router_report(self._router_tables, compressed)

            router_compressed_summary_report(
                self._router_tables, self._hostname, self._machine)

            report = RoutingTableFromMachineReport()
            report(compressed)

    def _execute_fixed_route_report(self, graph_changed):
        """
        Runs, times and logs the FixedRouteFromMachineReport is requested

        :param bool graph_changed: Flag to say the graph changed,
        """
        with FecTimer("Execute Fixed Route Report") as timer:
            if timer.skip_if_virtual_board():
                return
            if self._has_ran and not graph_changed:
                timer.skip("graph not changed since last run")
                return
            if timer.skip_if_cfg_false(
                    "Machine", "enable_advanced_monitor_support"):
                return
            # TODO at the same time as LoadFixedRoutes?
            report = FixedRouteFromMachineReport()
            report(self._txrx, self._machine, self._app_id)

    def _execute_application_load_executables(self):
        """ algorithms needed for loading the binaries to the SpiNNaker machine

        :return:
        """
        with FecTimer("Execute Load Executable App Images") as timer:
            if timer.skip_if_virtual_board():
                return
            loader = LoadExecutableImages()
            loader.load_app_images(
                self._executable_targets, self._app_id, self._txrx)

    def _do_load(self, graph_changed):
        """
        Runs, times and logs the load algotithms

        :param bool graph_changed: Flag to say the graph changed,
        """
        # set up timing
        load_timer = Timer()
        load_timer.start_timing()

        self._execute_routing_setup(graph_changed)
        self._execute_graph_binary_gatherer(graph_changed)
        # loading_algorithms
        compressed, self._compressor_provenance = self._do_compression()
        self._execute_load_routing_tables(compressed)
        self._report_uncompressed_routing_table()
        self._report_bit_field_compressor()
        self._execute_load_fixed_routes(graph_changed)
        processor_to_app_data_base_address = \
            self._execute_system_data_specification()
        self._execute_load_system_executable_images()

        # TODO Was master correct to run the report first?
        self._execute_tags_from_machine_report()
        self._execute_load_tags()
        processor_to_app_data_base_address = \
            self._execute_application_data_specification(
                processor_to_app_data_base_address)
        self._do_extra_load_algorithms()
        self._report_memory_on_host(
            graph_changed, processor_to_app_data_base_address)
        self._report_memory_on_chip(graph_changed)
        self._execute_compressed_reports(graph_changed, compressed)
        self._execute_fixed_route_report(graph_changed)
        self._execute_application_load_executables()

        self._load_time += convert_time_diff_to_total_milliseconds(
            load_timer.take_sample())

    def _execute_sdram_usage_report_per_chip(self):
        # TODO why in do run
        with FecTimer("Execute Sdram Usage Report Per Chip") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_sdram_usage_report_per_chip"):
                return
            sdram_usage_report_per_chip(
                self._hostname, self._placements, self._machine,
                self._plan_n_timesteps,
                data_n_timesteps=self._max_run_time_steps)

    def _execute_dsg_region_reloader(self, graph_changed):
        """
            Runs, times and logs the DSGRegionReloader if required

            Reload any parameters over the loaded data if we have already
            run and not using a virtual board and the data hasn't already
            been regenerated

        :param bool graph_changed: Flag to say the graph changed,
        """
        with FecTimer("Execute DSG Region Reloader") as timer:
            if timer.skip_if_has_not_run():
                return
            if timer.skip_if_virtual_board():
                return
            if timer.skip_if_value_true(graph_changed, "graph changed"):
                return
            reloader = DSGRegionReloader()
            reloader(self._txrx, self._placements, self._hostname)

    def _execute_graph_provenance_gatherer(self):
        """
        Runs, times and log the GraphProvenanceGatherer if requested

        :rtype: list(ProvenanceDataItem)
        """
        with FecTimer("Execute Graph Provenance Gatherer") as timer:
            if timer.skip_if_cfg_false("Reports", "read_provenance_data"):
                return []
            gatherer = GraphProvenanceGatherer()
            return gatherer(self._machine_graph, self._application_graph)

    def _execute_placements_provenance_gatherer(self):
        """
        Runs, times and log the PlacementsProvenanceGatherer if requested

        :rtype: list(ProvenanceDataItem)
        """
        with FecTimer("Execute Placements Provenance Gatherer") as timer:
            if timer.skip_if_cfg_false("Reports", "read_provenance_data"):
                return []
            if timer.skip_if_virtual_board():
                return []
            gatherer = PlacementsProvenanceGatherer()
            return gatherer(self._txrx, self._placements)

    def _execute_router_provenance_gatherer(self):
        """
        Runs, times and log the RouterProvenanceGatherer if requested

        :rtype: list(ProvenanceDataItem)
        """
        with FecTimer("Execute Router Provenance Gatherer") as timer:
            if timer.skip_if_cfg_false("Reports", "read_provenance_data"):
                return []
            if timer.skip_if_virtual_board():
                return []
            gatherer = RouterProvenanceGatherer()
            provenance_data_objects = None
            return gatherer(
                self._txrx, self._machine, self._router_tables,
                provenance_data_objects, self._extra_monitor_vertices,
                self._placements)

    def _execute_Profile_data_gatherer(self):
        """
        Runs, times and logs the ProfileDataGatherer if requested
        """
        with FecTimer("Execute Profile Data Gatherer") as timer:
            if timer.skip_if_cfg_false("Reports", "read_provenance_data"):
                return
            if timer.skip_if_virtual_board():
                return
            gatherer = ProfileDataGatherer()
            gatherer(self._txrx, self._placements)

    def _do_read_provenance(self):
        """
        Runs, times and log the methods that gather provenance

        :rtype: list(ProvenanceDataItem)
        """
        prov_items = list()
        if self._version_provenance is not None:
            prov_items.extend(self._version_provenance)
        prov_items.extend(FecTimer.get_provenance())
        prov_items.extend(self._execute_graph_provenance_gatherer())
        prov_items.extend(self._execute_placements_provenance_gatherer())
        prov_items.extend(self._execute_router_provenance_gatherer())
        self._execute_Profile_data_gatherer()
        return prov_items

    def _report_energy(self, router_provenance_items, run_time):
        """
        Runs, times and logs the energy report if requested

        :param list(ProvenanceDataItem) router_provenance_items:
        :param int run_time: the run duration in milliseconds.
        """
        with FecTimer("Execute energy report") as timer:
            if timer.skip_if_cfg_false("Reports", "write_energy_report"):
                return []

            # TODO runtime is None
            compute_energy_used = ComputeEnergyUsed()
            power_used = compute_energy_used(
                self._placements, self._machine, self._board_version,
                router_provenance_items, run_time,
                self._buffer_manager, self._mapping_time, self._load_time,
                self._execute_time, self._dsg_time, self._extraction_time,
                self._spalloc_server, self._remote_spinnaker_url,
                self._machine_allocation_controller)

            energy_prov_reporter = EnergyProvenanceReporter()
            prov_items = energy_prov_reporter(power_used, self._placements)

            # create energy reporter
            energy_reporter = EnergyReport(
                get_config_int("Machine", "version"), self._spalloc_server,
                self._remote_spinnaker_url)

            # run energy report
            energy_reporter.write_energy_report(
                self._placements, self._machine,
                self._current_run_timesteps,
                self._buffer_manager, power_used)

            return prov_items

    def _do_provenance_reports(self, prov_items):
        """
        Can be extended to add more provance reports

        :param list(ProvenanceDataItem) prov_items:
        """
        self._report_provenance(prov_items)

    def _report_provenance(self, prov_items):
        """
        Runs, times and logs the writing of provenance

        :param list(ProvenanceDataItem) prov_items:
        """
        with FecTimer("Write Provenance") as timer:
            FecTimer.clear_provenance()
            self._version_provenance = list()
            if timer.skip_if_cfg_false("Reports", "write_provenance_data"):
                return
            self._write_provenance(prov_items)

    def _execute_clear_io_buf(self, n_machine_time_steps):
        """
        Runs, times and logs the ChipIOBufClearer if required

        :param n_machine_time_steps: Number of timesteps run
        :type n_machine_time_steps: int or None
        """
        with FecTimer("Execute Clear IO Buffer") as timer:
            if timer.skip_if_virtual_board():
                return
            if timer.skip_if_value_is_none(
                    n_machine_time_steps, "n_machine_time_steps"):
                return
            # TODO Why check empty_graph is always false??
            if timer.skip_if_cfg_false("Reports", "clear_iobuf_during_run"):
                return
            clearer = ChipIOBufClearer()
            clearer(self._txrx, self._executable_types)

    def _execute_runtime_update(self, n_sync_steps):
        """
        Runs, times and logs the runtime updater if required

        :param int n_sync_steps:
            The number of timesteps between synchronisations
        """
        with FecTimer("Execute Runtime Update") as timer:
            if timer.skip_if_virtual_board():
                return
            if (ExecutableType.USES_SIMULATION_INTERFACE in
                    self._executable_types):
                updater = ChipRuntimeUpdater()
                updater(self._txrx,  self._app_id, self._executable_types,
                        self._current_run_timesteps,
                        self._first_machine_time_step, n_sync_steps)
            else:
                timer.skip("No Simulation Interface used")

    def _execute_create_database_interface(self, run_time, graph_changed):
        """
        Runs, times and logs Database Interface Creater

        Sets the _database_file_path data object

        :param int run_time: the run duration in milliseconds.
        :param bool graph_changed: Flag to say the graph changed,
        """
        with FecTimer("Execute Create Database Interface") as timer:
            if not self._has_ran or graph_changed:
                interface_maker = DatabaseInterface()
                # Used to used compressed routing tables if available on host
                # TODO consider not saving router tabes.
                _, self._database_file_path = interface_maker(
                    self._machine_graph, self._tags, run_time, self._machine,
                    self._max_run_time_steps, self._placements,
                    self._routing_infos, self._router_tables,
                    self._application_graph)
            else:
                timer.skip("already run and no graph change")

    def _execute_create_notifiaction_protocol(self):
        """
        Runs, times and logs the creation of the Notification Protocol

        Sets the notification_interface data object
        """
        with FecTimer("Execute Create Notification Protocol"):
            creator = CreateNotificationProtocol()
            self._notification_interface = creator(
                self._database_socket_addresses, self._database_file_path)

    def _execute_runner(self, n_sync_steps, run_time):
        """
        Runs, times and logs the ApplicationRunner

        :param int n_sync_steps:
            The number of timesteps between synchronisations
        :param int run_time: the run duration in milliseconds.
        :return:
        """
        with FecTimer("Execute Runner") as timer:
            if timer.skip_if_virtual_board():
                return
            runner = ApplicationRunner()
            # Don't timeout if a stepped mode is in operation
            if n_sync_steps:
                time_threshold = None
            else:
                time_threshold = get_config_int(
                    "Machine", "post_simulation_overrun_before_error")
            self._no_sync_changes = runner(
                self._buffer_manager, self._notification_interface,
                self._executable_types, self._app_id, self._txrx, run_time,
                self._no_sync_changes, time_threshold, self._machine,
                self._run_until_complete)

    def _execute_extract_iobuff(self):
        """
        Runs, times and logs the ChipIOBufExtractor if required
        """
        with FecTimer("Execute Extract IO Buff") as timer:
            if timer.skip_if_virtual_board():
                return
            if timer.skip_if_cfg_false(
                    "Reports", "extract_iobuf_during_run"):
                return
            if timer.skip_if_cfg_false(
                    "Reports", "extract_iobuf"):
                return
            iobuf_extractor = ChipIOBufExtractor()
            # ErrorMessages, WarnMessages output ignored as never used!
            iobuf_extractor(
                self._txrx, self._executable_targets, self._executable_finder)

    def _execute_buffer_extractor(self):
        """
        Runs, times and logs the BufferExtractor if required
        """
        with FecTimer("Execute Buffer Extractor") as timer:
            if timer.skip_if_virtual_board():
                return
            buffer_extractor = BufferExtractor()
            buffer_extractor(
                self._machine_graph, self._placements,
                self._buffer_manager)

    def _do_extract_from_machine(self, run_time):
        """
        Runs, times and logs the steps to extract data from the machine

        :param run_time: the run duration in milliseconds.
        :type run_time: int or None
        """
        self._execute_extract_iobuff()
        self._execute_buffer_extractor()
        # FinaliseTimingData never needed as just pushed self._ to inputs
        prov_items = self._do_read_provenance()
        self._execute_time += convert_time_diff_to_total_milliseconds(
            self._run_timer.take_sample())
        prov_items.extend(self._report_energy(prov_items, run_time))
        self._do_provenance_reports(prov_items)

    def _do_run(self, n_machine_time_steps, graph_changed, n_sync_steps):
        """
        Runs, times and logs the do run steps.

        :param n_machine_time_steps: Number of timesteps run
        :type n_machine_time_steps: int or None
        :param int n_sync_steps:
            The number of timesteps between synchronisations
        :param bool graph_changed: Flag to say the graph changed,
        """
        # TODO virtual board
        self._run_timer = Timer()
        self._run_timer.start_timing()
        run_time = None
        if n_machine_time_steps is not None:
            run_time = n_machine_time_steps * self.machine_time_step_ms
        self._first_machine_time_step = self._current_run_timesteps
        self._current_run_timesteps = \
            self._calculate_number_of_machine_time_steps(n_machine_time_steps)

        # TODO is there a better way to get update_buffer to run
        provide_injectables(self)
        do_injection(self)

        self._execute_sdram_usage_report_per_chip()
        self._execute_dsg_region_reloader(graph_changed)
        self._execute_clear_io_buf(n_machine_time_steps)
        self._execute_runtime_update(n_sync_steps)
        self._execute_create_database_interface(run_time, graph_changed)
        self._execute_create_notifiaction_protocol()
        self._execute_runner(n_sync_steps, run_time)
        if n_machine_time_steps is not None or self._run_until_complete:
            self._do_extract_from_machine(run_time)
        self._has_reset_last = False
        self._has_ran = True
        # reset at the end of each do_run cycle
        self._first_machine_time_step = None
        clear_injectables()

    def _write_provenance(self, provenance_data_items):
        """ Write provenance to disk.

        :param list(ProvenanceDataItem) provenance_data_items:
        """
        provenance_format = get_config_str("Reports", "provenance_format")
        if provenance_format == "xml":
            writer = ProvenanceXMLWriter()
        elif provenance_format == "json":
            writer = ProvenanceJSONWriter()
        elif provenance_format == "sql":
            writer = ProvenanceSQLWriter()
        else:
            if provenance_format != "auto":
                logger.warning(
                    f"Unexpected provenance_format {provenance_format}")
            if len(provenance_data_items) < PROVENANCE_TYPE_CUTOFF:
                writer = ProvenanceXMLWriter()
            else:
                writer = ProvenanceSQLWriter()
        writer(provenance_data_items, self._provenance_file_path)

    def _recover_from_error(self, exception, exc_info, executable_targets):
        """
        :param Exception exception:
        :param tuple(type,Exception,traceback) exc_info:
        :param ExecutableTargets executable_targets:
        """
        # if exception has an exception, print to system
        logger.error("An error has occurred during simulation")
        # Print the detail including the traceback
        real_exception = exception
        logger.error(exception, exc_info=exc_info)

        logger.info("\n\nAttempting to extract data\n\n")

        # Extract router provenance
        prov_items = list()
        try:
            router_provenance = RouterProvenanceGatherer()
            new_prov_items = router_provenance(
                transceiver=self._txrx, machine=self._machine,
                router_tables=self._router_tables,
                provenance_data_objects=prov_items,
                extra_monitor_vertices=self._extra_monitor_vertices,
                placements=self._placements)
            if new_prov_items is not None:
                prov_items.extend(new_prov_items)
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
        for (x, y, p), core_info in unsuccessful_cores.items():
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
            for (x, y, p), core_info in unsuccessful_cores.items()
            if (core_info.state != CPUState.RUN_TIME_EXCEPTION and
                core_info.state != CPUState.WATCHDOG)]

        # If there are any cores that are not in RTE, extract data from them
        if (non_rte_cores and
                ExecutableType.USES_SIMULATION_INTERFACE in
                self._executable_types):
            non_rte_core_subsets = CoreSubsets()
            for (x, y, p) in non_rte_cores:
                non_rte_core_subsets.add_processor(x, y, p)

            # Attempt to force the cores to write provenance and exit
            try:
                updater = ChipProvenanceUpdater()
                updater(self._txrx, self._app_id, non_rte_core_subsets)
            except Exception:
                logger.exception("Could not update provenance on chip")

            # Extract any written provenance data
            try:
                finished_cores = self._txrx.get_cores_in_state(
                    non_rte_core_subsets, CPUState.FINISHED)
                finished_placements = Placements()
                for (x, y, p) in finished_cores:
                    finished_placements.add_placement(
                        self._placements.get_placement_on_processor(x, y, p))
                extractor = PlacementsProvenanceGatherer()
                new_prov_items = extractor(self._txrx, finished_placements)
                if new_prov_items is not None:
                    prov_items.extend(new_prov_items)
            except Exception:
                logger.exception("Could not read provenance")

        # Finish getting the provenance
        prov_items.extend(FecTimer.get_provenance())
        FecTimer.clear_provenance()
        self._write_provenance(prov_items)

        # Read IOBUF where possible (that should be everywhere)
        iobuf = IOBufExtractor(
            self._txrx, executable_targets, self._executable_finder)
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

    def _detect_if_graph_has_changed(self, reset_flags=True):
        """ Iterates though the original graphs looking for changes.

        :param bool reset_flags:
        :return: mapping_changed, data_changed
        :rtype: tuple(bool, bool)
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
    def has_ran(self):
        """ Whether the simulation has executed anything at all.

        :rtype: bool
        """
        return self._has_ran

    @property
    def machine(self):
        """ The python machine description object.

         :rtype: ~spinn_machine.Machine
         """
        return self._get_machine()

    @property
    def no_machine_time_steps(self):
        """ The number of machine time steps.

        :rtype: int
        """
        return self._current_run_timesteps

    @property
    def machine_graph(self):
        """
        Returns a protected view of the machine_graph
        :rtype: ~pacman.model.graphs.machine.MachineGraph
        """
        return MachineGraphView(self._machine_graph)

    @property
    def original_machine_graph(self):
        """
        :rtype: ~pacman.model.graphs.machine.MachineGraph
        """
        return self._original_machine_graph

    @property
    def original_application_graph(self):
        """
        :rtype: ~pacman.model.graphs.application.ApplicationGraph
        """
        return self._original_application_graph

    @property
    def application_graph(self):
        """ The protected view of the application graph used to derive the
            runtime machine configuration.

        :rtype: ~pacman.model.graphs.application.ApplicationGraph
        """
        return ApplicationGraphView(self._application_graph)

    @property
    def routing_infos(self):
        """
        :rtype: ~pacman.model.routing_info.RoutingInfo
        """
        return self._routing_infos

    @property
    def fixed_routes(self):
        """
        :rtype: dict(tuple(int,int),~spinn_machine.FixedRouteEntry)
        """
        return self._fixed_routes

    @property
    def placements(self):
        """ Where machine vertices are placed on the machine.

        :rtype: ~pacman.model.placements.Placements
        """
        return self._placements

    @property
    def transceiver(self):
        """ How to talk to the machine.

        :rtype: ~spinnman.transceiver.Transceiver
        """
        return self._txrx

    @property
    def tags(self):
        """
        :rtype: ~pacman.model.tags.Tags
        """
        return self._tags

    @property
    def buffer_manager(self):
        """ The buffer manager being used for loading/extracting buffers

        :rtype:
            ~spinn_front_end_common.interface.buffer_management.BufferManager
        """
        return self._buffer_manager

    @property
    def none_labelled_edge_count(self):
        """ The number of times edges have not been labelled.

        :rtype: int
        """
        return self._none_labelled_edge_count

    def increment_none_labelled_edge_count(self):
        """ Increment the number of new edges which have not been labelled.
        """
        self._none_labelled_edge_count += 1

    @property
    def use_virtual_board(self):
        """ True if this run is using a virtual machine

        :rtype: bool
        """
        return self._use_virtual_board

    def get_current_time(self):
        """ Get the current simulation time.

        :rtype: float
        """
        if self._has_ran:
            return self._current_run_timesteps * self.machine_time_step_ms
        return 0.0

    def __repr__(self):
        return "general front end instance for machine {}".format(
            self._hostname)

    def add_application_vertex(self, vertex):
        """
        :param ~pacman.model.graphs.application.ApplicationVertex vertex:
            the vertex to add to the graph
        :raises ConfigurationException: when both graphs contain vertices
        :raises PacmanConfigurationException:
            If there is an attempt to add the same vertex more than once
        """
        if self._original_machine_graph.n_vertices:
            raise ConfigurationException(
                "Cannot add vertices to both the machine and application"
                " graphs")
        self._original_application_graph.add_vertex(vertex)
        self._vertices_or_edges_added = True

    def add_machine_vertex(self, vertex):
        """
        :param ~pacman.model.graphs.machine.MachineVertex vertex:
            the vertex to add to the graph
        :raises ConfigurationException: when both graphs contain vertices
        :raises PacmanConfigurationException:
            If there is an attempt to add the same vertex more than once
        """
        # check that there's no application vertices added so far
        if self._original_application_graph.n_vertices:
            raise ConfigurationException(
                "Cannot add vertices to both the machine and application"
                " graphs")
        self._original_machine_graph.add_vertex(vertex)
        self._vertices_or_edges_added = True

    def add_application_edge(self, edge_to_add, partition_identifier):
        """
        :param ~pacman.model.graphs.application.ApplicationEdge edge_to_add:
            the edge to add to the graph
        :param str partition_identifier:
            the partition identifier for the outgoing edge partition
        """
        self._original_application_graph.add_edge(
            edge_to_add, partition_identifier)
        self._vertices_or_edges_added = True

    def add_machine_edge(self, edge, partition_id):
        """
        :param ~pacman.model.graphs.machine.MachineEdge edge:
            the edge to add to the graph
        :param str partition_id:
            the partition identifier for the outgoing edge partition
        """
        self._original_machine_graph.add_edge(edge, partition_id)
        self._vertices_or_edges_added = True

    def _shutdown(
            self, turn_off_machine=None, clear_routing_tables=None,
            clear_tags=None):
        """
        :param bool turn_off_machine:
        :param bool clear_routing_tables:
        :param bool clear_tags:
        """
        self._status = Simulator_Status.SHUTDOWN

        if turn_off_machine is None:
            turn_off_machine = get_config_bool(
                "Machine", "turn_off_machine")

        if clear_routing_tables is None:
            clear_routing_tables = get_config_bool(
                "Machine", "clear_routing_tables")

        if clear_tags is None:
            clear_tags = get_config_bool("Machine", "clear_tags")

        if self._txrx is not None:
            # if stopping on machine, clear IP tags and routing table
            self.__clear(clear_tags, clear_routing_tables)

        # Fully stop the application
        self.__stop_app()

        # stop the transceiver and allocation controller
        self.__close_transceiver(turn_off_machine)
        self.__close_allocation_controller()

        try:
            if self._notification_interface:
                self._notification_interface.close()
                self._notification_interface = None
        except Exception:
            logger.exception(
                "Error when closing Notifications")

    def __clear(self, clear_tags, clear_routing_tables):
        """
        :param bool clear_tags:
        :param bool clear_routing_tables:
        """
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
        """
        :param bool turn_off_machine:
        """
        if self._txrx is not None:
            if turn_off_machine:
                logger.info("Turning off machine")

            self._txrx.close(power_off_machine=turn_off_machine)
            self._txrx = None

    def __close_allocation_controller(self):
        if self._machine_allocation_controller is not None:
            self._machine_allocation_controller.close()
            self._machine_allocation_controller = None

    def stop(self, turn_off_machine=None,  # pylint: disable=arguments-differ
             clear_routing_tables=None, clear_tags=None):
        """
        End running of the simulation.

        :param bool turn_off_machine:
            decides if the machine should be powered down after running the
            execution. Note that this powers down all boards connected to the
            BMP connections given to the transceiver
        :param bool clear_routing_tables: informs the tool chain if it
            should turn off the clearing of the routing tables
        :param bool clear_tags: informs the tool chain if it should clear the
            tags off the machine at stop
        """
        if self._status in [Simulator_Status.SHUTDOWN]:
            raise ConfigurationException("Simulator has already been shutdown")
        self._status = Simulator_Status.SHUTDOWN

        # Keep track of any exception to be re-raised
        exn = None

        # If we have run forever, stop the binaries

        if (self._has_ran and self._current_run_timesteps is None and
                not self._use_virtual_board and not self._run_until_complete):
            self._do_stop_workflow()
            # TODO recover from errors?
            # self._recover_from_error(
            # e, exc_info[2], executor.get_item("ExecutableTargets"))

        # shut down the machine properly
        self._shutdown(turn_off_machine, clear_routing_tables, clear_tags)

        if exn is not None:
            self.write_errored_file()
            raise exn  # pylint: disable=raising-bad-type
        self.write_finished_file()

    def _execute_application_finisher(self):
        with FecTimer("Execute Application Finisher"):
            finisher = ApplicationFinisher()
            finisher(self._app_id, self._txrx, self._executable_types)

    def _do_stop_workflow(self):
        """
        :rtype: ~.PACMANAlgorithmExecutor
        """
        self._execute_application_finisher()
        # TODO is self._current_run_timesteps just 0
        self._do_extract_from_machine(self._current_run_timesteps)

    def add_socket_address(self, socket_address):
        """ Add the address of a socket used in the run notification protocol.

        :param ~spinn_utilities.socket_address.SocketAddress socket_address:
            The address of the database socket
        """
        self._database_socket_addresses.add(socket_address)

    @property
    def has_reset_last(self):
        return self._has_reset_last

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
        take_into_account_chip_power_monitor = get_config_bool(
            "Reports", "write_energy_report")
        if take_into_account_chip_power_monitor:
            cores -= self._machine.n_chips
        take_into_account_extra_monitor_cores = (get_config_bool(
            "Machine", "enable_advanced_monitor_support") or
                get_config_bool("Machine", "enable_reinjection"))
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
        if self._status is not Simulator_Status.IN_RUN:
            return
        with self._state_condition:
            self._status = Simulator_Status.STOP_REQUESTED
            self._state_condition.notify_all()

    def continue_simulation(self):
        """ Continue a simulation that has been started in stepped mode
        """
        if self._no_sync_changes % 2 == 0:
            sync_signal = Signal.SYNC0
        else:
            sync_signal = Signal.SYNC1
        self._txrx.send_signal(self._app_id, sync_signal)
        self._no_sync_changes += 1

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

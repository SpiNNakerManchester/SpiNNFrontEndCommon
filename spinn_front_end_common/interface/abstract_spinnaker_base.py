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
from pacman.executor import PACMANAlgorithmExecutor
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
    get_config_bool, get_config_int, get_config_str, get_config_str_list,
    set_config)
from spinn_front_end_common.abstract_models import (
    AbstractSendMeMulticastCommandsVertex,
    AbstractVertexWithEdgeToDependentVertices, AbstractChangableAfterRun,
    AbstractCanReset)
from spinn_front_end_common.interface.interface_functions import (
    ApplicationRunner,  BufferExtractor, BufferManagerCreator,
    ChipIOBufClearer, ChipIOBufExtractor,
    ChipProvenanceUpdater, ChipRuntimeUpdater, ComputeEnergyUsed,
    CreateNotificationProtocol, DatabaseInterface,
    DSGRegionReloader, EdgeToNKeysMapper, EnergyProvenanceReporter,
    GraphBinaryGatherer, GraphDataSpecificationWriter,
    GraphMeasurer, GraphProvenanceGatherer,  HostBasedBitFieldRouterCompressor,
    HostExecuteDataSpecification, HBPAllocator, HBPMaxMachineGenerator,
    InsertChipPowerMonitorsToGraphs,
    InsertEdgesToExtraMonitorFunctionality, InsertExtraMonitorVerticesToGraphs,
    interface_xml, LoadExecutableImages, LoadFixedRoutes,
    LocalTDMABuilder, LocateExecutableStartType, MachineGenerator,
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
    RoutingTableFromMachineReport, TagsFromMachineReport, report_xml,
    WriteJsonMachine, WriteJsonPartitionNKeysMap, WriteJsonPlacements,
    WriteJsonRoutingTables)
from spinn_front_end_common.utilities.utility_objs import (
    ExecutableType, ProvenanceDataItem)
from spinn_front_end_common.utility_models import (
    CommandSender, CommandSenderMachineVertex,
    DataSpeedUpPacketGatherMachineVertex)
from spinn_front_end_common.utilities import IOBufExtractor
from spinn_front_end_common.interface.java_caller import JavaCaller
from spinn_front_end_common.interface.config_handler import ConfigHandler
from spinn_front_end_common.interface.provenance import (
    PacmanProvenanceExtractor)
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

#: Number of cores to be used when using a Virtual Machine and not specified
DEFAULT_N_VIRTUAL_CORES = 16

#: The minimum time a board is kept in the off state, in seconds
MINIMUM_OFF_STATE_TIME = 20

# 0-15 are reserved for system use (per lplana)
ALANS_DEFAULT_RANDOM_APP_ID = 16

# Number of provenace items before auto changes to sql format
PROVENANCE_TYPE_CUTOFF = 20000

_PREALLOC_NAME = 'PreAllocatedResources'


class AbstractSpinnakerBase(ConfigHandler):
    """ Main interface into the tools logic flow.
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

        # boolean for empty graphs
        "_empty_graphs",

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
        "_status",

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

        # Set when run_until_complete is specified by the user
        "_run_until_complete",

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
        # the timer used to log the execute time
        "_run_timer",

        # time takes to do data generation
        "_dsg_time",

        # time taken by the front end extracting things
        "_extraction_time",

        # Version information from the front end
        "_front_end_versions",

        "_last_except_hook",

        "_vertices_or_edges_added",

        # Version provenance
        "_version_provenance",

        # New for no exactor
        "_database_file_path",
        "_executable_targets",
        "_board_version",
        "_extra_monitor_vertices",
        "_first_machine_time_step",
        "_machine_partition_n_keys_map",
        "_run_until_time_step",
        "_system_multicast_router_timeout_keys",
        "_dsg_targets",
        "_region_sizes",
        "_vertex_to_ethernet_connected_chip_mapping",
        "_data_in_multicast_routing_tables",
        "_data_in_multicast_key_to_chip_map",
        "_plan_n_timesteps",
        "_compressor_provenance",
        "_routing_table_by_partition",
        "_multicast_routes_loaded",
        "_extra_monitor_to_chip_mapping",
        "_max_machine",
        "_n_chips_needed",
    ]

    def __init__(
            self, executable_finder, graph_label=None,
            database_socket_addresses=None, extra_algorithm_xml_paths=None,
            n_chips_required=None, n_boards_required=None,
            front_end_versions=None):
        """
        :param executable_finder: How to find APLX files to deploy to SpiNNaker
        :type executable_finder:
            ~spinn_utilities.executable_finder.ExecutableFinder
        :param str graph_label: A label for the overall application graph
        :param database_socket_addresses: How to talk to notification databases
        :type database_socket_addresses:
            iterable(~spinn_utilities.socket_address.SocketAddress) or None
        :param iterable(str) extra_algorithm_xml_paths:
            Where to load definitions of extra algorithms from
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
        self._original_application_graph = ApplicationGraph(
            label=self._graph_label)
        self._original_machine_graph = MachineGraph(
            label=self._graph_label,
            application_graph=self._original_application_graph)
        self._empty_graphs = False

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
        self._last_run_outputs = dict()
        self._last_run_tokens = dict()
        self._pacman_provenance = PacmanProvenanceExtractor()
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

        # holder for timing and running related values
        self._run_until_complete = False
        self._has_ran = False
        self._status = Simulator_Status.INIT
        self._state_condition = Condition()
        self._has_reset_last = False
        self._n_calls_to_run = 1
        self._current_run_timesteps = 0
        self._no_sync_changes = 0
        self._max_run_time_steps = None
        self._no_machine_time_steps = None
        self._minimum_auto_time_steps = get_config_int(
                "Buffers", "minimum_auto_time_steps")

        self._app_id = get_config_int("Machine", "app_id")

        # folders
        self._pacman_executor_provenance_path = None
        self._set_up_output_folders(self._n_calls_to_run)

        # timing provenance elements
        self._do_timings = get_config_bool(
            "Reports", "write_algorithm_timings")
        self._print_timings = get_config_bool(
            "Reports", "display_algorithm_timings")
        self._provenance_format = get_config_str(
            "Reports", "provenance_format")
        if self._provenance_format not in ["xml", "json", "sql", "auto"]:
            raise Exception("Unknown provenance format: {}".format(
                self._provenance_format))

        # Setup for signal handling
        self._raise_keyboard_interrupt = False

        globals_variables.set_simulator(self)

        # Front End version information
        self._front_end_versions = front_end_versions

        self._last_except_hook = sys.excepthook
        self._vertices_or_edges_added = False
        self._database_file_path = None
        self._executable_targets = None
        self._board_version = None
        self._extra_monitor_vertices = None
        self._first_machine_time_step = None
        self._machine_partition_n_keys_map = None
        self._run_until_time_step = None
        self._system_multicast_router_timeout_keys = None
        self._dsg_targets = None
        self._region_sizes = None
        self._vertex_to_ethernet_connected_chip_mapping = None
        self._data_in_multicast_routing_tables = None
        self._data_in_multicast_key_to_chip_map = None
        self._plan_n_timesteps = None
        self._compressor_provenance = None
        self._routing_table_by_partition = None
        self._multicast_routes_loaded = False
        self._extra_monitor_to_chip_mapping = None
        self._max_machine = None
        self._n_chips_needed = None

        FecTimer.setup(self)

        # Safety in case a previous run left a bad state
        clear_injectables()

    def __getitem__(self, item):
        """
        To allow ASB to work as the injector

        :param str item: key to object wanted
        :return: Object asked for
        """
        value = self._unchecked_gettiem(item)
        if value or value == 0:
            return value
        if value is None:
            raise KeyError(f"Item {item} is currently not set")
        else:
            raise KeyError(f"Unexpected Item {item}")

    def __contains__(self, item):
        if self._unchecked_gettiem(item) is not None:
            return True
        return False

    def items(self):
        results = []
        for key in ["APPID", "ApplicationGraph", "DataInMulticastKeyToChipMap",
                    "DataInMulticastRoutingTables", "DataNTimeSteps",
                    "ExtendedMachine", "FirstMachineTimeStep", "MachineGraph",
                    "MachinePartitionNKeysMap", "Placements", "RoutingInfos",
                    "RunUntilTimeSteps", "SystemMulticastRouterTimeoutKeys",
                    "Tags"]:
            item = self._unchecked_gettiem(key)
            # Skip None and False but not 0
            if item or item == 0:
                results.append((key, item))
        return results

    def _unchecked_gettiem(self, item):
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
            return self._run_until_time_step
        if item == "SystemMulticastRouterTimeoutKeys":
            return self._system_multicast_router_timeout_keys
        if item == "Tags":
            return self._tags
        return False

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

    def update_extra_mapping_inputs(self, extra_mapping_inputs):
        """ Supply extra inputs to the mapping algorithms. Mappings are from\
            known names (the logical type names) to the values to bind to them.

        :param dict(str,any) extra_inputs: The additional inputs to provide
        """
        if self.has_ran:
            raise ConfigurationException(
                "Changing mapping inputs is not supported after run")
        if extra_mapping_inputs is not None:
            self._extra_mapping_inputs.update(extra_mapping_inputs)

    def update_extra_inputs(self, extra_inputs):
        """ Supply extra inputs to the runtime algorithms. Mappings are from\
            known names (the logical type names) to the values to bind to them.

        :param dict(str,any) extra_inputs: The additional inputs to provide
        """
        if self.has_ran:
            raise ConfigurationException(
                "Changing inputs is not supported after run")
        if extra_inputs is not None:
            self._extra_inputs.update(extra_inputs)

    def extend_extra_mapping_algorithms(self, extra_mapping_algorithms):
        """ Add custom mapping algorithms to the end of the sequence of \
            mapping algorithms to be run.

        :param list(str) extra_mapping_algorithms: Algorithms to add
        """
        if self.has_ran:
            raise ConfigurationException(
                "Changing algorithms is not supported after run")
        if extra_mapping_algorithms is not None:
            self._extra_mapping_algorithms.extend(extra_mapping_algorithms)

    def prepend_extra_pre_run_algorithms(self, extra_pre_run_algorithms):
        """ Add custom pre-execution algorithms to the front of the sequence \
            of algorithms to be run.

        :param list(str) extra_pre_run_algorithms: Algorithms to add
        """
        if self.has_ran:
            raise ConfigurationException(
                "Changing algorithms is not supported after run")
        if extra_pre_run_algorithms is not None:
            self._extra_pre_run_algorithms[0:0] = extra_pre_run_algorithms

    def extend_extra_post_run_algorithms(self, extra_post_run_algorithms):
        """ Add custom post-execution algorithms to the sequence of \
            such algorithms to be run.

        :param list(str) extra_post_run_algorithms: Algorithms to add
        """
        if self.has_ran:
            raise ConfigurationException(
                "Changing algorithms is not supported after run")
        if extra_post_run_algorithms is not None:
            self._extra_post_run_algorithms.extend(extra_post_run_algorithms)

    def extend_extra_load_algorithms(self, extra_load_algorithms):
        """ Add custom data-loading algorithms to the sequence of \
            such algorithms to be run.

        :param list(str) extra_load_algorithms: Algorithms to add
        """
        if self.has_ran:
            raise ConfigurationException(
                "Changing algorithms is not supported after run")
        if extra_load_algorithms is not None:
            self._extra_load_algorithms.extend(extra_load_algorithms)

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

            # change number of resets as loading the binary again resets the
            # sync to 0
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
                self._machine = None
                self._buffer_manager = None
                self._java_caller = None
                if self._txrx is not None:
                    self._txrx.close()
                    self._app_id = None
                if self._machine_allocation_controller is not None:
                    self._machine_allocation_controller.close()
                self._max_run_time_steps = None
                self._n_chips_needed = None

            if self._machine is None:
                self._get_machine(total_run_time, n_machine_time_steps)
            self._do_mapping(run_time, total_run_time)

        # Check if anything has per-timestep SDRAM usage
        provide_injectables(self._mapping_outputs)
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
            self._do_data_generation(self._max_run_time_steps)

            self._do_load(graph_changed, data_changed)

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
            self._no_machine_time_steps = total_timesteps
            return total_timesteps

        self._no_machine_time_steps = None
        return None

    def _run_algorithms(
            self, inputs, algorithms, outputs, tokens, required_tokens,
            provenance_name, optional_algorithms=None):
        """ Runs getting a SpiNNaker machine logic

        :param dict(str,any) inputs: the inputs
        :param list(str) algorithms: algorithms to call
        :param list(str) outputs: outputs to get
        :param list(str) tokens: The tokens to start with
        :param list(str) required_tokens: The tokens that must be generated
        :param str provenance_name: the name for provenance
        :param list(str) optional_algorithms: optional algorithms to use
        :return: the executor that did the running of the algorithms
        :rtype: ~.PACMANAlgorithmExecutor
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
        except Exception as e:
            self._txrx = executor.get_item("Transceiver")
            self._machine_allocation_controller = executor.get_item(
                "MachineAllocationController")
            try:
                TagsFromMachineReport()(self._txrx)
            except Exception as e2:
                logger.warning(
                    "problem with TagsFromMachineReport {}".format(e2),
                    exc_info=True)
            try:
                self._shutdown()
            except Exception as e3:
                logger.warning("problem when shutting down {}".format(e3),
                               exc_info=True)
            self.write_errored_file()
            self.write_finished_file()
            raise e

    def _execute_get_virtual_machine(self):
        with FecTimer("Execute Virtual Machine Generator") as executor:
            if executor.skip_if_value_already_set(self._machine, "machine"):
                return
            if executor.skip_if_value_false(
                    self._use_virtual_board, "use_virtual_board"):
                return
            generator = VirtualMachineGenerator()
            # TODO fix params
            self._machine = generator(get_config_int("Machine", "version"))

    def _execute_allocator(self, total_run_time):
        with FecTimer("Execute Allocator") as executor:
            self._max_machine = None
            if executor.skip_if_value_already_set(self._machine, "machine"):
                return None
            if executor.skip_if_value_not_none(self._hostname, "hostname"):
                return None
            if self._n_chips_needed:
                # TODO check needed vs required
                n_chips_required = self._n_chips_needed
            else:
                n_chips_required = self._n_chips_required
            if n_chips_required is None and self._n_boards_required is None:
                executor.skip("Size of required machine not yet known")
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
        with FecTimer("Execute Machine Generator") as executor:
            if executor.skip_if_value_already_set(self._machine, "machine"):
                return
            if executor.skip_if_value_true(
                    self._use_virtual_board, "use_virtual_machine"):
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
                executor.skip("Size of required machine not yet known")
                return

            generator = MachineGenerator()
            self._machine, self._txrx = generator(
                self._hostname, bmp_details, self._board_version,
                auto_detect_bmp, scamp_connection_data, boot_port_num,
                reset_machine)
            return self._machine

    def _execute_get_max_machine(self, total_run_time):
        with FecTimer("Execute Max Machine Generator") as executor:
            if executor.skip_if_value_already_set(self._machine, "machine"):
                return self._machine

            if self._spalloc_server:
                generator = SpallocMaxMachineGenerator()
                # TODO fix params
                self._max_machine = generator(
                    self._spalloc_server,
                    max_machine_core_reduction=get_config_int(
                        "Machine", "max_machine_core_reduction"))

            elif self._remote_spinnaker_url:
                generator = HBPMaxMachineGenerator()
                self._max_machine = generator(
                    self._remote_spinnaker_url, total_run_time,
                    get_config_int("Machine", "max_machine_core_reduction"))

            else:
                raise NotImplementedError("No machine generataion possible")

    def _get_machine(self, total_run_time=0.0, n_machine_time_steps=None):
        if get_config_bool("Buffers", "use_auto_pause_and_resume"):
            self._plan_n_timesteps = self._minimum_auto_time_steps
        else:
            self._plan_n_timesteps = n_machine_time_steps

        if self._app_id is None:
            if self._txrx is None:
                self._app_id = ALANS_DEFAULT_RANDOM_APP_ID
            else:
                self._app_id = self._txrx.app_id_tracker.get_new_id()

        self._execute_get_virtual_machine()
        allocator_data = self._execute_allocator(total_run_time)
        self._execute_machine_generator(allocator_data)
        self._execute_get_max_machine(total_run_time)
        if self._machine:
            return self._machine
        else:
            return self._max_machine

    def _get_machineX(self, total_run_time=0.0, n_machine_time_steps=None):
        """
        :param float total_run_time:
        :param n_machine_time_steps:
        :type n_machine_time_steps: int or None
        :rtype: ~spinn_machine.Machine
        :raises ConfigurationException:
        """
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
        """
        :param n_machine_time_steps:
        :type n_machine_time_steps: int or None
        :param float total_run_time:
        """
        inputs, algorithms = self._get_machine_common(
            n_machine_time_steps, total_run_time)
        outputs = list()
        inputs["IPAddress"] = self._hostname
        inputs["BMPDetails"] = get_config_str("Machine", "bmp_names")
        inputs["AutoDetectBMPFlag"] = get_config_bool(
            "Machine", "auto_detect_bmp")
        inputs["ScampConnectionData"] = get_config_str(
            "Machine", "scamp_connections_data")
        inputs[_PREALLOC_NAME] = PreAllocatedResourceContainer()
        algorithms.append("MachineGenerator")

        outputs.append("Machine")
        outputs.append("Transceiver")

        executor = self._run_algorithms(
            inputs, algorithms, outputs, [], [], "machine_generation")
        self._machine = executor.get_item("Machine")
        self._txrx = executor.get_item("Transceiver")
        self._machine_outputs = executor.get_items()
        self._machine_tokens = executor.get_completed_tokens()
        # new for no executor
        self._board_version = executor.get_item("BoardVersion")

    def _machine_by_virtual(self, n_machine_time_steps, total_run_time):
        """
        :param n_machine_time_steps:
        :type n_machine_time_steps: int or None
        :param float total_run_time:
        """
        inputs, algorithms = self._get_machine_common(
            n_machine_time_steps, total_run_time)
        outputs = list()

        inputs["IPAddress"] = "virtual"
        inputs["NumberOfBoards"] = get_config_int(
            "Machine", "number_of_boards")
        inputs["BMPDetails"] = None
        inputs["AutoDetectBMPFlag"] = False
        inputs["ScampConnectionData"] = None
        inputs[_PREALLOC_NAME] = PreAllocatedResourceContainer()

        algorithms.append("VirtualMachineGenerator")

        outputs.append("Machine")

        executor = self._run_algorithms(
            inputs, algorithms, outputs, [], [], "machine_generation")
        self._machine_outputs = executor.get_items()
        self._machine_tokens = executor.get_completed_tokens()
        self._machine = executor.get_item("Machine")
        # new for no executor
        self._board_version = executor.get_item("BoardVersion")

    def _machine_by_remote(self, n_machine_time_steps, total_run_time):
        """ Gets a machine when we know one of `self._spalloc_server` or
            `self._remote_spinnaker_url` is defined

        :param n_machine_time_steps:
        :type n_machine_time_steps: int or None
        :param float total_run_time:
        """
        inputs, algorithms = self._get_machine_common(
            n_machine_time_steps, total_run_time)
        outputs = list()

        do_partitioning = self._machine_by_size(inputs, algorithms, outputs)
        inputs[_PREALLOC_NAME] = PreAllocatedResourceContainer()

        # if using spalloc system
        if self._spalloc_server is not None:
            inputs["SpallocServer"] = self._spalloc_server
        else:
            # must be using HBP server system
            inputs["RemoteSpinnakerUrl"] = self._remote_spinnaker_url

        if self._spalloc_server is not None:
            algorithms.append("SpallocAllocator")
        elif self._remote_spinnaker_url is not None:
            algorithms.append("HBPAllocator")

        algorithms.append("MachineGenerator")

        outputs.append("Machine")
        outputs.append("IPAddress")
        outputs.append("Transceiver")
        outputs.append("MachineAllocationController")

        executor = self._run_algorithms(
            inputs, algorithms, outputs, [], [], "machine_generation")

        self._machine_outputs = executor.get_items()
        self._machine_tokens = executor.get_completed_tokens()
        self._machine = executor.get_item("Machine")
        self._ip_address = executor.get_item("IPAddress")
        self._txrx = executor.get_item("Transceiver")
        self._machine_allocation_controller = executor.get_item(
            "MachineAllocationController")

        if do_partitioning:
            self._machine_graph = executor.get_item("MachineGraph")
        # new for no executor
        self._board_version = executor.get_item("BoardVersion")

    def _machine_by_size(self, inputs, algorithms, outputs):
        """ Checks if we can get a remote machine by size of if we have to \
            use a virtual machine to get the size

        Adds the required info to inputs, algorithms, outputs

        :param dict(str,any) inputs: Data to go into executor; will be updated
        :param list(str) algorithms: Algorithms to execute; will be updated
        :param list(str) outputs: Data needed after execution; will be updated
        :return: True if and only if the required steps include partitioning
        :rtype: bool
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
        if self._machine_graph.n_vertices:
            inputs["MachineGraph"] = self._machine_graph
            algorithms.append("GraphMeasurer")
            do_partitioning = False
        # If we are using an allocation server, and we need a virtual
        # board, we need to use the virtual board to get the number of
        # chips to be allocated either by partitioning, or by measuring
        # the graph
        else:
            inputs["ApplicationGraph"] = self._application_graph
            algorithms.extend(get_config_str_list(
                "Mapping", "application_to_machine_graph_algorithms"))
            outputs.append("MachineGraph")
            do_partitioning = True

        # Ok we do need a virtual machine
        if self._spalloc_server is not None:
            algorithms.append("SpallocMaxMachineGenerator")
        else:
            algorithms.append("HBPMaxMachineGenerator")

        return do_partitioning

    def _get_machine_common(self, n_machine_time_steps, total_run_time):
        """
        :param n_machine_time_steps:
        :type n_machine_time_steps: int or None
        :param float total_run_time:
        :return: inputs, algorithms
        :rtype: tuple(dict(str,any), list(str))
        """
        inputs = dict(self._extra_inputs)
        algorithms = list()

        self._create_version_provenance()

        if get_config_bool("Buffers", "use_auto_pause_and_resume"):
            inputs["PlanNTimeSteps"] = self._minimum_auto_time_steps
        else:
            inputs["PlanNTimeSteps"] = n_machine_time_steps

        # Set the total run time
        inputs["TotalRunTime"] = total_run_time
        inputs["MaxMachineCoreReduction"] = get_config_int(
            "Machine", "max_machine_core_reduction")
        inputs["BoardVersion"] = get_config_int(
            "Machine", "version")
        inputs["ResetMachineOnStartupFlag"] = get_config_bool(
            "Machine", "reset_machine_on_startup")
        inputs["BootPortNum"] = get_config_int(
            "Machine", "boot_connection_port_num")

        # add algorithms for handling LPG placement and edge insertion
        if self._live_packet_recorder_params:
            algorithms.append("PreAllocateResourcesForLivePacketGatherers")
            inputs['LivePacketRecorderParameters'] = \
                self._live_packet_recorder_params

        if get_config_bool("Reports", "write_energy_report"):
            algorithms.append("PreAllocateResourcesForChipPowerMonitor")
            inputs['MemorySamplingFrequency'] = get_config_int(
                "EnergyMonitor", "sampling_frequency")

        # add algorithms for handling extra monitor code
        if (get_config_bool("Machine", "enable_advanced_monitor_support") or
                get_config_bool("Machine", "enable_reinjection")):
            algorithms.append("PreAllocateResourcesForExtraMonitorSupport")

        # add the application and machine graphs as needed
        # Both could be None if call from other than self._run
        if self._application_graph and self._application_graph.n_vertices:
            inputs["ApplicationGraph"] = self._application_graph
        elif self._machine_graph and self._machine_graph.n_vertices:
            inputs["MachineGraph"] = self._machine_graph

        # new for no executor
        self._plan_n_timesteps = inputs["PlanNTimeSteps"]

        return inputs, algorithms

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
        with FecTimer("Write Json Machine") as timer:
            if timer.skip_if_cfg_false("Reports", "write_json_machine"):
                return
            writer = WriteJsonMachine()
            writer(self._machine, self._json_folder)
            # TODO output ignored as never used

    def _report_network_specification(self):
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
        with FecTimer("Execute Chip Id Allocator"):
            allocator = MallocBasedChipIdAllocator()
            if self._application_graph is None:
                graph = self._machine_graph
            else:
                graph = self._application_graph
            allocator(self._machine, graph)
            # return ignored as changes done inside original machine object

    def _report_board_chip(self):
        with FecTimer("Report Write Board Chip Report") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_board_chip_report"):
                return
            report = BoardChipReport()
            report(self._machine)

    def _execute_splitter_reset(self):
        with FecTimer("Execute Splitter Reset"):
            splitter_reset(self._application_graph)

    def _execute_splitter_selector(self):
        """
        overirdden by spynakker

        :return:
        """
        with FecTimer("Execute Splitter Selector"):
            selector = SplitterSelector()
            selector(self._application_graph)

    def _execute_delay_support_adder(self):
        """
        Stub to allow spynakker to add delay supports
        :return:
        """

    def _execute_splitter_partitioner(self):
        """
        overirdden by spynakker

        :return:
        """
        with FecTimer("Execute Splitter Partitioner") as timer:
            if timer.skip_if_application_graph_empty():
                return
            if self._machine:
                machine = self._machine
            else:
                machine = self._max_machine
            partitioner = SplitterPartitioner()
            self._machine_graph, self._n_chips_needed = partitioner(
                self._application_graph, machine, self._plan_n_timesteps,
                pre_allocated_resources=None)

    def _execute_graph_measurer(self):
        with FecTimer("Execute Graph Measurer") as executor:
            if executor.skip_if_value_already_set(
                    self._n_chips_needed, "n_chips_needed"):
                return
            measurer = GraphMeasurer()
            self._n_chips_needed = measurer(
                self._machine_graph, self._machine, self._plan_n_timesteps)

    def _execute_insert_chip_power_monitors(self):
        with FecTimer("Execute Insert Chip Power Monitors") as timer:
            if timer.skip_if_cfg_false("Reports", "write_energy_report"):
                return
            inserter = InsertChipPowerMonitorsToGraphs()
            inserter(
                self._machine, self._machine_graph,
                get_config_int("EnergyMonitor", "sampling_frequency"),
                self._application_graph)

    def _execute_insert_extra_monitor_vertices(self):
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
        with FecTimer("Execute Partitioner Report") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_partitioner_reports"):
                return
            partitioner_report(self._hostname, self._application_graph)

    def _execute_edge_to_n_keys_mapper(self):
        with FecTimer("Execute Edge To N Keys Mapper"):
            mapper = EdgeToNKeysMapper()
            self._machine_partition_n_keys_map = mapper(self._machine_graph)

    def _execute_local_tdma_builder(self):
        with FecTimer("Execute Local TDMA Builder"):
            builder = LocalTDMABuilder()
            builder(self._machine_graph, self._machine_partition_n_keys_map,
                    self._application_graph)

    def _json_partition_n_keys_map(self):
        with FecTimer("Json Partition NKeys Map") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_json_partition_n_keys_map"):
                return
            writer = WriteJsonPartitionNKeysMap()
            writer(self._machine_partition_n_keys_map, self._json_folder)
            # Output ignored as never used

    def _execute_connective_based_placer(self):
        with FecTimer("Execute Connective Based Placer"):
            placer = ConnectiveBasedPlacer()
            self._placements = placer(
                self._machine_graph, self._machine, self._plan_n_timesteps)

    def _execute_one_to_one_placer(self):
        with FecTimer("Execute One To One Placer"):
            placer = OneToOnePlacer()
            self._placements = placer(
                self._machine_graph, self._machine, self._plan_n_timesteps)

    def _execute_radial_placer(self):
        with FecTimer("Execute Radial Placer"):
            placer = RadialPlacer()
            self._placements = placer(
                self._machine_graph, self._machine, self._plan_n_timesteps)

    def _execute_speader_placer(self):
        with FecTimer("Execute Spreader Placer"):
            placer = SpreaderPlacer()
            self._placements = placer(
                self._machine_graph, self._machine,
                self._machine_partition_n_keys_map, self._plan_n_timesteps)

    def _do_placer(self):
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
        # TODO: Why does Master create Fixed routes but not use them when
        # enable_reinjection = True enable_advanced_monitor_support = False
        with FecTimer("Execute Fixed Route Router") as timer:
            if timer.skip_if_cfg_false(
                    "Machine", "enable_advanced_monitor_support"):
                return
            router = FixedRouteRouter()
            self._fixed_routes = router(
                self._machine, self._placements,
                DataSpeedUpPacketGatherMachineVertex)

    def _report_placements_with_application_graph(self):
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
        with FecTimer("Report Placements With Machine Graph") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_machine_graph_placer_report"):
                return
            placer_reports_without_application_graph(
                self._hostname, self._machine_graph, self._placements,
                self._machine)

    def _write_json_placements(self):
        with FecTimer("Write Json Placements") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_json_placements"):
                return
            writer = WriteJsonPlacements()
            writer(self._placements, self._json_folder)
            # Output ignored as never used

    def _execute_ner_route_traffic_aware(self):
        with FecTimer("Execute Ner Route Traffic Aware"):
            router = NerRouteTrafficAware()
            self._routing_table_by_partition = router(
                self._machine_graph, self._machine, self._placements)

    def _execute_ner_route(self):
        with FecTimer("Execute Ner Route"):
            router = NerRoute()
            self._routing_table_by_partition = router(
                self._machine_graph, self._machine, self._placements)

    def _execute_basic_dijkstra_routing(self):
        with FecTimer("Execute Basic Dijkstra Routing"):
            router = BasicDijkstraRouting()
            self._routing_table_by_partition = router(
                self._machine_graph, self._machine, self._placements)

    def _do_routing(self):
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
        with FecTimer("Execute Basic Tag Allocator"):
            allocator = BasicTagAllocator()
            self._tags = allocator(
                self._machine, self._plan_n_timesteps, self._placements)

    def _report_tag_allocations(self):
        with FecTimer("Report Tag Allocations") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_tag_allocation_reports"):
                return
            tag_allocator_report(self._tags)

    def _execute_process_partition_constraints(self):
        with FecTimer("Execute Process Partition Constraints"):
            processor = ProcessPartitionConstraints()
            processor(self._machine_graph)

    def _execute_global_allocate(self):
        with FecTimer("Execute Global Zoned Routing Info Allocator"):
            self._routing_infos = global_allocate(
                self._machine_graph, self._machine_partition_n_keys_map)

    def _execute_flexible_allocate(self):
        with FecTimer("Execute Zoned Routing Info Allocator"):
            self._routing_infos = flexible_allocate(
                self._machine_graph, self._machine_partition_n_keys_map)

    def _execute_malloc_based_routing_info_allocator(self):
        with FecTimer("Execute Malloc Based Routing Info Allocator"):
            allocator = MallocBasedRoutingInfoAllocator()
            self._routing_infos = allocator(
                self._machine_graph, self._machine_partition_n_keys_map)

    def do_info_allocator(self):
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
        with FecTimer("Report Router Info") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_router_info_report"):
                return
            routing_info_report(self._machine_graph, self._routing_infos)

    def _execute_basic_routing_table_generator(self):
        with FecTimer("Execute Basic Routing Table Generator"):
            generator = BasicRoutingTableGenerator()
            self._router_tables = generator(
                self._routing_infos, self._routing_table_by_partition,
                self._machine)
        # TODO Nuke ZonedRoutingTableGenerator

    def _report_routers(self):
        with FecTimer("Report Router") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_router_reports"):
                return
        router_report_from_paths(
            self._router_tables, self._routing_infos, self._hostname,
            self._machine_graph, self._placements, self._machine)

    def _report_router_summary(self):
        with FecTimer("Report Router Summary") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_router_summary_report"):
                return
            router_summary_report(
                self._router_tables,  self._hostname, self._machine)

    def _write_json_routing_tables(self):
        with FecTimer("Write Json Routing Tables") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_json_routing_tables"):
                return
            writer = WriteJsonRoutingTables()
            writer(self._router_tables, self._json_folder)
            # Output ignored as never used

    def _report_router_collision_potential(self):
        with FecTimer("Report Router Collision Potential"):
            # TODO cfg flag!
            report = RouterCollisionPotentialReport()
            report(self._routing_table_by_partition,
                   self._machine_partition_n_keys_map, self._machine)

    def _execute_locate_executable_start_type(self):
        with FecTimer("Execute Locate Executable Start Type") as timer:
            # TODO why skip if virtual ?
            if timer.skip_if_virtual_board():
                return
            locator = LocateExecutableStartType()
            self._executable_types = locator(
                self._machine_graph, self._placements)

    def _execute_buffer_manager_creator(self):
        with FecTimer("Execute Buffer Manager Creator") as timer:
            if timer.skip_if_virtual_board():
                return
            # TODO Why keep old if placements and or machine changed?
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
            print(self._buffer_manager)

    def _execute_sdram_outgoing_partition_allocator(self):
        with FecTimer("Execute SDRAM Outgoing Partition Allocator"):
            allocator = SDRAMOutgoingPartitionAllocator()
            # Ok if transceiver = None
            allocator(
                self._machine_graph, self._placements, self._app_id,
                self._txrx)

    def _do_mapping(self, run_time, total_run_time):
        """
        :param float run_time:
        :param float total_run_time:
        """
        # time the time it takes to do all pacman stuff
        mapping_total_timer = Timer()
        mapping_total_timer.start_timing()
        provide_injectables(self)

        self._do_extra_mapping_algorithms()
        self._report_network_specification()
        self._execute_splitter_reset()
        self._execute_splitter_selector()
        self._execute_delay_support_adder()
        self._execute_splitter_partitioner()
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
        self._write_json_routing_tables()
        self._report_router_collision_potential()
        self._execute_locate_executable_start_type()
        self._execute_buffer_manager_creator()
        self._execute_sdram_outgoing_partition_allocator()

        clear_injectables()
        self._mapping_time += convert_time_diff_to_total_milliseconds(
            mapping_total_timer.take_sample())

    def _do_mappingX(self, run_time, total_run_time):
        """
        :param float run_time:
        :param float total_run_time:
        """
        # time the time it takes to do all pacman stuff
        mapping_total_timer = Timer()
        mapping_total_timer.start_timing()

        # update inputs with extra mapping inputs if required
        inputs = dict(self._machine_outputs)
        tokens = list(self._machine_tokens)
        if self._extra_mapping_inputs is not None:
            inputs.update(self._extra_mapping_inputs)

        # runtime full runtime from pynn
        inputs["RunTime"] = run_time
        inputs["TotalRunTime"] = total_run_time

        # handle graph additions
        if self._application_graph.n_vertices:
            inputs["ApplicationGraph"] = self._application_graph
        else:
            inputs['MachineGraph'] = self._machine_graph

        inputs["JsonFolder"] = self._json_folder
        inputs["APPID"] = self._app_id
        inputs["DatabaseSocketAddresses"] = self._database_socket_addresses
        inputs["ExecutableFinder"] = self._executable_finder

        algorithms = list()

        # process for TDMA required cores
        algorithms.append("LocalTDMABuilder")

        if self._live_packet_recorder_params:
            algorithms.append(
                "InsertLivePacketGatherersToGraphs")
            algorithms.append("InsertEdgesToLivePacketGatherers")
            inputs['LivePacketRecorderParameters'] = \
                self._live_packet_recorder_params

        if get_config_bool("Reports", "write_energy_report"):
            algorithms.append(
                "InsertChipPowerMonitorsToGraphs")
            inputs['MemorySamplingFrequency'] = get_config_int(
                "EnergyMonitor", "sampling_frequency")

        # handle extra monitor functionality
        add_data_speed_up = (get_config_bool(
            "Machine", "enable_advanced_monitor_support") or
            get_config_bool("Machine", "enable_reinjection"))
        if add_data_speed_up:
            algorithms.append("InsertExtraMonitorVerticesToGraphs")
            algorithms.append("InsertEdgesToExtraMonitorFunctionality")
            algorithms.append("SystemMulticastRoutingGenerator")
            algorithms.append("FixedRouteRouter")
            inputs['FixedRouteDestinationClass'] = \
                DataSpeedUpPacketGatherMachineVertex

        # handle extra mapping algorithms if required
        if self._extra_mapping_algorithms is not None:
            algorithms.extend(self._extra_mapping_algorithms)

        optional_algorithms = list()

        # Add reports
        if get_config_bool("Reports", "reports_enabled"):
            if get_config_bool("Reports", "write_tag_allocation_reports"):
                algorithms.append("TagReport")
            if get_config_bool("Reports", "write_router_info_report"):
                algorithms.append("routingInfoReports")
            if get_config_bool("Reports", "write_router_reports"):
                algorithms.append("RouterReports")
            if get_config_bool(
                    "Reports", "write_router_summary_report"):
                algorithms.append("RouterSummaryReport")

            # only add board chip report if requested
            if get_config_bool("Reports", "write_board_chip_report"):
                algorithms.append("BoardChipReport")

            # only add partitioner report if using an application graph
            if (get_config_bool(
                    "Reports", "write_partitioner_reports") and
                    self._application_graph.n_vertices):
                algorithms.append("PartitionerReport")

            # only add write placer report with application graph when
            # there's application vertices
            if (get_config_bool(
                    "Reports", "write_application_graph_placer_report") and
                    self._application_graph.n_vertices):
                algorithms.append("PlacerReportWithApplicationGraph")

            if get_config_bool(
                    "Reports", "write_machine_graph_placer_report"):
                algorithms.append("PlacerReportWithoutApplicationGraph")

            if get_config_bool(
                    "Reports", "write_json_machine"):
                algorithms.append("WriteJsonMachine")

            if get_config_bool(
                    "Reports", "write_json_machine_graph"):
                algorithms.append("WriteJsonMachineGraph")

            if get_config_bool(
                    "Reports", "write_json_placements"):
                algorithms.append("WriteJsonPlacements")

            if get_config_bool(
                    "Reports", "write_json_routing_tables"):
                algorithms.append("WriteJsonRoutingTables")

            if get_config_bool(
                    "Reports", "write_json_partition_n_keys_map"):
                algorithms.append("WriteJsonPartitionNKeysMap")

            # only add network specification report if there's
            # application vertices.
            if (get_config_bool(
                    "Reports", "write_network_specification_report")):
                algorithms.append("NetworkSpecificationReport")

        # only add the partitioner if there isn't already a machine graph
        algorithms.append("MallocBasedChipIDAllocator")
        if _PREALLOC_NAME not in inputs:
            inputs[_PREALLOC_NAME] = PreAllocatedResourceContainer()
        if not self._machine_graph.n_vertices:
            algorithms.extend(get_config_str_list(
                "Mapping", "application_to_machine_graph_algorithms"))

        if self._use_virtual_board:
            algorithms.extend(get_config_str_list(
                "Mapping", "machine_graph_to_virtual_machine_algorithms"))
        else:
            algorithms.extend(get_config_str_list(
                "Mapping", "machine_graph_to_machine_algorithms"))

        # add check for algorithm start type
        if not self._use_virtual_board:
            algorithms.append("LocateExecutableStartType")

        # handle outputs
        outputs = [
            "Placements", "RoutingTables",
            "Tags", "RoutingInfos",
            "MachineGraph"
        ]

        if not self._use_virtual_board:
            outputs.append("ExecutableTypes")

        if add_data_speed_up:
            outputs.append("FixedRoutes")

        # Create a buffer manager if there isn't one already
        if not self._use_virtual_board:
            if self._buffer_manager is None:
                algorithms.append("BufferManagerCreator")
                outputs.append("BufferManager")
            else:
                inputs["BufferManager"] = self._buffer_manager
            if self._java_caller is None:
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
            inputs["JavaCaller"] = self._java_caller

        # Add the sdram allocator to ensure the sdram is allocated before
        # DSG.  Note this can run with a virtual machine but then makes fake
        # allocations, but avoids DSG issues.
        algorithms.append("SDRAMOutgoingPartitionAllocator")

        # Execute the mapping algorithms
        executor = self._run_algorithms(
            inputs, algorithms, outputs, tokens, [], "mapping",
            optional_algorithms)

        # get result objects from the pacman executor
        self._mapping_outputs = executor.get_items()
        self._mapping_tokens = executor.get_completed_tokens()

        # Get the outputs needed
        self._placements = executor.get_item("Placements")
        self._router_tables = executor.get_item("RoutingTables")
        self._tags = executor.get_item("Tags")
        self._routing_infos = executor.get_item("RoutingInfos")
        self._machine_graph = executor.get_item("MachineGraph")
        self._executable_types = executor.get_item("ExecutableTypes")

        if add_data_speed_up:
            self._fixed_routes = executor.get_item("FixedRoutes")

        if not self._use_virtual_board:
            self._buffer_manager = executor.get_item("BufferManager")

        self._mapping_time += convert_time_diff_to_total_milliseconds(
            mapping_total_timer.take_sample())
        self._mapping_outputs["MappingTimeMs"] = self._mapping_time

        # New for no executor
        self._extra_monitor_vertices = executor.get_item(
            "ExtraMonitorVertices")
        self._vertex_to_ethernet_connected_chip_mapping = \
            executor.get_item("VertexToEthernetConnectedChipMapping")
        self._data_in_multicast_key_to_chip_map = executor.get_item(
            "DataInMulticastKeyToChipMap")
        self._machine_partition_n_keys_map = executor.get_item(
            "MachinePartitionNKeysMap")
        self._system_multicast_router_timeout_keys = \
            executor.get_item("SystemMulticastRouterTimeoutKeys")
        self._data_in_multicast_routing_tables = executor.get_item(
            "DataInMulticastRoutingTables")

    def _execute_graph_data_specification_writer(self):
        """
        Overridden by spy which adds placement_order

        :return:
        """
        with FecTimer("Execute Graph Data Specification Writer"):
            writer = GraphDataSpecificationWriter()
            self._dsg_targets, self._region_sizes = writer(
                self._placements, self._hostname, self._machine,
                self._max_run_time_steps)

    def _do_data_generation(self, n_machine_time_steps):
        self._run_until_time_step = n_machine_time_steps
        # set up timing
        data_gen_timer = Timer()
        data_gen_timer.start_timing()

        self._run_until_time_step = n_machine_time_steps
        self._first_machine_time_step = self._current_run_timesteps

        provide_injectables(self)
        self._execute_graph_data_specification_writer()
        clear_injectables()

        self._dsg_time += convert_time_diff_to_total_milliseconds(
            data_gen_timer.take_sample())

    def _do_data_generationX(self, n_machine_time_steps):
        """
        :param int n_machine_time_steps:
        """
        self._run_until_time_step = n_machine_time_steps
        # set up timing
        data_gen_timer = Timer()
        data_gen_timer.start_timing()

        # The initial inputs are the mapping outputs
        inputs = dict(self._mapping_outputs)
        tokens = list(self._mapping_tokens)
        inputs["RunUntilTimeSteps"] = n_machine_time_steps
        inputs["FirstMachineTimeStep"] = self._current_run_timesteps

        # This is done twice to make things nicer for things which don't have
        # time steps without breaking existing code; it is purely aesthetic
        inputs["DataNTimeSteps"] = self._max_run_time_steps
        inputs["DataNSteps"] = self._max_run_time_steps

        # Run the data generation algorithms
        outputs = []
        algorithms = [self._dsg_algorithm]

        executor = self._run_algorithms(
            inputs, algorithms, outputs, tokens, [], "data_generation")
        self._mapping_outputs = executor.get_items()
        self._mapping_tokens = executor.get_completed_tokens()

        self._dsg_time += convert_time_diff_to_total_milliseconds(
            data_gen_timer.take_sample())
        self._mapping_outputs["DSGTimeMs"] = self._dsg_time
        # new for no executor
        self._dsg_targets = self._mapping_outputs["DataSpecificationTargets"]
        self._region_sizes = self._mapping_outputs["RegionSizes"]

    def _execute_routing_setup(self, graph_changed):
        with FecTimer("Execute Routing Setup") as timer:
            if timer.skip_if_virtual_board():
                return
            if timer.skip_if_value_false(graph_changed, "graph_changed"):
                return
            if self._multicast_routes_loaded:
                timer.skip("Routing tables already loaded")
                return
            setup = RoutingSetup()
            setup(self._router_tables, self._app_id, self._txrx, self._machine)

    def _execute_graph_binary_gatherer(self, graph_changed):
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
                    timer.stop("exectable not found and virtual board")
                    return
                raise

    def _execute_host_bitfield_compressor(self):
        with FecTimer("Execute HostBasedBitFieldRouterCompressor") as timer:
            if timer.skip_if_virtual_board():
                return None, []
            self._multicast_routes_loaded = False
            compressor = HostBasedBitFieldRouterCompressor()
            return compressor(
                self._router_tables, self._machine, self._placements,
                self._txrx, self._machine_graph, self._routing_infos)

    def _execute_machine_bitfield_ordered_covering_compressor(self):
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
        with FecTimer("Execute OrderedCoveringCompressor"):
            self._multicast_routes_loaded = False
            compressor = OrderedCoveringCompressor()
            compressed = compressor(self._router_tables)
            return compressed, []

    def _execute_ordered_covering_compression(self):
        with FecTimer("Execute OrderedCoveringCompressor") as timer:
            if timer.skip_if_virtual_board():
                return None, []
            ordered_covering_compression(
                self._router_tables, self._txrx, self._executable_finder,
                self._machine, self._app_id)
            self._multicast_routes_loaded = True
            return None, []

    def _execute_pair_compressor(self):
        with FecTimer("Execute PairCompressor"):
            compressor = PairCompressor()
            compressed = compressor(self._router_tables)
            self._multicast_routes_loaded = False
            return compressed, []

    def _execute_pair_compression(self):
        with FecTimer("Execute PairOnChipRouterCompression") as timer:
            if timer.skip_if_virtual_board():
                return None, []
            pair_compression(
                self._router_tables, self._txrx, self._executable_finder,
                self._machine, self._app_id)
            self._multicast_routes_loaded = True
            return None, []

    def _execute_pair_unordered_compressor(self):
        with FecTimer("Execute PairUnorderedCompressor"):
            compressor = CheckedUnorderedPairCompressor()
            compressed = compressor(self._router_tables)
            self._multicast_routes_loaded = False
            return compressed, []

    def _do_compression(self):
        """

        :return: CompressedRoutingTables (likely to be None),
            RouterCompressorProvenanceItems
        """
        if self.use_virtual_board:
            name = get_config_str("Mapping", "virtual_compressor")
            if name is None:
                logger.info("As no virtual_compressor specified "
                            "using compressor setting")
                name = get_config_str("Mapping", "compressor")
        else:
            name = get_config_str("Mapping", "compressor")

        return self._do_compression_by_name(name)

    def _do_compression_by_name(self, name):
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
        with FecTimer("Execute Routing Table Loader") as timer:
            if timer.skip_if_virtual_board():
                return
            if compressed:
                loader = RoutingTableLoader()
                loader(compressed, self._app_id, self._txrx, self._machine)
            else:
                timer.skip("Tables loaded by compressor")

    def _report_uncompressed_routing_table(self):
        # TODO why not during mapping?
        with FecTimer("Report Uncompressed RoutingTable") as timer:
            if timer.skip_if_cfg_false(
                    "Reports", "write_routing_table_reports"):
                return
            router_report_from_router_tables(self._router_tables)

    def _report_bit_field_compressor(self):
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
        with FecTimer("Execute Load Executable System Images") as timer:
            if timer.skip_if_virtual_board():
                return
            loader = LoadExecutableImages()
            loader.load_sys_images(
                self._executable_targets, self._app_id, self._txrx)

    def _execute_application_data_specification(
            self, processor_to_app_data_base_address):
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
        with FecTimer("Execute Tags From Machine Report") as timer:
            if timer.skip_if_virtual_board():
                return
            if timer.skip_if_cfg_false(
                    "Reports", "write_tag_allocation_reports"):
                return
            report = TagsFromMachineReport()
            report(self._txrx)

    def _execute_load_tags(self):
        # TODO why: if graph_changed or data_changed:
        with FecTimer("Execute Tags Loader") as timer:
            if timer.skip_if_virtual_board():
                return
            loader = TagsLoader()
            loader(self._txrx, self._tags)

    def _do_extra_load_algorithms(self):
        """
        Allows overriding classes to add algorithms
        """

    def _execute_memory_report(
            self, graph_changed, processor_to_app_data_base_address):
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

            report = MemoryMapOnHostChipReport()
            report(self._dsg_targets, self._txrx)

    def _execute_compressed_reports(self, graph_changed, compressed):
        """ Add reports that depend on compression

        :param graph_changed:
        :param compressed:
        :return:
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

    def _do_load(self, graph_changed, data_changed):
        # todo remove param data_changed
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
        self._execute_memory_report(
            graph_changed, processor_to_app_data_base_address)
        self._execute_compressed_reports(graph_changed, compressed)
        self._execute_fixed_route_report(graph_changed)
        self._execute_application_load_executables()

        # TODO why in do_load
        # self._no_sync_changes = executor.get_item("NoSyncChanges")

        self._load_time += convert_time_diff_to_total_milliseconds(
            load_timer.take_sample())
        # self._load_outputs["LoadTimeMs"] = self._load_time

    def _do_loadX(self, graph_changed, data_changed):
        """
        :param bool graph_changed:
        :param bool data_changed:
        """
        # If we are using a virtual board, don't load
        if self._use_virtual_board:
            return

        # set up timing
        load_timer = Timer()
        load_timer.start_timing()

        # The initial inputs are the mapping outputs
        inputs = dict(self._mapping_outputs)
        tokens = list(self._mapping_tokens)
        inputs["NoSyncChanges"] = self._no_sync_changes

        if not graph_changed and self._has_ran:
            inputs["ExecutableTargets"] = self._last_run_outputs[
                "ExecutableTargets"]

        algorithms = list()

        # add report for extracting routing table from machine report if needed
        # Add algorithm to clear routing tables and set up routing
        if not self._use_virtual_board and graph_changed:
            # only clear routing tables if we've not loaded them by now
            found = False
            for token in self._mapping_tokens:
                if token.name == "DataLoaded":
                    if token.part == "MulticastRoutesLoaded":
                        found = True
            if not found:
                algorithms.append("RoutingSetup")

            # Get the executable targets
            algorithms.append("GraphBinaryGatherer")

        algorithms.extend(get_config_str_list(
            "Mapping", "loading_algorithms"))

        algorithms.extend(self._extra_load_algorithms)

        write_memory_report = get_config_bool(
            "Reports", "write_memory_map_report")
        if write_memory_report and graph_changed:
            algorithms.append("MemoryMapOnHostReport")
            algorithms.append("MemoryMapOnHostChipReport")

        # Add reports that depend on compression
        routing_tables_needed = False
        if graph_changed:
            if get_config_bool(
                    "Reports", "write_routing_table_reports"):
                routing_tables_needed = True
                algorithms.append("unCompressedRoutingTableReports")

                if get_config_bool(
                        "Reports",
                        "write_routing_tables_from_machine_reports"):
                    algorithms.append("ReadRoutingTablesFromMachine")
                    algorithms.append("compressedRoutingTableReports")
                    algorithms.append("comparisonOfRoutingTablesReport")
                    algorithms.append("CompressedRouterSummaryReport")
                    algorithms.append("RoutingTableFromMachineReport")

        if get_config_bool(
                "Reports", "write_bit_field_compressor_report"):
            algorithms.append("BitFieldCompressorReport")

        # handle extra monitor functionality
        enable_advanced_monitor = get_config_bool(
            "Machine", "enable_advanced_monitor_support")
        if enable_advanced_monitor and (graph_changed or not self._has_ran):
            algorithms.append("LoadFixedRoutes")
            algorithms.append("FixedRouteFromMachineReport")

        # add optional algorithms
        optional_algorithms = list()

        if graph_changed or data_changed:
            optional_algorithms.append("RoutingTableLoader")
            optional_algorithms.append("TagsLoader")

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
        if get_config_bool("Reports", "write_tag_allocation_reports"):
            algorithms.append("TagsFromMachineReport")

        # Decide what needs to be done
        required_tokens = ["DataLoaded", "BinariesLoaded"]

        executor = self._run_algorithms(
            inputs, algorithms, [], tokens, required_tokens, "loading",
            optional_algorithms)
        self._no_sync_changes = executor.get_item("NoSyncChanges")
        self._load_outputs = executor.get_items()
        self._load_tokens = executor.get_completed_tokens()

        self._load_time += convert_time_diff_to_total_milliseconds(
            load_timer.take_sample())
        self._load_outputs["LoadTimeMs"] = self._load_time

        # new for no executor
        self._executable_targets = self._load_outputs["ExecutableTargets"]

    def _end_of_run_timing(self):
        """
        :return:
            mapping_time, dsg_time, load_time, execute_time, extraction_time
        :rtype: tuple(float, float, float, float, float)
        """
        timer = self._run_timer
        if timer is not None:
            self._execute_time += convert_time_diff_to_total_milliseconds(
                self._run_timer.take_sample())
        return (
            self._mapping_time, self._dsg_time, self._load_time,
            self._execute_time, self._extraction_time)

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
            Reload any parameters over the loaded data if we have already
            run and not using a virtual board and the data hasn't already
            been regenerated
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

    def _execute_read_provenance(self, n_machine_time_steps):
        prov_items = list()
        if self._version_provenance is not None:
            prov_items.extend(self._version_provenance)
        prov_items.extend(self._pacman_provenance.data_items)

        with FecTimer("Execute Read Provenance") as timer:
            if timer.skip_if_cfg_false("Reports", "read_provenance_data"):
                return prov_items

            gatherer = GraphProvenanceGatherer()
            prov_items.extend(gatherer(
                self._machine_graph, self._application_graph))

            # TODO verify why master only add
            #  if n_machine_time_steps is not None
            if timer.stop_if_none(
                    n_machine_time_steps, "n_machine_time_steps"):
                return prov_items

            if timer.stop_if_virtual_board():
                return prov_items
            placement_gather = PlacementsProvenanceGatherer()
            prov_items.extend(placement_gather(
                self._txrx, self._placements))

            router_gather = RouterProvenanceGatherer()
            provenance_data_objects = None
            prov_items.extend(router_gather(
                self._txrx, self._machine, self._router_tables,
                provenance_data_objects, self._extra_monitor_vertices,
                self._placements))

            profile_data_gatherer = ProfileDataGatherer()
            profile_data_gatherer(
                self._txrx, self._placements)

            return prov_items

    def _execute_energy_report(self, router_provenance_items, run_time):
        with FecTimer("Execute energy report") as timer:
            if timer.skip_if_cfg_false("Reports", "write_energy_report"):
                return []

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

            self._do_energy_report(power_used)
            return prov_items

    def _report_provenance(self, prov_items, n_machine_time_steps):
        with FecTimer("Write Provenance") as timer:
            if timer.skip_if_cfg_false("Reports", "write_provenance_data"):
                return
            if timer.stop_if_none(
                    n_machine_time_steps, "n_machine_time_steps"):
                return
            # TODO Why does master only clear on write?
            self._pacman_provenance.clear()
            self._version_provenance = list()
            self._write_provenance(prov_items)

    def _gather_provenance_for_writing(self, executor):
        """ Handles the gathering of provenance items for writer.

        :param ~pacman.executor.PACMANAlgorithmExecutor executor:
            the pacman executor.
        :return:
        """
        prov_items = list()
        if self._version_provenance is not None:
            prov_items.extend(self._version_provenance)
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
        prov_item = executor.get_item("PowerProvenanceItems")
        if prov_item is not None:
            prov_items.extend(prov_item)
        self._pacman_provenance.clear()
        self._version_provenance = list()
        self._write_provenance(prov_items)

    def _execute_clear_io_buf(self, n_machine_time_steps):
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
        with FecTimer("Execute Create Database Interface") \
                as timer:
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
        with FecTimer("Execute Create Notification Protocol"):
            creator = CreateNotificationProtocol()
            return creator(
                self._database_socket_addresses, self._database_file_path)

    def _execute_runner(self, n_sync_steps, run_time, notification_interface):
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
                self._buffer_manager, notification_interface,
                self._executable_types, self._app_id, self._txrx, run_time,
                self._no_sync_changes, time_threshold, self._machine,
                self._run_until_complete)

    def _execute_extract_iobuff(self, n_machine_time_steps):
        with FecTimer("Execute Extract IO Buff") as timer:
            if timer.skip_if_virtual_board():
                return
            if timer.skip_if_cfg_false(
                    "Reports", "extract_iobuf_during_run"):
                return
            if timer.skip_if_cfg_false(
                    "Reports", "extract_iobuf"):
                return
            if timer.skip_if_value_is_none(
                    n_machine_time_steps, "n_machine_time_steps"):
                return
            iobuf_extractor = ChipIOBufExtractor()
            # ErrorMessages, WarnMessages output ignored as never used!
            iobuf_extractor(
                self._txrx, self._executable_targets, self._executable_finder)

    def _execute_buffer_extractor(self, n_machine_time_steps):
        with FecTimer("Execute Buffer Extractor") as timer:
            if timer.skip_if_virtual_board():
                return
            if (self._run_until_complete or n_machine_time_steps is not None):
                buffer_extractor = BufferExtractor()
                buffer_extractor(
                    self._machine_graph, self._placements,
                    self._buffer_manager)
            else:
                timer.skip(
                    "Neither run until complete or n_machine_time_steps")

    def _do_run(self, n_machine_time_steps, graph_changed, n_sync_steps):
        # TODO virtual board
        self._run_timer = Timer()
        self._run_timer.start_timing()
        run_time = None
        if n_machine_time_steps is not None:
            run_time = n_machine_time_steps * self.machine_time_step_ms
        self._first_machine_time_step = self._current_run_timesteps
        self._current_run_timesteps = \
            self._calculate_number_of_machine_time_steps(n_machine_time_steps)
        self._run_until_time_step = self._current_run_timesteps

        # TODO is there a better way to get update_buffer to run
        provide_injectables(self)
        do_injection(self)

        self._execute_sdram_usage_report_per_chip()
        self._execute_dsg_region_reloader(graph_changed)
        self._execute_clear_io_buf(n_machine_time_steps)
        self._execute_runtime_update(n_sync_steps)
        self._execute_create_database_interface(run_time, graph_changed)
        notification_interface = self._execute_create_notifiaction_protocol()
        self._execute_runner(n_sync_steps, run_time, notification_interface)
        self._execute_extract_iobuff(n_machine_time_steps)
        self._execute_buffer_extractor(n_machine_time_steps)
        # FinaliseTimingData never needed as just pushed self._ to inputs
        prov_items = self._execute_read_provenance(n_machine_time_steps)
        prov_items.extend(self._execute_energy_report(
             prov_items, run_time))
        self._report_provenance(prov_items, n_machine_time_steps)

        self._has_reset_last = False
        self._has_ran = True
        self._first_machine_time_step = None
        clear_injectables()

    def _do_runX(self, n_machine_time_steps, graph_changed, n_sync_steps):
        """
        :param n_machine_time_steps: The number of steps to simulate
        :type n_machine_time_steps: int or None
        :param bool graph_changed: Has the graph changed between runs
        :param int n_sync_steps: The number of steps between synchronisation
        """
        # start timer
        self._run_timer = Timer()
        self._run_timer.start_timing()

        run_complete = False
        executor, self._current_run_timesteps = self._create_execute_workflowX(
            n_machine_time_steps, graph_changed, n_sync_steps)

        # Update the number of sync changes now in case this is used in a
        # synchronised simulation.  Note that the "correct" value will be
        # extracted later if not
        self._no_sync_changes += 1

        try:
            executor.execute_mapping()
            self._pacman_provenance.extract_provenance(executor)
            run_complete = True

            # write provenance to file if necessary
            if (get_config_bool("Reports", "write_provenance_data") and
                    n_machine_time_steps is not None):
                self._gather_provenance_for_writing(executor)

            # move data around
            self._last_run_outputs = executor.get_items()
            self._last_run_tokens = executor.get_completed_tokens()
            self._no_sync_changes = executor.get_item("NoSyncChanges")
            self._has_reset_last = False
            self._has_ran = True

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
            if get_config_str("Mode", "mode") != "Debug":
                try:
                    self.stop(
                        turn_off_machine=False, clear_routing_tables=False,
                        clear_tags=False)
                except Exception:
                    logger.exception("Error when attempting to stop")

            # reraise exception
            raise e

    def _create_execute_workflowX(
            self, n_machine_time_steps, graph_changed, n_sync_steps):
        """
        :param n_machine_time_steps:
        :type n_machine_time_steps: int or None
        :param bool graph_changed:
        :param int n_sync_steps:
        """
        # calculate number of machine time steps
        run_until_timesteps = self._calculate_number_of_machine_time_steps(
            n_machine_time_steps)
        run_time = None
        if n_machine_time_steps is not None:
            run_time = n_machine_time_steps * self.machine_time_step_ms

        # if running again, load the outputs from last load or last mapping
        if self._load_outputs is not None:
            inputs = dict(self._load_outputs)
            tokens = list(self._load_tokens)
        else:
            inputs = dict(self._mapping_outputs)
            tokens = list(self._mapping_tokens)

        inputs["NoSyncChanges"] = self._no_sync_changes
        inputs["RunTimeMachineTimeSteps"] = n_machine_time_steps
        inputs["RunUntilTimeSteps"] = run_until_timesteps
        inputs["RunTime"] = run_time
        inputs["NSyncSteps"] = n_sync_steps
        inputs["FirstMachineTimeStep"] = self._current_run_timesteps
        if self._run_until_complete:
            inputs["RunUntilCompleteFlag"] = True

        # Don't timeout if a stepped mode is in operation
        if n_sync_steps:
            inputs["PostSimulationOverrunBeforeError"] = None
        else:
            inputs["PostSimulationOverrunBeforeError"] = get_config_int(
                "Machine", "post_simulation_overrun_before_error")

        # update algorithm list with extra pre algorithms if needed
        if self._extra_pre_run_algorithms is not None:
            algorithms = list(self._extra_pre_run_algorithms)
        else:
            algorithms = list()

        if get_config_bool(
                "Reports", "write_sdram_usage_report_per_chip"):
            algorithms.append("SdramUsageReportPerChip")

        # Clear iobuf from machine
        if (n_machine_time_steps is not None and
                not self._use_virtual_board and not self._empty_graphs and
                get_config_bool("Reports", "clear_iobuf_during_run")):
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
            algorithms.append("CreateNotificationProtocol")

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
            tokens.append("ApplicationRun")
        else:
            algorithms.append("ApplicationRunner")

        # add extractor of iobuf if needed
        if (get_config_bool("Reports", "extract_iobuf") and
                get_config_bool(
                    "Reports", "extract_iobuf_during_run") and
                not self._use_virtual_board and
                n_machine_time_steps is not None):
            algorithms.append("ChipIOBufExtractor")

        # ensure we exploit the parallel of data extraction by running it at\
        # end regardless of multirun, but only run if using a real machine
        if ((self._run_until_complete or n_machine_time_steps is not None)
                and not self._use_virtual_board):
            algorithms.append("BufferExtractor")

        read_prov = get_config_bool(
            "Reports", "read_provenance_data")
        if read_prov:
            algorithms.append("GraphProvenanceGatherer")

        # add any extra post algorithms as needed
        if self._extra_post_run_algorithms is not None:
            algorithms += self._extra_post_run_algorithms

        # add in the timing finalisation
        if not self._use_virtual_board:
            algorithms.append("FinaliseTimingData")
            if get_config_bool("Reports", "write_energy_report"):
                algorithms.append("ComputeEnergyUsed")
                if read_prov:
                    algorithms.append("EnergyProvenanceReporter")

        # add extractor of provenance if needed
        if (read_prov and not self._use_virtual_board and
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
        """ Write provenance to disk.

        :param list(ProvenanceDataItem) provenance_data_items:
        """

        writer = None
        if self._provenance_format == "xml":
            writer = ProvenanceXMLWriter()
        elif self._provenance_format == "json":
            writer = ProvenanceJSONWriter()
        elif self._provenance_format == "sql":
            writer = ProvenanceSQLWriter()
        elif len(provenance_data_items) < PROVENANCE_TYPE_CUTOFF:
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
            prov_item = router_provenance(
                transceiver=self._txrx, machine=self._machine,
                router_tables=self._router_tables,
                extra_monitor_vertices=self._extra_monitor_vertices,
                placements=self._placements,
                using_reinjection=get_config_bool(
                    "Machine", "enable_reinjection"))
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
                prov_item = extractor(self._txrx, finished_placements)
                if prov_item is not None:
                    prov_items.extend(prov_item)
            except Exception:
                logger.exception("Could not read provenance")

        # Finish getting the provenance
        prov_items.extend(self._pacman_provenance.data_items)
        self._pacman_provenance.clear()
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

    def _create_xml_paths(self, extra_algorithm_xml_paths):
        """
        :param list(str) extra_algorithm_xml_paths:
        :rtype: list(str)
        """
        # add the extra xml files from the config file
        xml_paths = get_config_str_list("Mapping", "extra_xmls_paths")
        xml_paths.append(interface_xml())
        xml_paths.append(report_xml())

        if extra_algorithm_xml_paths is not None:
            xml_paths.extend(extra_algorithm_xml_paths)

        return xml_paths

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
        return self._no_machine_time_steps

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
    def dsg_algorithm(self):
        """ The DSG algorithm used by the tools

        :rtype: str
        """
        return self._dsg_algorithm

    @dsg_algorithm.setter
    def dsg_algorithm(self, new_dsg_algorithm):
        """ Set the DSG algorithm to be used by the tools

        :param str new_dsg_algorithm: the new DSG algorithm name
        """
        self._dsg_algorithm = new_dsg_algorithm

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

    def get_generated_output(self, name_of_variable):
        """ Get the value of an inter-algorithm variable.

        :param str name_of_variable: The variable to retrieve
        :return: The value (of arbitrary type), or `None` if the variable is
            not found.
        :raises ConfigurationException: If the simulation hasn't yet run
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
            if self._last_run_outputs and \
                    "NotificationInterface" in self._last_run_outputs:
                self._last_run_outputs["NotificationInterface"].close()
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
            executor = self._create_stop_workflow()
            run_complete = False
            try:
                executor.execute_mapping()
                self._pacman_provenance.extract_provenance(executor)
                run_complete = True

                # write provenance to file if necessary
                if get_config_bool("Reports", "write_provenance_data"):
                    self._gather_provenance_for_writing(executor)
            except Exception as e:
                exn = e
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

            # handle iobuf extraction
            if get_config_bool("Reports", "extract_iobuf"):
                self._extract_iobufs()

        # shut down the machine properly
        self._shutdown(turn_off_machine, clear_routing_tables, clear_tags)

        if exn is not None:
            self.write_errored_file()
            raise exn  # pylint: disable=raising-bad-type
        self.write_finished_file()

    def _create_stop_workflow(self):
        """
        :rtype: ~.PACMANAlgorithmExecutor
        """
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

        read_prov = get_config_bool("Reports", "read_provenance_data")

        # add extractor of iobuf if needed
        if get_config_bool("Reports", "extract_iobuf") and \
                get_config_bool("Reports", "extract_iobuf_during_run"):
            algorithms.append("ChipIOBufExtractor")

        # add extractor of provenance if needed
        if read_prov:
            algorithms.append("PlacementsProvenanceGatherer")
            algorithms.append("RouterProvenanceGatherer")
            algorithms.append("ProfileDataGatherer")
        if (get_config_bool("Reports", "write_energy_report") and
                not self._use_virtual_board):
            algorithms.append("ComputeEnergyUsed")
            if read_prov:
                algorithms.append("EnergyProvenanceReporter")

        # Assemble how to run the algorithms
        return PACMANAlgorithmExecutor(
            algorithms=algorithms, optional_algorithms=[], inputs=inputs,
            tokens=tokens, required_output_tokens=[],
            xml_paths=self._xml_paths,
            required_outputs=outputs, do_timings=self._do_timings,
            print_timings=self._print_timings,
            provenance_path=self._pacman_executor_provenance_path,
            provenance_name="stopping")

    def _do_energy_report(self, power_used):
        # create energy reporter
        energy_reporter = EnergyReport(
            get_config_int("Machine", "version"), self._spalloc_server,
            self._remote_spinnaker_url)

        if self._buffer_manager is None or self._last_run_outputs is None:
            return

        # run energy report
        energy_reporter.write_energy_report(
            self._placements, self._machine, self._current_run_timesteps,
            self._buffer_manager, power_used)

    def _extract_iobufs(self):
        if get_config_bool("Reports", "extract_iobuf_during_run"):
            return
        if get_config_bool("Reports", "clear_iobuf_during_run"):
            return
        extractor = IOBufExtractor(
            transceiver=self._txrx,
            executable_targets=self._last_run_outputs["ExecutableTargets"],
            executable_finder=self._executable_finder)
        extractor.extract_iobuf()

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

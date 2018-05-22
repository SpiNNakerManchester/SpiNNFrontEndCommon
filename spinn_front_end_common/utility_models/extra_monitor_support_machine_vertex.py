import logging
from enum import Enum
from pacman.executor.injection_decorator import inject_items
from pacman.model.graphs.common import EdgeTrafficType
from pacman.model.graphs.machine import MachineVertex
from pacman.model.resources import ResourceContainer, SDRAMResource
from spinn_front_end_common.abstract_models import (
    AbstractHasAssociatedBinary, AbstractGeneratesDataSpecification)
from spinn_front_end_common.utilities import globals_variables
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.utilities.utility_objs.\
    extra_monitor_scp_processes import (
        ReadStatusProcess, ResetCountersProcess,
        SetApplicationMCRoutesProcess, SetPacketTypesProcess,
        SetRouterEmergencyTimeoutProcess, SetRouterTimeoutProcess,
        SetSystemMCRoutesProcess, ClearQueueProcess)
from .data_speed_up_packet_gatherer_machine_vertex import (
    DataSpeedUpPacketGatherMachineVertex)
from spinn_machine import CoreSubsets, Router
from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides
from spinn_front_end_common.utilities.helpful_functions import (
    convert_vertices_to_core_subset)

log = FormatAdapter(logging.getLogger(__name__))


class ExtraMonitorSupportMachineVertex(
        MachineVertex, AbstractHasAssociatedBinary,
        AbstractGeneratesDataSpecification):
    __slots__ = (
        # if we reinject mc packets
        "_reinject_multicast",
        # if we reinject point to point packets
        "_reinject_point_to_point",
        # if we reinject nearest neighbour packets
        "_reinject_nearest_neighbour",
        # if we reinject fixed route packets
        "_reinject_fixed_route",
        # placement holder for ease of access
        "_placement"
    )

    _EXTRA_MONITOR_DSG_REGIONS = Enum(
        value="_EXTRA_MONITOR_DSG_REGIONS",
        names=[('CONFIG', 0),
               ('DATA_OUT_SPEED_CONFIG', 1),
               ("DATA_IN_SPEED_CONFIG", 2)])

    _CONFIG_REGION_RE_INJECTOR_SIZE_IN_BYTES = 4 * 4
    _CONFIG_DATA_SPEED_UP_SIZE_IN_BYTES = 4 * 4
    _CONFIG_MAX_EXTRA_SEQ_NUM_SIZE_IN_BYTES = 460 * 1024
    _CONFIG_DATA_IN_KEYS_SDRAM_IN_BYTES = 12
    _MAX_DATA_SIZE_FOR_DATA_IN_MULTICAST_ROUTING = (48 * 3 * 4) + 4
    _BIT_SHIFT_TO_MOVE_APP_ID = 24

    # SDRAM requirement for containing router table entries
    # 16 bytes per entry:
    # 4 for a key, 4 for mask,
    # 4 for word alignment for 18 cores and 6 links
    # (24 bits, for word aligning)
    _SDRAM_FOR_ROUTER_TABLE_ENTRIES = 1024 * 4 * 4

    _EXTRA_MONITOR_COMMANDS = Enum(
        value="EXTRA_MONITOR_COMMANDS",
        names=[("SET_ROUTER_TIMEOUT", 0),
               ("SET_ROUTER_EMERGENCY_TIMEOUT", 1),
               ("SET_PACKET_TYPES", 2),
               ("GET_STATUS", 3),
               ("RESET_COUNTERS", 4),
               ("EXIT", 5),
               ("READ_APPLICATION_ROUTING_TABLE", 6),
               ("LOAD_APPLICATION_MC_ROUTES", 7),
               ("LOAD_SYSTEM_MC_ROUTES", 8)])

    _KEY_OFFSETS = Enum(
        value="EXTRA_MONITOR_KEY_OFFSETS_TO_COMMANDS",
        names=[("ADDRESS_KEY_OFFSET", 0),
               ("DATA_KEY_OFFSET", 1),
               ("RESTART_KEY_OFFSET", 2)])

    def __init__(
            self, constraints, reinject_multicast=None,
            reinject_point_to_point=False, reinject_nearest_neighbour=False,
            reinject_fixed_route=False):
        """
        :param constraints: constraints on this vertex
        :param reinject_multicast: if we reinject multicast packets
        :param reinject_point_to_point: if we reinject point-to-point packets
        :param reinject_nearest_neighbour: \
            if we reinject nearest-neighbour packets
        :param reinject_fixed_route: if we reinject fixed-route packets
        """
        # pylint: disable=too-many-arguments
        super(ExtraMonitorSupportMachineVertex, self).__init__(
            label="ExtraMonitorSupportMachineVertex", constraints=constraints)

        if reinject_multicast is None:
            config = globals_variables.get_simulator().config
            self._reinject_multicast = config.getboolean(
                "Machine", "enable_reinjection")
        else:
            self._reinject_multicast = reinject_multicast
        self._reinject_point_to_point = reinject_point_to_point
        self._reinject_nearest_neighbour = reinject_nearest_neighbour
        self._reinject_fixed_route = reinject_fixed_route

        # placement holder for ease of access
        self._placement = None

    @property
    def reinject_multicast(self):
        return self._reinject_multicast

    @property
    def reinject_point_to_point(self):
        return self._reinject_point_to_point

    @property
    def reinject_nearest_neighbour(self):
        return self._reinject_nearest_neighbour

    @property
    def reinject_fixed_route(self):
        return self._reinject_fixed_route

    @property
    @overrides(MachineVertex.resources_required)
    def resources_required(self):
        return self.static_resources_required()

    @property
    def placement(self):
        return self._placement

    @staticmethod
    def static_resources_required():
        return ResourceContainer(sdram=SDRAMResource(
            sdram=ExtraMonitorSupportMachineVertex.
            _CONFIG_REGION_RE_INJECTOR_SIZE_IN_BYTES +
            ExtraMonitorSupportMachineVertex.
            _CONFIG_DATA_SPEED_UP_SIZE_IN_BYTES +
            ExtraMonitorSupportMachineVertex.
            _CONFIG_MAX_EXTRA_SEQ_NUM_SIZE_IN_BYTES +
            ExtraMonitorSupportMachineVertex.
            _MAX_DATA_SIZE_FOR_DATA_IN_MULTICAST_ROUTING +
            ExtraMonitorSupportMachineVertex._SDRAM_FOR_ROUTER_TABLE_ENTRIES +
            ExtraMonitorSupportMachineVertex.
            _CONFIG_DATA_IN_KEYS_SDRAM_IN_BYTES))

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return self.static_get_binary_start_type()

    @staticmethod
    def static_get_binary_start_type():
        return ExecutableType.SYSTEM

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return self.static_get_binary_file_name()

    @staticmethod
    def static_get_binary_file_name():
        return "extra_monitor_support.aplx"

    @inject_items({"routing_info": "MemoryRoutingInfos",
                   "machine_graph": "MemoryMachineGraph",
                   "data_in_routing_tables": "DataInMulticastRoutingTables",
                   "mc_data_chips_to_keys": "DataInMulticastKeyToChipMap",
                   "app_id": "APPID"})
    @overrides(AbstractGeneratesDataSpecification.generate_data_specification,
               additional_arguments={
                   "routing_info", "machine_graph", "data_in_routing_tables",
                   "mc_data_chips_to_keys", "app_id"})
    def generate_data_specification(
            self, spec, placement, routing_info, machine_graph,
            data_in_routing_tables, mc_data_chips_to_keys, app_id):
        # pylint: disable=arguments-differ
        # storing for future usage
        self._placement = placement

        # write reinjection functionality
        self._generate_reinjection_functionality_data_specification(spec)

        # write data out functionality
        self._generate_data_out_speed_up_functionality_data_specification(
            spec, routing_info, machine_graph)

        # write data in functionality
        self._generate_data_in_speed_up_functionality_data_specification(
            spec, data_in_routing_tables, placement, mc_data_chips_to_keys,
            app_id)

        spec.end_specification()

    def _generate_data_in_speed_up_functionality_data_specification(
            self, spec, data_in_routing_tables, placement,
            mc_data_chips_to_keys, app_id):
        """ data in spec

        :param spec: spec file
        :type spec:\
            :py:class:`~data_specification.DataSpecificationGenerator`
        :param data_in_routing_tables: routing tables for all chips
        :type data_in_routing_tables: \
            :py:class:`~pacman.model.routing_tables.MulticastRoutingTables`
        :param placement: this placement
        :type placement: :py:class:`~pacman.model.placements.Placement`
        :param mc_data_chips_to_keys: data in keys to chips map.
        :type mc_data_chips_to_keys: dict(tuple(int,int),int)
        :param app_id: The app id expected to write entries with
        :type app_id: int
        :rtype: None
        """
        spec.reserve_memory_region(
            region=self._EXTRA_MONITOR_DSG_REGIONS.DATA_IN_SPEED_CONFIG.value,
            size=(self._MAX_DATA_SIZE_FOR_DATA_IN_MULTICAST_ROUTING +
                  self._CONFIG_DATA_IN_KEYS_SDRAM_IN_BYTES),
            label="Data in speed up functionality config region")
        spec.switch_write_focus(
            self._EXTRA_MONITOR_DSG_REGIONS.DATA_IN_SPEED_CONFIG.value)

        # write address key and data key
        spec.write_value(
            mc_data_chips_to_keys[placement.x, placement.y] +
            self._KEY_OFFSETS.ADDRESS_KEY_OFFSET.value)
        spec.write_value(
            mc_data_chips_to_keys[placement.x, placement.y] +
            self._KEY_OFFSETS.DATA_KEY_OFFSET.value)
        spec.write_value(
            mc_data_chips_to_keys[placement.x, placement.y] +
            self._KEY_OFFSETS.RESTART_KEY_OFFSET.value)

        # write table entries
        table = data_in_routing_tables.get_routing_table_for_chip(
            placement.x, placement.y)
        spec.write_value(table.number_of_entries)
        for entry in table.multicast_routing_entries:
            spec.write_value(entry.routing_entry_key)
            spec.write_value(entry.mask)
            route = app_id << self._BIT_SHIFT_TO_MOVE_APP_ID
            route = \
                route | Router.convert_routing_table_entry_to_spinnaker_route(
                    entry)
            spec.write_value(route)
            # log.info("key {}".format(entry.routing_entry_key))
            # log.info("mask {}".format(entry.mask))
            # log.info("route {}".format(route))

    def _generate_data_out_speed_up_functionality_data_specification(
            self, spec, routing_info, machine_graph):
        """
        :param spec: spec file
        :type spec:\
            :py:class:`~data_specification.DataSpecificationGenerator`
        :type routing_info: \
            :py:class:`~pacman.model.routing_info.RoutingInfo`
        :type machine_graph: \
            :py:class:`~pacman.model.graphs.machine.MachineGraph`
        :rtype: None
        """
        spec.reserve_memory_region(
            region=self._EXTRA_MONITOR_DSG_REGIONS.DATA_OUT_SPEED_CONFIG.value,
            size=self._CONFIG_DATA_SPEED_UP_SIZE_IN_BYTES,
            label="data_speed functionality config region")
        spec.switch_write_focus(
            self._EXTRA_MONITOR_DSG_REGIONS.DATA_OUT_SPEED_CONFIG.value)

        if DataSpeedUpPacketGatherMachineVertex.TRAFFIC_TYPE == \
                EdgeTrafficType.MULTICAST:
            base_key = routing_info.get_first_key_for_edge(
                list(machine_graph.get_edges_starting_at_vertex(self))[0])
            spec.write_value(base_key)
            spec.write_value(
                base_key +
                DataSpeedUpPacketGatherMachineVertex.NEW_SEQ_KEY_OFFSET)
            spec.write_value(
                base_key +
                DataSpeedUpPacketGatherMachineVertex.FIRST_DATA_KEY_OFFSET)
            spec.write_value(
                base_key +
                DataSpeedUpPacketGatherMachineVertex.END_FLAG_KEY_OFFSET)
        else:
            spec.write_value(DataSpeedUpPacketGatherMachineVertex.BASE_KEY)
            spec.write_value(DataSpeedUpPacketGatherMachineVertex.NEW_SEQ_KEY)
            spec.write_value(
                DataSpeedUpPacketGatherMachineVertex.FIRST_DATA_KEY)
            spec.write_value(DataSpeedUpPacketGatherMachineVertex.END_FLAG_KEY)

    def _generate_reinjection_functionality_data_specification(self, spec):
        """
        :param spec: spec file
        :type spec:\
            :py:class:`~data_specification.DataSpecificationGenerator`
        """
        spec.reserve_memory_region(
            region=self._EXTRA_MONITOR_DSG_REGIONS.CONFIG.value,
            size=self._CONFIG_REGION_RE_INJECTOR_SIZE_IN_BYTES,
            label="re-injection functionality config region")

        spec.switch_write_focus(self._EXTRA_MONITOR_DSG_REGIONS.CONFIG.value)
        for value in [
                self._reinject_multicast, self._reinject_point_to_point,
                self._reinject_fixed_route,
                self._reinject_nearest_neighbour]:
            spec.write_value(int(not value))

    def set_router_time_outs(
            self, timeout_mantissa, timeout_exponent, transceiver, placements,
            extra_monitor_cores_to_set):
        """ Supports setting of the router time outs for a set of chips via\
            their extra monitor cores.

        :param timeout_mantissa: what timeout mantissa to set it to
        :type timeout_exponent: int
        :type timeout_mantissa: int
        :param timeout_exponent: what timeout exponent to set it to
        :param transceiver: the spinnman interface
        :type transceiver: :py:class:`~spinnman.Transceiver`
        :param placements: placements object
        :type placements: :py:class:`~pacman.model.placements.Placements`
        :param extra_monitor_cores_to_set: which vertices to use
        :rtype: None
        """
        # pylint: disable=too-many-arguments
        core_subsets = convert_vertices_to_core_subset(
            extra_monitor_cores_to_set, placements)
        process = SetRouterTimeoutProcess(
            transceiver.scamp_connection_selector)
        process.set_timeout(
            timeout_mantissa, timeout_exponent, core_subsets)

    def set_router_emergency_timeout(
            self, timeout_mantissa, timeout_exponent, transceiver, placements,
            extra_monitor_cores_to_set):
        """ Sets the timeout of the routers

        :param timeout_mantissa: \
            The mantissa of the timeout value, between 0 and 15
        :type timeout_mantissa: int
        :param timeout_exponent: \
            The exponent of the timeout value, between 0 and 15
        :type timeout_exponent: int
        :param transceiver: the spinnMan instance
        :type transceiver: :py:class:`~spinnman.Transceiver`
        :param placements: the placements object
        :type placements: :py:class:`~pacman.model.placements.Placements`
        :param extra_monitor_cores_to_set: \
            the set of vertices to change the local chip for.
        """
        # pylint: disable=too-many-arguments
        core_subsets = convert_vertices_to_core_subset(
            extra_monitor_cores_to_set, placements)
        process = SetRouterEmergencyTimeoutProcess(
            transceiver.scamp_connection_selector)
        process.set_timeout(
            timeout_mantissa, timeout_exponent, core_subsets)

    def reset_reinjection_counters(
            self, transceiver, placements, extra_monitor_cores_to_set):
        """ Resets the counters for reinjection

        :type transceiver: :py:class:`~spinnman.Transceiver`
        :type placements: :py:class:`~pacman.model.placements.Placements`
        :type extra_monitor_cores_to_set: \
            iterable(:py:class:`ExtraMonitorSupportMachineVertex`)
        """
        core_subsets = convert_vertices_to_core_subset(
            extra_monitor_cores_to_set, placements)
        process = ResetCountersProcess(transceiver.scamp_connection_selector)
        process.reset_counters(core_subsets)

    def clear_reinjection_queue(
            self, transceiver, placements, extra_monitor_cores_to_set):
        """ Clears the queues for reinjection
        """
        core_subsets = convert_vertices_to_core_subset(
            extra_monitor_cores_to_set, placements)
        process = ClearQueueProcess(transceiver.scamp_connection_selector)
        process.reset_counters(core_subsets)

    def get_reinjection_status(self, placements, transceiver):
        """ gets the reinjection status from this extra monitor vertex

        :param transceiver: the spinnMan interface
        :type transceiver: :py:class:`~spinnman.Transceiver`
        :param placements: the placements object
        :type placements: :py:class:`~pacman.model.placements.Placements`
        :return: the reinjection status for this vertex
        """
        placement = placements.get_placement_of_vertex(self)
        process = ReadStatusProcess(transceiver.scamp_connection_selector)
        return process.get_reinjection_status(
            placement.x, placement.y, placement.p)

    def get_reinjection_status_for_vertices(
            self, placements, extra_monitor_cores_for_data, transceiver):
        """ gets the reinjection status from a set of extra monitor cores

        :param placements: the placements object
        :type placements: :py:class:`~pacman.model.placements.Placements`
        :param extra_monitor_cores_for_data: \
            the extra monitor cores to get status from
        :type extra_monitor_cores_for_data: \
            iterable(:py:class:`ExtraMonitorSupportMachineVertex`)
        :param transceiver: the spinnMan interface
        :type transceiver: :py:class:`~spinnman.Transceiver`
        :rtype: None
        """
        core_subsets = convert_vertices_to_core_subset(
            extra_monitor_cores_for_data, placements)
        process = ReadStatusProcess(transceiver.scamp_connection_selector)
        return process.get_reinjection_status_for_core_subsets(core_subsets)

    def set_reinjection_packets(
            self, placements, extra_monitor_cores_for_data, transceiver,
            point_to_point=None, multicast=None, nearest_neighbour=None,
            fixed_route=None):
        """
        :param placements: placements object
        :type placements: :py:class:`~pacman.model.placements.Placements`
        :param extra_monitor_cores_for_data: \
            the extra monitor cores to set the packets of
        :type extra_monitor_cores_for_data: \
            iterable(:py:class:`ExtraMonitorSupportMachineVertex`)
        :param transceiver: spinnman instance
        :type transceiver: :py:class:`~spinnman.Transceiver`
        :param point_to_point: \
            If point to point should be set, or None if left as before
        :type point_to_point: bool or None
        :param multicast: \
            If multicast should be set, or None if left as before
        :type multicast: bool or None
        :param nearest_neighbour: \
            If nearest neighbour should be set, or None if left as before
        :type nearest_neighbour: bool or None
        :param fixed_route: \
            If fixed route should be set, or None if left as before.
        :type fixed_route: bool or None
        :rtype: None
        """
        # pylint: disable=too-many-arguments
        if multicast is not None:
            self._reinject_multicast = multicast
        if point_to_point is not None:
            self._reinject_point_to_point = point_to_point
        if nearest_neighbour is not None:
            self._reinject_nearest_neighbour = nearest_neighbour
        if fixed_route is not None:
            self._reinject_fixed_route = fixed_route

        core_subsets = convert_vertices_to_core_subset(
            extra_monitor_cores_for_data, placements)
        process = SetPacketTypesProcess(transceiver.scamp_connection_selector)
        process.set_packet_types(
            core_subsets, self._reinject_point_to_point,
            self._reinject_multicast, self._reinject_nearest_neighbour,
            self._reinject_fixed_route)

    def set_up_system_mc_routes(
            self, placements, extra_monitor_cores_for_data, transceiver):
        """ Get the extra monitor cores to load up the system-based \
            multicast routes (used by data in).

        :param placements: the placements object
        :type placements: :py:class:`~pacman.model.placements.Placements`
        :param extra_monitor_cores_for_data: \
            the extra monitor cores to get status from
        :type extra_monitor_cores_for_data: \
            iterable(:py:class:`ExtraMonitorSupportMachineVertex`)
        :param transceiver: the spinnMan interface
        :type transceiver: :py:class:`~spinnman.Transceiver`
        :rtype: None
        """
        core_subsets = self._convert_vertices_to_core_subset(
            extra_monitor_cores_for_data, placements)
        process = SetSystemMCRoutesProcess(
            transceiver.scamp_connection_selector)
        return process.set_system_mc_routes(
            core_subsets, self._EXTRA_MONITOR_COMMANDS.LOAD_SYSTEM_MC_ROUTES)

    def set_up_application_mc_routes(
            self, placements, extra_monitor_cores_for_data, transceiver):
        """ Get the extra monitor cores to load up the application-based\
            multicast routes (used by data in).

        :param placements: the placements object
        :type placements: :py:class:`~pacman.model.placements.Placements`
        :param extra_monitor_cores_for_data: \
            the extra monitor cores to get status from
        :type extra_monitor_cores_for_data: \
            iterable(:py:class:`ExtraMonitorSupportMachineVertex`)
        :param transceiver: the spinnMan interface
        :type transceiver: :py:class:`~spinnman.Transceiver`
        :rtype: None
        """
        core_subsets = self._convert_vertices_to_core_subset(
            extra_monitor_cores_for_data, placements)
        process = SetApplicationMCRoutesProcess(
            transceiver.scamp_connection_selector)
        return process.set_application_mc_routes(
            core_subsets,
            self._EXTRA_MONITOR_COMMANDS.LOAD_APPLICATION_MC_ROUTES)

    @staticmethod
    def _convert_vertices_to_core_subset(
            extra_monitor_cores, placements):
        """ Convert vertices into the subset of cores where they've been\
            placed.

        :param extra_monitor_cores: \
            the vertices to convert to core subsets
        :type extra_monitor_cores: \
            iterable(:py:class:`ExtraMonitorSupportMachineVertex`)
        :param placements: the placements object
        :type placements: :py:class:`~pacman.model.placements.Placements`
        :return: where the vertices have been placed
        :rtype: :py:class:`~spinn_machine.CoreSubsets`
        """
        core_subsets = CoreSubsets()
        for vertex in extra_monitor_cores:
            if not isinstance(vertex, ExtraMonitorSupportMachineVertex):
                raise Exception(
                    "can only use ExtraMonitorSupportMachineVertex to set "
                    "the router time out")
            placement = placements.get_placement_of_vertex(vertex)
            core_subsets.add_processor(placement.x, placement.y, placement.p)
        return core_subsets

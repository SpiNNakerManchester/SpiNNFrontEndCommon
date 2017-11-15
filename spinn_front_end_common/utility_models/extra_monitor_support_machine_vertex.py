from enum import Enum

from pacman.executor.injection_decorator import inject_items
from pacman.model.graphs.common import EdgeTrafficType
from pacman.model.graphs.machine import MachineVertex
from pacman.model.resources import ResourceContainer, SDRAMResource
from spinn_front_end_common.abstract_models import \
    AbstractHasAssociatedBinary, AbstractGeneratesDataSpecification
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.utilities.utility_objs.\
    extra_monitor_scp_processes.read_status_process import \
    ReadStatusProcess
from spinn_front_end_common.utilities.utility_objs.\
    extra_monitor_scp_processes.reset_counters_process import \
    ResetCountersProcess
from spinn_front_end_common.utilities.utility_objs.\
    extra_monitor_scp_processes.set_packet_types_process import \
    SetPacketTypesProcess
from spinn_front_end_common.utilities.utility_objs.\
    extra_monitor_scp_processes.set_router_emergency_timeout_process import \
    SetRouterEmergencyTimeoutProcess
from spinn_front_end_common.utilities.utility_objs.\
    extra_monitor_scp_processes.set_router_timeout_process import \
    SetRouterTimeoutProcess
from spinn_front_end_common.utility_models.\
    data_speed_up_packet_gatherer_machine_vertex import \
    DataSpeedUpPacketGatherMachineVertex
from spinn_machine import CoreSubsets
from spinn_utilities.overrides import overrides


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
        "_reinject_fixed_route"
    )

    _EXTRA_MONITOR_DSG_REGIONS = Enum(
        value="_EXTRA_MONITOR_DSG_REGIONS",
        names=[('CONFIG', 0),
               ('DATA_SPEED_CONFIG', 1)])

    _CONFIG_REGION_REINEJCTOR_SIZE_IN_BYTES = 4 * 4
    _CONFIG_DATA_SPEED_UP_SIZE_IN_BYTES = 1 * 4

    _EXTRA_MONITOR_COMMANDS = Enum(
        value="EXTRA_MONITOR_COMMANDS",
        names=[("SET_ROUTER_TIMEOUT", 0),
               ("SET_ROUTER_EMERGENCY_TIMEOUT", 1),
               ("SET_PACKET_TYPES", 2),
               ("GET_STATUS", 3),
               ("RESET_COUNTERS", 4),
               ("EXIT", 5)])

    def __init__(
            self, constraints, reinject_multicast=True,
            reinject_point_to_point=False, reinject_nearest_neighbour=False,
            reinject_fixed_route=False):
        """ constructor

        :param constraints: constraints on this vertex
        :param reinject_multicast: if we reinject mc packets
        :param reinject_point_to_point: if we reinject point to point packets
        :param reinject_nearest_neighbour: if we reinject nearest neighbour \
        packets
        :param reinject_fixed_route: if we reinject fixed route packets
        """
        MachineVertex.__init__(
            self, label="ExtraMonitorSupportMachineVertex",
            constraints=constraints)
        AbstractHasAssociatedBinary.__init__(self)
        AbstractGeneratesDataSpecification.__init__(self)

        self._reinject_multicast = reinject_multicast
        self._reinject_point_to_point = reinject_point_to_point
        self._reinject_nearest_neighbour = reinject_nearest_neighbour
        self._reinject_fixed_route = reinject_fixed_route

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

    @staticmethod
    def static_resources_required():
        return ResourceContainer(sdram=SDRAMResource(
            sdram=ExtraMonitorSupportMachineVertex.
            _CONFIG_REGION_REINEJCTOR_SIZE_IN_BYTES +
            ExtraMonitorSupportMachineVertex.
            _CONFIG_DATA_SPEED_UP_SIZE_IN_BYTES))

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
                   "machine_graph": "MemoryMachineGraph"})
    @overrides(AbstractGeneratesDataSpecification.generate_data_specification,
               additional_arguments={"routing_info", "machine_graph"})
    def generate_data_specification(
            self, spec, placement, routing_info, machine_graph):
        self._generate_reinjector_functionality_data_specification(spec)
        self._generate_data_speed_up_functionality_data_specification(
            spec, routing_info, machine_graph)
        spec.end_specification()

    def _generate_data_speed_up_functionality_data_specification(
            self, spec, routing_info, machine_graph):
        spec.reserve_memory_region(
            region=self._EXTRA_MONITOR_DSG_REGIONS.DATA_SPEED_CONFIG.value,
            size=self._CONFIG_DATA_SPEED_UP_SIZE_IN_BYTES,
            label="data_speed functionality config region")
        spec.switch_write_focus(
            self._EXTRA_MONITOR_DSG_REGIONS.DATA_SPEED_CONFIG.value)

        if DataSpeedUpPacketGatherMachineVertex.TRAFFIC_TYPE == \
                EdgeTrafficType.MULTICAST:
            base_key = routing_info.get_first_key_for_edge(
                list(machine_graph.get_edges_starting_at_vertex(self))[0])
            spec.write_value(base_key)
        else:
            spec.write_value(DataSpeedUpPacketGatherMachineVertex.BASE_KEY)

    def _generate_reinjector_functionality_data_specification(self, spec):
        spec.reserve_memory_region(
            region=self._EXTRA_MONITOR_DSG_REGIONS.CONFIG.value,
            size=self._CONFIG_REGION_REINEJCTOR_SIZE_IN_BYTES,
            label="re-injection functionality config region")

        spec.switch_write_focus(self._EXTRA_MONITOR_DSG_REGIONS.CONFIG.value)
        for value in [
                self._reinject_multicast, self._reinject_point_to_point,
                self._reinject_fixed_route,
                self._reinject_nearest_neighbour]:
            if value:
                spec.write_value(0)
            else:
                spec.write_value(1)


    def set_router_time_outs(
            self, timeout_mantissa, timeout_exponent, transceiver, placements,
            extra_monitor_cores_to_set):
        """ supports setting of the router time outs for a set of chips via
         their extra monitor cores.

        :param timeout_mantissa: what timeout mantissa to set it to
        :type timeout_exponent: int
        :type timeout_mantissa: int
        :param timeout_exponent: what timeout exponent to set it to
        :param transceiver: the spinnman interface
        :param placements: placements object
        :param extra_monitor_cores_to_set: which vertices to use
        :rtype: None
        """

        core_subsets = self._convert_vertices_to_core_subset(
            extra_monitor_cores_to_set, placements)
        process = SetRouterTimeoutProcess(
            transceiver.scamp_connection_selector)
        process.set_timeout(
            timeout_mantissa, timeout_exponent, core_subsets,
            self._EXTRA_MONITOR_COMMANDS.SET_ROUTER_TIMEOUT)

    def set_reinjection_router_emergency_timeout(
            self, timeout_mantissa, timeout_exponent, transceiver, placements,
            extra_monitor_cores_to_set):
        """ Sets the timeout of the routers

        :param timeout_mantissa: The mantissa of the timeout value, between 0\
                and 15
        :type timeout_mantissa: int
        :param timeout_exponent: The exponent of the timeout value, between 0\
                and 15
        :type timeout_exponent: int
        :param transceiver: the spinnMan instance
        :param placements: the placements object
        :param extra_monitor_cores_to_set: the set of vertices to \
        change the local chip for.
        """
        core_subsets = self._convert_vertices_to_core_subset(
            extra_monitor_cores_to_set, placements)
        process = SetRouterEmergencyTimeoutProcess(
            transceiver.scamp_connection_selector)
        process.set_timeout(
            timeout_mantissa, timeout_exponent, core_subsets,
            self._EXTRA_MONITOR_COMMANDS.SET_ROUTER_EMERGENCY_TIMEOUT)

    def reset_reinjection_counters(
            self, transceiver, placements, extra_monitor_cores_to_set):
        """ Resets the counters for re injection
        """
        core_subsets = self._convert_vertices_to_core_subset(
            extra_monitor_cores_to_set, placements)
        process = ResetCountersProcess(transceiver.scamp_connection_selector)
        process.reset_counters(
            core_subsets, self._EXTRA_MONITOR_COMMANDS.RESET_COUNTERS)

    def get_reinjection_status(self, placements, transceiver):
        """ gets the reinjection status from this extra monitor vertex

        :param transceiver: the spinnMan interface
        :param placements: the placements object
        :return: the reinjection status for this vertex
        """
        placement = placements.get_placement_of_vertex(self)
        process = ReadStatusProcess(transceiver.scamp_connection_selector)
        return process.get_reinjection_status(
            placement.x, placement.y, placement.p,
            self._EXTRA_MONITOR_COMMANDS.GET_STATUS)

    def get_reinjection_status_for_vertices(
            self, placements, extra_monitor_cores_for_data, transceiver):
        """ gets the reinjection status from a set of extra monitor cores

        :param placements: the placements object
        :param extra_monitor_cores_for_data: the extra monitor cores to get\
         status from
        :param transceiver: the spinnMan interface
        :rtype: None
        """
        core_subsets = self._convert_vertices_to_core_subset(
            extra_monitor_cores_for_data, placements)
        process = ReadStatusProcess(transceiver.scamp_connection_selector)
        return process.get_reinjection_status_for_core_subsets(
            core_subsets, self._EXTRA_MONITOR_COMMANDS.GET_STATUS)

    def set_reinjection_packets(
            self, placements, transceiver, point_to_point=None, multicast=None,
            nearest_neighbour=None, fixed_route=None):
        """

        :param placements: placements object
        :param transceiver: spinnman instance
        :param point_to_point: bool stating if point to point should be set,\
         or None if left as before
        :param multicast: bool stating if multicast should be set,\
         or None if left as before
        :param nearest_neighbour: bool stating if nearest neighbour should be \
        set, or None if left as before
        :param fixed_route: bool stating if fixed route should be set, or \
        None if left as before.
        :rtype: None
        """
        if multicast is not None:
            self._reinject_multicast = multicast
        if point_to_point is not None:
            self._reinject_point_to_point = point_to_point
        if nearest_neighbour is not None:
            self._reinject_nearest_neighbour = nearest_neighbour
        if fixed_route is not None:
            self._reinject_fixed_route = fixed_route

        placement = placements.get_placement_of_vertex(self)
        core_subsets = CoreSubsets()
        core_subsets.add_processor(placement.x, placement.y, placement.p)
        process = SetPacketTypesProcess(transceiver.scamp_connection_selector)
        process.set_packet_types(
            core_subsets, self._reinject_point_to_point,
            self._reinject_multicast, self._reinject_nearest_neighbour,
            self._reinject_fixed_route,
            self._EXTRA_MONITOR_COMMANDS.GET_STATUS)

    @staticmethod
    def _convert_vertices_to_core_subset(
            extra_monitor_cores_to_set, placements):
        """ converts vertices into core subsets.

        :param extra_monitor_cores_to_set: the vertices to convert to core \
        subsets
        :param placements: the placements object
        :return: the converts CoreSubSets to the vertices
        """
        core_subsets = CoreSubsets()
        for vertex in extra_monitor_cores_to_set:
            if not isinstance(vertex, ExtraMonitorSupportMachineVertex):
                raise Exception(
                    "can only use ExtraMonitorSupportMachineVertex to set "
                    "the router time out")
            placement = placements.get_placement_of_vertex(vertex)
            core_subsets.add_processor(placement.x, placement.y, placement.p)
        return core_subsets


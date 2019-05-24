from enum import Enum
from spinn_utilities.overrides import overrides
from pacman.executor.injection_decorator import inject_items
from pacman.model.graphs.common import EdgeTrafficType
from pacman.model.graphs.machine import MachineVertex
from pacman.model.resources import ConstantSDRAM, ResourceContainer
from spinn_front_end_common.abstract_models import (
    AbstractHasAssociatedBinary, AbstractGeneratesDataSpecification)
from spinn_front_end_common.utilities import globals_variables
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.utilities.utility_objs.\
    extra_monitor_scp_processes import (
        ReadStatusProcess, ResetCountersProcess, SetPacketTypesProcess,
        SetRouterEmergencyTimeoutProcess, SetRouterTimeoutProcess,
        ClearQueueProcess)
from spinn_front_end_common.utilities.constants import (
    SARK_PER_MALLOC_SDRAM_USAGE, DATA_SPECABLE_BASIC_SETUP_INFO_N_BYTES)
from .data_speed_up_packet_gatherer_machine_vertex import (
    DataSpeedUpPacketGatherMachineVertex)
from spinn_front_end_common.utilities.helpful_functions import (
    convert_vertices_to_core_subset)


class ExtraMonitorSupportMachineVertex(
        MachineVertex, AbstractHasAssociatedBinary,
        AbstractGeneratesDataSpecification):

    __slots__ = (
        # if we reinject multicast packets
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
    _CONFIG_DATA_SPEED_UP_SIZE_IN_BYTES = 4 * 4
    _CONFIG_MAX_EXTRA_SEQ_NUM_SIZE_IN_BYTES = 460 * 1024

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
        :param reinject_fixed_route: if we reinject fixed route packets
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
        return ResourceContainer(sdram=ConstantSDRAM(
            sdram=ExtraMonitorSupportMachineVertex.
            _CONFIG_REGION_REINEJCTOR_SIZE_IN_BYTES +
            ExtraMonitorSupportMachineVertex.
            _CONFIG_DATA_SPEED_UP_SIZE_IN_BYTES +
            ExtraMonitorSupportMachineVertex.
            _CONFIG_MAX_EXTRA_SEQ_NUM_SIZE_IN_BYTES +
            # Data spec size
            DATA_SPECABLE_BASIC_SETUP_INFO_N_BYTES +
            # One malloc for extra sequence numbers
            SARK_PER_MALLOC_SDRAM_USAGE))

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
            self, spec, placement,  # @UnusedVariable
            routing_info, machine_graph):
        # pylint: disable=arguments-differ
        self._generate_reinjection_functionality_data_specification(spec)
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
        spec.reserve_memory_region(
            region=self._EXTRA_MONITOR_DSG_REGIONS.CONFIG.value,
            size=self._CONFIG_REGION_REINEJCTOR_SIZE_IN_BYTES,
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
        :param placements: placements object
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

    def set_reinjection_router_emergency_timeout(
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
        :param placements: the placements object
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
        """ Resets the counters for re injection
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
        """ Get the reinjection status from this extra monitor vertex

        :param transceiver: the spinnMan interface
        :param placements: the placements object
        :return: the reinjection status for this vertex
        """
        placement = placements.get_placement_of_vertex(self)
        process = ReadStatusProcess(transceiver.scamp_connection_selector)
        return process.get_reinjection_status(
            placement.x, placement.y, placement.p)

    def get_reinjection_status_for_vertices(
            self, placements, extra_monitor_cores_for_data, transceiver):
        """ Get the reinjection status from a set of extra monitor cores

        :param placements: the placements object
        :param extra_monitor_cores_for_data: \
            the extra monitor cores to get status from
        :param transceiver: the spinnMan interface
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
        :param extra_monitor_cores_for_data: \
            the extra monitor cores to set the packets of
        :param transceiver: spinnman instance
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

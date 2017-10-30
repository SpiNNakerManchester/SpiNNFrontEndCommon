from enum import Enum

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
    extra_monitor_scp_processes.set_router_emergency_timeout_process import \
    SetRouterEmergencyTimeoutProcess
from spinn_front_end_common.utilities.utility_objs.\
    extra_monitor_scp_processes.set_router_timeout_process import \
    SetRouterTimeoutProcess
from spinn_machine import CoreSubsets
from spinn_utilities.overrides import overrides


class ExtraMonitorSupportMachineVertex(
        MachineVertex, AbstractHasAssociatedBinary,
        AbstractGeneratesDataSpecification):

    __slots__ = (

        # if we reinject mc packets
        "_reinject_multicast",

        # if we reinject point to point packets
        "reinject_point_to_point",

        # if we reinject nearest neighbour packets
        "reinject_nearest_neighbour",

        # if we reinject fixed route packets
        "reinject_fixed_route"
    )

    _EXTRA_MONITOR_DSG_REGIONS = Enum(
        value="_EXTRA_MONITOR_DSG_REGIONS",
        names=[('CONFIG', 0)])

    _CONFIG_REGION_SIZE_IN_BYTES = 4 * 4

    EXTRA_MONITOR_COMMANDS = Enum(
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
    @overrides(MachineVertex.resources_required)
    def resources_required(self):
        return self.static_resources_required()

    @staticmethod
    def static_resources_required():
        return ResourceContainer(sdram=SDRAMResource(
            sdram=ExtraMonitorSupportMachineVertex.
            _CONFIG_REGION_SIZE_IN_BYTES))

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return self.static_get_binary_start_type()

    @staticmethod
    def static_get_binary_start_type():
        return ExecutableType.RUNNING

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return self.static_get_binary_file_name()

    @staticmethod
    def static_get_binary_file_name():
        return "extra_monitor_support.aplx"

    @overrides(AbstractGeneratesDataSpecification.generate_data_specification)
    def generate_data_specification(self, spec, placement):
        spec.reserve_memory_region(
            region=self._EXTRA_MONITOR_DSG_REGIONS.CONFIG.value(),
            size=self._CONFIG_REGION_SIZE_IN_BYTES,
            label="re-injection functionality config region")
        spec.switch_write_focus(self._EXTRA_MONITOR_DSG_REGIONS.CONFIG.value())
        spec.write_value(self._reinject_multicast)
        spec.write_value(self._reinject_point_to_point)
        spec.write_value(self._reinject_fixed_route)
        spec.write_value(self._reinject_nearest_neighbour)
        spec.end_specification()

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
        process.set_timeout(timeout_mantissa, timeout_exponent, core_subsets)

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
        :param extra_monitor_cores_to_set: the set of vertices to 
        change the local chip for.
        """
        core_subsets = self._convert_vertices_to_core_subset(
            extra_monitor_cores_to_set, placements)
        process = SetRouterEmergencyTimeoutProcess(
            transceiver.scamp_connection_selector)
        process.set_timeout(timeout_mantissa, timeout_exponent, core_subsets)

    def reset_reinjection_counters(
            self, transceiver, placements, extra_monitor_cores_to_set):
        """ Resets the counters for re injection
        """
        core_subsets = self._convert_vertices_to_core_subset(
            extra_monitor_cores_to_set, placements)
        process = ResetCountersProcess(transceiver.scamp_connection_selector)
        process.reset_counters(core_subsets)

    def get_reinjection_status(self, placements, transceiver):
        """ gets the reinjection status from this extra monitor vertex
        
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
        core_subsets = self._convert_vertices_to_core_subset(
            extra_monitor_cores_for_data, placements)
        process = ReadStatusProcess(transceiver.scamp_connection_selector)
        return process.get_reinjection_status_for_core_subsets(core_subsets)



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

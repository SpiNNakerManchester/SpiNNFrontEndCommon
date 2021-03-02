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

from enum import Enum
import logging
from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides
from spinn_machine import CoreSubsets, Router
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
        SetRouterTimeoutProcess, ClearQueueProcess,
        LoadApplicationMCRoutesProcess, LoadSystemMCRoutesProcess)
from spinn_front_end_common.utilities.constants import (
    SARK_PER_MALLOC_SDRAM_USAGE, DATA_SPECABLE_BASIC_SETUP_INFO_N_BYTES,
    BYTES_PER_WORD, BYTES_PER_KB)
from spinn_front_end_common.utilities.helpful_functions import (
    convert_vertices_to_core_subset)
from spinn_front_end_common.utilities.emergency_recovery import (
    emergency_recover_state_from_failure)
from .data_speed_up_packet_gatherer_machine_vertex import (
    DataSpeedUpPacketGatherMachineVertex as
    Gatherer)

log = FormatAdapter(logging.getLogger(__name__))

_CONFIG_REGION_REINJECTOR_SIZE_IN_BYTES = 5 * BYTES_PER_WORD
#: 1.new seq key, 2.first data key, 3. transaction id key 4.end flag key,
# 5.base key
_CONFIG_DATA_SPEED_UP_SIZE_IN_BYTES = 5 * BYTES_PER_WORD
_CONFIG_MAX_EXTRA_SEQ_NUM_SIZE_IN_BYTES = 460 * BYTES_PER_KB
_CONFIG_DATA_IN_KEYS_SDRAM_IN_BYTES = 3 * BYTES_PER_WORD
_MAX_DATA_SIZE_FOR_DATA_IN_MULTICAST_ROUTING = ((49 * 3) + 1) * BYTES_PER_WORD
_BIT_SHIFT_TO_MOVE_APP_ID = 24

# cap for stopping wrap arounds
TRANSACTION_ID_CAP = 0xFFFFFFFF

# SDRAM requirement for containing router table entries
# 16 bytes per entry:
# 4 for a key, 4 for mask,
# 4 for word alignment for 18 cores and 6 links
# (24 bits, for word aligning)
_SDRAM_FOR_ROUTER_TABLE_ENTRIES = 1024 * 4 * BYTES_PER_WORD


class _DSG_REGIONS(Enum):
    REINJECT_CONFIG = 0
    DATA_OUT_CONFIG = 1
    DATA_IN_CONFIG = 2


class _KEY_OFFSETS(Enum):
    ADDRESS_KEY_OFFSET = 0
    DATA_KEY_OFFSET = 1
    BOUNDARY_KEY_OFFSET = 2


class ExtraMonitorSupportMachineVertex(
        MachineVertex, AbstractHasAssociatedBinary,
        AbstractGeneratesDataSpecification):
    """ Machine vertex for talking to extra monitor cores. \
        Supports reinjection control and the faster data transfer protocols.

    Usually deployed once per chip.
    """

    __slots__ = (
        # if we reinject multicast packets
        "_reinject_multicast",
        # if we reinject point to point packets
        "_reinject_point_to_point",
        # if we reinject nearest neighbour packets
        "_reinject_nearest_neighbour",
        # if we reinject fixed route packets
        "_reinject_fixed_route",
        # placement holder for ease of access
        "_placement",
        # app id, used for reporting failures on system core RTE
        "_app_id",
        # machine instance
        "_machine",
        # the local transaction id
        "_transaction_id"
    )

    def __init__(
            self, constraints, app_vertex,
            reinject_multicast=None, reinject_point_to_point=False,
            reinject_nearest_neighbour=False, reinject_fixed_route=False):
        """
        :param constraints: constraints on this vertex
        :type constraints:
            iterable(~pacman.model.constraints.AbstractConstraint)
        :param bool reinject_multicast:
            if we reinject multicast packets; defaults to value of
            `enable_reinjection` setting in configuration file
        :param bool reinject_point_to_point:
            if we reinject point-to-point packets
        :param bool reinject_nearest_neighbour:
            if we reinject nearest-neighbour packets
        :param bool reinject_fixed_route: if we reinject fixed route packets
        """
        # pylint: disable=too-many-arguments
        super().__init__(
            label="SYSTEM:ExtraMonitor", constraints=constraints,
            app_vertex=app_vertex)

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
        self._app_id = None
        self._machine = None
        self._transaction_id = 0

    @property
    def reinject_multicast(self):
        """
        :rtype: bool
        """
        return self._reinject_multicast

    @property
    def transaction_id(self):
        return self._transaction_id

    def update_transaction_id(self):
        self._transaction_id = (self._transaction_id + 1) & TRANSACTION_ID_CAP

    def update_transaction_id_from_machine(self, txrx):
        """ looks up from the machine what the current transaction id is
        and updates the extra monitor.

        :param txrx: SpiNNMan instance
        :rtype: None
        """
        self._transaction_id = txrx.read_user_1(
            self._placement.x, self._placement.y, self._placement.p)

    @property
    def reinject_point_to_point(self):
        """
        :rtype: bool
        """
        return self._reinject_point_to_point

    @property
    def reinject_nearest_neighbour(self):
        """
        :rtype: bool
        """
        return self._reinject_nearest_neighbour

    @property
    def reinject_fixed_route(self):
        """
        :rtype: bool
        """
        return self._reinject_fixed_route

    @property
    @overrides(MachineVertex.resources_required)
    def resources_required(self):
        return self.static_resources_required()

    @property
    def placement(self):
        """
        :rtype: ~pacman.model.placements.Placement
        """
        return self._placement

    @staticmethod
    def static_resources_required():
        """ The resources required by this vertex.

        :rtype: ~pacman.model.resources.ResourceContainer
        """
        return ResourceContainer(sdram=ConstantSDRAM(
            _CONFIG_REGION_REINJECTOR_SIZE_IN_BYTES +
            _CONFIG_DATA_SPEED_UP_SIZE_IN_BYTES +
            _CONFIG_MAX_EXTRA_SEQ_NUM_SIZE_IN_BYTES +
            # Data spec size
            DATA_SPECABLE_BASIC_SETUP_INFO_N_BYTES +
            # One malloc for extra sequence numbers
            SARK_PER_MALLOC_SDRAM_USAGE +
            _MAX_DATA_SIZE_FOR_DATA_IN_MULTICAST_ROUTING +
            _SDRAM_FOR_ROUTER_TABLE_ENTRIES +
            _CONFIG_DATA_IN_KEYS_SDRAM_IN_BYTES))

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return self.static_get_binary_start_type()

    @staticmethod
    def static_get_binary_start_type():
        """ The type of the binary implementing this vertex.

        :rtype: ExecutableType
        """
        return ExecutableType.SYSTEM

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return self.static_get_binary_file_name()

    @staticmethod
    def static_get_binary_file_name():
        """ The name of the binary implementing this vertex.

        :rtype: str
        """
        return "extra_monitor_support.aplx"

    @inject_items({"routing_info": "MemoryRoutingInfos",
                   "machine_graph": "MemoryMachineGraph",
                   "data_in_routing_tables": "DataInMulticastRoutingTables",
                   "mc_data_chips_to_keys": "DataInMulticastKeyToChipMap",
                   "app_id": "APPID",
                   "machine": "MemoryExtendedMachine",
                   "router_timeout_keys": "SystemMulticastRouterTimeoutKeys"})
    @overrides(AbstractGeneratesDataSpecification.generate_data_specification,
               additional_arguments={
                   "routing_info", "machine_graph", "data_in_routing_tables",
                   "mc_data_chips_to_keys", "app_id", "machine",
                   "router_timeout_keys"})
    def generate_data_specification(
            self, spec, placement, routing_info, machine_graph,
            data_in_routing_tables, mc_data_chips_to_keys, app_id,
            machine, router_timeout_keys):
        """
        :param ~pacman.model.routing_info.RoutingInfo routing_info: (injected)
        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
            (injected)
        :param data_in_routing_tables: (injected)
        :type data_in_routing_tables:
            ~pacman.model.routing_tables.MulticastRoutingTables
        :param dict(tuple(int,int),int) mc_data_chips_to_keys: (injected)
        :param int app_id: (injected)
        :param ~spinn_machine.Machine machine: (injected)
        """
        # pylint: disable=arguments-differ
        # storing for future usage
        self._placement = placement
        self._app_id = app_id
        self._machine = machine
        # write reinjection config
        self._generate_reinjection_config(
            spec, router_timeout_keys, placement, machine)
        # write data speed up out config
        self._generate_data_speed_up_out_config(
            spec, routing_info, machine_graph)
        # write data speed up in config
        self._generate_data_speed_up_in_config(
            spec, data_in_routing_tables,
            machine.get_chip_at(placement.x, placement.y),
            mc_data_chips_to_keys)
        spec.end_specification()

    def _generate_data_speed_up_out_config(
            self, spec, routing_info, machine_graph):
        """
        :param ~.DataSpecificationGenerator spec: spec file
        :param ~.RoutingInfo routing_info: the packet routing info
        :param ~.MachineGraph machine_graph: The graph containing this vertex
        """
        spec.reserve_memory_region(
            region=_DSG_REGIONS.DATA_OUT_CONFIG.value,
            size=_CONFIG_DATA_SPEED_UP_SIZE_IN_BYTES,
            label="data speed-up out config region")
        spec.switch_write_focus(_DSG_REGIONS.DATA_OUT_CONFIG.value)

        if Gatherer.TRAFFIC_TYPE == EdgeTrafficType.MULTICAST:
            base_key = routing_info.get_first_key_for_edge(
                list(machine_graph.get_edges_starting_at_vertex(self))[0])
            spec.write_value(base_key)
            spec.write_value(base_key + Gatherer.NEW_SEQ_KEY_OFFSET)
            spec.write_value(base_key + Gatherer.FIRST_DATA_KEY_OFFSET)
            spec.write_value(base_key + Gatherer.TRANSACTION_ID_KEY_OFFSET)
            spec.write_value(base_key + Gatherer.END_FLAG_KEY_OFFSET)
        else:
            spec.write_value(Gatherer.BASE_KEY)
            spec.write_value(Gatherer.NEW_SEQ_KEY)
            spec.write_value(Gatherer.FIRST_DATA_KEY)
            spec.write_value(Gatherer.TRANSACTION_ID_KEY)
            spec.write_value(Gatherer.END_FLAG_KEY)

    def _generate_reinjection_config(
            self, spec, router_timeout_keys, placement, machine):
        """
        :param ~.DataSpecificationGenerator spec: spec file
        :param dict(tuple(int,int),int) router_timeout_keys:
        :param ~.Placement placement:
        :param ~.Machine machine:
        """
        spec.reserve_memory_region(
            region=_DSG_REGIONS.REINJECT_CONFIG.value,
            size=_CONFIG_REGION_REINJECTOR_SIZE_IN_BYTES,
            label="re-injection config region")

        spec.switch_write_focus(_DSG_REGIONS.REINJECT_CONFIG.value)
        for value in [
                self._reinject_multicast, self._reinject_point_to_point,
                self._reinject_fixed_route,
                self._reinject_nearest_neighbour]:
            # Note that this is inverted! Why... I dunno!
            spec.write_value(int(not value))

        # add the reinjection mc interface
        chip = machine.get_chip_at(placement.x, placement.y)
        reinjector_base_mc_key = (
            router_timeout_keys[
                (chip.nearest_ethernet_x, chip.nearest_ethernet_y)])
        spec.write_value(reinjector_base_mc_key)

    def _generate_data_speed_up_in_config(
            self, spec, data_in_routing_tables, chip, mc_data_chips_to_keys):
        """
        :param ~.DataSpecificationGenerator spec: spec file
        :param ~.MulticastRoutingTables data_in_routing_tables:
            routing tables for all chips
        :param ~.Chip chip: the chip where this monitor will run
        :param dict(tuple(int,int),int) mc_data_chips_to_keys:
            data in keys to chips map.
        """
        spec.reserve_memory_region(
            region=_DSG_REGIONS.DATA_IN_CONFIG.value,
            size=(_MAX_DATA_SIZE_FOR_DATA_IN_MULTICAST_ROUTING +
                  _CONFIG_DATA_IN_KEYS_SDRAM_IN_BYTES),
            label="data speed-up in config region")
        spec.switch_write_focus(_DSG_REGIONS.DATA_IN_CONFIG.value)

        # write address key and data key
        base_key = mc_data_chips_to_keys[chip.x, chip.y]
        spec.write_value(base_key + _KEY_OFFSETS.ADDRESS_KEY_OFFSET.value)
        spec.write_value(base_key + _KEY_OFFSETS.DATA_KEY_OFFSET.value)
        spec.write_value(base_key + _KEY_OFFSETS.BOUNDARY_KEY_OFFSET.value)

        # write table entries
        table = data_in_routing_tables.get_routing_table_for_chip(
            chip.x, chip.y)
        spec.write_value(table.number_of_entries)
        for entry in table.multicast_routing_entries:
            spec.write_value(entry.routing_entry_key)
            spec.write_value(entry.mask)
            spec.write_value(self.__encode_route(entry))

    def __encode_route(self, entry):
        """
        :param ~spinn_machine.MulticastRoutingEntry entry:
        :rtype: int
        """
        route = self._app_id << _BIT_SHIFT_TO_MOVE_APP_ID
        route |= Router.convert_routing_table_entry_to_spinnaker_route(entry)
        return route

    def set_router_wait1_timeout(
            self, timeout, transceiver, placements,
            extra_monitor_cores_to_set):
        """ Supports setting of the router time outs for a set of chips via\
            their extra monitor cores. This sets the timeout for the time\
            between when a packet arrives and when it starts to be emergency\
            routed. (Actual emergency routing is disabled by default.)

        :param tuple(int,int) timeout:
            The mantissa and exponent of the timeout value, each between
            0 and 15
        :param ~spinnman.transceiver.Transceiver transceiver:
            the spinnman interface
        :param ~pacman.model.placements.Placements placements:
            vertex placements
        :param extra_monitor_cores_to_set:
            which monitors control the routers to set the timeout of
        :type extra_monitor_cores_to_set:
            iterable(ExtraMonitorSupportMachineVertex)
        """
        mantissa, exponent = timeout
        core_subsets = convert_vertices_to_core_subset(
            extra_monitor_cores_to_set, placements)
        process = SetRouterTimeoutProcess(
            transceiver.scamp_connection_selector)
        try:
            process.set_wait1_timeout(mantissa, exponent, core_subsets)
        except:  # noqa: E722
            emergency_recover_state_from_failure(
                transceiver, self._app_id, self,
                placements.get_placement_of_vertex(self))
            raise

    def set_router_wait2_timeout(
            self, timeout, transceiver, placements,
            extra_monitor_cores_to_set):
        """ Supports setting of the router time outs for a set of chips via\
            their extra monitor cores. This sets the timeout for the time\
            between when a packet starts to be emergency routed and when it\
            is dropped. (Actual emergency routing is disabled by default.)

        :param tuple(int,int) timeout:
            The mantissa and exponent of the timeout value, each between
            0 and 15
        :param ~spinnman.transceiver.Transceiver transceiver:
            the spinnMan instance
        :param ~pacman.model.placements.Placements placements:
            vertex placements
        :param extra_monitor_cores_to_set:
            which monitors control the routers to set the timeout of
        :type extra_monitor_cores_to_set:
            iterable(ExtraMonitorSupportMachineVertex)
        """
        mantissa, exponent = timeout
        core_subsets = convert_vertices_to_core_subset(
            extra_monitor_cores_to_set, placements)
        process = SetRouterTimeoutProcess(
            transceiver.scamp_connection_selector)
        try:
            process.set_wait2_timeout(mantissa, exponent, core_subsets)
        except:  # noqa: E722
            emergency_recover_state_from_failure(
                transceiver, self._app_id, self,
                placements.get_placement_of_vertex(self))
            raise

    def reset_reinjection_counters(
            self, transceiver, placements, extra_monitor_cores_to_set):
        """ Resets the counters for reinjection

        :param ~spinnman.transceiver.Transceiver transceiver:
            the spinnMan interface
        :param ~pacman.model.placements.Placements placements:
            the placements object
        :param extra_monitor_cores_to_set:
            which monitors control the routers to reset the counters of
        :type extra_monitor_cores_to_set:
            iterable(ExtraMonitorSupportMachineVertex)
        """
        core_subsets = convert_vertices_to_core_subset(
            extra_monitor_cores_to_set, placements)
        process = ResetCountersProcess(transceiver.scamp_connection_selector)
        try:
            process.reset_counters(core_subsets)
        except:  # noqa: E722
            emergency_recover_state_from_failure(
                transceiver, self._app_id, self,
                placements.get_placement_of_vertex(self))
            raise

    def clear_reinjection_queue(
            self, transceiver, placements, extra_monitor_cores_to_set):
        """ Clears the queues for reinjection

        :param ~spinnman.transceiver.Transceiver transceiver:
            the spinnMan interface
        :param ~pacman.model.placements.Placements placements:
            the placements object
        :param extra_monitor_cores_to_set:
            Which extra monitors need to clear their queues.
        :type extra_monitor_cores_to_set:
            iterable(ExtraMonitorSupportMachineVertex)
        """
        core_subsets = convert_vertices_to_core_subset(
            extra_monitor_cores_to_set, placements)
        process = ClearQueueProcess(transceiver.scamp_connection_selector)
        try:
            process.reset_counters(core_subsets)
        except:  # noqa: E722
            emergency_recover_state_from_failure(
                transceiver, self._app_id, self,
                placements.get_placement_of_vertex(self))
            raise

    def get_reinjection_status(self, placements, transceiver):
        """ Get the reinjection status from this extra monitor vertex

        :param ~spinnman.transceiver.Transceiver transceiver:
            the spinnMan interface
        :param ~pacman.model.placements.Placements placements:
            the vertex placements
        :return: the reinjection status for this vertex
        :rtype: ReInjectionStatus
        """
        placement = placements.get_placement_of_vertex(self)
        process = ReadStatusProcess(transceiver.scamp_connection_selector)
        try:
            return process.get_reinjection_status(
                placement.x, placement.y, placement.p)
        except:  # noqa: E722
            emergency_recover_state_from_failure(
                transceiver, self._app_id, self, placement)
            raise

    def get_reinjection_status_for_vertices(
            self, placements, extra_monitor_cores_for_data, transceiver):
        """ Get the reinjection status from a set of extra monitor cores

        :param ~pacman.model.placements.Placements placements:
            the placements object
        :param extra_monitor_cores_for_data:
            the extra monitor cores to get status from
        :type extra_monitor_cores_for_data:
            iterable(ExtraMonitorSupportMachineVertex)
        :param ~spinnman.transceiver.Transceiver transceiver:
            the spinnMan interface
        :rtype: dict(tuple(int,int), ReInjectionStatus)
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
        :param ~pacman.model.placements.Placements placements:
            placements object
        :param extra_monitor_cores_for_data:
            the extra monitor cores to set the packets of
        :type extra_monitor_cores_for_data:
            iterable(ExtraMonitorSupportMachineVertex)
        :param ~spinnman.transceiver.Transceiver transceiver: spinnman instance
        :param point_to_point:
            If point to point should be set, or None if left as before
        :type point_to_point: bool or None
        :param multicast:
            If multicast should be set, or None if left as before
        :type multicast: bool or None
        :param nearest_neighbour:
            If nearest neighbour should be set, or None if left as before
        :type nearest_neighbour: bool or None
        :param fixed_route:
            If fixed route should be set, or None if left as before.
        :type fixed_route: bool or None
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
        try:
            process.set_packet_types(
                core_subsets, self._reinject_point_to_point,
                self._reinject_multicast, self._reinject_nearest_neighbour,
                self._reinject_fixed_route)
        except:  # noqa: E722
            emergency_recover_state_from_failure(
                transceiver, self._app_id, self,
                placements.get_placement_of_vertex(self))
            raise

    def load_system_mc_routes(
            self, placements, extra_monitor_cores_for_data, transceiver):
        """ Get the extra monitor cores to load up the system-based \
            multicast routes (used by data in).

        :param ~pacman.model.placements.Placements placements:
            the placements object
        :param extra_monitor_cores_for_data:
            the extra monitor cores to get status from
        :type extra_monitor_cores_for_data:
            iterable(ExtraMonitorSupportMachineVertex)
        :param ~spinnman.transceiver.Transceiver transceiver:
            the spinnMan interface
        """
        core_subsets = self._convert_vertices_to_core_subset(
            extra_monitor_cores_for_data, placements)
        process = LoadSystemMCRoutesProcess(
            transceiver.scamp_connection_selector)
        try:
            return process.load_system_mc_routes(core_subsets)
        except:  # noqa: E722
            emergency_recover_state_from_failure(
                transceiver, self._app_id, self,
                placements.get_placement_of_vertex(self))
            raise

    def load_application_mc_routes(
            self, placements, extra_monitor_cores_for_data, transceiver):
        """ Get the extra monitor cores to load up the application-based\
            multicast routes (used by data in).

        :param ~pacman.model.placements.Placements placements:
            the placements object
        :param extra_monitor_cores_for_data:
            the extra monitor cores to get status from
        :type extra_monitor_cores_for_data:
            iterable(ExtraMonitorSupportMachineVertex)
        :param ~spinnman.transceiver.Transceiver transceiver:
            the spinnMan interface
        """
        core_subsets = self._convert_vertices_to_core_subset(
            extra_monitor_cores_for_data, placements)
        process = LoadApplicationMCRoutesProcess(
            transceiver.scamp_connection_selector)
        try:
            return process.load_application_mc_routes(core_subsets)
        except:  # noqa: E722
            emergency_recover_state_from_failure(
                transceiver, self._app_id, self,
                placements.get_placement_of_vertex(self))
            raise

    @staticmethod
    def _convert_vertices_to_core_subset(extra_monitor_cores, placements):
        """ Convert vertices into the subset of cores where they've been\
            placed.

        :param iterable(ExtraMonitorSupportMachineVertex) extra_monitor_cores:
            the vertices to convert to core subsets
        :param ~.Placements placements: the placements object
        :return: where the vertices have been placed
        :rtype: ~.CoreSubsets
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

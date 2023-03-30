# Copyright (c) 2017 The University of Manchester
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

from enum import Enum, IntEnum
import logging
import struct
from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides
from spinn_machine import CoreSubsets, Router
from pacman.model.graphs.machine import MachineVertex
from pacman.model.resources import ConstantSDRAM
from spinn_utilities.config_holder import get_config_bool
from spinn_front_end_common.abstract_models import (
    AbstractHasAssociatedBinary, AbstractGeneratesDataSpecification)
from spinn_front_end_common.data import FecDataView
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
    convert_vertices_to_core_subset, get_region_base_address_offset)
from spinn_front_end_common.utilities.emergency_recovery import (
    emergency_recover_state_from_failure)
from .data_speed_up_packet_gatherer_machine_vertex import (
    DataSpeedUpPacketGatherMachineVertex as
    Gatherer)
from spinn_front_end_common.interface.provenance import (
    AbstractProvidesProvenanceDataFromMachine, ProvenanceWriter)

log = FormatAdapter(logging.getLogger(__name__))

_CONFIG_REGION_REINJECTOR_SIZE_IN_BYTES = 5 * BYTES_PER_WORD
#: 1.new seq key, 2.first data key, 3. transaction id key 4.end flag key,
# 5.base key
_CONFIG_DATA_SPEED_UP_SIZE_IN_BYTES = 5 * BYTES_PER_WORD
_CONFIG_MAX_EXTRA_SEQ_NUM_SIZE_IN_BYTES = 460 * BYTES_PER_KB
_CONFIG_DATA_IN_KEYS_SDRAM_IN_BYTES = 3 * BYTES_PER_WORD
_MAX_DATA_SIZE_FOR_DATA_IN_MULTICAST_ROUTING = ((49 * 3) + 1) * BYTES_PER_WORD
_BIT_SHIFT_TO_MOVE_APP_ID = 24

_ONE_WORD = struct.Struct("<I")
# typedef struct extra_monitor_provenance_t {
#     uint n_sdp_packets;
#     uint n_in_streams;
#     uint n_out_streams;
#     uint n_router_changes;
# } extra_monitor_provenance_t;
_PROVENANCE_FORMAT = struct.Struct("<IIII")

# cap for stopping wrap arounds
TRANSACTION_ID_CAP = 0xFFFFFFFF

# SDRAM requirement for containing router table entries
# 16 bytes per entry:
# 4 for a key, 4 for mask,
# 4 for word alignment for 18 cores and 6 links
# (24 bits, for word aligning)
_SDRAM_FOR_ROUTER_TABLE_ENTRIES = 1024 * 4 * BYTES_PER_WORD


class _DSG_REGIONS(IntEnum):
    REINJECT_CONFIG = 0
    DATA_OUT_CONFIG = 1
    DATA_IN_CONFIG = 2
    PROVENANCE_AREA = 3


class _KEY_OFFSETS(Enum):
    ADDRESS_KEY_OFFSET = 0
    DATA_KEY_OFFSET = 1
    BOUNDARY_KEY_OFFSET = 2


class ExtraMonitorSupportMachineVertex(
        MachineVertex, AbstractHasAssociatedBinary,
        AbstractGeneratesDataSpecification,
        AbstractProvidesProvenanceDataFromMachine):
    """
    Machine vertex for talking to extra monitor cores.
    Supports reinjection control and the faster data transfer protocols.

    Usually deployed once per chip.

    .. note::
        This is an unusual machine vertex, in that it has no associated
        application vertex.
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
        # the local transaction id
        "_transaction_id",
        # provenance region address
        "_prov_region"
    )

    def __init__(
            self, reinject_point_to_point=False,
            reinject_nearest_neighbour=False, reinject_fixed_route=False):
        """
        :param bool reinject_point_to_point:
            if we reinject point-to-point packets
        :param bool reinject_nearest_neighbour:
            if we reinject nearest-neighbour packets
        :param bool reinject_fixed_route: if we reinject fixed route packets
        """
        # pylint: disable=too-many-arguments
        super().__init__(
            label="SYSTEM:ExtraMonitor", app_vertex=None)

        self._reinject_multicast = get_config_bool(
            "Machine", "enable_reinjection")
        self._reinject_point_to_point = reinject_point_to_point
        self._reinject_nearest_neighbour = reinject_nearest_neighbour
        self._reinject_fixed_route = reinject_fixed_route
        # placement holder for ease of access
        self._placement = None
        self._app_id = None
        self._transaction_id = 0
        self._prov_region = None

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

    def update_transaction_id_from_machine(self):
        """
        Looks up from the machine what the current transaction id is
        and updates the extra monitor.
        """
        self._transaction_id = FecDataView.get_transceiver().read_user_1(
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
    @overrides(MachineVertex.sdram_required)
    def sdram_required(self):
        return ConstantSDRAM(
            _CONFIG_REGION_REINJECTOR_SIZE_IN_BYTES +
            _CONFIG_DATA_SPEED_UP_SIZE_IN_BYTES +
            _CONFIG_MAX_EXTRA_SEQ_NUM_SIZE_IN_BYTES +
            # Data spec size
            DATA_SPECABLE_BASIC_SETUP_INFO_N_BYTES +
            # One malloc for extra sequence numbers
            SARK_PER_MALLOC_SDRAM_USAGE +
            _MAX_DATA_SIZE_FOR_DATA_IN_MULTICAST_ROUTING +
            _SDRAM_FOR_ROUTER_TABLE_ENTRIES +
            _CONFIG_DATA_IN_KEYS_SDRAM_IN_BYTES)

    @property
    def placement(self):
        """
        :rtype: ~pacman.model.placements.Placement
        """
        return self._placement

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return self.static_get_binary_start_type()

    @staticmethod
    def static_get_binary_start_type():
        """
        The type of the binary implementing this vertex.

        :rtype: ExecutableType
        """
        return ExecutableType.SYSTEM

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return self.static_get_binary_file_name()

    @staticmethod
    def static_get_binary_file_name():
        """
        The name of the binary implementing this vertex.

        :rtype: str
        """
        return "extra_monitor_support.aplx"

    @overrides(AbstractGeneratesDataSpecification.generate_data_specification)
    def generate_data_specification(self, spec, placement):
        # storing for future usage
        self._placement = placement
        self._app_id = FecDataView.get_app_id()
        # write reinjection config
        self._generate_reinjection_config(spec, placement)
        # write data speed up out config
        self._generate_data_speed_up_out_config(spec)
        # write data speed up in config
        self._generate_data_speed_up_in_config(
            spec, FecDataView().get_chip_at(placement.x, placement.y))
        self._generate_provenance_area(spec)
        spec.end_specification()

    def _generate_data_speed_up_out_config(self, spec):
        """
        :param ~.DataSpecificationGenerator spec: spec file
        """
        spec.reserve_memory_region(
            region=_DSG_REGIONS.DATA_OUT_CONFIG,
            size=_CONFIG_DATA_SPEED_UP_SIZE_IN_BYTES,
            label="data speed-up out config region")
        spec.switch_write_focus(_DSG_REGIONS.DATA_OUT_CONFIG)
        spec.write_value(Gatherer.BASE_KEY)
        spec.write_value(Gatherer.NEW_SEQ_KEY)
        spec.write_value(Gatherer.FIRST_DATA_KEY)
        spec.write_value(Gatherer.TRANSACTION_ID_KEY)
        spec.write_value(Gatherer.END_FLAG_KEY)

    def _generate_reinjection_config(self, spec, placement):
        """
        :param ~.DataSpecificationGenerator spec: spec file
        :param ~.Placement placement:
        """
        spec.reserve_memory_region(
            region=_DSG_REGIONS.REINJECT_CONFIG,
            size=_CONFIG_REGION_REINJECTOR_SIZE_IN_BYTES,
            label="re-injection config region")

        spec.switch_write_focus(_DSG_REGIONS.REINJECT_CONFIG)
        for value in [
                self._reinject_multicast, self._reinject_point_to_point,
                self._reinject_fixed_route,
                self._reinject_nearest_neighbour]:
            # Note that this is inverted! Why... I dunno!
            spec.write_value(int(not value))

        # add the reinjection mc interface
        router_timeout_keys = \
            FecDataView.get_system_multicast_router_timeout_keys()
        chip = FecDataView().get_chip_at(placement.x, placement.y)
        # pylint: disable=unsubscriptable-object
        reinjector_base_mc_key = (
            router_timeout_keys[
                (chip.nearest_ethernet_x, chip.nearest_ethernet_y)])
        spec.write_value(reinjector_base_mc_key)

    def _generate_data_speed_up_in_config(self, spec, chip):
        """
        :param ~.DataSpecificationGenerator spec: spec file
        :param ~.Chip chip: the chip where this monitor will run
        """
        spec.reserve_memory_region(
            region=_DSG_REGIONS.DATA_IN_CONFIG,
            size=(_MAX_DATA_SIZE_FOR_DATA_IN_MULTICAST_ROUTING +
                  _CONFIG_DATA_IN_KEYS_SDRAM_IN_BYTES),
            label="data speed-up in config region")
        spec.switch_write_focus(_DSG_REGIONS.DATA_IN_CONFIG)

        # write address key and data key
        mc_data_chips_to_keys = \
            FecDataView.get_data_in_multicast_key_to_chip_map()
        # pylint: disable=unsubscriptable-object
        base_key = mc_data_chips_to_keys[chip.x, chip.y]
        spec.write_value(base_key + _KEY_OFFSETS.ADDRESS_KEY_OFFSET.value)
        spec.write_value(base_key + _KEY_OFFSETS.DATA_KEY_OFFSET.value)
        spec.write_value(base_key + _KEY_OFFSETS.BOUNDARY_KEY_OFFSET.value)

        # write table entries
        data_in_routing_tables = \
            FecDataView.get_data_in_multicast_routing_tables()
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

    def _generate_provenance_area(self, spec):
        """
        :param ~.DataSpecificationGenerator spec: spec file
        """
        spec.reserve_memory_region(
            region=_DSG_REGIONS.PROVENANCE_AREA, size=_PROVENANCE_FORMAT.size,
            label="provenance collection region", empty=True)

    def __get_provenance_region_address(self, txrx, place):
        """
        :param ~spinnman.transceiver.Transceiver txrx:
        :param ~pacman.model.placements.Placement place:
        :rtype: int
        """
        if self._prov_region is None:
            region_table_addr = txrx.get_cpu_information_from_core(
                place.x, place.y, place.p).user[0]
            region_entry_addr = get_region_base_address_offset(
                region_table_addr, _DSG_REGIONS.PROVENANCE_AREA)
            self._prov_region, = _ONE_WORD.unpack(txrx.read_memory(
                place.x, place.y, region_entry_addr, BYTES_PER_WORD))
        return self._prov_region

    @overrides(AbstractProvidesProvenanceDataFromMachine.
               get_provenance_data_from_machine)
    def get_provenance_data_from_machine(self, placement):
        # No standard provenance region, so no standard provenance data
        # But we do have our own.
        transceiver = FecDataView.get_transceiver()
        provenance_address = self.__get_provenance_region_address(
            transceiver, placement)
        data = transceiver.read_memory(
            placement.x, placement.y, provenance_address,
            _PROVENANCE_FORMAT.size)
        (n_sdp_packets, n_in_streams, n_out_streams, n_router_changes) = \
            _PROVENANCE_FORMAT.unpack_from(data)
        with ProvenanceWriter() as db:
            db.insert_monitor(
                placement.x, placement.y,
                "Number_of_Router_Configuration_Changes", n_router_changes)
            db.insert_monitor(
                placement.x, placement.y,
                "Number_of_Relevant_SDP_Messages", n_sdp_packets)
            db.insert_monitor(
                placement.x, placement.y,
                "Number_of_Input_Streamlets", n_in_streams)
            db.insert_monitor(
                placement.x, placement.y,
                "Number_of_Output_Streamlets", n_out_streams)

    def set_router_wait1_timeout(
            self, timeout, extra_monitor_cores_to_set):
        """
        Supports setting of the router time outs for a set of chips via their
        extra monitor cores. This sets the timeout for the time between when a
        packet arrives and when it starts to be emergency routed. (Actual
        emergency routing is disabled by default.)

        :param tuple(int,int) timeout:
            The mantissa and exponent of the timeout value, each between
            0 and 15
        :param extra_monitor_cores_to_set:
            which monitors control the routers to set the timeout of
        :type extra_monitor_cores_to_set:
            iterable(ExtraMonitorSupportMachineVertex)
        """
        mantissa, exponent = timeout
        core_subsets = convert_vertices_to_core_subset(
            extra_monitor_cores_to_set)
        process = SetRouterTimeoutProcess(
            FecDataView.get_scamp_connection_selector())
        try:
            process.set_wait1_timeout(mantissa, exponent, core_subsets)
        except:  # noqa: E722
            emergency_recover_state_from_failure(
                self, FecDataView.get_placement_of_vertex(self))
            raise

    def set_router_wait2_timeout(
            self, timeout, extra_monitor_cores_to_set):
        """
        Supports setting of the router time outs for a set of chips via their
        extra monitor cores. This sets the timeout for the time between when a
        packet starts to be emergency routed and when it is dropped. (Actual
        emergency routing is disabled by default.)

        :param tuple(int,int) timeout:
            The mantissa and exponent of the timeout value, each between
            0 and 15
        :param extra_monitor_cores_to_set:
            which monitors control the routers to set the timeout of
        :type extra_monitor_cores_to_set:
            iterable(ExtraMonitorSupportMachineVertex)
        """
        mantissa, exponent = timeout
        core_subsets = convert_vertices_to_core_subset(
            extra_monitor_cores_to_set)
        process = SetRouterTimeoutProcess(
            FecDataView.get_scamp_connection_selector())
        try:
            process.set_wait2_timeout(mantissa, exponent, core_subsets)
        except:  # noqa: E722
            emergency_recover_state_from_failure(
                self, FecDataView.get_placement_of_vertex(self))
            raise

    def reset_reinjection_counters(self, extra_monitor_cores_to_set):
        """
        Resets the counters for reinjection.

        :param ~spinnman.transceiver.Transceiver transceiver:
            the spinnMan interface
        :param extra_monitor_cores_to_set:
            which monitors control the routers to reset the counters of
        :type extra_monitor_cores_to_set:
            iterable(ExtraMonitorSupportMachineVertex)
        """
        core_subsets = convert_vertices_to_core_subset(
            extra_monitor_cores_to_set)
        process = ResetCountersProcess(
            FecDataView.get_scamp_connection_selector())
        try:
            process.reset_counters(core_subsets)
        except:  # noqa: E722
            emergency_recover_state_from_failure(
                self, FecDataView.get_placement_of_vertex(self))
            raise

    def clear_reinjection_queue(self, extra_monitor_cores_to_set):
        """
        Clears the queues for reinjection.

        :param extra_monitor_cores_to_set:
            Which extra monitors need to clear their queues.
        :type extra_monitor_cores_to_set:
            iterable(ExtraMonitorSupportMachineVertex)
        """
        core_subsets = convert_vertices_to_core_subset(
            extra_monitor_cores_to_set)
        process = ClearQueueProcess(
            FecDataView.get_scamp_connection_selector())
        try:
            process.reset_counters(core_subsets)
        except:  # noqa: E722
            emergency_recover_state_from_failure(
                self, FecDataView.get_placement_of_vertex(self))
            raise

    def get_reinjection_status(self):
        """
        Get the reinjection status from this extra monitor vertex.

        :return: the reinjection status for this vertex
        :rtype: ReInjectionStatus
        """
        placement = FecDataView.get_placement_of_vertex(self)
        process = ReadStatusProcess(
            FecDataView.get_scamp_connection_selector())
        try:
            return process.get_reinjection_status(
                placement.x, placement.y, placement.p)
        except:  # noqa: E722
            emergency_recover_state_from_failure(self, placement)
            raise

    def get_reinjection_status_for_vertices(self):
        """
        Get the reinjection status from a set of extra monitor cores.

        :rtype: dict(tuple(int,int), ReInjectionStatus)
        """
        core_subsets = convert_vertices_to_core_subset(
            FecDataView.iterate_monitors())
        process = ReadStatusProcess(
            FecDataView.get_scamp_connection_selector())
        return process.get_reinjection_status_for_core_subsets(core_subsets)

    def set_reinjection_packets(
            self, point_to_point=None, multicast=None, nearest_neighbour=None,
            fixed_route=None):
        """
        :param point_to_point:
            If point to point should be set, or `None` if left as before
        :type point_to_point: bool or None
        :param multicast:
            If multicast should be set, or `None` if left as before
        :type multicast: bool or None
        :param nearest_neighbour:
            If nearest neighbour should be set, or `None` if left as before
        :type nearest_neighbour: bool or None
        :param fixed_route:
            If fixed route should be set, or `None` if left as before.
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
            FecDataView.iterate_monitors())
        process = SetPacketTypesProcess(
            FecDataView.get_scamp_connection_selector())
        try:
            process.set_packet_types(
                core_subsets, self._reinject_point_to_point,
                self._reinject_multicast, self._reinject_nearest_neighbour,
                self._reinject_fixed_route)
        except:  # noqa: E722
            emergency_recover_state_from_failure(
                self, FecDataView.get_placement_of_vertex(self))
            raise

    def load_system_mc_routes(self):
        """
        Get the extra monitor cores to load up the system-based
        multicast routes (used by the Data In protocol).

        :param ~spinnman.transceiver.Transceiver transceiver:
            the spinnMan interface
        """
        core_subsets = self._convert_vertices_to_core_subset()
        process = LoadSystemMCRoutesProcess(
            FecDataView.get_scamp_connection_selector())
        try:
            return process.load_system_mc_routes(core_subsets)
        except:  # noqa: E722
            emergency_recover_state_from_failure(
                self, FecDataView.get_placement_of_vertex(self))
            raise

    def load_application_mc_routes(self):
        """
        Get the extra monitor cores to load up the application-based
        multicast routes (used by the Data In protocol).
        """
        core_subsets = self._convert_vertices_to_core_subset()
        process = LoadApplicationMCRoutesProcess(
            FecDataView.get_scamp_connection_selector())
        try:
            return process.load_application_mc_routes(core_subsets)
        except:  # noqa: E722
            emergency_recover_state_from_failure(
                self, FecDataView.get_placement_of_vertex(self))
            raise

    @staticmethod
    def _convert_vertices_to_core_subset():
        """
        Convert vertices into the subset of cores where they've been placed.

        :return: where the vertices have been placed
        :rtype: ~.CoreSubsets
        """
        core_subsets = CoreSubsets()
        for vertex in FecDataView.iterate_monitors():
            placement = FecDataView.get_placement_of_vertex(vertex)
            core_subsets.add_processor(placement.x, placement.y, placement.p)
        return core_subsets

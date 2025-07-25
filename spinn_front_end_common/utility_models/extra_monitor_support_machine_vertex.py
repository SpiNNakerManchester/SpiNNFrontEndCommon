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
from __future__ import annotations
from enum import Enum, IntEnum
import logging
import struct
from typing import Dict, Iterable, Optional, ContextManager, Type
from types import TracebackType

from typing_extensions import Literal

from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides
from spinn_utilities.config_holder import get_config_bool

from spinn_machine import Chip, CoreSubsets, MulticastRoutingEntry, Router

from spinnman.model.enums import ExecutableType, UserRegister

from pacman.model.graphs.machine import MachineVertex
from pacman.model.resources import AbstractSDRAM, ConstantSDRAM
from pacman.model.placements import Placement

from spinn_front_end_common.abstract_models import (
    AbstractHasAssociatedBinary, AbstractGeneratesDataSpecification)
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.scp import (
    ReinjectorControlProcess, LoadMCRoutesProcess)
from spinn_front_end_common.utilities.constants import (
    SARK_PER_MALLOC_SDRAM_USAGE, DATA_SPECABLE_BASIC_SETUP_INFO_N_BYTES,
    BYTES_PER_WORD, BYTES_PER_KB)
from spinn_front_end_common.utilities.helpful_functions import (
    convert_vertices_to_core_subset, get_region_base_address_offset)
from spinn_front_end_common.utilities.emergency_recovery import (
    emergency_recover_state_from_failure)
from spinn_front_end_common.utilities.utility_objs import ReInjectionStatus
from spinn_front_end_common.interface.provenance import (
    AbstractProvidesProvenanceDataFromMachine, ProvenanceWriter)
from spinn_front_end_common.interface.ds import DataSpecificationGenerator

from .data_speed_up_packet_gatherer_machine_vertex import (
    DataSpeedUpPacketGatherMachineVertex as Gatherer)

log = FormatAdapter(logging.getLogger(__name__))

_CONFIG_REGION_REINJECTOR_SIZE_IN_BYTES = 5 * BYTES_PER_WORD
#: 1.new sequence key, 2.first data key, 3. transaction id key
# 4.end flag key, 5.base key
_CONFIG_DATA_SPEED_UP_SIZE_IN_BYTES = 5 * BYTES_PER_WORD
_CONFIG_MAX_EXTRA_SEQ_NUM_SIZE_IN_BYTES = 460 * BYTES_PER_KB
_CONFIG_DATA_IN_KEYS_SDRAM_IN_BYTES = 3 * BYTES_PER_WORD
_MAX_DATA_SIZE_FOR_DATA_IN_MULTICAST_ROUTING = ((49 * 3) + 1) * BYTES_PER_WORD
_BIT_SHIFT_TO_MOVE_APP_ID = 24

_ONE_WORD = struct.Struct("<I")
# pylint: disable=wrong-spelling-in-comment
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


class _DsgRegions(IntEnum):
    REINJECT_CONFIG = 0
    DATA_OUT_CONFIG = 1
    DATA_IN_CONFIG = 2
    PROVENANCE_AREA = 3


class _KeyOffsets(IntEnum):
    ADDRESS_KEY_OFFSET = 0
    DATA_KEY_OFFSET = 1
    BOUNDARY_KEY_OFFSET = 2


class _ProvLabels(str, Enum):
    N_CHANGES = "Number_of_Router_Configuration_Changes"
    N_PACKETS = "Number_of_Relevant_SDP_Messages"
    N_IN_STREAMS = "Number_of_Input_Streamlets"
    N_OUT_STREAMS = "Number_of_Output_Streamlets"


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
        "__placement",
        # app id, used for reporting failures on system core RTE
        "_app_id",
        # the local transaction id
        "_transaction_id",
        # provenance region address
        "__prov_region")

    def __init__(
            self, reinject_point_to_point: bool = False,
            reinject_nearest_neighbour: bool = False,
            reinject_fixed_route: bool = False):
        """
        :param reinject_point_to_point:
            if we reinject point-to-point packets
        :param reinject_nearest_neighbour:
            if we reinject nearest-neighbour packets
        :param reinject_fixed_route: if we reinject fixed route packets
        """
        super().__init__("SYSTEM:ExtraMonitor")

        multicast = get_config_bool("Machine", "enable_reinjection")
        self._reinject_multicast = multicast if multicast is not None else True
        self._reinject_point_to_point = reinject_point_to_point
        self._reinject_nearest_neighbour = reinject_nearest_neighbour
        self._reinject_fixed_route = reinject_fixed_route
        # placement holder for ease of access
        self.__placement: Optional[Placement] = None
        self._app_id: Optional[int] = None
        self._transaction_id = 0
        self.__prov_region: Optional[int] = None

    @property
    def reinject_multicast(self) -> bool:
        """
        The enable_reinjection value from the configs
        """
        return self._reinject_multicast

    @property
    def transaction_id(self) -> int:
        """
        The current transaction id.
        """
        return self._transaction_id

    def update_transaction_id(self) -> None:
        """
        Advance the transaction ID.
        """
        self._transaction_id = (self._transaction_id + 1) & TRANSACTION_ID_CAP

    def update_transaction_id_from_machine(self) -> None:
        """
        Looks up from the machine what the current transaction ID is
        and updates the extra monitor.
        """
        placement = self.placement
        self._transaction_id = FecDataView.get_transceiver().read_user(
            placement.x, placement.y, placement.p, UserRegister.USER_1)

    @property
    def reinject_point_to_point(self) -> bool:
        """
        if we reinject point to point packets
        """
        return self._reinject_point_to_point

    @property
    def reinject_nearest_neighbour(self) -> bool:
        """
        if we reinject nearest neighbour packets
        """
        return self._reinject_nearest_neighbour

    @property
    def reinject_fixed_route(self) -> bool:
        """
        if we reinject fixed route packets
        """
        return self._reinject_fixed_route

    @property
    @overrides(MachineVertex.sdram_required)
    def sdram_required(self) -> AbstractSDRAM:
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
    def placement(self) -> Placement:
        """
        The Placement set by generate_data_specifications

        :raises AssertionError: If the placement has not yet been set
        """
        assert self.__placement is not None, "vertex not placed!"
        return self.__placement

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self) -> ExecutableType:
        return self.static_get_binary_start_type()

    @staticmethod
    def static_get_binary_start_type() -> ExecutableType:
        """
        The type of the binary implementing this vertex.

        :returns: The System type as this is a System vertex
        """
        return ExecutableType.SYSTEM

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self) -> str:
        return self.static_get_binary_file_name()

    @staticmethod
    def static_get_binary_file_name() -> str:
        """
        The name of the binary implementing this vertex.

        :return: Name of the aplx files for this vertex
        """
        return "extra_monitor_support.aplx"

    @overrides(AbstractGeneratesDataSpecification.generate_data_specification)
    def generate_data_specification(self, spec: DataSpecificationGenerator,
                                    placement: Placement) -> None:
        # storing for future usage
        self.__placement = placement
        chip = placement.chip
        self._app_id = FecDataView.get_app_id()
        # write reinjection config
        self._generate_reinjection_config(spec, chip)
        # write data speed up out config
        self._generate_data_speed_up_out_config(spec)
        # write data speed up in config
        self._generate_data_speed_up_in_config(spec, chip)
        self._generate_provenance_area(spec)
        spec.end_specification()

    def _generate_data_speed_up_out_config(
            self, spec: DataSpecificationGenerator) -> None:
        spec.reserve_memory_region(
            region=_DsgRegions.DATA_OUT_CONFIG,
            size=_CONFIG_DATA_SPEED_UP_SIZE_IN_BYTES,
            label="data speed-up out config region")
        spec.switch_write_focus(_DsgRegions.DATA_OUT_CONFIG)
        spec.write_value(Gatherer.BASE_KEY)
        spec.write_value(Gatherer.NEW_SEQ_KEY)
        spec.write_value(Gatherer.FIRST_DATA_KEY)
        spec.write_value(Gatherer.TRANSACTION_ID_KEY)
        spec.write_value(Gatherer.END_FLAG_KEY)

    def _generate_reinjection_config(
            self, spec: DataSpecificationGenerator, chip: Chip) -> None:
        spec.reserve_memory_region(
            region=_DsgRegions.REINJECT_CONFIG,
            size=_CONFIG_REGION_REINJECTOR_SIZE_IN_BYTES,
            label="re-injection config region")

        spec.switch_write_focus(_DsgRegions.REINJECT_CONFIG)
        for value in [
                self._reinject_multicast, self._reinject_point_to_point,
                self._reinject_fixed_route,
                self._reinject_nearest_neighbour]:
            # Note that this is inverted! Why... I dunno!
            spec.write_value(int(not value))

        # add the reinjection multi cast interface
        router_timeout_keys = \
            FecDataView.get_system_multicast_router_timeout_keys()
        # Write the base key for multicast communication
        spec.write_value(router_timeout_keys[
            chip.nearest_ethernet_x, chip.nearest_ethernet_y])

    def _generate_data_speed_up_in_config(
            self, spec: DataSpecificationGenerator, chip: Chip) -> None:
        spec.reserve_memory_region(
            region=_DsgRegions.DATA_IN_CONFIG,
            size=(_MAX_DATA_SIZE_FOR_DATA_IN_MULTICAST_ROUTING +
                  _CONFIG_DATA_IN_KEYS_SDRAM_IN_BYTES),
            label="data speed-up in config region")
        spec.switch_write_focus(_DsgRegions.DATA_IN_CONFIG)

        # write address key and data key
        mc_data_chips_to_keys = \
            FecDataView.get_data_in_multicast_key_to_chip_map()
        base_key = mc_data_chips_to_keys[chip.x, chip.y]
        spec.write_value(base_key + _KeyOffsets.ADDRESS_KEY_OFFSET)
        spec.write_value(base_key + _KeyOffsets.DATA_KEY_OFFSET)
        spec.write_value(base_key + _KeyOffsets.BOUNDARY_KEY_OFFSET)

        # write table entries
        data_in_routing_tables = \
            FecDataView.get_data_in_multicast_routing_tables()
        table = data_in_routing_tables.get_routing_table_for_chip(
            chip.x, chip.y)
        assert table is not None
        spec.write_value(table.number_of_entries)
        for entry in table.multicast_routing_entries:
            spec.write_value(entry.key)
            spec.write_value(entry.mask)
            spec.write_value(self.__encode_route(entry))

    def __encode_route(self, entry: MulticastRoutingEntry) -> int:
        assert self._app_id is not None
        route = self._app_id << _BIT_SHIFT_TO_MOVE_APP_ID
        route |= Router.convert_routing_table_entry_to_spinnaker_route(entry)
        return route

    def _generate_provenance_area(
            self, spec: DataSpecificationGenerator) -> None:
        spec.reserve_memory_region(
            region=_DsgRegions.PROVENANCE_AREA, size=_PROVENANCE_FORMAT.size,
            label="provenance collection region")

    def __provenance_address(self, place: Placement) -> int:
        if self.__prov_region is not None:
            return self.__prov_region

        txrx = FecDataView.get_transceiver()
        region_table_addr = txrx.get_region_base_address(
            place.x, place.y, place.p)
        region_entry_addr = get_region_base_address_offset(
            region_table_addr, _DsgRegions.PROVENANCE_AREA)
        r = txrx.read_word(place.x, place.y, region_entry_addr)
        self.__prov_region = r
        return r

    @overrides(AbstractProvidesProvenanceDataFromMachine.
               get_provenance_data_from_machine)
    def get_provenance_data_from_machine(self, placement: Placement) -> None:
        # No standard provenance region, so no standard provenance data
        # But we do have our own.
        x, y = placement.x, placement.y
        data = FecDataView.get_transceiver().read_memory(
            x, y, self.__provenance_address(placement),
            _PROVENANCE_FORMAT.size)
        (n_sdp_packets, n_in_streams, n_out_streams, n_router_changes) = \
            _PROVENANCE_FORMAT.unpack_from(data)
        with ProvenanceWriter() as db:
            db.insert_monitor(x, y, _ProvLabels.N_CHANGES, n_router_changes)
            db.insert_monitor(x, y, _ProvLabels.N_PACKETS, n_sdp_packets)
            db.insert_monitor(x, y, _ProvLabels.N_IN_STREAMS, n_in_streams)
            db.insert_monitor(x, y, _ProvLabels.N_OUT_STREAMS, n_out_streams)

    def __recover(self) -> ContextManager[Placement]:
        """
        Set up a context to recover what we can on failure.
        The value of the setup is the placement.
        """
        return _Recoverer(self, self.placement)

    def reset_reinjection_counters(self, extra_monitor_cores_to_set: Iterable[
            ExtraMonitorSupportMachineVertex]) -> None:
        """
        Resets the counters for reinjection.

        :param extra_monitor_cores_to_set:
            which monitors control the routers to reset the counters of
        """
        core_subsets = convert_vertices_to_core_subset(
            extra_monitor_cores_to_set)
        process = ReinjectorControlProcess(
            FecDataView.get_scamp_connection_selector())
        with self.__recover():
            process.reset_counters(core_subsets)

    def get_reinjection_status(self) -> ReInjectionStatus:
        """
        Get the reinjection status from this extra monitor vertex.

        :return: the reinjection status for this vertex
        """
        process = ReinjectorControlProcess(
            FecDataView.get_scamp_connection_selector())
        with self.__recover() as placement:
            return process.get_reinjection_status(
                placement.x, placement.y, placement.p)

    def get_reinjection_status_for_vertices(self) -> Dict[
            Chip, ReInjectionStatus]:
        """
        Get the reinjection status from a set of extra monitor cores.

        :returns: Mapping of the Chips to their reinjection status.
        """
        core_subsets = convert_vertices_to_core_subset(
            FecDataView.iterate_monitors())
        process = ReinjectorControlProcess(
            FecDataView.get_scamp_connection_selector())
        return process.get_reinjection_status_for_core_subsets(core_subsets)

    def set_reinjection_packets(
            self, point_to_point: Optional[bool] = None,
            multicast: Optional[bool] = None,
            nearest_neighbour: Optional[bool] = None,
            fixed_route: Optional[bool] = None) -> None:
        """
        Sends the reinjection packets for this vertex

        :param point_to_point:
            If point to point should be set, or `None` if left as before
        :param multicast:
            If multicast should be set, or `None` if left as before
        :param nearest_neighbour:
            If nearest neighbour should be set, or `None` if left as before
        :param fixed_route:
            If fixed route should be set, or `None` if left as before.
        """
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
        process = ReinjectorControlProcess(
            FecDataView.get_scamp_connection_selector())
        with self.__recover():
            process.set_packet_types(
                core_subsets, self._reinject_point_to_point,
                self._reinject_multicast, self._reinject_nearest_neighbour,
                self._reinject_fixed_route)

    def load_system_mc_routes(self) -> None:
        """
        Get the extra monitor cores to load up the system-based
        multicast routes (used by the Data In protocol).
        """
        core_subsets = self.__all_monitor_locations()
        process = LoadMCRoutesProcess(
            FecDataView.get_scamp_connection_selector())
        with self.__recover():
            process.load_system_mc_routes(core_subsets)

    def load_application_mc_routes(self) -> None:
        """
        Get the extra monitor cores to load up the application-based
        multicast routes (used by the Data In protocol).
        """
        core_subsets = self.__all_monitor_locations()
        process = LoadMCRoutesProcess(
            FecDataView.get_scamp_connection_selector())
        with self.__recover():
            process.load_application_mc_routes(core_subsets)

    @staticmethod
    def __all_monitor_locations() -> CoreSubsets:
        """
        Convert vertices into the subset of cores where they've been placed.

        :return: where the vertices have been placed
        """
        core_subsets = CoreSubsets()
        for vertex in FecDataView.iterate_monitors():
            placement = FecDataView.get_placement_of_vertex(vertex)
            core_subsets.add_processor(placement.x, placement.y, placement.p)
        return core_subsets


class _Recoverer:
    """
    Helper class that will run the emergency state recovery system if its
    context body throws.
    """
    def __init__(self, vertex: ExtraMonitorSupportMachineVertex,
                 placement: Placement):
        """
        :param vertex:
            The vertex to retrieve the IOBUF from
            if it is suspected as being dead
        :param placement:
            Where the vertex is located.
        """
        self.__vtx = vertex
        self.__placement = placement

    def __enter__(self) -> Placement:
        return self.__placement

    def __exit__(self, exc_type: Optional[Type],
                 exc_val: Optional[BaseException],
                 exc_tb: Optional[TracebackType]) -> Literal[False]:
        if exc_val:
            emergency_recover_state_from_failure(self.__vtx, self.__placement)
        return False

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
The code in this module is intended primarily for being invoked via the
PACMAN Executor.
"""

import os
from .application_finisher import ApplicationFinisher
from .application_runner import ApplicationRunner
from .buffer_extractor import BufferExtractor
from .chip_iobuf_clearer import ChipIOBufClearer
from .chip_iobuf_extractor import ChipIOBufExtractor
from .buffer_manager_creator import BufferManagerCreator
from .chip_provenance_updater import ChipProvenanceUpdater
from .chip_runtime_updater import ChipRuntimeUpdater
from .compute_energy_used import ComputeEnergyUsed
from .database_interface import DatabaseInterface
from .system_multicast_routing_generator import (
    SystemMulticastRoutingGenerator)
from .dsg_region_reloader import DSGRegionReloader
from .edge_to_n_keys_mapper import EdgeToNKeysMapper
from .energy_provenance_reporter import EnergyProvenanceReporter
from .finalise_timing_data import FinaliseTimingData
from .find_application_chips_used import FindApplicationChipsUsed
from .graph_binary_gatherer import GraphBinaryGatherer
from .graph_data_specification_writer import (
    GraphDataSpecificationWriter)
from .graph_measurer import GraphMeasurer
from .graph_provenance_gatherer import GraphProvenanceGatherer
from .hbp_allocator import HBPAllocator
from .hbp_max_machine_generator import HBPMaxMachineGenerator
from .host_bit_field_router_compressor import HostBasedBitFieldRouterCompressor
from .host_execute_data_specification import HostExecuteDataSpecification
from .insert_chip_power_monitors_to_graphs import (
    InsertChipPowerMonitorsToGraphs)
from .insert_edges_to_extra_monitor_functionality import (
    InsertEdgesToExtraMonitorFunctionality)
from .insert_edges_to_live_packet_gatherers import (
    InsertEdgesToLivePacketGatherers)
from .insert_extra_monitor_vertices_to_graphs import (
    InsertExtraMonitorVerticesToGraphs)
from .insert_live_packet_gatherers_to_graphs import (
    InsertLivePacketGatherersToGraphs)
from .load_executable_images import LoadExecutableImages
from .load_fixed_routes import LoadFixedRoutes
from .local_tdma_builder import LocalTDMABuilder
from .locate_executable_start_type import LocateExecutableStartType
from .machine_bit_field_router_compressor import (
    MachineBitFieldRouterCompressor)
from .machine_generator import MachineGenerator
from .create_notification_protocol import CreateNotificationProtocol
from .placements_provenance_gatherer import PlacementsProvenanceGatherer
from .pre_allocate_for_bit_field_router_compressor import (
    PreAllocateForBitFieldRouterCompressor)
from .pre_allocate_resources_for_chip_power_monitor import (
    PreAllocateResourcesForChipPowerMonitor)
from .pre_allocate_resources_for_live_packet_gatherers import (
    PreAllocateResourcesForLivePacketGatherers)
from .preallocate_resources_for_extra_monitor_support import (
    PreAllocateResourcesForExtraMonitorSupport)
from .process_partition_constraints import ProcessPartitionConstraints
from .profile_data_gatherer import ProfileDataGatherer
from .provenance_json_writer import ProvenanceJSONWriter
from .provenance_sql_writer import ProvenanceSQLWriter
from .provenance_xml_writer import ProvenanceXMLWriter
from .router_provenance_gatherer import RouterProvenanceGatherer
from .routing_setup import RoutingSetup
from .routing_table_loader import RoutingTableLoader
from .spalloc_allocator import SpallocAllocator
from .spalloc_max_machine_generator import SpallocMaxMachineGenerator
from .tags_loader import TagsLoader
from .tdma_agenda_builder import TDMAAgendaBuilder
from .virtual_machine_generator import VirtualMachineGenerator
from .read_routing_tables_from_machine import ReadRoutingTablesFromMachine
from .sdram_outgoing_partition_allocator import SDRAMOutgoingPartitionAllocator


def interface_xml():
    return os.path.join(
        os.path.dirname(__file__), "front_end_common_interface_functions.xml")


__all__ = [
    "ApplicationFinisher",
    "ApplicationRunner", "BufferExtractor",
    "BufferManagerCreator", "ChipIOBufClearer",
    "ChipIOBufExtractor", "ChipProvenanceUpdater",
    "ChipRuntimeUpdater", "CreateNotificationProtocol",
    "ComputeEnergyUsed", "DatabaseInterface",
    "SystemMulticastRoutingGenerator",
    "DSGRegionReloader", "EdgeToNKeysMapper",
    "EnergyProvenanceReporter", "FinaliseTimingData",
    "FindApplicationChipsUsed",
    "GraphBinaryGatherer", "GraphDataSpecificationWriter",
    "GraphMeasurer", "GraphProvenanceGatherer",
    "HBPAllocator", "HostBasedBitFieldRouterCompressor",
    "HBPMaxMachineGenerator",
    "HostExecuteDataSpecification",
    "InsertChipPowerMonitorsToGraphs",
    "InsertEdgesToExtraMonitorFunctionality",
    "InsertEdgesToLivePacketGatherers",
    "InsertExtraMonitorVerticesToGraphs",
    "InsertLivePacketGatherersToGraphs", "interface_xml",
    "LoadExecutableImages", "LoadFixedRoutes", "LocalTDMABuilder",
    "LocateExecutableStartType", "MachineBitFieldRouterCompressor",
    "MachineGenerator", "PlacementsProvenanceGatherer",
    "PreAllocateForBitFieldRouterCompressor",
    "PreAllocateResourcesForChipPowerMonitor",
    "PreAllocateResourcesForExtraMonitorSupport",
    "PreAllocateResourcesForLivePacketGatherers",
    "ProcessPartitionConstraints", "ProfileDataGatherer",
    "ProvenanceJSONWriter", "ProvenanceSQLWriter", "ProvenanceXMLWriter",
    "ReadRoutingTablesFromMachine", "RouterProvenanceGatherer", "RoutingSetup",
    "RoutingTableLoader", "SDRAMOutgoingPartitionAllocator",
    "SpallocAllocator", "SpallocMaxMachineGenerator", "TagsLoader",
    "TDMAAgendaBuilder", "VirtualMachineGenerator"]

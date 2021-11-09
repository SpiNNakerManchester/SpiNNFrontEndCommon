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
Much of the code in this module is intended primarily for being invoked via the
PACMAN Executor.
"""

import os
from .bit_field_compressor_report import BitFieldCompressorReport
from .bit_field_summary import BitFieldSummary
from .board_chip_report import board_chip_report
from .energy_report import EnergyReport
from .fixed_route_from_machine_report import FixedRouteFromMachineReport
from .memory_map_on_host_chip_report import MemoryMapOnHostChipReport
from .memory_map_on_host_report import MemoryMapOnHostReport
from .network_specification import network_specification
from .router_collision_potential_report import RouterCollisionPotentialReport
from .routing_table_from_machine_report import RoutingTableFromMachineReport
from .real_tags_report import TagsFromMachineReport
from .write_json_machine import write_json_machine
from .write_json_partition_n_keys_map import write_json_partition_n_keys_map
from .write_json_placements import write_json_placements
from .write_json_routing_tables import write_json_routing_tables

def report_xml():
    return os.path.join(
        os.path.dirname(__file__), "front_end_common_reports.xml")


__all__ = [
    "BitFieldCompressorReport",
    "BitFieldSummary",
    "board_chip_report",
    "EnergyReport",
    "FixedRouteFromMachineReport",
    "network_specification",
    "MemoryMapOnHostChipReport",
    "MemoryMapOnHostReport",
    "report_xml",
    "RouterCollisionPotentialReport",
    "RoutingTableFromMachineReport",
    "TagsFromMachineReport",
    "write_json_machine",
    "write_json_partition_n_keys_map",
    "write_json_placements",
    "write_json_routing_tables"]

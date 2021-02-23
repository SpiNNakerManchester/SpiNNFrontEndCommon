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
from .board_chip_report import BoardChipReport
from .energy_report import EnergyReport
from .fixed_route_from_machine_report import FixedRouteFromMachineReport
from .memory_map_on_host_chip_report import MemoryMapOnHostChipReport
from .memory_map_on_host_report import MemoryMapOnHostReport
from .routing_table_from_machine_report import RoutingTableFromMachineReport
from .real_tags_report import TagsFromMachineReport


def report_xml():
    return os.path.join(
        os.path.dirname(__file__), "front_end_common_reports.xml")


__all__ = [
    "BitFieldCompressorReport",
    "BitFieldSummary",
    "BoardChipReport",
    "EnergyReport",
    "FixedRouteFromMachineReport",
    "MemoryMapOnHostChipReport",
    "MemoryMapOnHostReport",
    "report_xml",
    "RoutingTableFromMachineReport",
    "TagsFromMachineReport"]

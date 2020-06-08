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

from spinn_utilities.progress_bar import ProgressBar
from spinnman.constants import ROUTER_REGISTER_REGISTERS
from spinnman.model import DiagnosticFilter
from spinnman.model.enums import (
    DiagnosticFilterDefaultRoutingStatus, DiagnosticFilterPacketType,
    DiagnosticFilterSource)


class RoutingTableLoader(object):
    __slots__ = []

    def __call__(self, router_tables, app_id, transceiver, machine):
        progress = ProgressBar(router_tables.routing_tables,
                               "Loading routing data onto the machine")

        # load each router table that is needed for the application to run into
        # the chips SDRAM
        for table in progress.over(router_tables.routing_tables):
            if (not machine.get_chip_at(table.x, table.y).virtual
                    and table.multicast_routing_entries):
                transceiver.load_multicast_routes(
                    table.x, table.y, table.multicast_routing_entries,
                    app_id=app_id)

    @staticmethod
    def _set_router_diagnostic_filters(x, y, transceiver):
        transceiver.set_router_diagnostic_filter(
            x, y, ROUTER_REGISTER_REGISTERS.USER_3.value,
            DiagnosticFilter(
                enable_interrupt_on_counter_event=False,
                match_emergency_routing_status_to_incoming_packet=False,
                destinations=[],
                sources=[DiagnosticFilterSource.LOCAL],
                payload_statuses=[],
                default_routing_statuses=[
                    DiagnosticFilterDefaultRoutingStatus.DEFAULT_ROUTED],
                emergency_routing_statuses=[],
                packet_types=[DiagnosticFilterPacketType.MULTICAST]))

        transceiver.set_router_diagnostic_filter(
            x, y, ROUTER_REGISTER_REGISTERS.USER_2.value,
            DiagnosticFilter(
                enable_interrupt_on_counter_event=False,
                match_emergency_routing_status_to_incoming_packet=False,
                destinations=[],
                sources=[DiagnosticFilterSource.NON_LOCAL],
                payload_statuses=[],
                default_routing_statuses=[
                    DiagnosticFilterDefaultRoutingStatus.DEFAULT_ROUTED],
                emergency_routing_statuses=[],
                packet_types=[DiagnosticFilterPacketType.MULTICAST]))

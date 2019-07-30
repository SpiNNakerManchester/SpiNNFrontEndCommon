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


class RoutingSetup(object):
    __slots__ = []

    def __call__(self, router_tables, app_id, transceiver, machine):
        routing_tables = list(router_tables.routing_tables)
        progress = ProgressBar(routing_tables, "Preparing Routing Tables")

        # Clear the routing table for each router that needs to be set up
        # and set up the diagnostics
        for router_table in progress.over(routing_tables):
            if not machine.get_chip_at(router_table.x, router_table.y).virtual:
                transceiver.clear_multicast_routes(
                    router_table.x, router_table.y)
                transceiver.clear_router_diagnostic_counters(
                    router_table.x, router_table.y)

                # set the router diagnostic for user 3 to catch local default
                # routed packets. This can only occur when the source router
                # has no router entry, and therefore should be detected a bad
                # dropped packet.
                self._set_router_diagnostic_filters(
                    router_table.x, router_table.y, transceiver)

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

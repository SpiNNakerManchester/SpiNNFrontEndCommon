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

from spinn_utilities.progress_bar import ProgressBar
from spinnman.constants import ROUTER_REGISTER_REGISTERS
from spinnman.model import DiagnosticFilter
from spinnman.model.enums import (
    DiagnosticFilterDefaultRoutingStatus, DiagnosticFilterPacketType,
    DiagnosticFilterSource)
from spinn_front_end_common.data import FecDataView


def routing_setup():
    """
    Initialises the routers.

    .. note::
        This does not load any routes into them.

    :param ~spinnman.transceiver.Transceiver transceiver:
    """
    transceiver = FecDataView.get_transceiver()
    routing_tables = FecDataView.get_uncompressed().routing_tables
    progress = ProgressBar(len(routing_tables), "Preparing Routing Tables")

    # Clear the routing table for each router that needs to be set up
    # and set up the diagnostics
    for router_table in progress.over(routing_tables):
        transceiver.clear_multicast_routes(
            router_table.x, router_table.y)
        transceiver.clear_router_diagnostic_counters(
            router_table.x, router_table.y)

        # set the router diagnostic for user 3 to catch local default
        # routed packets. This can only occur when the source router
        # has no router entry, and therefore should be detected a bad
        # dropped packet.
        __set_router_diagnostic_filters(
            router_table.x, router_table.y, transceiver)


def __set_router_diagnostic_filters(x, y, transceiver):
    """
    :param int x:
    :param int y:
    :param ~.Transceiver transceiver:
    """
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

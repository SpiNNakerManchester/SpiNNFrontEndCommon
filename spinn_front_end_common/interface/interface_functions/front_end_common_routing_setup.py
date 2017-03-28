from spinnman import constants

from spinn_machine.utilities.progress_bar import ProgressBar
from spinnman.model.diagnostic_filter import DiagnosticFilter
from spinnman.model.enums.diagnostic_filter_default_routing_status import \
    DiagnosticFilterDefaultRoutingStatus
from spinnman.model.enums.diagnostic_filter_packet_type import \
    DiagnosticFilterPacketType
from spinnman.model.enums.diagnostic_filter_source \
    import DiagnosticFilterSource


class FrontEndCommonRoutingSetup(object):
    __slots__ = []

    def __call__(self, router_tables, app_id, transceiver, machine):
        progress_bar = ProgressBar(
            len(list(router_tables.routing_tables)),
            "Preparing Routing Tables")

        # Clear the routing table for each router that needs to be set up
        # and set up the diagnostics
        for router_table in router_tables.routing_tables:
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
            progress_bar.update()
        progress_bar.end()

    @staticmethod
    def _set_router_diagnostic_filters(x, y, transceiver):
        transceiver.set_router_diagnostic_filter(
            x, y,
            constants.ROUTER_REGISTER_REGISTERS.USER_3.value,
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
            x, y,
            constants.ROUTER_REGISTER_REGISTERS.USER_2.value,
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

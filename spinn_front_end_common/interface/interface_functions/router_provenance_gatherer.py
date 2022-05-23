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

import logging
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter
from spinnman.exceptions import SpinnmanException
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.provenance import ProvenanceWriter

logger = FormatAdapter(logging.getLogger(__name__))


def router_provenance_gatherer():
    gather = _RouterProvenanceGatherer()
    # pylint: disable=protected-access
    gather._add_router_provenance_data()


class _RouterProvenanceGatherer(object):
    """ Gathers diagnostics from the routers.
    """

    __slots__ = []

    def _add_router_provenance_data(self):
        """ Writes the provenance data of the router diagnostics
        """
        progress = ProgressBar(FecDataView.get_machine().n_chips*2,
                               "Getting Router Provenance")

        seen_chips = set()

        # get all extra monitor core data if it exists
        reinjection_data = None
        if FecDataView.has_monitors():
            monitor = FecDataView.get_monitor_by_xy(0, 0)
            reinjection_data = monitor.get_reinjection_status_for_vertices()

        for router_table in progress.over(
                FecDataView.get_uncompressed().routing_tables, False):
            seen_chips.add(self._add_router_table_diagnostic(
                router_table, reinjection_data))

        # Get what info we can for chips where there are problems or no table
        for chip in progress.over(sorted(
                FecDataView.get_machine().chips, key=lambda c: (c.x, c.y))):
            if not chip.virtual and (chip.x, chip.y) not in seen_chips:
                self._add_unseen_router_chip_diagnostic(
                    chip, reinjection_data)

    def _add_router_table_diagnostic(self, table, reinjection_data):
        """
        :param ~.MulticastRoutingTable table:
        :param dict(tuple(int,int),ReInjectionStatus) reinjection_data:
        """
        # pylint: disable=too-many-arguments, bare-except
        x = table.x
        y = table.y
        if not FecDataView.get_chip_at(x, y).virtual:
            try:
                transceiver = FecDataView.get_transceiver()
                diagnostics = transceiver.get_router_diagnostics(x, y)
            except SpinnmanException:
                logger.warning(
                    "Could not read routing diagnostics from {}, {}",
                    x, y, exc_info=True)
                return
            status = self.__get_status(reinjection_data, x, y)
            self.__router_diagnostics(x, y, diagnostics, status, True, table)
        return x, y

    def _add_unseen_router_chip_diagnostic(self, chip, reinjection_data):
        """
        :param ~.Chip chip:
        :param dict(tuple(int,int),ReInjectionStatus) reinjection_data:
        """
        # pylint: disable=bare-except
        try:
            transceiver = FecDataView.get_transceiver()
            diagnostics = transceiver.get_router_diagnostics(chip.x, chip.y)
        except SpinnmanException:
            # There could be issues with unused chips - don't worry!
            return
        if (diagnostics.n_dropped_multicast_packets or
                diagnostics.n_local_multicast_packets or
                diagnostics.n_external_multicast_packets):
            status = self.__get_status(reinjection_data, chip.x, chip.y)
            self.__router_diagnostics(
                chip.x, chip.y, diagnostics, status, False, None)

    @staticmethod
    def __get_status(reinjection_data, x, y):
        """
        :param dict(tuple(int,int),ReInjectionStatus) reinjection_data:
        :param int x:
        :param int y:
        :rtype: ReInjectionStatus or None
        """
        return reinjection_data[x, y] if reinjection_data else None

    def __router_diagnostics(self, x, y, diagnostics, status, expected, table):
        """ Describes the router diagnostics for one router.

        :param int x: x coordinate of the router in question
        :param int y: y coordinate of the router in question
        :param ~.RouterDiagnostics diagnostics: the router diagnostics object
        :param ReInjectionStatus status:
            the data gained from the extra monitor re-injection subsystem
        :param bool expected:
        :param ~.AbstractMulticastRoutingTable table:
            the router table generated by the PACMAN tools
        """
        # pylint: disable=too-many-arguments

        # simplify the if by making components of it outside.
        has_dropped = (diagnostics.n_dropped_multicast_packets > 0)
        missing_stuff = False
        has_reinjection = status is not None
        if has_reinjection:
            missing_stuff = ((
                status.n_dropped_packets + status.n_missed_dropped_packets +
                status.n_dropped_packet_overflows +
                status.n_reinjected_packets + status.n_processor_dumps +
                status.n_link_dumps) < diagnostics.n_dropped_multicast_packets)

        with ProvenanceWriter() as db:
            db.insert_router(
                x, y, "Local_Multicast_Packets",
                diagnostics.n_local_multicast_packets, expected)

            db.insert_router(
                x, y, "External_Multicast_Packets",
                diagnostics.n_external_multicast_packets, expected)

            db.insert_router(
                x, y, "Dropped_Multicast_Packets",
                diagnostics.n_dropped_multicast_packets, expected)
            if (has_dropped and not has_reinjection) or (
                    has_dropped and has_reinjection and missing_stuff):
                db.insert_report(
                    f"The router on {x}, {y} has dropped "
                    f"{diagnostics.n_dropped_multicast_packets} "
                    f"multicast route packets. "
                    f"Try increasing the machine_time_step and/or the time "
                    f"scale factor or reducing the number of atoms per core.")

            db.insert_router(
                x, y, "Dropped_Multicast_Packets_via_local_transmission",
                diagnostics.user_3, expected)
            if diagnostics.user_3 > 0:
                db.insert_report(
                    f"The router on {x}, {y} has dropped {diagnostics.user_3} "
                    "multicast packets that were transmitted by local cores. "
                    "This occurs where the router has no entry associated "
                    "with the multicast key. "
                    "Try investigating the keys allocated to the vertices "
                    "and the router table entries for this chip.")

            db.insert_router(
                x, y, "default_routed_external_multicast_packets",
                diagnostics.user_2, expected)
            if diagnostics.user_2 > 0 and not (
                    table and table.number_of_defaultable_entries):
                db.insert_report(
                    f"The router on {x}, {y} has default routed "
                    f"{diagnostics.user_2} multicast packets, but the router "
                    f"table did not expect any default routed packets. "
                    f"This occurs where the router has no entry associated "
                    f"with the multicast key. "
                    f"Try investigating the keys allocated to the vertices "
                    f"and the router table entries for this chip.")

            if table:
                db.insert_router(
                    x, y, "Entries", table.number_of_entries, expected)
                routes = set()
                for ent in table.multicast_routing_entries:
                    routes.add(ent.spinnaker_route)
                db.insert_router(x, y, "Unique_Routes", len(routes), expected)

            db.insert_router(
                x, y, "Local_P2P_Packets",
                diagnostics.n_local_peer_to_peer_packets, expected)

            db.insert_router(
                x, y, "External_P2P_Packets",
                diagnostics.n_external_peer_to_peer_packets, expected)

            db.insert_router(
                x, y, "Dropped_P2P_Packets",
                diagnostics.n_dropped_peer_to_peer_packets, expected)

            db.insert_router(
                x, y, "Local_NN_Packets",
                diagnostics.n_local_nearest_neighbour_packets, expected)

            db.insert_router(
                x, y, "External_NN_Packets",
                diagnostics.n_external_nearest_neighbour_packets, expected)

            db.insert_router(
                x, y, "Dropped_NN_Packets",
                diagnostics.n_dropped_nearest_neighbour_packets, expected)

            db.insert_router(
                x, y, "Local_FR_Packets",
                diagnostics.n_local_fixed_route_packets, expected)

            db.insert_router(
                x, y, "External_FR_Packets",
                diagnostics.n_external_fixed_route_packets, expected)

            db.insert_router(
                x, y, "Dropped_FR_Packets",
                diagnostics.n_dropped_fixed_route_packets, expected)
            if diagnostics.n_dropped_fixed_route_packets > 0:
                db.insert_report(
                    f"The router on chip {x}:{y} dropped "
                    f"{diagnostics.n_dropped_fixed_route_packets} fixed "
                    f"route packets. "
                    f"This is indicative of an error within the data "
                    f"extraction process as this is the only expected user of "
                    "fixed route packets.")

            db.insert_router(
                x, y, "Error status", diagnostics.error_status, expected)
            if diagnostics.error_status > 0:
                db.insert_report(
                    f"The router on {x}, {y} has a non-zero error status. "
                    f"This could indicate a hardware fault. "
                    f"The errors set are {diagnostics.errors_set}, and the "
                    f"error count is {diagnostics.error_count}")

            if status is None:
                return  # rest depends on status

            db.insert_router(
                x, y, "Received_For_Reinjection",
                status.n_dropped_packets, expected)

            db.insert_router(
                x, y, "Missed_For_Reinjection",
                status.n_missed_dropped_packets, expected)
            if status.n_missed_dropped_packets > 0:
                db.insert_report(
                    f"The extra monitor on {x}, {y} has missed "
                    f"{status.n_missed_dropped_packets} packets.")

            db.insert_router(
                x, y, "Reinjection_Overflows",
                status.n_dropped_packet_overflows, expected,)
            if status.n_dropped_packet_overflows > 0:
                db.insert_report(
                    f"The extra monitor on {x}, {y} has dropped "
                    f"{status.n_dropped_packet_overflows} packets.")

            db.insert_router(
                x, y, "Reinjected", status.n_reinjected_packets, expected)

            db.insert_router(
                x, y, "Dumped_from_a_Link", status.n_link_dumps, expected)
            if status.n_link_dumps > 0 and (
                    self.__has_virtual_chip_connected(x, y)):
                db.insert_report(
                    f"The extra monitor on {x}, {y} has detected that "
                    f"{status.n_link_dumps} packets were dumped from an "
                    f"outgoing link of this chip's router. This often occurs "
                    f"when external devices are used in the script but not "
                    f"connected to the communication fabric correctly. "
                    f"These packets may have been reinjected multiple times "
                    f"and so this number may be an overestimate.")

            db.insert_router(
                x, y, "Dumped_from_a_processor", status.n_processor_dumps,
                expected)
            if status.n_processor_dumps > 0:
                db.insert_report(
                    f"The extra monitor on {x}, {y} has detected that "
                    f"{status.n_processor_dumps} packets were dumped from a "
                    "core failing to take the packet. This often occurs when "
                    "the executable has crashed or has not been given a "
                    "multicast packet callback. It can also result from the "
                    "core taking too long to process each packet. These "
                    "packets were reinjected and so this number is likely an "
                    "overestimate.")

    def __has_virtual_chip_connected(self, x, y):
        """
        :param int x:
        :param int y:
        :rtype: bool
        """
        return any(
            FecDataView.get_chip_at(
                link.destination_x, link.destination_y).virtual
            for link in FecDataView.get_chip_at(x, y).router.links)

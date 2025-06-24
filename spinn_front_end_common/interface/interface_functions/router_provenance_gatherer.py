# Copyright (c) 2016 The University of Manchester
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

import logging
from typing import Dict, Optional, Set
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter
from spinn_utilities.typing.coords import XY
from spinn_machine import Chip
from spinnman.exceptions import SpinnmanException
from spinnman.model import RouterDiagnostics
from pacman.model.routing_tables import AbstractMulticastRoutingTable
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.provenance import ProvenanceWriter
from spinn_front_end_common.utilities.utility_objs import ReInjectionStatus

logger = FormatAdapter(logging.getLogger(__name__))


def router_provenance_gatherer(provenance_prefix: str = "") -> None:
    """
    Gathers diagnostics from the routers.

    :param provenance_prefix: The prefix to add to the provenance names
    """
    _RouterProvenanceGatherer().add_router_provenance_data(provenance_prefix)


class _RouterProvenanceGatherer(object):
    """
    Gathers diagnostics from the routers.
    """
    __slots__ = ()

    def add_router_provenance_data(self, provenance_prefix: str) -> None:
        """
        Writes the provenance data of the router diagnostics

        :param provenance_prefix: The prefix to add to the provenance names
        """
        count = len(FecDataView.get_uncompressed().routing_tables) \
            + FecDataView.get_machine().n_chips + 1
        progress = ProgressBar(count, "Getting Router Provenance")

        seen_chips: Set[XY] = set()

        # get all extra monitor core data if it exists
        reinjection_data: Optional[Dict[Chip, ReInjectionStatus]] = None
        if FecDataView.has_monitors():
            monitor = FecDataView.get_monitor_by_xy(0, 0)
            reinjection_data = monitor.get_reinjection_status_for_vertices()
        progress.update()

        for router_table in progress.over(
                FecDataView.get_uncompressed().routing_tables, False):
            seen_chips.add(self._add_router_table_diagnostic(
                router_table, reinjection_data, provenance_prefix))

        # Get what info we can for chips where there are problems or no table
        for chip in progress.over(sorted(
                FecDataView.get_machine().chips, key=lambda c: (c.x, c.y))):
            if (chip.x, chip.y) not in seen_chips:
                self._add_unseen_router_chip_diagnostic(
                    chip, reinjection_data, provenance_prefix)

    def __get_router_diagnostics(self, chip: Chip) -> RouterDiagnostics:
        return FecDataView.get_transceiver().get_router_diagnostics(
            chip.x, chip.y)

    def _add_router_table_diagnostic(
            self, table: AbstractMulticastRoutingTable,
            reinjection_data: Optional[Dict[Chip, ReInjectionStatus]],
            prefix: str) -> XY:
        chip = table.chip
        try:
            diagnostics = self.__get_router_diagnostics(chip)
        except SpinnmanException:
            logger.warning(
                "Could not read routing diagnostics from {},{}",
                chip.x, chip.y, exc_info=True)
            return (-1, -1)  # Not a chip location
        status = self.__get_status(reinjection_data, chip)
        self.__router_diagnostics(
            chip, diagnostics, status, True, table, prefix)
        return chip.x, chip.y

    def _add_unseen_router_chip_diagnostic(
            self, chip: Chip,
            reinjection_data: Optional[Dict[Chip, ReInjectionStatus]],
            prefix: str) -> None:
        try:
            diagnostics = self.__get_router_diagnostics(chip)
        except SpinnmanException:
            # There could be issues with unused chips - don't worry!
            return
        if (diagnostics.n_dropped_multicast_packets or
                diagnostics.n_local_multicast_packets or
                diagnostics.n_external_multicast_packets):
            status = self.__get_status(reinjection_data, chip)
            self.__router_diagnostics(
                chip, diagnostics, status, False, None, prefix)

    @staticmethod
    def __get_status(
            reinjection_data: Optional[Dict[Chip, ReInjectionStatus]],
            chip: Chip) -> Optional[ReInjectionStatus]:
        return reinjection_data.get(chip) if reinjection_data else None

    def __router_diagnostics(
            self, chip: Chip, diagnostics: RouterDiagnostics,
            status: Optional[ReInjectionStatus], expected: bool,
            table: Optional[AbstractMulticastRoutingTable],
            prefix: str) -> None:
        """
        Describes the router diagnostics for one router.

        :param chip: Chip of the router in question
        :param diagnostics: the router diagnostics object
        :param status:
            the data gained from the extra monitor re-injection subsystem
        :param expected:
        :param table: the router table generated by the PACMAN tools
        """
        # simplify the if by making components of it outside.
        has_dropped = (diagnostics.n_dropped_multicast_packets > 0)
        has_reinjection = status is not None
        missing_stuff = status is not None and ((
            status.n_dropped_packets + status.n_missed_dropped_packets +
            status.n_dropped_packet_overflows + status.n_reinjected_packets +
            status.n_processor_dumps + status.n_link_dumps) <
            diagnostics.n_dropped_multicast_packets)
        x, y = chip.x, chip.y

        with ProvenanceWriter() as db:
            db.insert_router(
                x, y, f"{prefix}Local_Multicast_Packets",
                diagnostics.n_local_multicast_packets, expected)

            db.insert_router(
                x, y, f"{prefix}External_Multicast_Packets",
                diagnostics.n_external_multicast_packets, expected)

            db.insert_router(
                x, y, f"{prefix}Dropped_Multicast_Packets",
                diagnostics.n_dropped_multicast_packets, expected)
            if has_dropped and (not has_reinjection or missing_stuff):
                db.insert_report(
                    f"The router on {x}, {y} has dropped "
                    f"{diagnostics.n_dropped_multicast_packets} "
                    f"multicast route packets. "
                    f"Try increasing the machine_time_step and/or the time "
                    f"scale factor or reducing the number of atoms per core.")

            db.insert_router(
                x, y,
                f"{prefix}Dropped_Multicast_Packets_via_local_transmission",
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
                x, y, f"{prefix}default_routed_external_multicast_packets",
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
                    x, y, f"{prefix}Entries", table.number_of_entries,
                    expected)
                routes = set()
                for ent in table.multicast_routing_entries:
                    routes.add(ent.spinnaker_route)
                db.insert_router(x, y, "Unique_Routes", len(routes), expected)

            db.insert_router(
                x, y, f"{prefix}Local_P2P_Packets",
                diagnostics.n_local_peer_to_peer_packets, expected)

            db.insert_router(
                x, y, f"{prefix}External_P2P_Packets",
                diagnostics.n_external_peer_to_peer_packets, expected)

            db.insert_router(
                x, y, f"{prefix}Dropped_P2P_Packets",
                diagnostics.n_dropped_peer_to_peer_packets, expected)

            db.insert_router(
                x, y, f"{prefix}Local_NN_Packets",
                diagnostics.n_local_nearest_neighbour_packets, expected)

            db.insert_router(
                x, y, f"{prefix}External_NN_Packets",
                diagnostics.n_external_nearest_neighbour_packets, expected)

            db.insert_router(
                x, y, f"{prefix}Dropped_NN_Packets",
                diagnostics.n_dropped_nearest_neighbour_packets, expected)

            db.insert_router(
                x, y, f"{prefix}Local_FR_Packets",
                diagnostics.n_local_fixed_route_packets, expected)

            db.insert_router(
                x, y, f"{prefix}External_FR_Packets",
                diagnostics.n_external_fixed_route_packets, expected)

            db.insert_router(
                x, y, f"{prefix}Dropped_FR_Packets",
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
                x, y, f"{prefix}Error status", diagnostics.error_status,
                expected)
            if diagnostics.error_status > 0:
                db.insert_report(
                    f"The router on {x}, {y} has a non-zero error status. "
                    f"This could indicate a hardware fault. "
                    f"The errors set are {diagnostics.errors_set}, and the "
                    f"error count is {diagnostics.error_count}")

            if status is None:
                return  # rest depends on status

            db.insert_router(
                x, y, f"{prefix}Received_For_Reinjection",
                status.n_dropped_packets, expected)

            db.insert_router(
                x, y, f"{prefix}Missed_For_Reinjection",
                status.n_missed_dropped_packets, expected)
            if status.n_missed_dropped_packets > 0:
                db.insert_report(
                    f"The extra monitor on {x}, {y} has missed "
                    f"{status.n_missed_dropped_packets} packets.")

            db.insert_router(
                x, y, f"{prefix}Reinjection_Overflows",
                status.n_dropped_packet_overflows, expected,)
            if status.n_dropped_packet_overflows > 0:
                db.insert_report(
                    f"The extra monitor on {x}, {y} has dropped "
                    f"{status.n_dropped_packet_overflows} packets.")

            db.insert_router(
                x, y, f"{prefix}Reinjected", status.n_reinjected_packets,
                expected)

            db.insert_router(
                x, y, f"{prefix}Dumped_from_a_Link", status.n_link_dumps,
                expected)
            if status.n_link_dumps > 0:
                db.insert_report(
                    f"The extra monitor on {x}, {y} has detected that "
                    f"{status.n_link_dumps} packets were dumped from "
                    f"outgoing links {status.links_dropped_from} of this "
                    f"chip's router. This often occurs "
                    f"when external devices are used in the script but not "
                    f"connected to the communication fabric correctly. "
                    f"These packets may have been reinjected multiple times "
                    f"and so this number may be an overestimate.")

            db.insert_router(
                x, y, f"{prefix}Dumped_from_a_processor",
                status.n_processor_dumps, expected)
            if status.n_processor_dumps > 0:
                db.insert_report(
                    f"The extra monitor on {x}, {y} has detected that "
                    f"{status.n_processor_dumps} packets were dumped from "
                    f"cores {status.processors_dropped_from} failing to take "
                    "the packet. This often occurs when "
                    "the executable has crashed or has not been given a "
                    "multicast packet callback. It can also result from the "
                    "core taking too long to process each packet. These "
                    "packets were reinjected and so this number is likely an "
                    "overestimate.")

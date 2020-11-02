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
from spinn_front_end_common.utilities.utility_objs import ProvenanceDataItem

logger = FormatAdapter(logging.getLogger(__name__))


class RouterProvenanceGatherer(object):
    """ Gathers diagnostics from the routers.

    :param ~spinnman.transceiver.Transceiver transceiver:
        the SpiNNMan interface object
    :param ~spinn_machine.Machine machine:
        the SpiNNaker machine
    :param ~pacman.model.routing_tables.MulticastRoutingTables router_tables:
        the router tables that have been generated
    :param bool using_reinjection: whether we are reinjecting packets
    :param list(~.ProvenanceDataItem) provenance_data_objects:
        any existing provenance information to add to
    :param list(ExtraMonitorSupportMachineVertex) extra_monitor_vertices:
        vertices which represent the extra monitor code
    :param ~pacman.model.placements.Placements placements:
        the placements object
    """

    __slots__ = [
        # int for how many packets were sent
        '_total_sent_packets',

        # how many new packets were received
        '_total_new_packets',

        # how many dropped packets
        '_total_dropped_packets',

        # total missed dropped packets
        '_total_missed_dropped_packets',

        # total lost dropped packets
        '_total_lost_dropped_packets',

        # machine
        '_machine',
        # placements
        '_placements',
        # transceiver
        '_txrx',
    ]
    __DROPPED_MC_MSG = (
        "The router on {}, {} has dropped {} multicast route packets. "
        "Try increasing the machine_time_step and/or the time scale factor "
        "or reducing the number of atoms per core.")
    __DROPPED_LOCAL_MC_MSG = (
        "The router on {}, {} has dropped {} multicast packets that were "
        "transmitted by local cores. This occurs where the router has no "
        "entry associated with the multi-cast key. Try investigating the "
        "keys allocated to the vertices and the router table entries for "
        "this chip.")
    __DEFAULT_MC_MSG = (
        "The router on {}, {} has default routed {} multicast packets, but "
        "the router table did not expect any default routed packets. This "
        "occurs where the router has no entry associated with the multi-cast "
        "key. Try investigating the keys allocated to the vertices and the "
        "router table entries for this chip.")
    __DROPPED_FR_MSG = (
        "The router on chip {}:{} dropped {} Fixed route packets. This is "
        "indicative of a error within the data extraction process as this "
        "is the only expected user of fixed route packets.")
    __MONITOR_MISSED_MSG = "The extra monitor on {}, {} has missed {} packets."
    __MONITOR_DROPPED_MSG = (
        "The extra monitor on {}, {} has dropped {} packets.")
    __MONITOR_DUMPED_LINK_MSG = (
        "The extra monitor on {}, {} has detected that {} packets were "
        "dumped from a outgoing link of this chip's router. This often "
        "occurs when external devices are used in the script but not "
        "connected to the communication fabric correctly. These packets may "
        "have been reinjected multiple times and so this number may be a "
        "overestimate.")
    __MONITOR_DUMPED_PROC_MSG = (
        "The extra monitor on {}, {} has detected that {} packets were "
        "dumped from a core failing to take the packet. This often occurs "
        "when the executable has crashed or has not been given a multicast "
        "packet callback. It can also result from the core taking too long "
        "to process each packet. These packets were reinjected and so this "
        "number is likely a overestimate.")
    __ROUTER_ERR_MSG = (
        "The router on {}, {} has a non-zero error status. This could "
        "indicate a hardware fault. The errors set are {}, and the error "
        "count is {}")

    def __call__(
            self, transceiver, machine, router_tables, using_reinjection,
            provenance_data_objects=None, extra_monitor_vertices=None,
            placements=None):
        """
        :param ~.Transceiver transceiver:
        :param ~.Machine machine:
        :param ~.MulticastRoutingTables router_tables:
        :param bool using_reinjection:
        :param list(~.ProvenanceDataItem) provenance_data_objects:
        :param list(ExtraMonitorSupportMachineVertex) extra_monitor_vertices:
        :param ~.Placements placements:
        """
        # pylint: disable=too-many-arguments
        # pylint: disable=attribute-defined-outside-init
        self._total_sent_packets = 0
        self._total_new_packets = 0
        self._total_dropped_packets = 0
        self._total_missed_dropped_packets = 0
        self._total_lost_dropped_packets = 0
        self._txrx = transceiver
        self._machine = machine
        self._placements = placements

        if provenance_data_objects is not None:
            prov_items = provenance_data_objects
        else:
            prov_items = list()

        self._add_router_provenance_data(
            router_tables, extra_monitor_vertices, prov_items)

        prov_items.extend(self.__summary_items())
        return prov_items

    def __summary_items(self):
        """
        :rtype: iterable(ProvenanceDataItem)
        """
        yield ProvenanceDataItem(
            ["router_provenance", "total_multi_cast_sent_packets"],
            self._total_sent_packets)
        yield ProvenanceDataItem(
            ["router_provenance", "total_created_packets"],
            self._total_new_packets)
        yield ProvenanceDataItem(
            ["router_provenance", "total_dropped_packets"],
            self._total_dropped_packets)
        yield ProvenanceDataItem(
            ["router_provenance", "total_missed_dropped_packets"],
            self._total_missed_dropped_packets)
        yield ProvenanceDataItem(
            ["router_provenance", "total_lost_dropped_packets"],
            self._total_lost_dropped_packets)

    def _add_router_provenance_data(
            self, router_tables, extra_monitor_vertices, items):
        """ Writes the provenance data of the router diagnostics

        :param ~.MulticastRoutingTables router_tables:
            the routing tables generated by PACMAN
        :param list(ExtraMonitorSupportMachineVertex) extra_monitor_vertices:
            list of extra monitor vertices
        :param list(ProvenanceDataItem) items:
        """
        progress = ProgressBar(self._machine.n_chips*2,
                               "Getting Router Provenance")

        seen_chips = set()

        # get all extra monitor core data if it exists
        reinjection_data = None
        if extra_monitor_vertices is not None:
            monitor = extra_monitor_vertices[0]
            reinjection_data = monitor.get_reinjection_status_for_vertices(
                placements=self._placements,
                extra_monitor_cores_for_data=extra_monitor_vertices,
                transceiver=self._txrx)

        for router_table in progress.over(sorted(
                router_tables.routing_tables,
                key=lambda table: (table.x, table.y)), False):
            self._add_router_table_diagnostic(
                router_table, seen_chips, items, reinjection_data)

        # Get what info we can for chips where there are problems or no table
        for chip in progress.over(sorted(
                self._machine.chips, key=lambda c: (c.x, c.y))):
            if not chip.virtual and (chip.x, chip.y) not in seen_chips:
                self._add_unseen_router_chip_diagnostic(
                    chip, items, reinjection_data)

    def _add_router_table_diagnostic(
            self, table, seen_chips, items, reinjection_data):
        """
        :param ~.MulticastRoutingTable table:
        :param set(tuple(int,int)) seen_chips:
        :param list(ProvenanceDataItem) items:
        :param dict(tuple(int,int),ReInjectionStatus) reinjection_data:
        """
        # pylint: disable=too-many-arguments, bare-except
        x = table.x
        y = table.y
        if not self._machine.get_chip_at(x, y).virtual:
            try:
                diagnostics = self._txrx.get_router_diagnostics(x, y)
            except:  # noqa: E722
                logger.warning(
                    "Could not read routing diagnostics from {}, {}",
                    x, y, exc_info=True)
                return
            seen_chips.add((x, y))
            status = self.__get_status(reinjection_data, x, y)
            items.extend(self.__router_diagnostics(
                x, y, diagnostics, status, True, table))
            self.__add_totals(diagnostics, status)

    def _add_unseen_router_chip_diagnostic(
            self, chip, items, reinjection_data):
        """
        :param ~.Chip chip:
        :param set(tuple(int,int)) seen_chips:
        :param list(ProvenanceDataItem) items:
        :param dict(tuple(int,int),ReInjectionStatus) reinjection_data:
        """
        # pylint: disable=bare-except
        try:
            diagnostics = self._txrx.get_router_diagnostics(chip.x, chip.y)
        except:  # noqa: E722
            # There could be issues with unused chips - don't worry!
            return
        if (diagnostics.n_dropped_multicast_packets or
                diagnostics.n_local_multicast_packets or
                diagnostics.n_external_multicast_packets):
            status = self.__get_status(reinjection_data, chip.x, chip.y)
            items.extend(self.__router_diagnostics(
                chip.x, chip.y, diagnostics, status, False, None))
            self.__add_totals(diagnostics, status)

    @staticmethod
    def __get_status(reinjection_data, x, y):
        """
        :param dict(tuple(int,int),ReInjectionStatus) reinjection_data:
        :param int x:
        :param int y:
        :rtype: ReInjectionStatus or None
        """
        status = None
        if reinjection_data is not None:
            status = reinjection_data[x, y]
        return status

    def __add_totals(self, diagnostics, status):
        """
        :param ~.RouterDiagnostics diagnostics:
        :param ReInjectionStatus status:
        """
        self._total_sent_packets += (
            diagnostics.n_local_multicast_packets +
            diagnostics.n_external_multicast_packets)
        self._total_new_packets += diagnostics.n_local_multicast_packets
        self._total_dropped_packets += diagnostics.n_dropped_multicast_packets
        if status is not None:
            self._total_missed_dropped_packets += (
                status.n_missed_dropped_packets)
            self._total_lost_dropped_packets += (
                status.n_dropped_packet_overflows)
        else:
            self._total_lost_dropped_packets += (
                diagnostics.n_dropped_multicast_packets)

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
        :rtype: iterable(ProvenanceDataItem)
        """
        # pylint: disable=too-many-arguments
        names = ["router_provenance"]
        if expected:
            names.append("expected_routers")
        else:
            names.append("unexpected_routers")
        names.append("router_at_chip_{}_{}".format(x, y))

        yield ProvenanceDataItem(
            names + ["Local_Multicast_Packets"],
            diagnostics.n_local_multicast_packets)
        yield ProvenanceDataItem(
            names + ["External_Multicast_Packets"],
            diagnostics.n_external_multicast_packets)

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

        yield ProvenanceDataItem(
            names + ["Dropped_Multicast_Packets"],
            diagnostics.n_dropped_multicast_packets,
            report=((has_dropped and not has_reinjection) or (
                has_dropped and has_reinjection and missing_stuff)),
            message=self.__DROPPED_MC_MSG.format(
                x, y, diagnostics.n_dropped_multicast_packets))
        yield ProvenanceDataItem(
            names + ["Dropped_Multicast_Packets_via_local_transmission"],
            diagnostics.user_3,
            report=(diagnostics.user_3 > 0),
            message=self.__DROPPED_LOCAL_MC_MSG.format(
                x, y, diagnostics.user_3))
        yield ProvenanceDataItem(
            names + ["default_routed_external_multicast_packets"],
            diagnostics.user_2,
            report=(diagnostics.user_2 > 0 and not (
                table and table.number_of_defaultable_entries)),
            message=self.__DEFAULT_MC_MSG.format(x, y, diagnostics.user_2))

        if table:
            yield ProvenanceDataItem(
                names + ["Entries"], table.number_of_entries)
            routes = set()
            for ent in table.multicast_routing_entries:
                routes.add(ent.spinnaker_route)
            yield ProvenanceDataItem(
                names + ["Unique_Routes"], len(routes))

        yield ProvenanceDataItem(
            names + ["Local_P2P_Packets"],
            diagnostics.n_local_peer_to_peer_packets)
        yield ProvenanceDataItem(
            names + ["External_P2P_Packets"],
            diagnostics.n_external_peer_to_peer_packets)
        yield ProvenanceDataItem(
            names + ["Dropped_P2P_Packets"],
            diagnostics.n_dropped_peer_to_peer_packets)
        yield ProvenanceDataItem(
            names + ["Local_NN_Packets"],
            diagnostics.n_local_nearest_neighbour_packets)
        yield ProvenanceDataItem(
            names + ["External_NN_Packets"],
            diagnostics.n_external_nearest_neighbour_packets)
        yield ProvenanceDataItem(
            names + ["Dropped_NN_Packets"],
            diagnostics.n_dropped_nearest_neighbour_packets)
        yield ProvenanceDataItem(
            names + ["Local_FR_Packets"],
            diagnostics.n_local_fixed_route_packets)
        yield ProvenanceDataItem(
            names + ["External_FR_Packets"],
            diagnostics.n_external_fixed_route_packets)
        yield ProvenanceDataItem(
            names + ["Dropped_FR_Packets"],
            diagnostics.n_dropped_fixed_route_packets,
            report=(diagnostics.n_dropped_fixed_route_packets > 0),
            message=self.__DROPPED_FR_MSG.format(
                x, y, diagnostics.n_dropped_fixed_route_packets))

        if status is not None:
            yield ProvenanceDataItem(
                names + ["Received_For_Reinjection"], status.n_dropped_packets)
            yield ProvenanceDataItem(
                names + ["Missed_For_Reinjection"],
                status.n_missed_dropped_packets,
                report=(status.n_missed_dropped_packets > 0),
                message=self.__MONITOR_MISSED_MSG.format(
                    x, y, status.n_missed_dropped_packets))
            yield ProvenanceDataItem(
                names + ["Reinjection_Overflows"],
                status.n_dropped_packet_overflows,
                report=(status.n_dropped_packet_overflows > 0),
                message=self.__MONITOR_DROPPED_MSG.format(
                    x, y, status.n_dropped_packet_overflows))
            yield ProvenanceDataItem(
                names + ["Reinjected"], status.n_reinjected_packets)
            yield ProvenanceDataItem(
                names + ["Dumped_from_a_Link"], status.n_link_dumps,
                report=(
                    status.n_link_dumps > 0 and
                    self.__has_virtual_chip_connected(x, y)),
                message=self.__MONITOR_DUMPED_LINK_MSG.format(
                    x, y, status.n_link_dumps))
            yield ProvenanceDataItem(
                names + ["Dumped_from_a_processor"], status.n_processor_dumps,
                report=(status.n_processor_dumps > 0),
                message=self.__MONITOR_DUMPED_PROC_MSG.format(
                    x, y, status.n_processor_dumps))

        yield ProvenanceDataItem(
            names + ["Error status"], diagnostics.error_status,
            report=(diagnostics.error_status > 0),
            message=self.__ROUTER_ERR_MSG.format(
                x, y, diagnostics.errors_set, diagnostics.error_count))

    def __has_virtual_chip_connected(self, x, y):
        """
        :param int x:
        :param int y:
        :rtype: bool
        """
        return any(
            self._machine.get_chip_at(
                link.destination_x, link.destination_y).virtual
            for link in self._machine.get_chip_at(x, y).router.links)

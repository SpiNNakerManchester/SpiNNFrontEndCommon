from spinn_utilities.progress_bar import ProgressBar

# front end common imports
from spinn_front_end_common.utilities.utility_objs import ProvenanceDataItem
from spinn_front_end_common.utilities.exceptions import ConfigurationException

import logging

logger = logging.getLogger(__name__)


class RouterProvenanceGatherer(object):
    """
    RouterProvenanceGatherer: gathers diagnostics from the
    routers.
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
        '_total_lost_dropped_packets'

        # total
    ]

    def __call__(
            self, transceiver, machine, router_tables, has_ran,
            provenance_data_objects=None):
        """
        :param transceiver: the SpiNNMan interface object
        :param machine: the python representation of the spinnaker machine
        :param router_tables: the router tables that have been generated
        :param has_ran: token that states that the simulation has ran
        """

        if not has_ran:
            raise ConfigurationException(
                "This function has been called before the simulation has ran."
                " This is deemed an error, please rectify and try again")

        self._total_sent_packets = 0
        self._total_new_packets = 0
        self._total_dropped_packets = 0
        self._total_missed_dropped_packets = 0
        self._total_lost_dropped_packets = 0

        if provenance_data_objects is not None:
            prov_items = provenance_data_objects
        else:
            prov_items = list()

        prov_items.extend(self._write_router_provenance_data(
            router_tables, machine, transceiver))

        prov_items.append(ProvenanceDataItem(
            ["router_provenance", "total_multi_cast_sent_packets"],
            self._total_sent_packets))
        prov_items.append(ProvenanceDataItem(
            ["router_provenance", "total_created_packets"],
            self._total_new_packets))
        prov_items.append(ProvenanceDataItem(
            ["router_provenance", "total_dropped_packets"],
            self._total_dropped_packets))
        prov_items.append(ProvenanceDataItem(
            ["router_provenance", "total_missed_dropped_packets"],
            self._total_missed_dropped_packets))
        prov_items.append(ProvenanceDataItem(
            ["router_provenance", "total_lost_dropped_packets"],
            self._total_lost_dropped_packets))

        return prov_items

    def _write_router_provenance_data(self, router_tables, machine, txrx):
        """ Writes the provenance data of the router diagnostics

        :param router_tables: the routing tables generated by pacman
        :param machine: the spinnMachine object
        :param txrx: the transceiver object
        """
        progress = ProgressBar(machine.n_chips*2, "Getting Router Provenance")

        # acquire diagnostic data
        items = list()
        seen_chips = set()

        for router_table in sorted(
                router_tables.routing_tables,
                key=lambda table: (table.x, table.y)):
            self._write_router_table_diagnostic(
                txrx, machine, router_table.x, router_table.y, seen_chips,
                router_table, items)
            progress.update()

        for chip in sorted(machine.chips, key=lambda c: (c.x, c.y)):
            self._write_router_chip_diagnostic(txrx, chip, seen_chips, items)
            progress.update()
        progress.end()
        return items

    def _write_router_table_diagnostic(self, txrx, machine, x, y, seen_chips,
                                       router_table, items):
        if not machine.get_chip_at(x, y).virtual:
            try:
                router_diagnostic = txrx.get_router_diagnostics(x, y)
                seen_chips.add((x, y))
                reinjector_status = txrx.get_reinjection_status(x, y)
                items.extend(self._write_router_diagnostics(
                    x, y, router_diagnostic, reinjector_status, True,
                    router_table))
                self._add_totals(router_diagnostic, reinjector_status)
            except Exception as e:
                logger.warn(
                    "Could not read routing diagnostics from {}, {}: {}"
                    .format(x, y, e))

    def _write_router_chip_diagnostic(self, txrx, chip, seen_chips, items):
        if not chip.virtual and (chip.x, chip.y) not in seen_chips:
            try:
                diagnostic = txrx.get_router_diagnostics(chip.x, chip.y)

                if (diagnostic.n_dropped_multicast_packets or
                        diagnostic.n_local_multicast_packets or
                        diagnostic.n_external_multicast_packets):
                    reinjector_status = txrx.get_reinjection_status(
                            chip.x, chip.y)
                    items.extend(self._write_router_diagnostics(
                            chip.x, chip.y, diagnostic, reinjector_status,
                            False, None))
                    self._add_totals(diagnostic, reinjector_status)
            except Exception:
                # There could be issues with unused chips - don't worry!
                pass

    def _add_totals(self, router_diagnostic, reinjector_status):
        self._total_sent_packets += (
            router_diagnostic.n_local_multicast_packets +
            router_diagnostic.n_external_multicast_packets)
        self._total_new_packets += router_diagnostic.n_local_multicast_packets
        self._total_dropped_packets += (
            router_diagnostic.n_dropped_multicast_packets)
        if reinjector_status is not None:
            self._total_missed_dropped_packets += (
                reinjector_status.n_missed_dropped_packets)
            self._total_lost_dropped_packets += (
                reinjector_status.n_dropped_packet_overflows)
        else:
            self._total_lost_dropped_packets += (
                router_diagnostic.n_dropped_multicast_packets)

    @staticmethod
    def _add_name(names, name):
        new_names = list(names)
        new_names.append(name)
        return new_names

    def _write_router_diagnostics(
            self, x, y, router_diagnostic, reinjector_status, expected,
            router_table):
        """ Stores router diagnostics as a set of provenance data items

        :param x: x coord of the router in question
        :param y: y coord of the router in question
        :param router_diagnostic: the router diagnostic object
        :param reinjector_status: the data gained from the reinjector
        :param router_table: the router table generated by the PACMAN tools
        """
        names = list()
        names.append("router_provenance")
        if expected:
            names.append("expected_routers")
        else:
            names.append("unexpected_routers")
        names.append("router_at_chip_{}_{}".format(x, y))

        items = list()

        items.append(ProvenanceDataItem(
            self._add_name(names, "Local_Multicast_Packets"),
            str(router_diagnostic.n_local_multicast_packets)))
        items.append(ProvenanceDataItem(
            self._add_name(names, "External_Multicast_Packets"),
            str(router_diagnostic.n_external_multicast_packets)))
        items.append(ProvenanceDataItem(
            self._add_name(names, "Dropped_Multicast_Packets"),
            str(router_diagnostic.n_dropped_multicast_packets),
            report=(
                router_diagnostic.n_dropped_multicast_packets > 0 and
                reinjector_status is None),
            message=(
                "The router on {}, {} has dropped {} multicast route packets. "
                "Try increasing the machine_time_step and/or the time scale "
                "factor or reducing the number of atoms per core."
                .format(x, y, router_diagnostic.n_dropped_multicast_packets))))
        items.append(ProvenanceDataItem(
            self._add_name(
                names, "Dropped_Multicast_Packets_via_local_transmission"),
            str(router_diagnostic.user_3),
            report=(router_diagnostic.user_3 > 0),
            message=(
                "The router on {}, {} has dropped {} multicast packets that"
                " were transmitted by local cores. This occurs where the "
                "router has no entry associated with the multi-cast key. "
                "Try investigating the keys allocated to the vertices and "
                "the router table entries for this chip.".format(
                    x, y, router_diagnostic.user_3))))
        items.append(ProvenanceDataItem(
            self._add_name(names, "default_routed_external_multicast_packets"),
            str(router_diagnostic.user_2),
            report=(router_diagnostic.user_2 > 0 and
                    ((router_table is not None and
                      router_table.number_of_defaultable_entries == 0) or
                     router_table is None)),
            message=(
                "The router on {}, {} has default routed {} multicast packets,"
                " but the router table did not expect any default routed "
                "packets. This occurs where the router has no entry"
                " associated with the multi-cast key. "
                "Try investigating the keys allocated to the vertices and "
                "the router table entries for this chip.".format(
                    x, y, router_diagnostic.user_2))))

        items.append(ProvenanceDataItem(
            self._add_name(names, "Local_P2P_Packets"),
            str(router_diagnostic.n_local_peer_to_peer_packets)))
        items.append(ProvenanceDataItem(
            self._add_name(names, "External_P2P_Packets"),
            str(router_diagnostic.n_external_peer_to_peer_packets)))
        items.append(ProvenanceDataItem(
            self._add_name(names, "Dropped_P2P_Packets"),
            str(router_diagnostic.n_dropped_peer_to_peer_packets)))
        items.append(ProvenanceDataItem(
            self._add_name(names, "Local_NN_Packets"),
            str(router_diagnostic.n_local_nearest_neighbour_packets)))
        items.append(ProvenanceDataItem(
            self._add_name(names, "External_NN_Packets"),
            str(router_diagnostic.n_external_nearest_neighbour_packets)))
        items.append(ProvenanceDataItem(
            self._add_name(names, "Dropped_NN_Packets"),
            str(router_diagnostic.n_dropped_nearest_neighbour_packets)))
        items.append(ProvenanceDataItem(
            self._add_name(names, "Local_FR_Packets"),
            str(router_diagnostic.n_local_fixed_route_packets)))
        items.append(ProvenanceDataItem(
            self._add_name(names, "External_FR_Packets"),
            str(router_diagnostic.n_external_fixed_route_packets)))
        items.append(ProvenanceDataItem(
            self._add_name(names, "Dropped_FR_Packets"),
            str(router_diagnostic.n_dropped_fixed_route_packets)))
        if reinjector_status is not None:
            items.append(ProvenanceDataItem(
                self._add_name(names, "Received_For_Reinjection"),
                reinjector_status.n_dropped_packets))
            items.append(ProvenanceDataItem(
                self._add_name(names, "Missed_For_Reinjection"),
                reinjector_status.n_missed_dropped_packets,
                report=reinjector_status.n_missed_dropped_packets > 0,
                message=(
                    "The reinjector on {}, {} has missed {} packets.".format(
                        x, y, reinjector_status.n_missed_dropped_packets))))
            items.append(ProvenanceDataItem(
                self._add_name(names, "Reinjection_Overflows"),
                reinjector_status.n_dropped_packet_overflows,
                report=reinjector_status.n_dropped_packet_overflows > 0,
                message=(
                    "The reinjector on {}, {} has dropped {} packets.".format(
                        x, y, reinjector_status.n_dropped_packet_overflows))))
            items.append(ProvenanceDataItem(
                self._add_name(names, "Reinjected"),
                reinjector_status.n_reinjected_packets))
            items.append(ProvenanceDataItem(
                self._add_name(names, "Dumped_from_a_Link"),
                str(reinjector_status.n_link_dumps),
                report=reinjector_status.n_link_dumps > 0,
                message=(
                    "The reinjector on {}, {} has detected that {} packets "
                    "were dumped from a outgoing link of this chip's router."
                    " This often occurs when external devices are used in the "
                    "script but not connected to the communication fabric "
                    "correctly. These packets may have been reinjected "
                    "multiple times and so this number may be a overestimate."
                    .format(x, y, reinjector_status.n_link_dumps))))
            items.append(ProvenanceDataItem(
                self._add_name(names, "Dumped_from_a_processor"),
                str(reinjector_status.n_processor_dumps),
                report=reinjector_status.n_processor_dumps > 0,
                message=(
                    "The reinjector on {}, {} has detected that {} packets "
                    "were dumped from a core failing to take the packet."
                    " This often occurs when the executable has crashed or"
                    " has not been given a multicast packet callback. It can"
                    " also result from the core taking too long to process"
                    " each packet. These packets were reinjected and so this"
                    " number is likely a overestimate.".format(
                        x, y, reinjector_status.n_processor_dumps))))
        return items

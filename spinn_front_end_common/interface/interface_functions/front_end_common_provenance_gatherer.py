# pacman imports
from pacman.interfaces.abstract_provides_provenance_data import \
    AbstractProvidesProvenanceData
from pacman.utilities.utility_objs.progress_bar import ProgressBar

# front end common imports
from spinn_front_end_common.utilities import exceptions

# general imports
import os
from lxml import etree


class FrontEndCommonProvenanceGatherer(object):
    """
    """

    def __call__(self, file_path, transceiver, machine, router_tables, has_ran,
                 placements):
        """
        :param file_path: the file apth to write the provenance data to
        :param transceiver: the spinnman interface object
        :param machine: the python representation of the spiunnaker machine
        :param router_tables: the router tables that have been generated
        :param has_ran: token that states that the simulation has ran
        :return: none
        """

        if has_ran:
            root = etree.Element("root")
            router_file_path = os.path.join(file_path, "router_provenance.xml")
            self._write_router_provenance_data(
                root, router_tables, machine, transceiver)
            writer = open(router_file_path, "w")
            writer.write(etree.tostring(root, pretty_print=True))

            progress = ProgressBar(placements.n_placements,
                                   "Getting provenance data")

            # retrieve provenance data from any cores that provide data
            for placement in placements.placements:
                if isinstance(placement.subvertex,
                              AbstractProvidesProvenanceData):
                    core_file_path = os.path.join(
                        file_path,
                        "Provanence_data_for_{}_{}_{}_{}.xml".format(
                            placement.subvertex.label,
                            placement.x, placement.y, placement.p))
                    placement.subvertex.write_provenance_data_in_xml(
                        core_file_path, transceiver, placement)
                progress.update()
            progress.end()

        else:
            raise exceptions.ConfigurationException(
                "This function has been called before the simulation has ran."
                " This is deemed an error, please rectify and try again")

    def _write_router_provenance_data(
            self, root, router_tables, machine, txrx):
        """ Helper method which writes the provenance data of the router diag
        :param root: the root element to add diagnostics to
        :return: None
        """
        progress = ProgressBar(
            machine.n_chips,
            "Getting provenance data from machine's routing tables")

        # acquire diagnostic data
        router_diagnostics = dict()
        reinjector_statuses = dict()
        for router_table in router_tables.routing_tables:
            x = router_table.x
            y = router_table.y
            if not machine.get_chip_at(x, y).virtual:
                router_diagnostic = txrx.get_router_diagnostics(x, y)
                router_diagnostics[x, y] = router_diagnostic
                reinjector_status = txrx.get_reinjection_status(x, y)
                reinjector_statuses[x, y] = reinjector_status
        doc = etree.SubElement(root, "router_counters")
        expected_routers = etree.SubElement(doc, "Used_Routers")
        for x, y in router_diagnostics:
            self._write_router_diag(
                expected_routers, x, y, router_diagnostics[x, y],
                reinjector_statuses[x, y])
            progress.update()
        unexpected_routers = etree.SubElement(doc, "Unexpected_Routers")
        for chip in machine.chips:
            if not chip.virtual:
                if (chip.x, chip.y) not in router_diagnostics:
                    router_diagnostic = \
                        txrx.get_router_diagnostics(chip.x, chip.y)
                    has_dropped_mc_packets = \
                        router_diagnostic.n_dropped_multicast_packets != 0
                    has_local_multicast_packets = \
                        router_diagnostic.n_local_multicast_packets != 0
                    has_external_multicast_packets = \
                        router_diagnostic.n_external_multicast_packets != 0
                    reinjector_status = \
                        txrx.get_reinjection_status(chip.x, chip.y)
                    if (has_dropped_mc_packets or
                            has_local_multicast_packets or
                            has_external_multicast_packets):
                        self._write_router_diag(
                            unexpected_routers, chip.x, chip.y,
                            router_diagnostic, reinjector_status)
                        progress.update()
        progress.end()

    @staticmethod
    def _write_router_diag(parent_xml_element, x, y, router_diagnostic,
                           reinjector_status):
        router = etree.SubElement(
            parent_xml_element, "router_at_chip_{}_{}".format(x, y))
        etree.SubElement(router, "Loc__MC").text = str(
            router_diagnostic.n_local_multicast_packets)
        etree.SubElement(router, "Ext__MC").text = str(
            router_diagnostic.n_external_multicast_packets)
        etree.SubElement(router, "Dump_MC").text = str(
            router_diagnostic.n_dropped_multicast_packets)
        etree.SubElement(router, "Loc__PP").text = str(
            router_diagnostic.n_local_peer_to_peer_packets)
        etree.SubElement(router, "Ext__PP").text = str(
            router_diagnostic.n_external_peer_to_peer_packets)
        etree.SubElement(router, "Dump_PP").text = str(
            router_diagnostic.n_dropped_peer_to_peer_packets)
        etree.SubElement(router, "Loc__NN").text = str(
            router_diagnostic.n_local_nearest_neighbour_packets)
        etree.SubElement(router, "Ext__NN").text = str(
            router_diagnostic.n_external_nearest_neighbour_packets)
        etree.SubElement(router, "Dump_NN").text = str(
            router_diagnostic.n_dropped_nearest_neighbour_packets)
        etree.SubElement(router, "Loc__FR").text = str(
            router_diagnostic.n_local_fixed_route_packets)
        etree.SubElement(router, "Ext__FR").text = str(
            router_diagnostic.n_external_fixed_route_packets)
        etree.SubElement(router, "Dump_FR").text = str(
            router_diagnostic.n_dropped_fixed_route_packets)
        if reinjector_status is not None:
            etree.SubElement(router, "ReceviedForReinjection").text = str(
                reinjector_status.n_dropped_packets)
            etree.SubElement(router, "MissedForReinjection").text = str(
                reinjector_status.n_missed_dropped_packets)
            etree.SubElement(router, "ReinjectionOverflows").text = str(
                reinjector_status.n_dropped_packet_overflows)
            etree.SubElement(router, "Reinjected").text = str(
                reinjector_status.n_reinjected_packets)

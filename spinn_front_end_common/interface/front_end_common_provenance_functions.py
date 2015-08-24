"""
FrontEndCommonProvanenceFunctions
"""

# front end common imports
from spinn_front_end_common.abstract_models.\
    abstract_provides_provenance_data import AbstractProvidesProvenanceData


# general imports
import os
from lxml import etree


class FrontEndCommonProvenanceFunctions(AbstractProvidesProvenanceData):
    """
    functions supproting front ends with generating provenance data
    """

    def __init__(self):
        AbstractProvidesProvenanceData.__init__(self)

    def write_provenance_data_in_xml(self, file_path, transceiver,
                                     placement=None):
        """
        inheirtted from abstract prodives provenance data. forces the front end
        to gather machine like proenance which it desires.
        :param file_path: the file apth to write the provenance data to
        :param transceiver: the spinnman interface object
        :param placement: the placement object for this subvertex or None if
        the system does not require a placement object
        :return: none
        """
        root = etree.Element("root")
        router_file_path = os.path.join(file_path, "router_provenance.xml")
        self._write_router_provenance_data(root)
        writer = open(router_file_path, "w")
        writer.write(etree.tostring(root, pretty_print=True))

    def _write_router_provenance_data(self, root):
        """
        helper method which writes the provenance data of the router diag
        :param root: the root element to add diagnostics to
        :return: None
        """
        # acquire diagnostic data
        router_diagnostics = dict()
        reinjector_statuses = dict()
        for router_table in self._router_tables.routing_tables:
            x = router_table.x
            y = router_table.y
            if not self._machine.get_chip_at(x, y).virtual:
                router_diagnostic = self._txrx.get_router_diagnostics(x, y)
                router_diagnostics[x, y] = router_diagnostic
                reinjector_status = self._txrx.get_reinjection_status(x, y)
                reinjector_statuses[x, y] = reinjector_status
        doc = etree.SubElement(root, "router_counters")
        expected_routers = etree.SubElement(doc, "Used_Routers")
        for x, y in router_diagnostics:
            self._write_router_diag(
                expected_routers, x, y, router_diagnostics[x, y],
                reinjector_statuses[x, y])
        unexpected_routers = etree.SubElement(doc, "Unexpected_Routers")
        for chip in self._machine.chips:
            if not chip.virtual:
                if (chip.x, chip.y) not in router_diagnostics:
                    router_diagnostic = \
                        self._txrx.get_router_diagnostics(chip.x, chip.y)
                    has_dropped_mc_packets = \
                        router_diagnostic.n_dropped_multicast_packets != 0
                    has_local_multicast_packets = \
                        router_diagnostic.n_local_multicast_packets != 0
                    has_external_multicast_packets = \
                        router_diagnostic.n_external_multicast_packets != 0

                    if (has_dropped_mc_packets or
                            has_local_multicast_packets or
                            has_external_multicast_packets):
                        self._write_router_diag(
                            unexpected_routers, chip.x, chip.y,
                            router_diagnostics[chip.x, chip.y],
                            reinjector_statuses[chip.x, chip.y])

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

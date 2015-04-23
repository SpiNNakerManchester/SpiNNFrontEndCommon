"""
FrontEndCommonProvanenceFunctions
"""

# front end common imports
from spinn_front_end_common.abstract_models.\
    abstract_provides_provanence_data import AbstractProvidesProvanenceData


# general imports
import os
from lxml import etree

class FrontEndCommonProvanenceFunctions(AbstractProvidesProvanenceData):
    """
    functions supproting front ends with generating provanence data
    """

    def __init__(self):
        AbstractProvidesProvanenceData.__init__(self)

    def _write_provanence_data_in_xml(self, file_path):
        """
        inheirtted from abstract prodives provanence data. forces the front end
        to gather machine like proenance which it desires.
        :param file_path: the file apth to write the provanence data to
        :return: none
        """
        root = etree.Element("root")
        router_file_path = os.path.join(file_path, "router_provanence.xml")
        self._write_router_provanence_data(root)
        writer = open(router_file_path, "w")
        writer.write(etree.tostring(root, pretty_print=True))

    def _write_router_provanence_data(self, root):
        """
        helper method which writes the provanence data of the router diag
        :param root: the root element to add diagnostics to
        :return: None
        """
        # acquire diagnostic data
        router_diagnostics = dict()
        for router_table in self._router_tables.routing_tables:
            if not self._machine.get_chip_at(router_table.x,
                                             router_table.y).virtual:
                router_diagnostic = self._txrx.\
                    get_router_diagnostics(router_table.x, router_table.y)
                router_diagnostics[router_table.x, router_table.y] = \
                    router_diagnostic
        doc = etree.SubElement(root, "router_counters")
        expected_routers = etree.SubElement(doc, "Used_Routers")
        for router_diagnostic_coords in router_diagnostics:
            self._write_router_diag(
                expected_routers, router_diagnostic_coords,
                router_diagnostics[router_diagnostic_coords])
        unexpected_routers = etree.SubElement(doc, "Unexpected_Routers")
        for chip in self._machine.chips:
            if not chip.virtual:
                coords = (chip.x, chip.y)
                if coords not in router_diagnostics:
                    router_diagnostic = \
                        self._txrx.get_router_diagnostics(chip.x, chip.y)
                    if (router_diagnostic.n_dropped_multicast_packets != 0 or
                            router_diagnostic.n_local_multicast_packets != 0 or
                            router_diagnostic.n_external_multicast_packets != 0):
                        self._write_router_diag(
                            unexpected_routers, router_diagnostic_coords,
                            router_diagnostics[router_diagnostic_coords])

    @staticmethod
    def _write_router_diag(parent_xml_element, router_diagnostic_coords,
                           router_diagnostic):
        from lxml import etree
        router = etree.SubElement(
            parent_xml_element, "router_at_chip_{}_{}".format(
                router_diagnostic_coords[0], router_diagnostic_coords[1]))
        etree.SubElement(router, "Loc__MC").text = \
            str(router_diagnostic.n_local_multicast_packets)
        etree.SubElement(router, "Ext__MC").text = \
            str(router_diagnostic.n_external_multicast_packets)
        etree.SubElement(router, "Dump_MC").text = \
            str(router_diagnostic.n_dropped_multicast_packets)
        etree.SubElement(router, "Loc__PP").text = \
            str(router_diagnostic.n_local_peer_to_peer_packets)
        etree.SubElement(router, "Ext__PP")\
            .text = str(router_diagnostic.n_external_peer_to_peer_packets)
        etree.SubElement(router, "Dump_PP")\
            .text = str(router_diagnostic.n_dropped_peer_to_peer_packets)
        etree.SubElement(router, "Loc__NN")\
            .text = str(router_diagnostic.n_local_nearest_neighbour_packets)
        etree.SubElement(router, "Ext__NN")\
            .text = str(router_diagnostic.n_external_nearest_neighbour_packets)
        etree.SubElement(router, "Dump_NN")\
            .text = str(router_diagnostic.n_dropped_nearest_neighbour_packets)
        etree.SubElement(router, "Loc__FR").text = \
            str(router_diagnostic.n_local_fixed_route_packets)
        etree.SubElement(router, "Ext__FR")\
            .text = str(router_diagnostic.n_external_fixed_route_packets)
        etree.SubElement(router, "Dump_FR")\
            .text = str(router_diagnostic.n_dropped_fixed_route_packets)
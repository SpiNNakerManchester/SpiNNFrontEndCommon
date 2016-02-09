# general imports
import os
from lxml import etree


class FrontEndCommonProvenanceXMLWriter(object):
    """
    writes provenance data into xml.
    """

    def __call__(self, provenance_data_items, provenance_data_path,
                 router_tables):

        placements_with_prov = \
            provenance_data_items.get_placements_which_have_provenance_data()
        router_provenance = dict()
        for placement in placements_with_prov:

            # if not got a p, its a router based issue, add to routers
            if placement.p is None:
                router_provenance[placement] = provenance_data_items.\
                    get_prov_items_for_placement(placement)
            else:
                # generate file path for xml
                core_file_path = os.path.join(
                    provenance_data_path,
                    "Provenance_data_for_{}_{}_{}_{}.xml".format(
                        placement.subvertex.label,
                        placement.x, placement.y, placement.p))

                # get core level prov data items
                core_prov_items = provenance_data_items.\
                    get_prov_items_for_placement(placement)

                # write core xml
                self._write_data_items_in_xml(
                    core_prov_items, core_file_path, placement)

        # handle operations
        for operation in provenance_data_items.get_operation_ids():
            operation_file_path = os.path.join(
                provenance_data_path,
                "{}_provenance_data.xml".format(operation))
            self._write_operation_xml(
                provenance_data_items.get_prov_items_for_operation(operation),
                operation_file_path)

        self._generate_router_xml(
            provenance_data_path, router_tables, router_provenance)

    @staticmethod
    def _write_operation_xml(prov_items, operation_file_path):
        root = etree.Element("root")
        for item in prov_items:
            element = etree.SubElement(root, item.name)
            element.text = str(item.item)
        # write xml form into file provided
        writer = open(operation_file_path, "w")
        writer.write(etree.tostring(root, pretty_print=True))
        writer.flush()
        writer.close()

    def _generate_router_xml(
            self, provenance_data_path, router_tables, router_provenance):

        # create file path and overhanging elements
        router_file_path = \
            os.path.join(provenance_data_path, "router_provenance.xml")
        root = etree.Element("root")
        doc = etree.SubElement(root, "router_counters")
        expected_routers = etree.SubElement(doc, "Used_Routers")
        unexpected_routers = etree.SubElement(doc, "Unexpected_Routers")

        # generate xml tree for each piece of router provenance
        for placement in router_provenance:
            router_table = router_tables.get_routing_table_for_chip(
                placement.x, placement.y)
            if router_table is None:
                self._write_router_data_in_xml(
                    router_provenance[placement], placement, unexpected_routers)
            else:
                self._write_router_data_in_xml(
                    router_provenance[placement], placement, expected_routers)
        writer = open(router_file_path, "w")
        writer.write(etree.tostring(root, pretty_print=True))
        writer.flush()
        writer.close()

    @staticmethod
    def _write_router_data_in_xml(router_data, placement, parent_xml_element):
        router = etree.SubElement(
            parent_xml_element, "router_at_chip_{}_{}".format(
                placement.x, placement.y))
        for item in router_data:
            element = etree.SubElement(router, item.name)
            element.text = str(item.item)

    @staticmethod
    def _write_data_items_in_xml(prov_data_items, core_file_path, placement):
        # generate tree elements
        root = etree.Element(
            "located_at_{}_{}_{}".format(placement.x, placement.y, placement.p))
        for item in prov_data_items:
            element = etree.SubElement(root, item.name)
            element.text = str(item.item)

        # write xml form into file provided
        writer = open(core_file_path, "w")
        writer.write(etree.tostring(root, pretty_print=True))
        writer.flush()
        writer.close()

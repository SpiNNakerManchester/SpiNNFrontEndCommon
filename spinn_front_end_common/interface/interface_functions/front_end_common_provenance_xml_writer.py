from spinn_front_end_common.utilities import helpful_functions

# general imports
from lxml import etree
import itertools
import string


class FrontEndCommonProvenanceXMLWriter(object):
    """ Write provenance data into XML
    """

    __slots__ = []

    VALID_CHARS = frozenset(
        "-_.() {}{}".format(string.ascii_letters, string.digits))

    def __call__(self, provenance_data_items, provenance_data_path):
        """ writes provenance in xml format

        :param provenance_data_items: data items for provenance
        :param provenance_data_path: the file path to store provenance in
        :return:  None
        """

        # Group data by the first name
        items = sorted(provenance_data_items, key=lambda item: item.names[0])
        for name, group in itertools.groupby(
                items, lambda item: item.names[0]):

            filename = "".join(
                c if c in self.VALID_CHARS else '_' for c in name)

            # generate file path for xml
            file_path = helpful_functions.generate_unique_folder_name(
                provenance_data_path, filename, ".xml")

            # Create a root node
            root = etree.Element("provenance_data_items", name=name)

            # Keep track of sub-categories
            categories = {root: dict()}

            # Go through the items and add them
            for item in group:

                # Add the "categories" for the item (any name between the first
                # and last)
                super_element = root
                cats = categories[root]
                for cat_name in item.names[1:-1]:

                    if cat_name in cats:

                        # If there is already a category of this name under the
                        # super element, use it
                        super_element = cats[cat_name]
                    else:

                        # Otherwise, create a new category under the super
                        # element
                        super_element = etree.SubElement(
                            super_element, "provenance_data_items",
                            name=cat_name)
                        cats[cat_name] = super_element
                        categories[super_element] = dict()

                    # Get the next category for the next run of the loop
                    cats = categories[super_element]

                # Add the item
                element = etree.SubElement(
                    super_element, "provenance_data_item",
                    name=item.names[-1])
                element.text = str(item.value)

            # write xml form into file provided
            writer = open(file_path, "w")
            writer.write(etree.tostring(root, pretty_print=True))
            writer.flush()
            writer.close()

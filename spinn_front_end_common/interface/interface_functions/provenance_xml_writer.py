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

import itertools
import string
from lxml import etree
from spinn_front_end_common.utilities.helpful_functions import (
    generate_unique_folder_name)

_VALID_CHARS = frozenset(
    "-_.() {}{}".format(string.ascii_letters, string.digits))
_XML_BRANCH_NAME = "provenance_data_items"
_XML_LEAF_NAME = "provenance_data_item"


class ProvenanceXMLWriter(object):
    """ Write provenance data into XML
    """

    __slots__ = []

    def __call__(self, provenance_data_items, provenance_data_path):
        """ Writes provenance in XML format

        :param provenance_data_items: data items for provenance
        :param provenance_data_path: the file path to store provenance in
        :return: None
        """

        # Group data by the first name
        items = sorted(provenance_data_items, key=lambda item: item.names[0])
        for name, group in itertools.groupby(
                items, lambda item: item.names[0]):
            # Create a root node
            root = etree.Element(_XML_BRANCH_NAME, name=name)
            # Keep track of sub-categories
            categories = {root: dict()}

            # Go through the items and add them
            for item in group:
                # Add the "categories" for the item (any name between the first
                # and last)
                parent = self._build_path(root, categories, item)

                # Add the item
                element = etree.SubElement(
                    parent, _XML_LEAF_NAME, name=item.names[-1])
                element.text = str(item.value)

            # write xml form into file provided
            with open(self._get_file(provenance_data_path, name), "wb") as f:
                f.write(etree.tostring(root, pretty_print=True))

    @staticmethod
    def _get_file(path, name):
        remapped = "".join(c if c in _VALID_CHARS else '_' for c in name)
        return generate_unique_folder_name(path, remapped, ".xml")

    @staticmethod
    def _build_path(root, categories, item):
        parent = root
        cats = categories[root]
        for cat_name in item.names[1:-1]:
            if cat_name not in cats:
                # If there is not a category of this name under the parent
                # element, create a new category
                parent = etree.SubElement(
                    parent, _XML_BRANCH_NAME, name=cat_name)
                cats[cat_name] = parent
                categories[parent] = dict()
            # Update our state variables for the next run of the loop
            parent = cats[cat_name]
            cats = categories[parent]
        return parent

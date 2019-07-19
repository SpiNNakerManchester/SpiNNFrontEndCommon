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
import json
import string
from spinn_front_end_common.utilities.helpful_functions import (
    generate_unique_folder_name)

_VALID_CHARS = frozenset(
    "-_.() {}{}".format(string.ascii_letters, string.digits))


class ProvenanceJSONWriter(object):
    """ Write provenance data into JSON
    """

    __slots__ = []

    def __call__(self, provenance_data_items, provenance_data_path):

        # Group data by the first name
        items = sorted(provenance_data_items, key=lambda item: item.names[0])
        for name, group in itertools.groupby(
                items, lambda item: item.names[0]):
            # Create a root node
            root = dict()

            # Go through the items and add them
            for item in group:
                # Add the "categories" for the item (any name between the first
                # and last)
                parent = self._build_path(root, item)
                # Add the item
                parent[item.names[-1]] = str(item.value)

            # write json form into file provided
            with open(self._get_file(provenance_data_path, name), "w") as f:
                json.dump(root, f, indent=4, separators=(',', ': '))

    @staticmethod
    def _build_path(root, item):
        parent = root
        for name in item.names[1:-1]:
            if not (name in parent and isinstance(parent[name], dict)):
                # If there isn't already a category of this name under the
                # super element, create a new category under the parent
                parent[name] = dict()
            parent = parent[name]
        return parent

    @staticmethod
    def _get_file(path, name):
        remapped = "".join(c if c in _VALID_CHARS else '_' for c in name)
        return generate_unique_folder_name(path, remapped, ".xml")

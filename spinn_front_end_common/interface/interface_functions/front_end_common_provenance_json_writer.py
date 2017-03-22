# general imports
import os
import itertools
import json
import string


class FrontEndCommonProvenanceJSONWriter(object):
    """ Write provenance data into JSON
    """

    __slots__ = []

    VALID_CHARS = frozenset(
        "-_.() {}{}".format(string.ascii_letters, string.digits))

    def __call__(self, provenance_data_items, provenance_data_path):

        # Group data by the first name
        items = sorted(provenance_data_items, key=lambda item: item.names[0])
        for name, group in itertools.groupby(
                items, lambda item: item.names[0]):

            filename = "".join(
                c if c in self.VALID_CHARS else '_' for c in name)

            # generate file path for xml
            file_path = os.path.join(
                provenance_data_path, "{}.json".format(filename))
            count = 2
            while os.path.exists(file_path):
                file_path = os.path.join(
                    provenance_data_path, "{}_{}.json".format(filename, count))
                count += 1

            # Create a root node
            root = dict()

            # Go through the items and add them
            for item in group:

                # Add the "categories" for the item (any name between the first
                # and last)
                super_element = root
                for cat_name in item.names[1:-1]:

                    if (cat_name in super_element and
                            isinstance(super_element[cat_name], dict)):

                        # If there is already a category of this name under the
                        # super element, use it
                        super_element = super_element[cat_name]
                    else:

                        # Otherwise, create a new category under the super
                        # element
                        super_element[cat_name] = dict()
                        super_element = super_element[cat_name]

                # Add the item
                super_element[item.names[-1]] = str(item.value)

            # write json form into file provided
            writer = open(file_path, "w")
            json.dump(root, writer, indent=4, separators=(',', ': '))
            writer.flush()
            writer.close()

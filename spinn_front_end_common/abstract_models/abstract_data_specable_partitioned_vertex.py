"""
"""

# general imports
from abc import ABCMeta
from six import add_metaclass
from abc import abstractmethod


@add_metaclass(ABCMeta)
class AbstractDataSpecablePartitionedVertex(object):
    """ A partitioned vertex that can generate a data spec based on the\
        information given to it
    """

    @abstractmethod
    def generate_data_spec(
            self, placement, graph, routing_info, ip_tags, reverse_ip_tags,
            report_folder, output_folder, write_text_specs):
        """ Generates a data spec

        :param placement: the placement of the partitioned vertex
        :param graph: the partitioned graph containing the vertex
        :param routing_info: the routing information for the graph
        :param ip_tags: the ip tags associated with this vertex
        :param reverse_ip_tags: the reverse ip tags associated with this vertex
        :param report_folder: the folder to write reports to
        :param output_folder: the folder to write the data spec to
        :param write_text_specs: determines if text-versions of the data spec\
                    should be written, for debug purposes
        :return: The name of the data specification file generated
        """

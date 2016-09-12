import logging
import os
import time

logger = logging.getLogger(__name__)


class FrontEndCommonApplicationGraphNetworkSpecification(object):
    """ Generate report on the user's network specification.
    """

    def __call__(self, report_folder, graph, hostname):
        """
        :param report_folder: the directory to which reports are stored
        :type report_folder: str
        :param graph: the graph generated from the tools
        :type graph:\
                    pacman.model.graph.application.application_graph.ApplicationGraph
        :param hostname: the machine name
        :type hostname:
        :return: None
        """
        filename = report_folder + os.sep + "network_specification.rpt"
        f_network_specification = None
        try:
            f_network_specification = open(filename, "w")
        except IOError:
            logger.error("Generate_placement_reports: Can't open file {}"
                         " for writing.".format(filename))

        f_network_specification.write("        Network Specification\n")
        f_network_specification.write(" =====================\n\n")
        time_date_string = time.strftime("%c")
        f_network_specification.write("Generated: {}".format(time_date_string))
        f_network_specification.write(
            " for target machine '{}'".format(hostname))
        f_network_specification.write("\n\n")

        # Print information on vertices:
        f_network_specification.write("*** Vertices:\n")
        for vertex in graph.vertices:
            label = vertex.label
            model = vertex.__class__.__name__
            size = vertex.n_atoms
            constraints = vertex.constraints
            f_network_specification.write("Vertex {}, size: {}\n"
                                          .format(label, size))
            f_network_specification.write("Model: {}\n".format(model))
            for constraint in constraints:
                f_network_specification.write("constraint: {}\n"
                                              .format(str(constraint)))
            f_network_specification.write("\n")

        # Print information on edges:
        f_network_specification.write("*** Edges:\n")
        for edge in graph.edges:
            label = edge.label
            model = "No Model"
            if hasattr(edge, "connector"):
                model = edge.connector.__class__.__name__
            pre_v = edge.pre_vertex
            post_v = edge.post_vertex
            pre_v_sz = pre_v.n_atoms
            post_v_sz = post_v.n_atoms
            pre_v_label = pre_v.label
            post_v_label = post_v.label
            edge_str = \
                "Edge {} from vertex: '{}' ({} atoms) to vertex: '{}' " \
                "({} atoms)\n".format(label, pre_v_label, pre_v_sz,
                                      post_v_label, post_v_sz)
            f_network_specification.write(edge_str)
            f_network_specification.write("  Model: {}\n".format(model))
            f_network_specification.write("\n")

        # Close file:
        f_network_specification.close()

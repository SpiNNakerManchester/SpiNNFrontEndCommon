import logging
import os
import time

logger = logging.getLogger(__name__)


class FrontEndCommonMachineGraphNetworkSpecificationReport(object):
    """
    """

    def __call__(self, report_folder, machine_graph, hostname):
        """
        :param report_folder: the directory to which reports are stored
        :type report_folder: str
        :param machine_graph: the machine graph generated from the \
                    tools
        :type machine_graph:\
                    pacman.model.graph.machine.machine_graph.MachineGraph
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
        for vertex in machine_graph.vertices:
            label = vertex.label
            model = vertex.__class__.__name__
            constraints = vertex.constraints
            f_network_specification.write("Vertex {}\n".format(label))
            f_network_specification.write("Model: {}\n".format(model))
            for constraint in constraints:
                f_network_specification.write("constraint: {}\n"
                                              .format(str(constraint)))
            f_network_specification.write("\n")

        # Print information on edges:
        f_network_specification.write("*** Edges:\n")
        for edge in machine_graph.edges:
            label = edge.label
            model = "No Model"
            if hasattr(edge, "connector"):
                model = edge.connector.__class__.__name__
            pre_v = edge.pre_vertex
            post_v = edge.post_vertex
            pre_v_label = pre_v.label
            post_v_label = post_v.label
            edge_str = "Edge {} from vertex: '{}' to vertex: '{}' \n"\
                .format(label, pre_v_label, post_v_label)
            f_network_specification.write(edge_str)
            f_network_specification.write("  Model: {}\n".format(model))
            f_network_specification.write("\n")

        # Close file:
        f_network_specification.close()

from spinn_machine.utilities.progress_bar import ProgressBar

from pacman.model.resources.iptag_resource import IPtagResource


class FrontEndCommonPortConnectionAllocator(object):

    __slots__ = []

    def __init__(self):
        pass

    def __call__(self, transceiver, buffer_ip_address, machine_graph):
        """ runs through the application graph and allocates ports to
        tag constrained verts with no port assigned. It does this by creating a
         connection and reading the port. The connection is kept for future
         usage

        :param transceiver: the spinnman interface instance
        :param app_graph: the application graph.
        (is none if using a machine graph as the main graph).
        :type app_graph: pacman.model.graphs.application.impl.
        application_graph.ApplicationGraph
        :param machine_graph: the machine graph.
        (is none is using a app graph as the main graph)
        :type machine_graph: pacman.model.graphs.machine.impl.machine_graph.
        MachineGraph
        :param buffer_ip_address: the ip-address used by the buffer manager
        connections for receiving buffered data
        :return: 2 dicts, 1 for vertex to port mapping and
        1 for port, hostname, to connection
        """

        traffic_identifier_to_port_num = dict()
        verts = machine_graph.vertices
        progress_bar = ProgressBar(
            total_number_of_things_to_do= len(machine_graph.vertices),
            string_describing_what_being_progressed=
            "Allocating ports to connections")

        for vertex in verts:
            for ip_tag in vertex.resources_required.iptags:
                # if not created the connection yet, do so
                if (ip_tag.port is None and
                        ip_tag.traffic_identifier not in
                        traffic_identifier_to_port_num):

                    connection = transceiver.add_connection(
                        ip_tag.connection_type, buffer_ip_address)
                    traffic_identifier_to_port_num[
                        ip_tag.traffic_identifier] = connection.local_port

            progress_bar.update()
        progress_bar.end()

        return traffic_identifier_to_port_num

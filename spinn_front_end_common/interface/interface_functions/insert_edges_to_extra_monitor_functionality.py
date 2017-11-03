from pacman.model.graphs.application import ApplicationEdge
from pacman.model.graphs.machine import MachineEdge
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utility_models.\
    data_speed_up_packet_gatherer_machine_vertex import \
    DataSpeedUpPacketGatherMachineVertex
from spinn_front_end_common.utility_models.\
    extra_monitor_support_application_vertex import \
    ExtraMonitorSupportApplicationVertex
from spinn_front_end_common.utility_models.\
    extra_monitor_support_machine_vertex import \
    ExtraMonitorSupportMachineVertex
from spinn_utilities.progress_bar import ProgressBar


class InsertEdgesToExtraMonitorFunctionality(object):

    def __call__(self, machine_graph, placements, machine,
                 vertex_to_ethernet_connected_chip_mapping,
                 application_graph=None, graph_mapper=None):
        """ inserts edges between verts whom use mc speed up and its local 
        mc data gatherer
        
        :param machine_graph: the machine graph instance 
        :param placements: the placements
        :param machine: the machine object
        :param application_graph: the application graph
        :param vertex_to_ethernet_connected_chip_mapping: mapping between /
        ethernet connected chips and packet gatherers
        :param graph_mapper: the graph mapper
        :rtype: None 
        """
        n_app_vertices = 0
        if application_graph is not None:
            n_app_vertices = len(application_graph.vertices)

        progress = ProgressBar(
            len(machine_graph.vertices) + n_app_vertices,
            "Inserting edges between vertices which require mc speed up "
            "functionality. ")

        for vertex in progress.over(machine_graph.vertices, False):
            if isinstance(vertex, ExtraMonitorSupportMachineVertex):
                self._process_vertex(
                    vertex, machine, placements, machine_graph,
                    vertex_to_ethernet_connected_chip_mapping,
                    application_graph, graph_mapper)

        if application_graph is not None:
            for vertex in progress.over(application_graph.vertices):
                if isinstance(vertex, ExtraMonitorSupportApplicationVertex):
                    machine_verts = graph_mapper.get_machine_vertices(vertex)
                    for machine_vertex in machine_verts:
                        self._process_vertex(
                            machine_vertex, machine, placements, machine_graph,
                            vertex_to_ethernet_connected_chip_mapping,
                            application_graph, graph_mapper)
        progress.end()

    def _process_vertex(
            self, vertex, machine, placements, machine_graph,
            vertex_to_ethernet_connected_chip_mapping, application_graph,
            graph_mapper):
        """
        
        :param vertex: 
        :param machine: 
        :param placements: 
        :param machine_graph: 
        :param vertex_to_ethernet_connected_chip_mapping: 
        :param application_graph: 
        :param graph_mapper: 
        :return: 
        """
        placement = placements.get_placement_of_vertex(vertex)
        chip = machine.get_chip_at(placement.x, placement.y)
        ethernet_connected_chip = machine.get_chip_at(
            chip.nearest_ethernet_x, chip.nearest_ethernet_y)
        data_gatherer_vertex = \
            vertex_to_ethernet_connected_chip_mapping[
                (ethernet_connected_chip.x, ethernet_connected_chip.y)]

        # locate if a edge is already built
        already_built = self._has_edge_already(
            vertex, data_gatherer_vertex, machine_graph)

        # if not built, build a edge and do mapping
        if not already_built:
            machine_edge = MachineEdge(
                vertex, data_gatherer_vertex,
                traffic_type=DataSpeedUpPacketGatherMachineVertex.TRAFFIC_TYPE)
            machine_graph.add_edge(
                machine_edge,
                constants.PARTITION_ID_FOR_MULTICAST_DATA_SPEED_UP)

            if application_graph is not None:
                app_source = graph_mapper.get_application_vertex(vertex)
                app_dest = graph_mapper.get_application_vertex(
                    data_gatherer_vertex)

                # locate if a edge is already built
                already_built = self._has_edge_already(
                    app_source, app_dest, application_graph)

                # if not built, build a edge and do mapping
                if not already_built:
                    app_edge = ApplicationEdge(
                        app_source, app_dest,
                        traffic_type=
                        DataSpeedUpPacketGatherMachineVertex.TRAFFIC_TYPE)
                    application_graph.add_edge(
                        app_edge,
                        constants.PARTITION_ID_FOR_MULTICAST_DATA_SPEED_UP)
                    graph_mapper.add_edge_mapping(machine_edge, app_edge)

    @staticmethod
    def _has_edge_already(source, destination, graph):
        """
        
        :param source: 
        :param destination: 
        :param graph: 
        :return: 
        """
        edges_at_destination = \
            list(graph.get_edges_ending_at_vertex(destination))
        n_edges = len(edges_at_destination)
        position = 0
        found = False
        while not found and position < n_edges:
            if edges_at_destination[position].pre_vertex == source:
                found = True
            position += 1
        return found

from pacman.model.graphs.application import ApplicationVertex, ApplicationEdge
from pacman.model.graphs.machine import MachineEdge
from spinn_front_end_common.utilities import exceptions
from spinn_utilities.progress_bar import ProgressBar


class FrontEndCommonInsertEdgesToLivePacketGatherers(object):
    """ adds edges from the recorded vertices to the local LPGs

    """

    def __call__(
            self, live_packet_gatherers, placements,
            live_packet_recorder_recorded_vertex_type,
            live_packet_gatherers_to_vertex_mapping, machine,
            machine_graph, application_graph=None, graph_mapper=None):
        """ adds edges from the recorded vertices to the local LPGs

        :param live_packet_gatherers: the set of params and vertices to link to
        :param placements: the placements object
        :param live_packet_gatherers_to_vertex_mapping: the mapping of LPG
         parameters and the machine vertex associated with it
        :param machine: the SpiNNaker machine
        :param machine_graph: the machine graph
        :param application_graph:  the app graph
        :param graph_mapper: the graph mapper between app and machine graph
        :rtype: None
        """

        progress_bar = ProgressBar(
            total_number_of_things_to_do=len(live_packet_gatherers),
            string_describing_what_being_progressed=(
                "Adding edges to the machine graph between the vertices to "
                "which live output has been requested and its local Live "
                "Packet Gatherer"))

        for live_packet_gatherers_param in live_packet_gatherers:

            # locate vertices needed to be connected to a LPG with these params
            vertices_to_connect = live_packet_gatherers[
                live_packet_gatherers_param]
            for vertex_to_connect in vertices_to_connect:

                # locate correct LPG to wire to
                machine_live_packet_gatherers = \
                    live_packet_gatherers_to_vertex_mapping[
                        live_packet_gatherers_param]

                # if its a app vertex, find the bastard machine vertices for it
                if issubclass(
                        live_packet_recorder_recorded_vertex_type,
                        ApplicationVertex):

                    # flag for ensuring we don't add the edge to the app
                    # graph many times
                    app_graph_edge = None

                    # iterate through the associated machine vertices
                    machine_vertices = graph_mapper.get_machine_vertices(
                        vertex_to_connect)
                    for machine_vertex in machine_vertices:

                        # add a edge between the closest LPG and the vertex
                        machine_edge, machine_lpg = \
                            self._process_machine_vertex(
                                machine_vertex, machine_live_packet_gatherers,
                                machine, placements, machine_graph,
                                live_packet_gatherers_param.partition_id)

                        # update the app graph and graph mapper
                        app_graph_edge = \
                            self._update_application_graph_and_graph_mapper(
                                application_graph, graph_mapper, machine_lpg,
                                vertex_to_connect,
                                live_packet_gatherers_param.partition_id,
                                machine_edge, app_graph_edge)

                else:
                    # add a edge between the closest LPG and the vertex
                    self._process_machine_vertex(
                        vertex_to_connect, machine_live_packet_gatherers,
                        machine, placements, machine_graph,
                        live_packet_gatherers_param.partition_id)

            progress_bar.update()
        progress_bar.end()

    def _process_machine_vertex(
            self, machine_vertex, machine_live_packet_gatherers, machine,
            placements, machine_graph, partition_id):
        """ locates and places an edge for a machine vertex

        :param machine_vertex: the machine vertex that needs an edge to a LPG
        :param machine_live_packet_gatherers: list of LPGs that are\
         associated with the live_packet_gatherers_param
        :param machine: the spinnaker machine object
        :param placements: the placements object
        :param machine_graph: the machine graph object
        :param partition_id: the partition id to add to the edge
        :return: machine edge and the LPG vertex
        """

        # locate the LPG that's closest to this vertex
        machine_lpg = self._find_closest_live_packet_gatherer(
            machine_vertex, machine_live_packet_gatherers,
            machine, placements)

        # add edge for the machine graph
        machine_edge = MachineEdge(machine_vertex, machine_lpg)
        machine_graph.add_edge(machine_edge, partition_id)

        # return the machine edge
        return machine_edge, machine_lpg

    @staticmethod
    def _update_application_graph_and_graph_mapper(
            application_graph, graph_mapper, machine_lpg, vertex_to_connect,
            partition_id, machine_edge, app_graph_edge):
        """ handles changes to the app graph and graph mapper.

        :param application_graph: the app graph
        :param graph_mapper: the graph mapper
        :param machine_lpg: the machine LPG
        :param vertex_to_connect: the app vertex to link to
        :param partition_id: the partition id to put the edge on
        :return the application edge for this vertex and LPG
        :rtype: ApplicationEdge
        """

        # locate app vertex for LPG
        live_packet_gatherer_app_vertex = \
            graph_mapper.get_application_vertex(machine_lpg)

        # if not built the app edge, add the app edge now
        if app_graph_edge is None:
            app_graph_edge = ApplicationEdge(
                vertex_to_connect, live_packet_gatherer_app_vertex)
            application_graph.add_edge(app_graph_edge, partition_id)

        # add mapping between the app edge and the machine edge
        graph_mapper.add_edge_mapping(machine_edge, app_graph_edge)

        # return the app edge for reuse as needed
        return app_graph_edge

    @staticmethod
    def _find_closest_live_packet_gatherer(
            machine_vertex, machine_lpgs, machine, placements):
        """ locates the LPG on the nearest ethernet connected chip to the\
         machine vertex in question

        :param machine_vertex: the machine vertex to locate the nearest LPG to
        :param machine_lpgs: the LPG's that could be nearest to the machine\
         vertex
        :param machine: the spinn machine object
        :param placements: the placements object
        :return: the local LPG
        :raises ConfigurationException: when no LPG is located on the nearest\
         ethernet chip with the correct params space.
        """

        # locate location of vertex in machine
        vertex_placement = placements.get_placement_of_vertex(machine_vertex)
        vertex_chip = machine.get_chip_at(vertex_placement.x,
                                          vertex_placement.y)
        # locate closest LPG
        for machine_lpg in machine_lpgs:
            lpg_placement = placements.get_placement_of_vertex(machine_lpg)
            lpg_chip = machine.get_chip_at(lpg_placement.x, lpg_placement.y)

            if (vertex_chip.nearest_ethernet_x == lpg_chip.x or
                    vertex_chip.nearest_ethernet_y == lpg_chip.y):
                return machine_lpg

        # if got through all LPG vertices and not found the right one. go BOOM
        raise exceptions.ConfigurationException(
            "Cannot find the LPG that resides on the nearest ethernet "
            "connected chip to the vertex {} located {}:{}".format(
                machine_vertex, vertex_chip.x, vertex_chip.y))

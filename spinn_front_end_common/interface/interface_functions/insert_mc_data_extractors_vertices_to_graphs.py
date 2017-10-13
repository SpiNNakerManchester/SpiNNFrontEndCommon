from pacman.model.constraints.placer_constraints import ChipAndCoreConstraint
from pacman.model.graphs.common import Slice

from spinn_front_end_common.abstract_models.\
    abstract_utilities_data_speed_up_extractor import \
    AbstractUtilitiesDataSpeedUpExtractor
from spinn_front_end_common.utility_models.\
    multicast_data_speed_up_packet_gatherer_machine_vertex import \
    MulticastDataSpeedUpPacketGatherMachineVertex
from spinn_front_end_common.utility_models.\
    multicast_data_speed_up_packete_gatherer_application_vertex import \
    MulticastDataSpeedUpPacketGatherApplicationVertex

from spinn_utilities.progress_bar import ProgressBar


class InsertMCDataExtractorsVerticesToGraphs(object):
    """
    
    """

    def __call__(self, machine, connection_mapping, machine_graph,
                 n_cores_to_allocate=1, graph_mapper=None,
                 application_graph=None):
        """
        
        :param machine: 
        :param connection_mapping: 
        :param machine_graph: 
        :param n_cores_to_allocate: 
        :param graph_mapper: 
        :param application_graph: 
        :return: 
        """

        n_app_verts = 0
        if application_graph is not None:
            n_app_verts = len(application_graph.vertices)
        progress = ProgressBar(
            len(machine_graph.vertices) + n_app_verts +
            len(machine.ethernet_connected_chips),
            "Inserting multicast gatherers into graphs")

        # determine if the graph requires the vertices
        insert_vertices = False
        for vertex in progress.over(machine_graph.vertices, False):
            if isinstance(vertex, AbstractUtilitiesDataSpeedUpExtractor):
                insert_vertices = True
        if application_graph is not None:
            for vertex in progress.over(application_graph.vertices, False):
                if isinstance(vertex, AbstractUtilitiesDataSpeedUpExtractor):
                    insert_vertices = True

        vertex_to_ethernet_connected_chip_mapping = dict()

        # insert if needed
        if insert_vertices:

            # insert machine vertices
            for ethernet_connected_chip in progress.over(
                    machine.ethernet_connected_chips):
                connection = connection_mapping[
                    (ethernet_connected_chip.x, ethernet_connected_chip.y)]
                machine_vertex = \
                    MulticastDataSpeedUpPacketGatherMachineVertex(
                        connection, [ChipAndCoreConstraint(
                            x=ethernet_connected_chip.x,
                            y=ethernet_connected_chip.y)])
                machine_graph.add_vertex(machine_vertex)

                # update mapping for edge builder
                vertex_to_ethernet_connected_chip_mapping[
                    (ethernet_connected_chip.x,
                     ethernet_connected_chip.y)] = machine_vertex

                # add application graph as needed
                if application_graph is not None:
                    app_vertex = \
                        MulticastDataSpeedUpPacketGatherApplicationVertex()
                    application_graph.add_vertex(app_vertex)

                    graph_mapper.add_vertex_mapping(
                        machine_vertex, Slice(0, 0), app_vertex)

        return vertex_to_ethernet_connected_chip_mapping

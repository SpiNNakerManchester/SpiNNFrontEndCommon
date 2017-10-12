from pacman.model.graphs.application import ApplicationEdge
from pacman.model.graphs.machine import MachineEdge
from spinn_front_end_common.abstract_models.\
    abstract_utilities_data_speed_up_extractor import \
    AbstractUtilitiesDataSpeedUpExtractor
from spinn_front_end_common.utilities import constants
from spinn_utilities.progress_bar import ProgressBar


class InsertEdgesToMCDataExtractors(object):

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

        progress = ProgressBar(
            len(machine_graph.vertices),
            "Inserting edges between vertices which require mc speed up "
            "functionality. ")

        for vertex in progress.over(machine_graph.vertices):
            if isinstance(vertex, AbstractUtilitiesDataSpeedUpExtractor):
                placement = placements.get_placement_of_vertex(vertex)
                chip = machine.get_chip_at(placement.x, placement.y)
                ethernet_connected_chip = machine.get_chip_at(
                    chip.nearest_ethernet_x, chip.nearest_ethernet_y)
                data_gatherer_vertex = \
                    vertex_to_ethernet_connected_chip_mapping[
                        ethernet_connected_chip]
                machine_edge = MachineEdge(vertex, data_gatherer_vertex)
                machine_graph.add_edge(
                    machine_edge,
                    constants.PARTITION_ID_FOR_MULTICAST_DATA_SPEED_UP)

                if application_graph is not None:
                    app_source = graph_mapper.get_application_vertex(vertex)
                    app_dest = graph_mapper.get_application_vertex(
                        data_gatherer_vertex)
                    app_edge = ApplicationEdge(app_source, app_dest)
                    application_graph.add_edge(
                        app_edge,
                        constants.PARTITION_ID_FOR_MULTICAST_DATA_SPEED_UP)
                    graph_mapper.add_edge_mapping(machine_edge, app_edge)


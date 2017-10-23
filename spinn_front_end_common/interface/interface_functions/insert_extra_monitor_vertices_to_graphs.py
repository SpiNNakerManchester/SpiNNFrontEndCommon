from pacman.model.constraints.placer_constraints import ChipAndCoreConstraint
from pacman.model.graphs.common import Slice

from spinn_front_end_common.utility_models.\
    extra_monitor_support_application_vertex import \
    ExtraMonitorSupportApplicationVertex
from spinn_front_end_common.utility_models.\
    extra_monitor_support_machine_vertex import \
    ExtraMonitorSupportMachineVertex
from spinn_front_end_common.utility_models.\
    multicast_data_speed_up_packet_gatherer_machine_vertex import \
    MulticastDataSpeedUpPacketGatherMachineVertex
from spinn_front_end_common.utility_models.\
    multicast_data_speed_up_packete_gatherer_application_vertex import \
    MulticastDataSpeedUpPacketGatherApplicationVertex

from spinn_utilities.progress_bar import ProgressBar


class InsertExtraMonitorVerticesToGraphs(object):
    """
    
    """

    def __call__(self, machine, connection_mapping, machine_graph,
                 n_cores_to_allocate=1, graph_mapper=None,
                 application_graph=None):
        """ inserts vertices to corresponds to the extra monitor cores
        
        :param machine: spinnMachine instance
        :param connection_mapping: map between chip and connection
        :param machine_graph: machine graph
        :param n_cores_to_allocate: n cores to allocate for reception
        :param graph_mapper: graph mapper
        :param application_graph: app graph.
        :return: vertex to ethernet connection map
        """

        progress = ProgressBar(
            len(list(machine.chips)) +
            len(list(machine.ethernet_connected_chips)),
            "Inserting extra monitors into graphs")

        vertex_to_ethernet_connected_chip_mapping = dict()

        # progress data receiver for data extraction functionality
        self._handle_data_extraction_vertices(
            progress, machine, connection_mapping, application_graph,
            machine_graph, graph_mapper,
            vertex_to_ethernet_connected_chip_mapping)

        # handle re injector and chip based data extractor functionality.
        self._handle_second_monitor_functionality(
            progress, machine, application_graph, machine_graph, graph_mapper)

        return vertex_to_ethernet_connected_chip_mapping

    @staticmethod
    def _handle_second_monitor_functionality(
            progress, machine, application_graph, machine_graph, graph_mapper):
        """
        handles placing the second monitor vertex with extra functionality\
         into the graph
        :param progress: progress bar
        :param machine: spinnMachine instance
        :param application_graph: app graph
        :param machine_graph: machine graph
        :param graph_mapper: graph mapper
        :rtype: None 
        """
        for chip in progress.over(machine.chips):

            # add to machine graph
            machine_vertex = ExtraMonitorSupportMachineVertex(
                constraints=[ChipAndCoreConstraint(x=chip.x, y=chip.y)])
            machine_graph.add_vertex(machine_vertex)

            # add application graph as needed
            if application_graph is not None:
                app_vertex = ExtraMonitorSupportApplicationVertex(
                    constraints=[ChipAndCoreConstraint(x=chip.x, y=chip.y)])
                application_graph.add_vertex(app_vertex)
                graph_mapper.add_vertex_mapping(
                    machine_vertex, Slice(0, 0), app_vertex)

    @staticmethod
    def _handle_data_extraction_vertices(
            progress, machine, connection_mapping, application_graph,
            machine_graph, graph_mapper,
            vertex_to_ethernet_connected_chip_mapping):
        """ places vertices for receiving data extraction packets.

        :param progress: progress bar
        :param machine: machine instance
        :param connection_mapping: mapping between connection and ethernet chip 
        :param application_graph: application graph
        :param machine_graph: machine graph
        :param graph_mapper: graph mapper
        :param vertex_to_ethernet_connected_chip_mapping: vertex to chip map
        :rtype: None 
        """
        # insert machine vertices
        for ethernet_connected_chip in progress.over(
                machine.ethernet_connected_chips, finish_at_end=False):
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
from pacman.model.constraints.placer_constraints import ChipAndCoreConstraint
from pacman.model.graphs.common import Slice

from spinn_front_end_common.utility_models.\
    extra_monitor_support_application_vertex import \
    ExtraMonitorSupportApplicationVertex
from spinn_front_end_common.utility_models.\
    extra_monitor_support_machine_vertex import \
    ExtraMonitorSupportMachineVertex
from spinn_front_end_common.utility_models.\
    data_speed_up_packet_gatherer_machine_vertex import \
    DataSpeedUpPacketGatherMachineVertex
from spinn_front_end_common.utility_models.\
    data_speed_up_packete_gatherer_application_vertex import \
    DataSpeedUpPacketGatherApplicationVertex

from spinn_utilities.progress_bar import ProgressBar


class InsertExtraMonitorVerticesToGraphs(object):
    """inserts the extra monitor vertices into the graph.
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
            machine.n_chips + len(list(machine.ethernet_connected_chips)),
            "Inserting extra monitors into graphs")

        vertex_to_ethernet_connected_chip_mapping = dict()
        vertex_to_chip_map = dict()

        # progress data receiver for data extraction functionality
        self._handle_data_extraction_vertices(
            progress, machine, connection_mapping, application_graph,
            machine_graph, graph_mapper,
            vertex_to_ethernet_connected_chip_mapping)

        # handle re injector and chip based data extractor functionality.
        extra_monitor_vertices = self._handle_second_monitor_functionality(
            progress, machine, application_graph, machine_graph, graph_mapper,
            vertex_to_chip_map)

        return (vertex_to_ethernet_connected_chip_mapping,
                extra_monitor_vertices, vertex_to_chip_map)

    @staticmethod
    def _handle_second_monitor_functionality(
            progress, machine, application_graph, machine_graph, graph_mapper,
            vertex_to_chip_map):
        """ handles placing the second monitor vertex with extra functionality\
         into the graph
        :param progress: progress bar
        :param machine: spinnMachine instance
        :param application_graph: app graph
        :param machine_graph: machine graph
        :param graph_mapper: graph mapper
        :param vertex_to_chip_map: map between vertex and chip
        :rtype: list
        :return: list of extra monitor cores
        """

        extra_monitor_vertices = list()

        for chip in progress.over(machine.chips):

            # add to machine graph
            machine_vertex = ExtraMonitorSupportMachineVertex(
                constraints=[ChipAndCoreConstraint(x=chip.x, y=chip.y)])
            vertex_to_chip_map[(chip.x, chip.y)] = machine_vertex
            machine_graph.add_vertex(machine_vertex)
            extra_monitor_vertices.append(machine_vertex)

            # add application graph as needed
            if application_graph is not None:
                app_vertex = ExtraMonitorSupportApplicationVertex(
                    constraints=[ChipAndCoreConstraint(x=chip.x, y=chip.y)])
                application_graph.add_vertex(app_vertex)
                graph_mapper.add_vertex_mapping(
                    machine_vertex, Slice(0, 0), app_vertex)
        return extra_monitor_vertices

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
                DataSpeedUpPacketGatherMachineVertex(
                    x=ethernet_connected_chip.x,
                    y=ethernet_connected_chip.y, connection=connection,
                    constraints=[ChipAndCoreConstraint(
                        x=ethernet_connected_chip.x,
                        y=ethernet_connected_chip.y)])
            machine_graph.add_vertex(machine_vertex)

            # update mapping for edge builder
            vertex_to_ethernet_connected_chip_mapping[
                (ethernet_connected_chip.x,
                 ethernet_connected_chip.y)] = machine_vertex

            # add application graph as needed
            if application_graph is not None:
                app_vertex = DataSpeedUpPacketGatherApplicationVertex()
                application_graph.add_vertex(app_vertex)

                graph_mapper.add_vertex_mapping(
                    machine_vertex, Slice(0, 0), app_vertex)

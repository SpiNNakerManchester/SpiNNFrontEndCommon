from pacman.model.constraints.placer_constraints import ChipAndCoreConstraint
from pacman.model.graphs.common import Slice
from pacman.utilities import utility_calls

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

    def __call__(
            self, machine, machine_graph, default_report_directory,
            n_cores_to_allocate=1,
            graph_mapper=None, application_graph=None):
        """ inserts vertices to corresponds to the extra monitor cores

        :param machine: spinnMachine instance
        :param machine_graph: machine graph
        :param n_cores_to_allocate: n cores to allocate for reception
        :param default_report_directory: the directory where reports go
        :param graph_mapper: graph mapper
        :param application_graph: app graph.
        :return: vertex to Ethernet connection map
        """

        progress = ProgressBar(
            machine.n_chips + len(list(machine.ethernet_connected_chips)),
            "Inserting extra monitors into graphs")

        vertex_to_ethernet_connected_chip_mapping = dict()
        vertex_to_chip_map = dict()

        # progress data receiver for data extraction functionality
        self._handle_data_extraction_vertices(
            progress, machine, application_graph, machine_graph, graph_mapper,
            vertex_to_ethernet_connected_chip_mapping,
            default_report_directory)

        # handle re injector and chip based data extractor functionality.
        extra_monitor_vertices = self._handle_second_monitor_functionality(
            progress, machine, application_graph, machine_graph, graph_mapper,
            vertex_to_chip_map)

        return (vertex_to_ethernet_connected_chip_mapping,
                extra_monitor_vertices, vertex_to_chip_map)

    def _handle_second_monitor_functionality(
            self, progress, machine, application_graph, machine_graph,
            graph_mapper, vertex_to_chip_map):
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
            if not chip.virtual:
                equiv_machine_vertex = self._exists_equiv_vertex(
                        chip.x, chip.y, machine_graph,
                        ExtraMonitorSupportMachineVertex)
                if equiv_machine_vertex is None:
                    # add to machine graph
                    machine_vertex = ExtraMonitorSupportMachineVertex(
                        constraints=[
                            ChipAndCoreConstraint(x=chip.x, y=chip.y)])
                    machine_graph.add_vertex(machine_vertex)
                else:
                    machine_vertex = equiv_machine_vertex

                vertex_to_chip_map[(chip.x, chip.y)] = machine_vertex
                extra_monitor_vertices.append(machine_vertex)

                # add application graph as needed
                if application_graph is not None:
                    equiv_vertex = self._exists_equiv_vertex(
                        chip.x, chip.y, application_graph,
                        ExtraMonitorSupportApplicationVertex)
                    if equiv_vertex is None:
                        app_vertex = ExtraMonitorSupportApplicationVertex(
                            constraints=[
                                ChipAndCoreConstraint(x=chip.x, y=chip.y)])
                        application_graph.add_vertex(app_vertex)
                        graph_mapper.add_vertex_mapping(
                            machine_vertex, Slice(0, 0), app_vertex)
        return extra_monitor_vertices

    @staticmethod
    def _exists_equiv_vertex(x, y, graph, type):
        for vertex in graph.vertices:
            if isinstance(vertex, type):
                placement_constraints = \
                    utility_calls.locate_constraints_of_type(
                        vertex.constraints, ChipAndCoreConstraint)
                for placement_constraint in placement_constraints:
                    if (placement_constraint.x == x and
                            placement_constraint.y == y):
                        return vertex
        return None

    def _handle_data_extraction_vertices(
            self, progress, machine, application_graph, machine_graph,
            graph_mapper, vertex_to_ethernet_connected_chip_mapping,
            default_report_directory):
        """ places vertices for receiving data extraction packets.

        :param progress: progress bar
        :param machine: machine instance
        :param application_graph: application graph
        :param machine_graph: machine graph
        :param default_report_directory: the default directory for where\
         reports are to be written
        :param graph_mapper: graph mapper
        :param vertex_to_ethernet_connected_chip_mapping: vertex to chip map
        :rtype: None
        """
        # insert machine vertices
        for ethernet_connected_chip in progress.over(
                machine.ethernet_connected_chips, finish_at_end=False):

            # add to application graph if possible
            machine_vertex = None
            if application_graph is not None:
                equiv_vertex = self._exists_equiv_vertex(
                    ethernet_connected_chip.x, ethernet_connected_chip.y,
                    application_graph,
                    DataSpeedUpPacketGatherApplicationVertex)
                if equiv_vertex is None:
                    app_vertex = DataSpeedUpPacketGatherApplicationVertex(
                        x=ethernet_connected_chip.x,
                        y=ethernet_connected_chip.y,
                        ip_address=ethernet_connected_chip.ip_address,
                        report_default_directory=default_report_directory,
                        constraints=[ChipAndCoreConstraint(
                            x=ethernet_connected_chip.x,
                            y=ethernet_connected_chip.y)])
                    machine_vertex = app_vertex.machine_vertex
                    machine_graph.add_vertex(machine_vertex)
                    application_graph.add_vertex(app_vertex)
                    graph_mapper.add_vertex_mapping(
                        machine_vertex, Slice(0, 0), app_vertex)
                else:
                    machine_vertex = equiv_vertex.machine_vertex
            else:
                equiv_vertex = self._exists_equiv_vertex(
                    ethernet_connected_chip.x, ethernet_connected_chip.y,
                    machine_graph,
                    DataSpeedUpPacketGatherApplicationVertex)
                if equiv_vertex is None:
                    machine_vertex = DataSpeedUpPacketGatherMachineVertex(
                        x=ethernet_connected_chip.x,
                        y=ethernet_connected_chip.y,
                        ip_address=ethernet_connected_chip.ip_address,
                        constraints=[ChipAndCoreConstraint(
                            x=ethernet_connected_chip.x,
                            y=ethernet_connected_chip.y)],
                        report_default_directory=default_report_directory)
                    machine_graph.add_vertex(machine_vertex)
                else:
                    machine_vertex = equiv_vertex

            # update mapping for edge builder
            vertex_to_ethernet_connected_chip_mapping[
                (ethernet_connected_chip.x,
                 ethernet_connected_chip.y)] = machine_vertex

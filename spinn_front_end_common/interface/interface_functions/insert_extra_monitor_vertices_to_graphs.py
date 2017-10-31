from pacman.model.constraints.placer_constraints import ChipAndCoreConstraint
from pacman.model.graphs.common import Slice

from spinn_front_end_common.utility_models.\
    extra_monitor_support_application_vertex import \
    ExtraMonitorSupportApplicationVertex
from spinn_front_end_common.utility_models.\
    extra_monitor_support_machine_vertex import \
    ExtraMonitorSupportMachineVertex

from spinn_utilities.progress_bar import ProgressBar


class InsertExtraMonitorVerticesToGraphs(object):
    """
    
    """

    def __call__(self, machine, machine_graph, graph_mapper=None,
                 application_graph=None):
        """ inserts vertices to corresponds to the extra monitor cores
        
        :param machine: spinnMachine instance
        :param machine_graph: machine graph
        :param graph_mapper: graph mapper
        :param application_graph: app graph.
        :return: vertex to ethernet connection map
        """

        progress = ProgressBar(
            len(list(machine.chips)) +
            len(list(machine.ethernet_connected_chips)),
            "Inserting extra monitors into graphs")

        # handle re injector and chip based data extractor functionality.
        extra_monitor_vertices = self._handle_second_monitor_functionality(
            progress, machine, application_graph, machine_graph, graph_mapper)

        return extra_monitor_vertices

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
        :rtype: list 
        :return: list of extra monitor cores 
        """

        extra_monitor_vertices = list()

        for chip in progress.over(machine.chips):

            # add to machine graph
            machine_vertex = ExtraMonitorSupportMachineVertex(
                constraints=[ChipAndCoreConstraint(x=chip.x, y=chip.y)])
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

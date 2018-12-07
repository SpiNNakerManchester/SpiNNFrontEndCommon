from spinn_utilities.progress_bar import ProgressBar
from pacman.model.constraints.placer_constraints import ChipAndCoreConstraint
from pacman.model.graphs.common import Slice
from pacman.utilities.utility_calls import locate_constraints_of_type
from spinn_front_end_common.utility_models import (
    DataSpeedUpPacketGather, DataSpeedUpPacketGatherMachineVertex,
    ExtraMonitorSupport, ExtraMonitorSupportMachineVertex)


class InsertExtraMonitorVerticesToGraphs(object):
    """ Inserts the extra monitor vertices into the graph that correspond to\
        the extra monitor cores required.
    """

    def __call__(
            self, machine, machine_graph, default_report_directory,
            write_data_speed_up_report, n_cores_to_allocate=1,
            graph_mapper=None, application_graph=None):
        """
        :param machine: spinnMachine instance
        :param machine_graph: machine graph
        :param n_cores_to_allocate: n cores to allocate for reception
        :param default_report_directory: the directory where reports go
        :param write_data_speed_up_report: \
            determine whether to write the report for data speed up
        :param graph_mapper: graph mapper
        :param application_graph: app graph.
        :return: vertex to Ethernet connection map, \
            list of extra_monitor_vertices, \
            vertex_to_chip_map
        """
        # pylint: disable=too-many-arguments

        progress = ProgressBar(
            machine.n_chips + len(list(machine.ethernet_connected_chips)),
            "Inserting extra monitors into graphs")

        vertex_to_ethernet_connected_chip_mapping = dict()
        vertex_to_chip_map = dict()

        # progress data receiver for data extraction functionality
        self._handle_data_extraction_vertices(
            progress, machine, application_graph, machine_graph, graph_mapper,
            vertex_to_ethernet_connected_chip_mapping,
            default_report_directory, write_data_speed_up_report)

        # handle re injector and chip based data extractor functionality.
        extra_monitor_vertices = self._handle_second_monitor_functionality(
            progress, machine, application_graph, machine_graph, graph_mapper,
            vertex_to_chip_map)

        return (vertex_to_ethernet_connected_chip_mapping,
                extra_monitor_vertices, vertex_to_chip_map)

    def _handle_second_monitor_functionality(
            self, progress, machine, application_graph, machine_graph,
            graph_mapper, vertex_to_chip_map):
        """ Handles placing the second monitor vertex with extra functionality\
            into the graph

        :param progress: progress bar
        :param machine: spinnMachine instance
        :param application_graph: app graph
        :param machine_graph: machine graph
        :param graph_mapper: graph mapper
        :param vertex_to_chip_map: map between vertex and chip
        :return: list of extra monitor vertices
        :rtype: list(MachineVertex)
        """
        # pylint: disable=too-many-arguments

        extra_monitor_vertices = list()

        for chip in progress.over(machine.chips):
            if not chip.virtual:
                # add to machine graph
                machine_vertex = self.__new_mach_monitor(chip)
                machine_graph.add_vertex(machine_vertex)

                vertex_to_chip_map[chip.x, chip.y] = machine_vertex
                extra_monitor_vertices.append(machine_vertex)

                # add application graph as needed
                if application_graph is not None:
                    app_vertex = self.__new_app_monitor(chip)
                    application_graph.add_vertex(app_vertex)
                    graph_mapper.add_vertex_mapping(
                        machine_vertex, Slice(0, 0), app_vertex)
        return extra_monitor_vertices

    def _handle_data_extraction_vertices(
            self, progress, machine, application_graph, machine_graph,
            graph_mapper, vertex_to_ethernet_connected_chip_mapping,
            default_report_directory, write_data_speed_up_report):
        """ Places vertices for receiving data extraction packets.

        :param progress: progress bar
        :param machine: machine instance
        :param application_graph: application graph
        :param machine_graph: machine graph
        :param default_report_directory: \
            the default directory for where reports are to be written
        :param write_data_speed_up_report: \
            determine whether to write the report for data speed up
        :param graph_mapper: graph mapper
        :param vertex_to_ethernet_connected_chip_mapping: vertex to chip map
        :rtype: None
        """
        # pylint: disable=too-many-arguments

        # insert machine vertices
        for ethernet_chip in progress.over(
                machine.ethernet_connected_chips, finish_at_end=False):
            # add to application graph if possible
            if application_graph is not None:
                app_vertex = self.__new_app_gatherer(
                    ethernet_chip, default_report_directory,
                    write_data_speed_up_report)
                machine_vertex = app_vertex.machine_vertex
                machine_graph.add_vertex(machine_vertex)
                application_graph.add_vertex(app_vertex)
                graph_mapper.add_vertex_mapping(
                    machine_vertex, Slice(0, 0), app_vertex)
            else:
                machine_vertex = self.__new_mach_gatherer(
                    ethernet_chip, default_report_directory,
                    write_data_speed_up_report)
                machine_graph.add_vertex(machine_vertex)

            # update mapping for edge builder
            vertex_to_ethernet_connected_chip_mapping[
                (ethernet_chip.x,
                 ethernet_chip.y)] = machine_vertex

    @staticmethod
    def __new_app_monitor(chip):
        return ExtraMonitorSupport(constraints=[
            ChipAndCoreConstraint(x=chip.x, y=chip.y)])

    @staticmethod
    def __new_mach_monitor(chip):
        return ExtraMonitorSupportMachineVertex(constraints=[
            ChipAndCoreConstraint(x=chip.x, y=chip.y)])

    @staticmethod
    def __new_app_gatherer(
            ethernet_chip, default_report_directory,
            write_data_speed_up_report):
        return DataSpeedUpPacketGather(
            x=ethernet_chip.x, y=ethernet_chip.y,
            ip_address=ethernet_chip.ip_address,
            constraints=[ChipAndCoreConstraint(
                x=ethernet_chip.x, y=ethernet_chip.y)],
            report_default_directory=default_report_directory,
            write_data_speed_up_report=write_data_speed_up_report)

    @staticmethod
    def __new_mach_gatherer(
            ethernet_chip, default_report_directory,
            write_data_speed_up_report):
        return DataSpeedUpPacketGatherMachineVertex(
            x=ethernet_chip.x, y=ethernet_chip.y,
            ip_address=ethernet_chip.ip_address,
            constraints=[ChipAndCoreConstraint(
                x=ethernet_chip.x, y=ethernet_chip.y)],
            report_default_directory=default_report_directory,
            write_data_speed_up_report=write_data_speed_up_report)

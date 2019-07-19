# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from spinn_utilities.progress_bar import ProgressBar
from pacman.model.constraints.placer_constraints import ChipAndCoreConstraint
from pacman.model.graphs.common import Slice
from spinn_front_end_common.utility_models import (
    DataSpeedUpPacketGather, DataSpeedUpPacketGatherMachineVertex,
    ExtraMonitorSupport, ExtraMonitorSupportMachineVertex)


class InsertExtraMonitorVerticesToGraphs(object):
    """ Inserts the extra monitor vertices into the graph that correspond to\
        the extra monitor cores required.
    """

    def __call__(
            self, machine, machine_graph, default_report_directory,
            write_data_speed_up_reports, n_cores_to_allocate=1,
            graph_mapper=None, application_graph=None):
        """
        :param machine: spinnMachine instance
        :param machine_graph: machine graph
        :param n_cores_to_allocate: n cores to allocate for reception
        :param default_report_directory: the directory where reports go
        :param write_data_speed_up_out_report: \
            determine whether to write the report for data speed up out
        :param write_data_speed_up_in_report: \
            determine whether to write the report for data speed up in
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

        # handle re injector and chip based data extractor functionality.
        extra_monitor_vertices = self._handle_second_monitor_functionality(
            progress, machine, application_graph, machine_graph, graph_mapper,
            vertex_to_chip_map)

        # progress data receiver for data extraction functionality
        self._handle_data_extraction_vertices(
            progress, machine, application_graph, machine_graph, graph_mapper,
            vertex_to_ethernet_connected_chip_mapping, vertex_to_chip_map,
            default_report_directory, write_data_speed_up_reports)

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

        for chip in progress.over(machine.chips, finish_at_end=False):
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
            vertex_to_chip_map, default_report_directory,
            write_data_speed_up_reports):
        """ Places vertices for receiving data extraction packets.

        :param progress: progress bar
        :param machine: machine instance
        :param application_graph: application graph
        :param machine_graph: machine graph
        :param default_report_directory: \
            the default directory for where reports are to be written
        :param write_data_speed_up_reports: \
            determine whether to write the reports for data speed up
        :param graph_mapper: graph mapper
        :param vertex_to_ethernet_connected_chip_mapping: vertex to chip map
        :param vertex_to_chip_map: map between chip and extra monitor
        :rtype: None
        """
        # pylint: disable=too-many-arguments

        # insert machine vertices
        for ethernet_chip in progress.over(machine.ethernet_connected_chips):
            # add to application graph if possible
            if application_graph is not None:
                app_vertex = self.__new_app_gatherer(
                    ethernet_chip, vertex_to_chip_map,
                    default_report_directory, write_data_speed_up_reports)
                machine_vertex = app_vertex.machine_vertex
                machine_graph.add_vertex(machine_vertex)
                application_graph.add_vertex(app_vertex)
                graph_mapper.add_vertex_mapping(
                    machine_vertex, Slice(0, 0), app_vertex)
            else:
                machine_vertex = self.__new_mach_gatherer(
                    ethernet_chip, vertex_to_chip_map,
                    default_report_directory, write_data_speed_up_reports)
                machine_graph.add_vertex(machine_vertex)

            # update mapping for edge builder
            vertex_to_ethernet_connected_chip_mapping[
                ethernet_chip.x, ethernet_chip.y] = machine_vertex

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
            ethernet_chip, vertex_to_chip_map, default_report_directory,
            write_data_speed_up_reports):
        return DataSpeedUpPacketGather(
            x=ethernet_chip.x, y=ethernet_chip.y,
            ip_address=ethernet_chip.ip_address,
            constraints=[ChipAndCoreConstraint(
                x=ethernet_chip.x, y=ethernet_chip.y)],
            extra_monitors_by_chip=vertex_to_chip_map,
            report_default_directory=default_report_directory,
            write_data_speed_up_reports=write_data_speed_up_reports)

    @staticmethod
    def __new_mach_gatherer(
            ethernet_chip, vertex_to_chip_map, default_report_directory,
            write_data_speed_up_reports):
        return DataSpeedUpPacketGatherMachineVertex(
            x=ethernet_chip.x, y=ethernet_chip.y,
            ip_address=ethernet_chip.ip_address,
            constraints=[ChipAndCoreConstraint(
                x=ethernet_chip.x, y=ethernet_chip.y)],
            extra_monitors_by_chip=vertex_to_chip_map,
            report_default_directory=default_report_directory,
            write_data_speed_up_reports=write_data_speed_up_reports)

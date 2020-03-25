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
from spinn_front_end_common.utility_models import (
    DataSpeedUpPacketGather, DataSpeedUpPacketGatherMachineVertex,
    ExtraMonitorSupport, ExtraMonitorSupportMachineVertex)


class InsertExtraMonitorVerticesToGraphs(object):
    """ Inserts the extra monitor vertices into the graph that correspond to\
        the extra monitor cores required.
    """

    def __call__(
            self, machine, machine_graph, default_report_directory,
            write_data_speed_up_reports, application_graph=None):
        """
        :param machine: spinnMachine instance
        :param machine_graph: machine graph
        :param default_report_directory: the directory where reports go
        :param write_data_speed_up_out_report:
            determine whether to write the report for data speed up out
        :param write_data_speed_up_in_report:
            determine whether to write the report for data speed up in
        :param application_graph: app graph.
        :return: Ethernet chip to gatherer vertex map,
            list of extra_monitor vertices, vertex_to_chip_map
        """
        # pylint: disable=too-many-arguments, attribute-defined-outside-init
        self._report_dir = default_report_directory
        self._write_reports = write_data_speed_up_reports

        progress = ProgressBar(
            machine.n_chips + len(list(machine.ethernet_connected_chips)),
            "Inserting extra monitors into graphs")

        chip_to_gatherer_map = dict()
        vertex_to_chip_map = dict()

        # handle reinjector and chip based data extractor functionality.
        if application_graph is not None:
            extra_monitors = self._add_second_monitors_application_graph(
                progress, machine, application_graph, machine_graph,
                vertex_to_chip_map)
        else:
            extra_monitors = self._add_second_monitors_machine_graph(
                progress, machine, machine_graph, vertex_to_chip_map)

        # progress data receiver for data extraction functionality
        if application_graph is not None:
            self._add_data_extraction_vertices_app_graph(
                progress, machine, application_graph, machine_graph,
                chip_to_gatherer_map, vertex_to_chip_map)
        else:
            self._add_data_extraction_vertices_mach_graph(
                progress, machine, machine_graph, chip_to_gatherer_map,
                vertex_to_chip_map)

        return chip_to_gatherer_map, extra_monitors, vertex_to_chip_map

    def _add_second_monitors_application_graph(
            self, progress, machine, application_graph, machine_graph,
            vertex_to_chip_map):
        """ Handles placing the second monitor vertex with extra functionality\
            into the graph

        :param progress: progress bar
        :param machine: spinnMachine instance
        :param application_graph: app graph
        :param machine_graph: machine graph
        :param vertex_to_chip_map: map between vertex and chip
        :return: list of extra monitor vertices
        :rtype: list(MachineVertex)
        """
        # pylint: disable=too-many-arguments

        extra_monitor_vertices = list()

        for chip in progress.over(machine.chips, finish_at_end=False):
            if chip.virtual:
                continue
            # add to both application graph and machine graph
            app_vertex = self.__new_app_monitor(chip)
            application_graph.add_vertex(app_vertex)
            vertex = app_vertex.machine_vertex
            machine_graph.add_vertex(vertex)
            app_vertex.remember_associated_machine_vertex(vertex)
            vertex_to_chip_map[chip.x, chip.y] = vertex
            extra_monitor_vertices.append(vertex)

        return extra_monitor_vertices

    def _add_second_monitors_machine_graph(
            self, progress, machine, machine_graph, vertex_to_chip_map):
        """ Handles placing the second monitor vertex with extra functionality\
            into the graph

        :param progress: progress bar
        :param machine: spinnMachine instance
        :param machine_graph: machine graph
        :param vertex_to_chip_map: map between vertex and chip
        :return: list of extra monitor vertices
        :rtype: list(MachineVertex)
        """
        # pylint: disable=too-many-arguments

        extra_monitor_vertices = list()

        for chip in progress.over(machine.chips, finish_at_end=False):
            if chip.virtual:
                continue
            # add to machine graph
            vertex = self.__new_mach_monitor(chip)
            machine_graph.add_vertex(vertex)
            vertex_to_chip_map[chip.x, chip.y] = vertex
            extra_monitor_vertices.append(vertex)

        return extra_monitor_vertices

    def _add_data_extraction_vertices_app_graph(
            self, progress, machine, application_graph, machine_graph,
            chip_to_gatherer_map, vertex_to_chip_map):
        """ Places vertices for receiving data extraction packets.

        :param progress: progress bar
        :param machine: machine instance
        :param application_graph: application graph
        :param machine_graph: machine graph
        :param chip_to_gatherer_map: vertex to chip map
        :param vertex_to_chip_map: map between chip and extra monitor
        :rtype: None
        """
        # pylint: disable=too-many-arguments

        # insert machine vertices
        for chip in progress.over(machine.ethernet_connected_chips):
            # add to application graph
            app_vertex = self.__new_app_gatherer(chip, vertex_to_chip_map)
            vertex = app_vertex.machine_vertex
            machine_graph.add_vertex(vertex)
            application_graph.add_vertex(app_vertex)
            app_vertex.remember_associated_machine_vertex(vertex)
            # update mapping for edge builder
            chip_to_gatherer_map[chip.x, chip.y] = vertex

    def _add_data_extraction_vertices_mach_graph(
            self, progress, machine, machine_graph,
            chip_to_gatherer_map, vertex_to_chip_map):
        """ Places vertices for receiving data extraction packets.

        :param progress: progress bar
        :param machine: machine instance
        :param machine_graph: machine graph
        :param chip_to_gatherer_map: vertex to chip map
        :param vertex_to_chip_map: map between chip and extra monitor
        :rtype: None
        """
        # pylint: disable=too-many-arguments

        # insert machine vertices
        for chip in progress.over(machine.ethernet_connected_chips):
            machine_vertex = self.__new_mach_gatherer(chip, vertex_to_chip_map)
            machine_graph.add_vertex(machine_vertex)
            # update mapping for edge builder
            chip_to_gatherer_map[chip.x, chip.y] = machine_vertex

    @staticmethod
    def __new_app_monitor(chip):
        return ExtraMonitorSupport(constraints=[
            ChipAndCoreConstraint(x=chip.x, y=chip.y)])

    @staticmethod
    def __new_mach_monitor(chip):
        return ExtraMonitorSupportMachineVertex(
            constraints=[ChipAndCoreConstraint(x=chip.x, y=chip.y)],
            app_vertex=None)

    def __new_app_gatherer(self, ethernet_chip, vertex_to_chip_map):
        return DataSpeedUpPacketGather(
            x=ethernet_chip.x, y=ethernet_chip.y,
            ip_address=ethernet_chip.ip_address,
            constraints=[ChipAndCoreConstraint(
                x=ethernet_chip.x, y=ethernet_chip.y)],
            extra_monitors_by_chip=vertex_to_chip_map,
            report_default_directory=self._report_dir,
            write_data_speed_up_reports=self._write_reports)

    def __new_mach_gatherer(self, ethernet_chip, vertex_to_chip_map):
        return DataSpeedUpPacketGatherMachineVertex(
            app_vertex=None, x=ethernet_chip.x, y=ethernet_chip.y,
            ip_address=ethernet_chip.ip_address,
            constraints=[ChipAndCoreConstraint(
                x=ethernet_chip.x, y=ethernet_chip.y)],
            extra_monitors_by_chip=vertex_to_chip_map,
            report_default_directory=self._report_dir,
            write_data_speed_up_reports=self._write_reports)

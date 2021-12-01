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
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utility_models import (
    DataSpeedUpPacketGather, DataSpeedUpPacketGatherMachineVertex,
    ExtraMonitorSupport, ExtraMonitorSupportMachineVertex)


def insert_extra_monitor_vertices_to_graphs(machine):
    """ Inserts the extra monitor vertices into the graph that correspond to\
    the extra monitor cores required.

    :param ~spinn_machine.Machine machine: spinnMachine instance
    :return: vertex to Ethernet connection map,
        list of extra_monitor_vertices,
        vertex_to_chip_map
    :rtype: tuple(
        dict(tuple(int,int),DataSpeedUpPacketGatherMachineVertex),
        list(ExtraMonitorSupportMachineVertex),
        dict(tuple(int,int),ExtraMonitorSupportMachineVertex))
    """
    # pylint: disable=too-many-arguments, attribute-defined-outside-init

    progress = ProgressBar(
        machine.n_chips + len(list(machine.ethernet_connected_chips)),
        "Inserting extra monitors into graphs")

    chip_to_gatherer_map = dict()
    vertex_to_chip_map = dict()

    # handle reinjector and chip based data extractor functionality.
    if FecDataView().runtime_graph.n_vertices > 0:
        extra_monitors = __add_second_monitors_application_graph(
            progress, machine, vertex_to_chip_map)
    else:
        extra_monitors = __add_second_monitors_machine_graph(
            progress, machine, vertex_to_chip_map)

    # progress data receiver for data extraction functionality
    if FecDataView().runtime_graph.n_vertices > 0:
        __add_data_extraction_vertices_app_graph(
            progress, machine, chip_to_gatherer_map, vertex_to_chip_map)
    else:
        __add_data_extraction_vertices_mach_graph(
            progress, machine, chip_to_gatherer_map, vertex_to_chip_map)

    return chip_to_gatherer_map, extra_monitors, vertex_to_chip_map


def __add_second_monitors_application_graph(
        progress, machine, vertex_to_chip_map):
    """ Handles placing the second monitor vertex with extra functionality\
        into the graph

    :param ~.ProgressBar progress: progress bar
    :param ~.Machine machine: spinnMachine instance
    :param dict vertex_to_chip_map: map between vertex and chip
    :return: list of extra monitor vertices
    :rtype: list(~.MachineVertex)
    """
    # pylint: disable=too-many-arguments

    extra_monitor_vertices = list()

    application_graph = FecDataView().runtime_graph
    machine_graph = FecDataView().runtime_machine_graph
    for chip in progress.over(machine.chips, finish_at_end=False):
        if chip.virtual:
            continue
        # add to both application graph and machine graph
        app_vertex = __new_app_monitor(chip)
        application_graph.add_vertex(app_vertex)
        machine_vertex = app_vertex.machine_vertex
        machine_graph.add_vertex(machine_vertex)
        vertex_to_chip_map[chip.x, chip.y] = machine_vertex
        extra_monitor_vertices.append(machine_vertex)

    return extra_monitor_vertices


def __add_second_monitors_machine_graph(progress, machine, vertex_to_chip_map):
    """ Handles placing the second monitor vertex with extra functionality\
        into the graph

    :param ~.ProgressBar progress: progress bar
    :param ~.Machine machine: spinnMachine instance
    :param dict vertex_to_chip_map: map between vertex and chip
    :return: list of extra monitor vertices
    :rtype: list(~.MachineVertex)
    """
    # pylint: disable=too-many-arguments

    extra_monitor_vertices = list()

    machine_graph = FecDataView().runtime_machine_graph
    for chip in progress.over(machine.chips, finish_at_end=False):
        if chip.virtual:
            continue
        # add to machine graph
        vertex = __new_mach_monitor(chip)
        machine_graph.add_vertex(vertex)
        vertex_to_chip_map[chip.x, chip.y] = vertex
        extra_monitor_vertices.append(vertex)

    return extra_monitor_vertices


def __add_data_extraction_vertices_app_graph(
        progress, machine, chip_to_gatherer_map, vertex_to_chip_map):
    """ Places vertices for receiving data extraction packets.

    :param ~.ProgressBar progress: progress bar
    :param ~.Machine machine: machine instance
    :param dict chip_to_gatherer_map: vertex to chip map
    :param dict vertex_to_chip_map: map between chip and extra monitor
    """
    # pylint: disable=too-many-arguments

    application_graph = FecDataView().runtime_graph
    machine_graph = FecDataView().runtime_machine_graph
    # insert machine vertices
    for chip in progress.over(machine.ethernet_connected_chips):
        # add to application graph
        app_vertex = __new_app_gatherer(chip, vertex_to_chip_map)
        application_graph.add_vertex(app_vertex)
        machine_vertex = app_vertex.machine_vertex
        machine_graph.add_vertex(machine_vertex)
        # update mapping for edge builder
        chip_to_gatherer_map[chip.x, chip.y] = machine_vertex


def __add_data_extraction_vertices_mach_graph(
        progress, machine, chip_to_gatherer_map, vertex_to_chip_map):
    """ Places vertices for receiving data extraction packets.

    :param ~.ProgressBar progress: progress bar
    :param ~.Machine machine: machine instance
    :param dict chip_to_gatherer_map: vertex to chip map
    :param dict vertex_to_chip_map: map between chip and extra monitor
    """
    # pylint: disable=too-many-arguments

    machine_graph = FecDataView().runtime_machine_graph
    # insert machine vertices
    for chip in progress.over(machine.ethernet_connected_chips):
        machine_vertex = __new_mach_gatherer(chip, vertex_to_chip_map)
        machine_graph.add_vertex(machine_vertex)
        # update mapping for edge builder
        chip_to_gatherer_map[chip.x, chip.y] = machine_vertex


def __new_app_monitor(chip):
    """
    :param ~.Chip chip:
    :rtype: ExtraMonitorSupport
    """
    return ExtraMonitorSupport(constraints=[
        ChipAndCoreConstraint(x=chip.x, y=chip.y)])


def __new_mach_monitor(chip):
    """
    :param ~.Chip chip:
    :rtype: ExtraMonitorSupportMachineVertex
    """
    return ExtraMonitorSupportMachineVertex(
        constraints=[ChipAndCoreConstraint(x=chip.x, y=chip.y)],
        app_vertex=None)


def __new_app_gatherer(ethernet_chip, vertex_to_chip_map):
    """
    :param ~.Chip ethernet_chip:
    :param dict vertex_to_chip_map:
    :rtype: DataSpeedUpPacketGather
    """
    return DataSpeedUpPacketGather(
        x=ethernet_chip.x, y=ethernet_chip.y,
        ip_address=ethernet_chip.ip_address,
        constraints=[ChipAndCoreConstraint(
            x=ethernet_chip.x, y=ethernet_chip.y)],
        extra_monitors_by_chip=vertex_to_chip_map)


def __new_mach_gatherer(ethernet_chip, vertex_to_chip_map):
    """
    :param ~.Chip ethernet_chip:
    :param dict vertex_to_chip_map:
    :rtype: DataSpeedUpPacketGatherMachineVertex
    """
    return DataSpeedUpPacketGatherMachineVertex(
        x=ethernet_chip.x, y=ethernet_chip.y,
        ip_address=ethernet_chip.ip_address,
        constraints=[ChipAndCoreConstraint(
            x=ethernet_chip.x, y=ethernet_chip.y)],
        extra_monitors_by_chip=vertex_to_chip_map)

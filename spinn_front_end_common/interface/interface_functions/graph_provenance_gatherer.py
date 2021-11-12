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
from spinn_front_end_common.interface.provenance import (
    AbstractProvidesLocalProvenanceData)


def graph_provenance_gatherer(machine_graph, application_graph=None):
    """ Gets provenance information from the graphs.
    :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
        The machine graph to inspect
    :param application_graph: The optional application graph
    :type application_graph:
        ~pacman.model.graphs.application.ApplicationGraph
    """
    _get_machine_graph_provenance(machine_graph)
    if application_graph is not None:
        _get_app_graph_provenance(application_graph)


def _get_machine_graph_provenance(machine_graph):
    progress = ProgressBar(
        machine_graph.n_vertices +
        machine_graph.n_outgoing_edge_partitions,
        "Getting provenance data from machine graph")

    for vertex in progress.over(machine_graph.vertices, False):
        if isinstance(vertex, AbstractProvidesLocalProvenanceData):
            vertex.get_local_provenance_data()

    for partition in progress.over(machine_graph.outgoing_edge_partitions):
        for edge in partition.edges:
            if isinstance(edge, AbstractProvidesLocalProvenanceData):
                edge.get_local_provenance_data()


def _get_app_graph_provenance(application_graph):
    progress = ProgressBar(
        application_graph.n_vertices +
        application_graph.n_outgoing_edge_partitions,
        "Getting provenance data from application graph")

    for vertex in progress.over(application_graph.vertices, False):
        if isinstance(vertex, AbstractProvidesLocalProvenanceData):
            vertex.get_local_provenance_data()

    for partition in progress.over(
            application_graph.outgoing_edge_partitions):
        for edge in partition.edges:
            if isinstance(edge, AbstractProvidesLocalProvenanceData):
                edge.get_local_provenance_data()

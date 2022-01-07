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

import logging
import os.path
from spinn_utilities.log import FormatAdapter
from pacman.model.graphs.application import ApplicationVertex
from spinn_front_end_common.data import FecDataView

logger = FormatAdapter(logging.getLogger(__name__))

_FILENAME = "network_specification.rpt"


def network_specification():
    """ Generate report on the user's network specification.

    :rtype: None
    """
    filename = os.path.join(FecDataView.get_run_dir_path(), _FILENAME)
    graph = FecDataView().runtime_best_graph
    try:
        with open(filename, "w") as f:
            f.write("*** Vertices:\n")
            for vertex in graph.vertices:
                _write_report(f, vertex, graph)
    except IOError:
        logger.exception("Generate_placement_reports: Can't open file {}"
                         " for writing.", filename)


def _write_report(f, vertex, graph):
    """
    :param ~io.FileIO f:
    :param vertex:
    :type vertex: ApplicationVertex or MachineVertex
    :param ApplicationGraph graph:
    """
    if isinstance(vertex, ApplicationVertex):
        f.write("Vertex {}, size: {}, model: {}\n".format(
            vertex.label, vertex.n_atoms, vertex.__class__.__name__))
    else:
        f.write("Vertex {}, model: {}\n".format(
            vertex.label, vertex.__class__.__name__))

    f.write("    Constraints:\n")
    for constraint in vertex.constraints:
        f.write("        {}\n".format(
            str(constraint)))

    f.write("    Outgoing Edge Partitions:\n")
    for partition in graph.get_outgoing_edge_partitions_starting_at_vertex(
            vertex):
        f.write("    Partition {}:\n".format(
            partition.identifier))
        for edge in partition.edges:
            f.write("        Edge: {}, From {} to {}, model: {}\n".format(
                edge.label, edge.pre_vertex.label,
                edge.post_vertex.label, edge.__class__.__name__))
    f.write("\n")

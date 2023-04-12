# Copyright (c) 2017 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os.path
from spinn_utilities.log import FormatAdapter
from pacman.model.graphs.application import ApplicationVertex
from spinn_front_end_common.data import FecDataView

logger = FormatAdapter(logging.getLogger(__name__))

_FILENAME = "network_specification.rpt"


def network_specification():
    """
    Generate report on the user's network specification.
    """
    filename = os.path.join(FecDataView.get_run_dir_path(), _FILENAME)
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("*** Vertices:\n")
            for vertex in FecDataView.iterate_vertices():
                _write_report(f, vertex)
    except IOError:
        logger.exception("Generate_placement_reports: Can't open file {}"
                         " for writing.", filename)


def _write_report(f, vertex):
    """
    :param ~io.FileIO f:
    :param ~pacman.model.graphs.application.ApplicationVertex vertex:
    """
    if isinstance(vertex, ApplicationVertex):
        f.write(
            f"Vertex {vertex.label}, size: {vertex.n_atoms}, "
            f"model: {vertex.__class__.__name__}, "
            f"max_atoms: {vertex.get_max_atoms_per_core()}\n")
    else:
        f.write(f"Vertex {vertex.label}, model: {vertex.__class__.__name__}\n")

    if vertex.get_fixed_location():
        f.write(f"    Fixed at:{vertex.get_fixed_location()}\n")

    f.write("    Outgoing Edge Partitions:\n")
    for partition in \
            FecDataView.get_outgoing_edge_partitions_starting_at_vertex(
                vertex):
        f.write(f"    Partition {partition.identifier}:\n")
        for edge in partition.edges:
            f.write(
                f"        Edge: {edge.label}, "
                f"From {edge.pre_vertex.label} to {edge.post_vertex.label}, "
                f"model: {edge.__class__.__name__}\n")
    f.write("\n")

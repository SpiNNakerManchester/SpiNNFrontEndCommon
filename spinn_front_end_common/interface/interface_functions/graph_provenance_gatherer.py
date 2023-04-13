# Copyright (c) 2016 The University of Manchester
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

from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.provenance import (
    AbstractProvidesLocalProvenanceData)


def graph_provenance_gatherer():
    """
    Gets provenance information from the graph.
    """
    progress = ProgressBar(
        FecDataView.get_n_vertices() +
        FecDataView.get_n_partitions(),
        "Getting provenance data from application graph")
    for vertex in progress.over(FecDataView.iterate_vertices(), False):
        if isinstance(vertex, AbstractProvidesLocalProvenanceData):
            vertex.get_local_provenance_data()
            for m_vertex in vertex.machine_vertices:
                if isinstance(m_vertex, AbstractProvidesLocalProvenanceData):
                    m_vertex.get_local_provenance_data()
    for partition in progress.over(
            FecDataView.iterate_partitions()):
        for edge in partition.edges:
            if isinstance(edge, AbstractProvidesLocalProvenanceData):
                edge.get_local_provenance_data()

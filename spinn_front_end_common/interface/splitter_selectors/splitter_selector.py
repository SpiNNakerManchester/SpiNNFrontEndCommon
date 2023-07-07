# Copyright (c) 2020 The University of Manchester
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

from spinn_utilities.log import FormatAdapter
from pacman.data import PacmanDataView
from pacman.model.partitioner_splitters import (
    SplitterOneAppOneMachine, SplitterFixedLegacy)
from pacman.model.graphs.application.abstract import (
    AbstractOneAppOneMachineVertex)
from spinn_front_end_common.utility_models import ReverseIpTagMultiCastSource

logger = FormatAdapter(logging.getLogger(__name__))


def splitter_selector():
    """
    Basic selector which puts the legacy splitter object on
    everything without a splitter object.
    """
    for app_vertex in PacmanDataView.iterate_vertices():
        if app_vertex.splitter is None:
            vertex_selector(app_vertex)


def vertex_selector(app_vertex):
    """
    Main point for selecting a splitter object for a given app vertex.

    Will assume the SplitterFixedLegacy if no heuristic is known for the
    app vertex.

    :param ~pacman.model.graphs.application.ApplicationVertex app_vertex:
        app vertex to give a splitter object to
    """
    if isinstance(app_vertex, AbstractOneAppOneMachineVertex):
        app_vertex.splitter = SplitterOneAppOneMachine()
    elif isinstance(app_vertex, ReverseIpTagMultiCastSource):
        app_vertex.splitter = SplitterFixedLegacy()
    else:
        logger.warning(
            f"The SplitterSelector has not seen the {app_vertex} vertex "
            f"before. Therefore there is no known splitter to allocate to "
            f"this app vertex and so will use the SplitterFixedLegacy.")
        app_vertex.splitter = SplitterFixedLegacy()

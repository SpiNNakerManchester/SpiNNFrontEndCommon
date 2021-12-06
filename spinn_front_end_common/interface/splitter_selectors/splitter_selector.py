# Copyright (c) 2020-2021 The University of Manchester
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

from spinn_utilities.log import FormatAdapter
from pacman.data import PacmanDataView
from pacman.model.partitioner_splitters import (
    SplitterOneAppOneMachine, SplitterOneToOneLegacy, SplitterSliceLegacy)
from pacman.model.graphs.application.abstract import (
    AbstractOneAppOneMachineVertex)
from spinn_front_end_common.utility_models import (
    ReverseIpTagMultiCastSource, LivePacketGather, ChipPowerMonitor)

logger = FormatAdapter(logging.getLogger(__name__))


def splitter_selector():
    """ basic selector which puts the legacy splitter object on\
        everything without a splitter object

    :rtype: None
    """
    for app_vertex in PacmanDataView().runtime_graph.vertices:
        if app_vertex.splitter is None:
            vertex_selector(app_vertex)


def vertex_selector(app_vertex):
    """ main point for selecting a splitter object for a given app vertex.

    Will assume the SplitterSliceLegacy if no heuristic is known for the
    app vertex.

    :param ~pacman.model.graphs.application.ApplicationVertex app_vertex:
        app vertex to give a splitter object to
    :rtype: None
    """
    if isinstance(app_vertex, AbstractOneAppOneMachineVertex):
        app_vertex.splitter = SplitterOneAppOneMachine()
    elif isinstance(app_vertex, ReverseIpTagMultiCastSource):
        app_vertex.splitter = SplitterSliceLegacy()
    elif isinstance(app_vertex, LivePacketGather):
        app_vertex.splitter = SplitterOneToOneLegacy()
    elif isinstance(app_vertex, ChipPowerMonitor):
        app_vertex.splitter = SplitterOneToOneLegacy()
    else:
        logger.warning(
            f"The SplitterSelector has not seen the {app_vertex} vertex "
            f"before. Therefore there is no known splitter to allocate to "
            f"this app vertex and so will use the SplitterSliceLegacy.")
        app_vertex.splitter = SplitterSliceLegacy()

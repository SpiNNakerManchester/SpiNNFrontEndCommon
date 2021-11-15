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
from pacman.model.partitioner_splitters import (
    SplitterOneAppOneMachine, SplitterOneToOneLegacy, SplitterSliceLegacy)
from pacman.model.graphs.application.abstract import (
    AbstractOneAppOneMachineVertex)
from spinn_front_end_common.utility_models import (
    ReverseIpTagMultiCastSource, LivePacketGather, ChipPowerMonitor)

logger = FormatAdapter(logging.getLogger(__name__))


class SplitterSelector(object):
    """ Splitter object selector that allocates nothing but legacy\
        splitter objects where required
    """

    NOT_KNOWN_APP_VERTEX_ERROR_MESSAGE = (
        "The SplitterSelector has not seen the {} vertex before. Therefore "
        "there is no known splitter to allocate to this app vertex and so "
        "will use the SplitterSliceLegacy Splitter.")

    def __call__(self, app_graph):
        """ basic selector which puts the legacy splitter object on\
            everything without a splitter object

        :param ApplicationGraph app_graph: app graph
        :rtype: None
        """
        for app_vertex in app_graph.vertices:
            if app_vertex.splitter is None:
                self.vertex_selector(app_vertex)

    def vertex_selector(self, app_vertex):
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
                self.NOT_KNOWN_APP_VERTEX_ERROR_MESSAGE.format(app_vertex))
            app_vertex.splitter = SplitterSliceLegacy()

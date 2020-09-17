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
from six import add_metaclass

from pacman.exceptions import PacmanConfigurationException
from spinn_utilities.abstract_base import AbstractBase, abstractmethod


@add_metaclass(AbstractBase)
class AbstractSplitterCommon(object):

    __slots__ = [
        "_governed_app_vertex",
        "_splitter_name"
    ]

    SETTING_SPLITTER_OBJECT_ERROR_MSG = (
        "The app vertex {} is already governed by this "
        "{}. And so cannot govern app vertex {}."
        " Please fix and try again.")

    STR_MESSAGE = "{} governing app vertex {}"

    DEFAULT_SPLITTER_NAME = "AbstractSplitterCommon"

    def __init__(self, splitter_name=None):
        if splitter_name is None:
            splitter_name = self.DEFAULT_SPLITTER_NAME
        self._splitter_name = splitter_name

        self._governed_app_vertex = None

    def __str__(self):
        return self.STR_MESSAGE.format(
            self._splitter_name, self._governed_app_vertex)

    def __repr__(self):
        return self.__str__()

    def set_governed_app_vertex(self, app_vertex):
        if self._governed_app_vertex is not None:
            raise PacmanConfigurationException(
                self.SETTING_SPLITTER_OBJECT_ERROR_MSG.format(
                    self._governed_app_vertex, self._splitter_name,
                    app_vertex))
        self._governed_app_vertex = app_vertex

    def split(self, resource_tracker, machine_graph):
        """ executes splitting

        :param ResourceTracker resource_tracker: machine resources
        :param MachineGraph machine_graph: machine graph
        :return: bool true if successful, false otherwise
        """
        return self.create_machine_vertices(resource_tracker, machine_graph)

    @abstractmethod
    def create_machine_vertices(self, resource_tracker, machine_graph):
        """ method for specific splitter objects to use.

        :param resource_tracker:
        :param machine_graph:
        :return: bool true if successful, false otherwise
        """

    @abstractmethod
    def get_out_going_slices(self):
        """ allows a application vertex to control the set of slices for \
        outgoing application edges
        :return: list of Slices and bool of estimate or not
        """

    @abstractmethod
    def get_in_coming_slices(self):
        """ allows a application vertex to control the set of slices for \
        incoming application edges
        :return: the slices incoming to this vertex, bool if estimate or exact
        """

    @abstractmethod
    def get_pre_vertices(self, edge, outgoing_edge_partition):
        """ gets pre vertices and their acceptable edge types
        :param ApplicationEdge edge: app edge
        :param OutgoingEdgePartition outgoing_edge_partition: \
            outgoing edge partition
        :return: dict of keys being machine vertices and values are a list
        of acceptable edge types.
        """

    @abstractmethod
    def get_post_vertices(self, edge, outgoing_edge_partition,
                          src_machine_vertex):
        """ gets post vertices and their acceptable edge types
        :param ApplicationEdge edge: app edge
        :param OutgoingEdgePartition outgoing_edge_partition: \
            outgoing edge partition
        :param MachineVertex src_machine_vertex: the src machine vertex
        :return: dict of keys being machine vertices and values are a list
        of acceptable edge types.
        """

    @abstractmethod
    def machine_vertices_for_recording(self, variable_to_record):
        """

        :param variable_to_record:
        :return: list of machine vertices
        """

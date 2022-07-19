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

from spinn_utilities.abstract_base import abstractmethod
from spinn_utilities.overrides import overrides
from pacman.executor.injection_decorator import inject_items
from spinn_front_end_common.abstract_models import (
    AbstractGeneratesDataSpecification)


class MachineDataSpecableVertex(
        AbstractGeneratesDataSpecification, allow_derivation=True):
    """ Support for a vertex that simplifies generating a data specification.
    """
    __slots__ = ()

    @inject_items({
        "graph": "ApplicationGraph",
        "routing_info": "RoutingInfos",
        "tags": "Tags"})
    @overrides(
        AbstractGeneratesDataSpecification.generate_data_specification,
        additional_arguments={
            "graph", "routing_info", "tags",
        })
    def generate_data_specification(
            self, spec, placement, graph, routing_info, tags):
        """
        :param ~pacman.model.graphs.application.ApplicationGraph graph:
            (Injected)
        :param ~pacman.model.routing_info.RoutingInfo routing_info: (Injected)
        :param ~pacman.model.tags.Tags tags: (Injected)
        """
        # pylint: disable=too-many-arguments, arguments-differ
        iptags = tags.get_ip_tags_for_vertex(placement.vertex)
        reverse_iptags = tags.get_reverse_ip_tags_for_vertex(placement.vertex)
        self.generate_machine_data_specification(
            spec, placement, graph, routing_info, iptags,
            reverse_iptags)

    @abstractmethod
    def generate_machine_data_specification(
            self, spec, placement, graph, routing_info, iptags,
            reverse_iptags):
        """
        :param ~data_specification.DataSpecificationGenerator spec:
            The data specification to write into.
        :param ~pacman.model.placements.Placement placement:
            Where this node is on the SpiNNaker machine.
        :param ~pacman.model.graphs.application.ApplicationGraph graph:
            The graph containing this node.
        :param ~pacman.model.routing_info.RoutingInfo routing_info:
            The routing info.
        :param iptags: The (forward) IP tags for the vertex, if any
        :type iptags: iterable(~spinn_machine.tags.IPTag) or None
        :param reverse_iptags: The reverse IP tags for the vertex, if any
        :type reverse_iptags:
            iterable(~spinn_machine.tags.ReverseIPTag) or None
        :rtype: None
        """
        # pylint: disable=too-many-arguments

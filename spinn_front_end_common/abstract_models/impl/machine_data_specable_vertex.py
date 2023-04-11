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

from spinn_utilities.abstract_base import abstractmethod
from spinn_utilities.overrides import overrides
from spinn_front_end_common.abstract_models import (
    AbstractGeneratesDataSpecification)
from spinn_front_end_common.data import FecDataView


class MachineDataSpecableVertex(
        AbstractGeneratesDataSpecification, allow_derivation=True):
    """
    Support for a vertex that simplifies generating a data specification.
    """
    __slots__ = ()

    @overrides(AbstractGeneratesDataSpecification.generate_data_specification)
    def generate_data_specification(self, spec, placement):
        # pylint: disable=too-many-arguments, arguments-differ
        tags = FecDataView.get_tags()
        iptags = tags.get_ip_tags_for_vertex(placement.vertex)
        reverse_iptags = tags.get_reverse_ip_tags_for_vertex(placement.vertex)
        self.generate_machine_data_specification(
            spec, placement, iptags, reverse_iptags)

    @abstractmethod
    def generate_machine_data_specification(
            self, spec, placement, iptags, reverse_iptags):
        """
        :param ~data_specification.DataSpecificationGenerator spec:
            The data specification to write into.
        :param ~pacman.model.placements.Placement placement:
            Where this node is on the SpiNNaker machine.
        :param iptags: The (forward) IP tags for the vertex, if any
        :type iptags: iterable(~spinn_machine.tags.IPTag) or None
        :param reverse_iptags: The reverse IP tags for the vertex, if any
        :type reverse_iptags:
            iterable(~spinn_machine.tags.ReverseIPTag) or None
        """
        # pylint: disable=too-many-arguments

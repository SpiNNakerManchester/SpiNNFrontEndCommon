# Copyright (c) 2014 The University of Manchester
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

from .abstract_generates_data_specification import (
    AbstractGeneratesDataSpecification)
from .abstract_has_associated_binary import AbstractHasAssociatedBinary
from .abstract_machine_allocation_controller import (
    AbstractMachineAllocationController)
from .abstract_rewrites_data_specification import (
    AbstractRewritesDataSpecification)
from .abstract_send_me_multicast_commands_vertex import (
    AbstractSendMeMulticastCommandsVertex)
from .abstract_vertex_with_dependent_vertices import (
    AbstractVertexWithEdgeToDependentVertices)
from .abstract_supports_database_injection import (
    AbstractSupportsDatabaseInjection)
from .abstract_supports_bit_field_generation import (
    AbstractSupportsBitFieldGeneration)
from .abstract_supports_bit_field_routing_compression import (
    AbstractSupportsBitFieldRoutingCompression)
from .abstract_can_reset import AbstractCanReset
from .has_custom_atom_key_map import HasCustomAtomKeyMap

__all__ = ["AbstractGeneratesDataSpecification",
           "AbstractHasAssociatedBinary",
           "AbstractMachineAllocationController",
           "AbstractRewritesDataSpecification",
           "AbstractSendMeMulticastCommandsVertex",
           "AbstractSupportsDatabaseInjection",
           "AbstractVertexWithEdgeToDependentVertices", "AbstractCanReset",
           "AbstractSupportsBitFieldGeneration",
           "AbstractSupportsBitFieldRoutingCompression",
           "HasCustomAtomKeyMap"]

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

from .abstract_changable_after_run import AbstractChangableAfterRun
from .abstract_generates_data_specification import (
    AbstractGeneratesDataSpecification)
from .abstract_has_associated_binary import AbstractHasAssociatedBinary
from .abstract_machine_allocation_controller import (
    AbstractMachineAllocationController)
from .abstract_provides_incoming_partition_constraints import (
    AbstractProvidesIncomingPartitionConstraints)
from .abstract_provides_key_to_atom_mapping import (
    AbstractProvidesKeyToAtomMapping)
from .abstract_provides_n_keys_for_partition import (
    AbstractProvidesNKeysForPartition)
from .abstract_provides_outgoing_partition_constraints import (
    AbstractProvidesOutgoingPartitionConstraints)
from .abstract_recordable import AbstractRecordable
from .abstract_rewrites_data_specification import (
    AbstractRewritesDataSpecification)
from .abstract_send_me_multicast_commands_vertex import (
    AbstractSendMeMulticastCommandsVertex)
from .abstract_vertex_with_dependent_vertices import (
    AbstractVertexWithEdgeToDependentVertices)
from .abstract_supports_database_injection import (
    AbstractSupportsDatabaseInjection)
from .abstract_uses_memory_io import AbstractUsesMemoryIO
from .abstract_can_reset import AbstractCanReset

__all__ = ["AbstractChangableAfterRun", "AbstractGeneratesDataSpecification",
           "AbstractHasAssociatedBinary",
           "AbstractMachineAllocationController",
           "AbstractProvidesIncomingPartitionConstraints",
           "AbstractProvidesKeyToAtomMapping",
           "AbstractProvidesNKeysForPartition",
           "AbstractProvidesOutgoingPartitionConstraints",
           "AbstractRecordable", "AbstractRewritesDataSpecification",
           "AbstractSendMeMulticastCommandsVertex",
           "AbstractSupportsDatabaseInjection",
           "AbstractVertexWithEdgeToDependentVertices",
           "AbstractUsesMemoryIO", "AbstractCanReset"]

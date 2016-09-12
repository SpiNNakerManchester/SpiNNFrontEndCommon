from pacman.model.abstract_classes.impl.constrained_object import \
    ConstrainedObject
from pacman.model.decorators.delegates_to import delegates_to
from pacman.model.graphs.machine.impl.machine_vertex \
    import MachineVertex
from spinn_front_end_common.interface.provenance\
    .provides_provenance_data_from_machine_impl \
    import ProvidesProvenanceDataFromMachineImpl

_COMMAND_WITH_PAYLOAD_SIZE = 12

_COMMAND_WITHOUT_PAYLOAD_SIZE = 8


class CommandSenderMachineVertex(
        MachineVertex, ProvidesProvenanceDataFromMachineImpl):

    SYSTEM_REGION = 0
    COMMANDS = 1
    PROVENANCE_REGION = 2

    def __init__(self, constraints, resources_required, label):
        ProvidesProvenanceDataFromMachineImpl.__init__(
            self, self.PROVENANCE_REGION, n_additional_data_items=0)
        MachineVertex.__init__(self, resources_required, label, constraints)

        self._edge_constraints = dict()
        self._command_edge = dict()
        self._times_with_commands = set()
        self._commands_with_payloads = dict()
        self._commands_without_payloads = dict()

    @delegates_to("_constraints", ConstrainedObject.add_constraints)
    def add_constraints(self, constraints):
        pass

    @delegates_to("_constraints", ConstrainedObject.constraints)
    def constraints(self):
        pass

    @delegates_to("_constraints", ConstrainedObject.add_constraint)
    def add_constraint(self, constraint):
        pass

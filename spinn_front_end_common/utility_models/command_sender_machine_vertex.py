from pacman.model.decorators.overrides import overrides

from pacman.model.abstract_classes.impl.constrained_object import \
    ConstrainedObject
from pacman.model.decorators.delegates_to import delegates_to
from pacman.model.graphs.machine.abstract_machine_vertex \
    import AbstractMachineVertex
from spinn_front_end_common.interface.provenance\
    .provides_provenance_data_from_machine_impl \
    import ProvidesProvenanceDataFromMachineImpl

_COMMAND_WITH_PAYLOAD_SIZE = 12

_COMMAND_WITHOUT_PAYLOAD_SIZE = 8


class CommandSenderMachineVertex(
        AbstractMachineVertex, ProvidesProvenanceDataFromMachineImpl):

    SYSTEM_REGION = 0
    COMMANDS = 1
    PROVENANCE_REGION = 2

    def __init__(self, constraints, resources_required, label):
        ProvidesProvenanceDataFromMachineImpl.__init__(
            self, self.PROVENANCE_REGION, n_additional_data_items=0)

        self._edge_constraints = dict()
        self._command_edge = dict()
        self._times_with_commands = set()
        self._commands_with_payloads = dict()
        self._commands_without_payloads = dict()
        self._resources_required = resources_required
        self._label = label

        self._constraints = ConstrainedObject(constraints)

    @overrides(AbstractMachineVertex.resources_required)
    def resources_required(self):
        return self._resources_required

    @overrides(AbstractMachineVertex.set_resources_required)
    def set_resources_required(self, resource_required):
        self._resources_required = resource_required

    @property
    @overrides(AbstractMachineVertex.label)
    def label(self):
        return self._label

    @delegates_to("_constraints", ConstrainedObject.add_constraints)
    def add_constraints(self, constraints):
        pass

    @delegates_to("_constraints", ConstrainedObject.constraints)
    def constraints(self):
        pass

    @delegates_to("_constraints", ConstrainedObject.add_constraint)
    def add_constraint(self, constraint):
        pass

    @property
    @overrides(AbstractMachineVertex.model_name)
    def model_name(self):
        """ Return the name of the model as a string
        """
        return "machine_command_sender_multi_cast_source"

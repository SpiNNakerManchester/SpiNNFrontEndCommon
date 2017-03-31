from pacman.model.decorators.overrides import overrides
from pacman.model.graphs.machine import MachineVertex
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
        MachineVertex.__init__(self, label, constraints)

        self._edge_constraints = dict()
        self._command_edge = dict()
        self._times_with_commands = set()
        self._commands_with_payloads = dict()
        self._commands_without_payloads = dict()
        self._resources = resources_required

    @property
    @overrides(ProvidesProvenanceDataFromMachineImpl._provenance_region_id)
    def _provenance_region_id(self):
        return self.PROVENANCE_REGION

    @property
    @overrides(ProvidesProvenanceDataFromMachineImpl._n_additional_data_items)
    def _n_additional_data_items(self):
        return 0

    @property
    @overrides(MachineVertex.resources_required)
    def resources_required(self):
        return self._resources

from spinn_front_end_common.interface.provenance\
    .provides_provenance_data_from_machine_impl \
    import ProvidesProvenanceDataFromMachineImpl
from pacman.model.graph.machine.simple_machine_vertex import SimpleMachineVertex


class CommandSenderMachineVertex(
        SimpleMachineVertex, ProvidesProvenanceDataFromMachineImpl):

    SYSTEM_REGION = 0
    COMMANDS = 1
    PROVENANCE_REGION = 2

    def __init__(self, resources_required, label, constraints=None):
        SimpleMachineVertex.__init__(
            self, resources_required, label, constraints)
        ProvidesProvenanceDataFromMachineImpl.__init__(
            self, self.PROVENANCE_REGION, 0)

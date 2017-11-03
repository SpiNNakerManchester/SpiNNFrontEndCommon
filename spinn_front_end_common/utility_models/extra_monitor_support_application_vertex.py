from pacman.executor.injection_decorator import inject_items
from pacman.model.graphs.application import ApplicationVertex
from spinn_front_end_common.abstract_models import \
    AbstractHasAssociatedBinary, AbstractGeneratesDataSpecification
from spinn_front_end_common.utility_models.\
    extra_monitor_support_machine_vertex import \
    ExtraMonitorSupportMachineVertex
from spinn_utilities.overrides import overrides


class ExtraMonitorSupportApplicationVertex(
        ApplicationVertex, AbstractHasAssociatedBinary,
        AbstractGeneratesDataSpecification):

    def __init__(self, constraints):
        ApplicationVertex.__init__(
            self, label="ExtraMonitorSupportApplicationVertex",
            constraints=constraints)
        AbstractHasAssociatedBinary.__init__(self)
        AbstractGeneratesDataSpecification.__init__(self)

    @overrides(ApplicationVertex.create_machine_vertex)
    def create_machine_vertex(self, vertex_slice, resources_required,
                              label=None, constraints=None):
        return ExtraMonitorSupportMachineVertex(constraints=constraints)

    @property
    @overrides(ApplicationVertex.n_atoms)
    def n_atoms(self):
        return 1

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return ExtraMonitorSupportMachineVertex.static_get_binary_start_type()

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return ExtraMonitorSupportMachineVertex.static_get_binary_file_name()

    @overrides(ApplicationVertex.get_resources_used_by_atoms)
    def get_resources_used_by_atoms(self, vertex_slice):
        return ExtraMonitorSupportMachineVertex.static_resources_required()

    @inject_items({"routing_info": "MemoryRoutingInfos",
                   "machine_graph": "MemoryMachineGraph"})
    @overrides(AbstractGeneratesDataSpecification.generate_data_specification,
               additional_arguments={"routing_info", "machine_graph"})
    def generate_data_specification(
            self, spec, placement, routing_info, machine_graph):
        placement.vertex.generate_data_specification(
            spec, placement, routing_info, machine_graph)

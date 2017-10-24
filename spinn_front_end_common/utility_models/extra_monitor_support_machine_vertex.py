from pacman.model.graphs.machine import MachineVertex
from pacman.model.resources import ResourceContainer
from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_utilities.overrides import overrides


class ExtraMonitorSupportMachineVertex(
        MachineVertex, AbstractHasAssociatedBinary):

    def __init__(self, constraints):
        MachineVertex.__init__(
            self, label="ExtraMonitorSupportMachineVertex",
            constraints=constraints)
        AbstractHasAssociatedBinary.__init__(self)

    @property
    @overrides(MachineVertex.resources_required)
    def resources_required(self):
        return self.static_resources_required()

    @staticmethod
    def static_resources_required():
        return ResourceContainer()

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return self.static_get_binary_start_type()

    @staticmethod
    def static_get_binary_start_type():
        return ExecutableType.RUNNING

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return self.static_get_binary_file_name()

    @staticmethod
    def static_get_binary_file_name():
        return "extra_monitor_support.aplx"

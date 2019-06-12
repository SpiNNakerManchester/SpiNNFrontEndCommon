from spinn_utilities.overrides import overrides
from pacman.model.graphs.application import ApplicationVertex
from spinn_front_end_common.abstract_models import (
    AbstractHasAssociatedBinary, AbstractGeneratesDataSpecification)
from .data_speed_up_packet_gatherer_machine_vertex import (
    DataSpeedUpPacketGatherMachineVertex)


class DataSpeedUpPacketGather(
        ApplicationVertex, AbstractGeneratesDataSpecification,
        AbstractHasAssociatedBinary):
    __slots__ = ["_machine_vertex"]

    def __init__(
            self, x, y, ip_address, extra_monitors_by_chip,
            report_default_directory,
            write_data_speed_up_reports, constraints=None):
        super(DataSpeedUpPacketGather, self).__init__(
            "multicast speed up application vertex for {}, {}".format(
                x, y), constraints, 1)
        self._machine_vertex = DataSpeedUpPacketGatherMachineVertex(
            x=x, y=y, ip_address=ip_address, constraints=constraints,
            extra_monitors_by_chip=extra_monitors_by_chip,
            report_default_directory=report_default_directory,
            write_data_speed_up_reports=write_data_speed_up_reports)

    @property
    def machine_vertex(self):
        return self._machine_vertex

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return self._machine_vertex.get_binary_file_name()

    @overrides(ApplicationVertex.get_resources_used_by_atoms)
    def get_resources_used_by_atoms(self, vertex_slice):
        return self._machine_vertex.resources_required

    @overrides(ApplicationVertex.create_machine_vertex)
    def create_machine_vertex(self, vertex_slice, resources_required,
                              label=None, constraints=None):
        return self._machine_vertex

    @overrides(AbstractGeneratesDataSpecification.generate_data_specification)
    def generate_data_specification(self, spec, placement):
        placement.vertex.generate_data_specification(spec, placement)

    @property
    @overrides(ApplicationVertex.n_atoms)
    def n_atoms(self):
        return 1

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return self._machine_vertex.get_binary_start_type()

from pacman.executor.injection_decorator import inject_items
from pacman.model.graphs.application import ApplicationVertex
from pacman.model.decorators import overrides
from spinn_front_end_common.abstract_models \
    import AbstractHasAssociatedBinary, AbstractGeneratesDataSpecification
from spinn_front_end_common.utility_models.\
    multicast_data_speed_up_packet_gatherer_machine_vertex import \
    MulticastDataSpeedUpPacketGatherMachineVertex
from spinnman.connections.udp_packet_connections import UDPConnection


class MulticastDataSpeedUpPacketGatherApplicationVertex(
        ApplicationVertex, AbstractGeneratesDataSpecification,
        AbstractHasAssociatedBinary):

    def __init__(self):
        ApplicationVertex.__init__(
            self, "multicast speed up application vertex", None, 1)
        self._connection = UDPConnection(local_host=None)

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return MulticastDataSpeedUpPacketGatherMachineVertex.\
            static_get_binary_file_name()

    @overrides(ApplicationVertex.get_resources_used_by_atoms)
    def get_resources_used_by_atoms(self, vertex_slice):
        return MulticastDataSpeedUpPacketGatherMachineVertex.\
            resources_required_for_connection(self._connection)

    @overrides(ApplicationVertex.create_machine_vertex)
    def create_machine_vertex(self, vertex_slice, resources_required,
                              label=None, constraints=None):
        return MulticastDataSpeedUpPacketGatherMachineVertex(self._connection)

    @inject_items({"time_scale_factor": "TimeScaleFactor",
                   "machine_time_step": "MachineTimeStep",
                   "routing_infos": "MemoryRoutingInfo",
                   "machine_graph": "MemoryMachineGraph"})
    @overrides(AbstractGeneratesDataSpecification.generate_data_specification,
               additional_arguments={
                   "machine_time_step", "time_scale_factor", "routing_infos",
                   "machine_graph"})
    def generate_data_specification(
            self, spec, placement, machine_time_step, time_scale_factor,
            routing_infos, machine_graph):

        base_key = routing_infos.get_first_key_for_edge(
            list(machine_graph.get_edges_ending_at_vertex(
                placement.vertex()))[0])

        MulticastDataSpeedUpPacketGatherMachineVertex.\
            static_generate_machine_data_specification(
                spec, base_key, machine_time_step, time_scale_factor)

    @property
    @overrides(ApplicationVertex.n_atoms)
    def n_atoms(self):
        return 1

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return MulticastDataSpeedUpPacketGatherMachineVertex.\
            static_get_binary_start_type()


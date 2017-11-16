from pacman.executor.injection_decorator import inject_items
from pacman.model.graphs.application import ApplicationVertex
from pacman.model.decorators import overrides
from pacman.model.graphs.common import EdgeTrafficType

from spinn_front_end_common.abstract_models \
    import AbstractHasAssociatedBinary, AbstractGeneratesDataSpecification, \
    AbstractProvidesIncomingPartitionConstraints
from spinn_front_end_common.utility_models.\
    data_speed_up_packet_gatherer_machine_vertex import \
    DataSpeedUpPacketGatherMachineVertex
from spinn_front_end_common.utilities import constants

from spinnman.connections.udp_packet_connections import UDPConnection


class DataSpeedUpPacketGatherApplicationVertex(
        ApplicationVertex, AbstractGeneratesDataSpecification,
        AbstractHasAssociatedBinary,
        AbstractProvidesIncomingPartitionConstraints):

    def __init__(self):
        ApplicationVertex.__init__(
            self, "multicast speed up application vertex", None, 1)
        AbstractGeneratesDataSpecification.__init__(self)
        AbstractHasAssociatedBinary.__init__(self)
        AbstractProvidesIncomingPartitionConstraints.__init__(self)

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return DataSpeedUpPacketGatherMachineVertex.\
            static_get_binary_file_name()

    @overrides(ApplicationVertex.get_resources_used_by_atoms)
    def get_resources_used_by_atoms(self, vertex_slice):
        return DataSpeedUpPacketGatherMachineVertex.\
            resources_required_for_connection(self._connection)

    @overrides(ApplicationVertex.create_machine_vertex)
    def create_machine_vertex(self, vertex_slice, resources_required,
                              label=None, constraints=None):
        connection = UDPConnection(local_host=None)
        return DataSpeedUpPacketGatherMachineVertex(connection)

    @inject_items({"time_scale_factor": "TimeScaleFactor",
                   "machine_time_step": "MachineTimeStep",
                   "routing_infos": "MemoryRoutingInfos",
                   "machine_graph": "MemoryMachineGraph",
                   "tags": "MemoryTags"})
    @overrides(AbstractGeneratesDataSpecification.generate_data_specification,
               additional_arguments={
                   "machine_time_step", "time_scale_factor", "routing_infos",
                   "machine_graph", "tags"})
    def generate_data_specification(
            self, spec, placement, machine_time_step, time_scale_factor,
            routing_infos, machine_graph, tags):

        if DataSpeedUpPacketGatherMachineVertex.TRAFFIC_TYPE == \
                EdgeTrafficType.MULTICAST:
            base_key = routing_infos.get_first_key_for_edge(
                list(machine_graph.get_edges_ending_at_vertex(
                    placement.vertex))[0])
        else:
            base_key = DataSpeedUpPacketGatherMachineVertex.BASE_KEY

        DataSpeedUpPacketGatherMachineVertex.\
            static_generate_machine_data_specification(
                spec, base_key, machine_time_step, time_scale_factor,
                tags.get_ip_tags_for_vertex(placement.vertex))

    @property
    @overrides(ApplicationVertex.n_atoms)
    def n_atoms(self):
        return 1

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return DataSpeedUpPacketGatherMachineVertex.\
            static_get_binary_start_type()

    @inject_items({"application_graph": "MemoryApplicationGraph"})
    @overrides(AbstractProvidesIncomingPartitionConstraints.
               get_incoming_partition_constraints,
               additional_arguments={"application_graph"})
    def get_incoming_partition_constraints(self, partition, application_graph):
        if partition.identifier != \
                constants.PARTITION_ID_FOR_MULTICAST_DATA_SPEED_UP:
            raise Exception("do not recognise this partition identifier")

        vertex_partition = list()
        incoming_edges = application_graph.get_edges_ending_at_vertex(self)
        for incoming_edge in incoming_edges:
            partition = application_graph.\
                get_outgoing_edge_partition_starting_at_vertex(
                    incoming_edge.pre_vertex,
                    constants.PARTITION_ID_FOR_MULTICAST_DATA_SPEED_UP)
            vertex_partition.append(partition)
        return DataSpeedUpPacketGatherMachineVertex.\
            static_get_incoming_partition_constraints(
                partition, vertex_partition)

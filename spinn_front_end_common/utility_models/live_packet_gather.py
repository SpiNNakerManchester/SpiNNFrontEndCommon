# pacman imports
from pacman.model.partitionable_graph.abstract_partitionable_vertex \
    import AbstractPartitionableVertex

# spinn front end imports
from spinn_front_end_common.abstract_models.\
    abstract_data_specable_vertex import AbstractDataSpecableVertex
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utility_models\
    .live_packet_gather_partitioned_vertex \
    import LivePacketGatherPartitionedVertex

# spinnman imports
from spinnman.messages.eieio.eieio_type import EIEIOType
from spinnman.messages.eieio.eieio_prefix import EIEIOPrefix


class LivePacketGather(
        AbstractDataSpecableVertex, AbstractPartitionableVertex):
    """ A model which stores all the events it receives during a timer tick\
        and then compresses them into Ethernet packets and sends them out of\
        a spinnaker machine.
    """

    def __init__(self, machine_time_step, timescale_factor, ip_address,
                 port, board_address=None, tag=None, strip_sdp=True,
                 use_prefix=False, key_prefix=None, prefix_type=None,
                 message_type=EIEIOType.KEY_32_BIT, right_shift=0,
                 payload_as_time_stamps=True, use_payload_prefix=True,
                 payload_prefix=None, payload_right_shift=0,
                 number_of_packets_sent_per_time_step=0, constraints=None,
                 label=None):
        """
        """
        if ((message_type == EIEIOType.KEY_PAYLOAD_32_BIT or
             message_type == EIEIOType.KEY_PAYLOAD_16_BIT) and
                use_payload_prefix and payload_as_time_stamps):
            raise ConfigurationException(
                "Timestamp can either be included as payload prefix or as "
                "payload to each key, not both")
        if ((message_type == EIEIOType.KEY_32_BIT or
             message_type == EIEIOType.KEY_16_BIT) and
                not use_payload_prefix and payload_as_time_stamps):
            raise ConfigurationException(
                "Timestamp can either be included as payload prefix or as"
                " payload to each key, but current configuration does not "
                "specify either of these")
        if (not isinstance(prefix_type, EIEIOPrefix) and
                prefix_type is not None):
            raise ConfigurationException(
                "the type of a prefix type should be of a EIEIOPrefix, "
                "which can be located in :"
                "SpinnMan.messages.eieio.eieio_prefix_type")
        if label is None:
            label = "Live Packet Gatherer"

        AbstractDataSpecableVertex.__init__(
            self, machine_time_step=machine_time_step,
            timescale_factor=timescale_factor)
        AbstractPartitionableVertex.__init__(
            self, n_atoms=1, label=label, max_atoms_per_core=1,
            constraints=constraints)

        # add constraints the partitioned vertex decides it needs
        constraints_to_add = \
            LivePacketGatherPartitionedVertex.get_constraints(
                ip_address, port, strip_sdp, board_address, tag)
        for constraint in constraints_to_add:
            self.add_constraint(constraint)

        self._prefix_type = prefix_type
        self._use_prefix = use_prefix
        self._key_prefix = key_prefix
        self._message_type = message_type
        self._right_shift = right_shift
        self._payload_as_time_stamps = payload_as_time_stamps
        self._use_payload_prefix = use_payload_prefix
        self._payload_prefix = payload_prefix
        self._payload_right_shift = payload_right_shift
        self._number_of_packets_sent_per_time_step = \
            number_of_packets_sent_per_time_step

    @property
    def number_of_packets_sent_per_time_step(self):
        """ How many full UDP packets this model can send per timer tick
        :return:
        """
        return self._number_of_packets_sent_per_time_step

    @number_of_packets_sent_per_time_step.setter
    def number_of_packets_sent_per_time_step(self, new_value):
        """

        :param new_value:
        :return:
        """
        self._number_of_packets_sent_per_time_step = new_value

    # inherited from DataSpecable vertex
    def generate_data_spec(self, subvertex, placement, sub_graph, graph,
                           routing_info, hostname, graph_sub_graph_mapper,
                           report_folder, ip_tags, reverse_ip_tags,
                           write_text_specs, application_run_time_folder):

        return subvertex.generate_data_spec(
            placement, sub_graph, routing_info, hostname, report_folder,
            ip_tags, reverse_ip_tags, write_text_specs,
            application_run_time_folder)

    # inherited from partitionable vertex
    def get_cpu_usage_for_atoms(self, vertex_slice, graph):
        return LivePacketGatherPartitionedVertex.get_cpu_usage()

    # inherited from partitionable vertex
    def get_sdram_usage_for_atoms(self, vertex_slice, graph):
        return LivePacketGatherPartitionedVertex.get_sdram_usage()

    # inherited from partitionable vertex
    def get_dtcm_usage_for_atoms(self, vertex_slice, graph):
        return LivePacketGatherPartitionedVertex.get_dtcm_usage()

    # inherited from partitionable vertex
    def create_subvertex(
            self, vertex_slice, resources_required, label=None,
            constraints=None):
        return LivePacketGatherPartitionedVertex(
            label, self._machine_time_step, self._timescale_factor,
            self._use_prefix, self._key_prefix, self._prefix_type,
            self._message_type, self._right_shift,
            self._payload_as_time_stamps, self._use_payload_prefix,
            self._payload_prefix, self._payload_right_shift,
            self._number_of_packets_sent_per_time_step,
            constraints=constraints)

    @property
    def model_name(self):
        """ Human readable form of the model name
        """
        return "live packet gather"

    def get_binary_file_name(self):
        return 'live_packet_gather.aplx'

    def is_data_specable(self):
        return True

    def is_ip_tagable_vertex(self):
        return True

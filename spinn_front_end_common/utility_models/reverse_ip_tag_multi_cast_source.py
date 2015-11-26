# pacman imports
from pacman.model.partitionable_graph.abstract_partitionable_vertex import \
    AbstractPartitionableVertex

# front end common imports
from spinn_front_end_common.abstract_models.\
    abstract_provides_outgoing_edge_constraints \
    import AbstractProvidesOutgoingEdgeConstraints
from spinn_front_end_common.abstract_models.abstract_data_specable_vertex\
    import AbstractDataSpecableVertex
from spinn_front_end_common.utilities import constants

# spinnman imports
from spinnman.messages.eieio.eieio_prefix import EIEIOPrefix

# general imports
import sys
from spinn_front_end_common.utility_models\
    .reverse_ip_tag_multicast_source_partitioned_vertex \
    import ReverseIPTagMulticastSourcePartitionedVertex


class ReverseIpTagMultiCastSource(
        AbstractPartitionableVertex, AbstractDataSpecableVertex,
        AbstractProvidesOutgoingEdgeConstraints):
    """ A model which will allow events to be injected into a spinnaker\
        machine and converted into multicast packets.
    """

    def __init__(
            self, n_keys, machine_time_step, timescale_factor, label=None,
            constraints=None, max_atoms_per_core=sys.maxint,

            # General parameters
            board_address=None,

            # Live input parameters
            receive_port=None,
            receive_sdp_port=constants.SDP_PORTS.INPUT_BUFFERING_SDP_PORT,
            receive_tag=None,

            # Key parameters
            virtual_key=None, prefix=None,
            prefix_type=EIEIOPrefix.LOWER_HALF_WORD, check_keys=False,

            # Send buffer parameters
            send_buffer_times=None,
            send_buffer_max_space=1024 * 1024,
            send_buffer_space_before_notify=640,
            send_buffer_notification_ip_address=None,
            send_buffer_notification_port=None,
            send_buffer_notification_tag=None):
        """

        :param n_keys: The number of keys to be sent via this multicast source
        :param machine_time_step: The time step to be used on the machine
        :param timescale_factor: The time scaling to be used in the simulation
        :param label: The label of this vertex
        :param constraints: Any initial constraints to this vertex
        :param board_address: The IP address of the board on which to place\
                this vertex if receiving data, either buffered or live (by\
                default, any board is chosen)
        :param receive_port: The port on the board that will listen for\
                incoming event packets (default is to disable this feature;\
                set a value to enable it)
        :param receive_sdp_port: The SDP port to listen on for incoming event\
                packets (defaults to 1)
        :param receive_tag: The IP tag to use for receiving live events\
                (uses any by default)
        :param virtual_key: The base multicast key to send received events\
                with (assigned automatically by default)
        :param prefix: The prefix to "or" with generated multicast keys\
                (default is no prefix)
        :param prefix_type: Whether the prefix should apply to the upper or\
                lower half of the multicast keys (default is lower half)
        :param check_keys: True if the keys of received events should be\
                verified before sending (default False)
        :param send_buffer_times: An array of arrays of times at which keys\
                should be sent (one array for each key, default disabled)
        :param send_buffer_max_space: The maximum amount of space to use of\
                the SDRAM on the machine (default is 1MB)
        :param send_buffer_space_before_notify: The amount of space free in\
                the sending buffer before the machine will ask the host for\
                more data (default setting is optimised for most cases)
        :param send_buffer_notification_ip_address: The IP address of the host\
                that will send new buffers (must be specified if a send buffer\
                is specified)
        :param send_buffer_notification_port: The port that the host that will\
                send new buffers is listening on (must be specified if a\
                send buffer is specified)
        :param send_buffer_notification_tag: The IP tag to use to notify the\
                host about space in the buffer (default is to use any tag)
        """

        AbstractDataSpecableVertex.__init__(
            self, machine_time_step, timescale_factor)
        AbstractPartitionableVertex.__init__(
            self, n_keys, label, max_atoms_per_core, constraints)

        # Store the parameters
        self._board_address = board_address
        self._receive_port = receive_port
        self._receive_sdp_port = receive_sdp_port
        self._receive_tag = receive_tag
        self._virtual_key = virtual_key
        self._prefix = prefix
        self._prefix_type = prefix_type
        self._check_keys = check_keys
        self._send_buffer_times = send_buffer_times
        self._send_buffer_max_space = send_buffer_max_space
        self._send_buffer_space_before_notify = send_buffer_space_before_notify
        self._send_buffer_notification_ip_address = \
            send_buffer_notification_ip_address
        self._send_buffer_notification_port = send_buffer_notification_port
        self._send_buffer_notification_tag = send_buffer_notification_tag

        # Store recording parameters for later
        self._record_buffering_ip_address = None
        self._record_buffering_port = None
        self._record_buffering_board_address = None
        self._record_buffering_tag = None
        self._record_buffer_size = 0
        self._record_buffer_size_before_receive = 0

    def enable_recording(
            self, buffering_ip_address, buffering_port,
            board_address=None, notification_tag=None,
            record_buffer_size=constants.MAX_SIZE_OF_BUFFERED_REGION_ON_CHIP,
            buffer_size_before_receive=(constants.
                                        DEFAULT_BUFFER_SIZE_BEFORE_RECEIVE)):
        self._record_buffering_ip_address = buffering_ip_address
        self._record_buffering_port = buffering_port
        self._record_buffering_board_address = board_address
        self._record_buffering_tag = notification_tag
        self._record_buffer_size = record_buffer_size
        self._record_buffer_size_before_receive = buffer_size_before_receive

    def get_outgoing_edge_constraints(self, partitioned_edge, graph_mapper):
        return partitioned_edge.pre_subvertex.get_outgoing_edge_constraints(
            partitioned_edge, graph_mapper)

    def get_sdram_usage_for_atoms(self, vertex_slice, graph):
        send_buffer_size = 0
        if self._send_buffer_times is not None:
            send_buffer_size = self._send_buffer_max_space

        recording_size = (ReverseIPTagMulticastSourcePartitionedVertex
                          .get_recording_data_size(1))
        if self._record_buffer_size > 0:
            recording_size += self._record_buffer_size
            recording_size += (ReverseIPTagMulticastSourcePartitionedVertex.
                               get_buffer_state_region_size(1))
        return ((constants.DATA_SPECABLE_BASIC_SETUP_INFO_N_WORDS * 4) +
                (ReverseIPTagMulticastSourcePartitionedVertex.
                 _CONFIGURATION_REGION_SIZE) + send_buffer_size +
                recording_size)

    @property
    def model_name(self):
        return "ReverseIpTagMultiCastSource"

    def is_reverse_ip_tagable_vertex(self):
        return True

    def get_dtcm_usage_for_atoms(self, vertex_slice, graph):
        return 1

    def get_binary_file_name(self):
        return 'reverse_iptag_multicast_source.aplx'

    def get_cpu_usage_for_atoms(self, vertex_slice, graph):
        return 1

    def generate_data_spec(
            self, subvertex, placement, sub_graph, graph, routing_info,
            hostname, graph_mapper, report_folder, ip_tags, reverse_ip_tags,
            write_text_specs, application_run_time_folder):

        return subvertex.generate_data_spec(
            subvertex, placement, sub_graph, graph, routing_info,
            hostname, graph_mapper, report_folder, ip_tags, reverse_ip_tags,
            write_text_specs, application_run_time_folder)

    def create_subvertex(self, vertex_slice, resources_required, label=None,
                         constraints=None):
        send_buffer_times = None
        if self._send_buffer_times is not None:
            if hasattr(self._send_buffer_times[0], "__len__"):
                send_buffer_times = self._send_buffer_times[
                    vertex_slice.lo_atom:vertex_slice.hi_atom + 1]
            else:
                send_buffer_times = self._send_buffer_times
        subvertex = ReverseIPTagMulticastSourcePartitionedVertex(
            n_keys=self.n_atoms, resources_required=resources_required,
            machine_time_step=self._machine_time_step,
            timescale_factor=self._timescale_factor, label=label,
            constraints=constraints,
            board_address=self._board_address,
            receive_port=self._receive_port,
            receive_sdp_port=self._receive_sdp_port,
            receive_tag=self._receive_tag,
            virtual_key=self._virtual_key, prefix=self._prefix,
            prefix_type=self._prefix_type, check_keys=self._check_keys,
            send_buffer_times=send_buffer_times,
            send_buffer_max_space=self._send_buffer_max_space,
            send_buffer_space_before_notify=(
                self._send_buffer_space_before_notify),
            send_buffer_notification_ip_address=(
                self._send_buffer_notification_ip_address),
            send_buffer_notification_port=self._send_buffer_notification_port,
            send_buffer_notification_tag=self._send_buffer_notification_tag)
        subvertex.set_no_machine_time_steps(self._no_machine_time_steps)
        if self._record_buffer_size > 0:
            subvertex.enable_recording(
                self._record_buffering_ip_address, self._record_buffering_port,
                self._record_buffering_board_address,
                self._record_buffering_tag, self._record_buffer_size,
                self._record_buffer_size_before_receive)
        return subvertex

    def is_data_specable(self):
        return True

# pacman imports
from pacman.model.decorators.overrides import overrides
from pacman.model.graphs.application import ApplicationVertex
from pacman.model.resources import CPUCyclesPerTickResource, DTCMResource
from pacman.model.resources import ResourceContainer, SDRAMResource
from pacman.model.resources import ReverseIPtagResource, IPtagResource
from pacman.model.constraints.placer_constraints import PlacerBoardConstraint


# front end common imports
from spinn_front_end_common.abstract_models.\
    abstract_provides_outgoing_partition_constraints \
    import AbstractProvidesOutgoingPartitionConstraints
from spinn_front_end_common.abstract_models.impl\
    .provides_key_to_atom_mapping_impl import ProvidesKeyToAtomMappingImpl
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utility_models\
    .reverse_ip_tag_multicast_source_machine_vertex \
    import ReverseIPTagMulticastSourceMachineVertex
from spinn_front_end_common.abstract_models\
    .abstract_generates_data_specification \
    import AbstractGeneratesDataSpecification
from spinn_front_end_common.interface.buffer_management \
    import recording_utilities
from spinn_front_end_common.abstract_models.abstract_has_associated_binary \
    import AbstractHasAssociatedBinary
from spinn_front_end_common.utilities.utility_objs.executable_start_type \
    import ExecutableStartType

# general imports
import sys


class ReverseIpTagMultiCastSource(
        ApplicationVertex, AbstractGeneratesDataSpecification,
        AbstractHasAssociatedBinary,
        AbstractProvidesOutgoingPartitionConstraints,
        ProvidesKeyToAtomMappingImpl):
    """ A model which will allow events to be injected into a spinnaker\
        machine and converted into multicast packets.
    """

    def __init__(
            self, n_keys, label=None, constraints=None,
            max_atoms_per_core=sys.maxint,

            # General parameters
            board_address=None,

            # Live input parameters
            receive_port=None,
            receive_sdp_port=(
                constants.SDP_PORTS.INPUT_BUFFERING_SDP_PORT.value),
            receive_tag=None,
            receive_rate=10,

            # Key parameters
            virtual_key=None, prefix=None,
            prefix_type=None, check_keys=False,

            # Send buffer parameters
            send_buffer_times=None,
            send_buffer_partition_id=None,
            send_buffer_max_space=(
                constants.MAX_SIZE_OF_BUFFERED_REGION_ON_CHIP),
            send_buffer_space_before_notify=640,

            # Buffer parameters
            buffer_notification_ip_address=None,
            buffer_notification_port=None,
            buffer_notification_tag=None,

            # Extra flag for input without a reserved port
            reserve_reverse_ip_tag=False):
        """

        :param n_keys: The number of keys to be sent via this multicast source
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
        :param receive_rate: The estimated rate of packets that will be sent\
                by this source
        :param virtual_key: The base multicast key to send received events\
                with (assigned automatically by default)
        :param prefix: The prefix to "or" with generated multicast keys\
                (default is no prefix)
        :param prefix_type: Whether the prefix should apply to the upper or\
                lower half of the multicast keys (default is upper half)
        :param check_keys: True if the keys of received events should be\
                verified before sending (default False)
        :param send_buffer_times: An array of arrays of times at which keys\
                should be sent (one array for each key, default disabled)
        :param send_buffer_partition_id: The id of the partition containing\
                the edges down which the events are to be sent
        :param send_buffer_max_space: The maximum amount of space to use of\
                the SDRAM on the machine (default is 1MB)
        :param send_buffer_space_before_notify: The amount of space free in\
                the sending buffer before the machine will ask the host for\
                more data (default setting is optimised for most cases)
        :param buffer_notification_ip_address: The IP address of the host\
                that will send new buffers (must be specified if a send buffer\
                is specified or if recording will be used)
        :param buffer_notification_port: The port that the host that will\
                send new buffers is listening on (must be specified if a\
                send buffer is specified, or if recording will be used)
        :param buffer_notification_tag: The IP tag to use to notify the\
                host about space in the buffer (default is to use any tag)
        """
        ApplicationVertex.__init__(
            self, label, constraints, max_atoms_per_core)
        ProvidesKeyToAtomMappingImpl.__init__(self)

        # basic items
        self._n_atoms = n_keys

        # Store the parameters for EIEIO
        self._board_address = board_address
        self._receive_port = receive_port
        self._receive_sdp_port = receive_sdp_port
        self._receive_tag = receive_tag
        self._receive_rate = receive_rate
        self._virtual_key = virtual_key
        self._prefix = prefix
        self._prefix_type = prefix_type
        self._check_keys = check_keys

        self._reverse_iptags = None
        if receive_port is not None or reserve_reverse_ip_tag:
            self._reverse_iptags = [ReverseIPtagResource(
                port=receive_port, sdp_port=receive_sdp_port,
                tag=receive_tag)]
            if board_address is not None:
                self.add_constraint(PlacerBoardConstraint(board_address))

        # Store the send buffering details
        self._send_buffer_times = send_buffer_times
        self._send_buffer_partition_id = send_buffer_partition_id
        self._send_buffer_max_space = send_buffer_max_space
        self._send_buffer_space_before_notify = send_buffer_space_before_notify

        # Store the buffering details
        self._buffer_notification_ip_address = buffer_notification_ip_address
        self._buffer_notification_port = buffer_notification_port
        self._buffer_notification_tag = buffer_notification_tag
        self._reserve_reverse_ip_tag = reserve_reverse_ip_tag

        self._iptags = None
        if send_buffer_times is not None:
            self._iptags = [IPtagResource(
                buffer_notification_ip_address, buffer_notification_port, True,
                buffer_notification_tag)]
            if board_address is not None:
                self.add_constraint(PlacerBoardConstraint(board_address))

        # Store recording parameters
        self._record_buffer_size = 0
        self._record_buffer_size_before_receive = 0
        self._record_time_between_requests = 0

        # Keep the vertices for resuming runs
        self._machine_vertices = list()

    @property
    @overrides(ApplicationVertex.n_atoms)
    def n_atoms(self):
        return self._n_atoms

    @overrides(ApplicationVertex.get_resources_used_by_atoms)
    def get_resources_used_by_atoms(self, vertex_slice):
        container = ResourceContainer(
            sdram=SDRAMResource(
                ReverseIPTagMulticastSourceMachineVertex.get_sdram_usage(
                    self._send_buffer_times, self._send_buffer_max_space,
                    self._record_buffer_size > 0)),
            dtcm=DTCMResource(
                ReverseIPTagMulticastSourceMachineVertex.get_dtcm_usage()),
            cpu_cycles=CPUCyclesPerTickResource(
                ReverseIPTagMulticastSourceMachineVertex.get_cpu_usage()),
            iptags=self._iptags,
            reverse_iptags=self._reverse_iptags)
        if self._iptags is None:
            container.extend(recording_utilities.get_recording_resources(
                [self._record_buffer_size],
                self._buffer_notification_ip_address,
                self._buffer_notification_port, self._buffer_notification_tag))
        else:
            container.extend(recording_utilities.get_recording_resources(
                [self._record_buffer_size]))
        return container

    @property
    def send_buffer_times(self):
        return self._send_buffer_times

    @send_buffer_times.setter
    def send_buffer_times(self, send_buffer_times):
        self._send_buffer_times = send_buffer_times
        for (vertex_slice, vertex) in self._machine_vertices:
            send_buffer_times_to_set = self._send_buffer_times
            if (self._send_buffer_times is not None and
                    len(self._send_buffer_times) > 0):
                if hasattr(self._send_buffer_times[0], "__len__"):
                    send_buffer_times_to_set = self._send_buffer_times[
                        vertex_slice.lo_atom:vertex_slice.hi_atom + 1]
            vertex.send_buffer_times = send_buffer_times_to_set

    def enable_recording(
            self,
            record_buffer_size=constants.MAX_SIZE_OF_BUFFERED_REGION_ON_CHIP,
            buffer_size_before_receive=(
                constants.DEFAULT_BUFFER_SIZE_BEFORE_RECEIVE),
            time_between_requests=0):
        self._record_buffer_size = record_buffer_size
        self._record_buffer_size_before_receive = buffer_size_before_receive
        self._record_time_between_requests = time_between_requests

    @overrides(AbstractProvidesOutgoingPartitionConstraints.
               get_outgoing_partition_constraints)
    def get_outgoing_partition_constraints(self, partition):
        return partition.pre_vertex.get_outgoing_partition_constraints(
            partition)

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return 'reverse_iptag_multicast_source.aplx'

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return ExecutableStartType.USES_SIMULATION_INTERFACE

    def generate_data_specification(self, spec, placement):
        placement.vertex.generate_data_specification(spec, placement)

    @overrides(ApplicationVertex.create_machine_vertex)
    def create_machine_vertex(
            self, vertex_slice, resources_required, label=None,
            constraints=None):
        send_buffer_times = self._send_buffer_times
        if (self._send_buffer_times is not None and
                len(self._send_buffer_times) > 0):
            if hasattr(self._send_buffer_times[0], "__len__"):
                send_buffer_times = self._send_buffer_times[
                    vertex_slice.lo_atom:vertex_slice.hi_atom + 1]
        vertex = ReverseIPTagMulticastSourceMachineVertex(
            n_keys=vertex_slice.n_atoms,
            label=label, constraints=constraints,
            board_address=self._board_address,
            receive_port=self._receive_port,
            receive_sdp_port=self._receive_sdp_port,
            receive_tag=self._receive_tag,
            receive_rate=self._receive_rate,
            virtual_key=self._virtual_key, prefix=self._prefix,
            prefix_type=self._prefix_type, check_keys=self._check_keys,
            send_buffer_times=send_buffer_times,
            send_buffer_partition_id=self._send_buffer_partition_id,
            send_buffer_max_space=self._send_buffer_max_space,
            send_buffer_space_before_notify=(
                self._send_buffer_space_before_notify),
            buffer_notification_ip_address=(
                self._buffer_notification_ip_address),
            buffer_notification_port=self._buffer_notification_port,
            buffer_notification_tag=self._buffer_notification_tag,
            reserve_reverse_ip_tag=self._reserve_reverse_ip_tag)
        if self._record_buffer_size > 0:
            vertex.enable_recording(
                self._record_buffer_size,
                self._record_buffer_size_before_receive,
                self._record_time_between_requests)
        self._machine_vertices.append((vertex_slice, vertex))
        return vertex

    def __repr__(self):
        return self._label

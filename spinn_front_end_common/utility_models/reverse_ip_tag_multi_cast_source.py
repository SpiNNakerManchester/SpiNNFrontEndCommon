# pacman imports
from pacman.model.decorators.overrides import overrides
from pacman.model.graphs.application.impl.application_vertex import \
    ApplicationVertex
from pacman.model.resources.cpu_cycles_per_tick_resource import \
    CPUCyclesPerTickResource
from pacman.model.resources.dtcm_resource import DTCMResource
from pacman.model.resources.resource_container import ResourceContainer
from pacman.model.resources.sdram_resource import SDRAMResource

# front end common imports
from spinn_front_end_common.abstract_models.\
    abstract_provides_outgoing_partition_constraints \
    import AbstractProvidesOutgoingPartitionConstraints
from spinn_front_end_common.utilities import constants

from spinn_front_end_common.utility_models\
    .reverse_ip_tag_multicast_source_machine_vertex \
    import ReverseIPTagMulticastSourceMachineVertex
from spinn_front_end_common.abstract_models\
    .abstract_generates_data_specification \
    import AbstractGeneratesDataSpecification
from spinn_front_end_common.abstract_models\
    .abstract_binary_uses_simulation_run import AbstractBinaryUsesSimulationRun
from spinn_front_end_common.abstract_models.abstract_has_associated_binary \
    import AbstractHasAssociatedBinary

# general imports
import sys


class ReverseIpTagMultiCastSource(
        ApplicationVertex, AbstractGeneratesDataSpecification,
        AbstractHasAssociatedBinary,
        AbstractProvidesOutgoingPartitionConstraints,
        AbstractBinaryUsesSimulationRun):
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

            # Key parameters
            virtual_key=None, prefix=None,
            prefix_type=None, check_keys=False,

            # Send buffer parameters
            send_buffer_times=None,
            send_buffer_partition_id=None,
            send_buffer_max_space=(
                constants.MAX_SIZE_OF_BUFFERED_REGION_ON_CHIP),
            send_buffer_space_before_notify=640,
            send_buffer_notification_ip_address=None,
            send_buffer_notification_port=None,
            send_buffer_notification_tag=None):
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
        :param send_buffer_notification_ip_address: The IP address of the host\
                that will send new buffers (must be specified if a send buffer\
                is specified)
        :param send_buffer_notification_port: The port that the host that will\
                send new buffers is listening on (must be specified if a\
                send buffer is specified)
        :param send_buffer_notification_tag: The IP tag to use to notify the\
                host about space in the buffer (default is to use any tag)
        """
        ApplicationVertex.__init__(
            self, label, constraints, max_atoms_per_core)

        # basic items
        self._n_atoms = n_keys

        # Store the parameters for EIEIO
        self._board_address = board_address
        self._receive_port = receive_port
        self._receive_sdp_port = receive_sdp_port
        self._receive_tag = receive_tag
        self._virtual_key = virtual_key
        self._prefix = prefix
        self._prefix_type = prefix_type
        self._check_keys = check_keys
        self._send_buffer_times = send_buffer_times
        self._send_buffer_partition_id = send_buffer_partition_id
        self._send_buffer_max_space = send_buffer_max_space
        self._send_buffer_space_before_notify = send_buffer_space_before_notify
        self._send_buffer_notification_ip_address = \
            send_buffer_notification_ip_address
        self._send_buffer_notification_port = send_buffer_notification_port
        self._send_buffer_notification_tag = send_buffer_notification_tag

        # Store recording parameters for later
        self._recording_enabled = False
        self._record_buffering_ip_address = None
        self._record_buffering_port = None
        self._record_buffering_board_address = None
        self._record_buffering_tag = None
        self._record_buffer_size = 0
        self._record_buffer_size_before_receive = 0
        self._minimum_sdram_for_buffering = 0
        self._using_auto_pause_and_resume = False

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
                    self._recording_enabled, self._using_auto_pause_and_resume,
                    self._minimum_sdram_for_buffering,
                    self._record_buffer_size)),
            dtcm=DTCMResource(
                ReverseIPTagMulticastSourceMachineVertex.get_dtcm_usage()),
            cpu_cycles=CPUCyclesPerTickResource(
                ReverseIPTagMulticastSourceMachineVertex.get_cpu_usage()))
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
            self, buffering_ip_address, buffering_port,
            board_address=None, notification_tag=None,
            record_buffer_size=constants.MAX_SIZE_OF_BUFFERED_REGION_ON_CHIP,
            buffer_size_before_receive=(
                constants.DEFAULT_BUFFER_SIZE_BEFORE_RECEIVE),
            minimum_sdram_for_buffering=0,
            using_auto_pause_and_resume=False):
        self._recording_enabled = True
        self._record_buffering_ip_address = buffering_ip_address
        self._record_buffering_port = buffering_port
        self._record_buffering_board_address = board_address
        self._record_buffering_tag = notification_tag
        self._record_buffer_size = record_buffer_size
        self._record_buffer_size_before_receive = buffer_size_before_receive
        self._minimum_sdram_for_buffering = minimum_sdram_for_buffering
        self._using_auto_pause_and_resume = using_auto_pause_and_resume

    @overrides(AbstractProvidesOutgoingPartitionConstraints.
               get_outgoing_partition_constraints)
    def get_outgoing_partition_constraints(self, partition):
        return partition.edges[0].pre_vertex.\
            get_outgoing_partition_constraints(partition)

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return 'reverse_iptag_multicast_source.aplx'

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
            virtual_key=self._virtual_key, prefix=self._prefix,
            prefix_type=self._prefix_type, check_keys=self._check_keys,
            send_buffer_times=send_buffer_times,
            send_buffer_partition_id=self._send_buffer_partition_id,
            send_buffer_max_space=self._send_buffer_max_space,
            send_buffer_space_before_notify=(
                self._send_buffer_space_before_notify),
            send_buffer_notification_ip_address=(
                self._send_buffer_notification_ip_address),
            send_buffer_notification_port=self._send_buffer_notification_port,
            send_buffer_notification_tag=self._send_buffer_notification_tag)
        if self._record_buffer_size > 0:
            sdram_per_ts = 0
            if self._using_auto_pause_and_resume:

                # Currently not known how much SDRAM might be used per
                # timestep by this object, so we assume a minimum value here
                sdram_per_ts = 8

            vertex.enable_recording(
                self._record_buffering_ip_address, self._record_buffering_port,
                self._record_buffering_board_address,
                self._record_buffering_tag, self._record_buffer_size,
                self._record_buffer_size_before_receive,
                self._minimum_sdram_for_buffering, sdram_per_ts)
        self._machine_vertices.append((vertex_slice, vertex))
        return vertex

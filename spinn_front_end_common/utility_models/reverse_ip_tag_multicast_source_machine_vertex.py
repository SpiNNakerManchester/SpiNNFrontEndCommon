from pacman.executor.injection_decorator import inject_items
from pacman.executor.injection_decorator import supports_injection
from pacman.executor.injection_decorator import inject
from pacman.model.decorators.overrides import overrides
from pacman.model.constraints.key_allocator_constraints \
    import KeyAllocatorFixedKeyAndMaskConstraint
from pacman.model.constraints.placer_constraints import PlacerBoardConstraint
from pacman.model.resources import IPtagResource, ReverseIPtagResource
from pacman.model.resources import ResourceContainer, DTCMResource
from pacman.model.resources import SDRAMResource, CPUCyclesPerTickResource
from pacman.model.routing_info import BaseKeyAndMask
from pacman.model.graphs.machine import MachineVertex

from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.interface.buffer_management.buffer_manager \
    import BufferManager
from spinn_front_end_common.interface.buffer_management.buffer_models\
    .sends_buffers_from_host_pre_buffered_impl \
    import SendsBuffersFromHostPreBufferedImpl
from spinn_front_end_common.interface.buffer_management.storage_objects\
    .buffered_sending_region import BufferedSendingRegion
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.interface.buffer_management.buffer_models\
    .abstract_receive_buffers_to_host import AbstractReceiveBuffersToHost
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.abstract_models\
    .abstract_provides_outgoing_partition_constraints \
    import AbstractProvidesOutgoingPartitionConstraints
from spinn_front_end_common.interface.simulation import simulation_utilities
from spinn_front_end_common.abstract_models\
    .abstract_generates_data_specification \
    import AbstractGeneratesDataSpecification
from spinn_front_end_common.abstract_models.abstract_has_associated_binary \
    import AbstractHasAssociatedBinary
from spinn_front_end_common.abstract_models.abstract_recordable \
    import AbstractRecordable
from spinn_front_end_common.interface.provenance\
    .provides_provenance_data_from_machine_impl import \
    ProvidesProvenanceDataFromMachineImpl
from spinn_front_end_common.interface.buffer_management\
    import recording_utilities
from spinn_front_end_common.utilities.utility_objs.provenance_data_item \
    import ProvenanceDataItem
from spinn_front_end_common.utilities.utility_objs.executable_start_type \
    import ExecutableStartType

from spinnman.messages.eieio.eieio_prefix import EIEIOPrefix

from enum import Enum
import math
import sys
import struct

_DEFAULT_MALLOC_REGIONS = 2


@supports_injection
class ReverseIPTagMulticastSourceMachineVertex(
        MachineVertex, AbstractGeneratesDataSpecification,
        AbstractHasAssociatedBinary,
        ProvidesProvenanceDataFromMachineImpl,
        AbstractProvidesOutgoingPartitionConstraints,
        SendsBuffersFromHostPreBufferedImpl,
        AbstractReceiveBuffersToHost, AbstractRecordable):
    """ A model which allows events to be injected into spinnaker and\
        converted in to multicast packets
    """

    _REGIONS = Enum(
        value="_REGIONS",
        names=[('SYSTEM', 0),
               ('CONFIGURATION', 1),
               ('RECORDING', 2),
               ('SEND_BUFFER', 3),
               ('PROVENANCE_REGION', 4)])

    _PROVENANCE_ITEMS = Enum(
        value="_PROVENANCE_ITEMS",
        names=[("N_RECEIVED_PACKETS", 0),
               ("N_SENT_PACKETS", 1),
               ("INCORRECT_KEYS", 2),
               ("INCORRECT_PACKETS", 3),
               ("LATE_PACKETS", 4)])

    # 12 ints (1. has prefix, 2. prefix, 3. prefix type, 4. check key flag,
    #          5. has key, 6. key, 7. mask, 8. buffer space,
    #          9. send buffer flag before notify, 10. tag,
    #          11. tag destination (y, x), 12. receive SDP port)
    _CONFIGURATION_REGION_SIZE = 12 * 4

    def __init__(
            self, n_keys, label, constraints=None,

            # General input and output parameters
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

            # Buffer notification details
            buffer_notification_ip_address=None,
            buffer_notification_port=None,
            buffer_notification_tag=None,

            # Extra flag for receiving packets without a port
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
        :param send_buffer_max_space: The maximum amount of space to use of\
                the SDRAM on the machine (default is 1MB)
        :param send_buffer_space_before_notify: The amount of space free in\
                the sending buffer before the machine will ask the host for\
                more data (default setting is optimised for most cases)
        :param buffer_notification_ip_address: The IP address of the host\
                that will send new buffers (must be specified if a send buffer\
                is specified)
        :param buffer_notification_port: The port that the host that will\
                send new buffers is listening on (must be specified if a\
                send buffer is specified)
        :param buffer_notification_tag: The IP tag to use to notify the\
                host about space in the buffer (default is to use any tag)
        """
        MachineVertex.__init__(self, label, constraints)
        AbstractReceiveBuffersToHost.__init__(self)

        AbstractProvidesOutgoingPartitionConstraints.__init__(self)

        self._iptags = None
        self._reverse_iptags = None

        # Set up for receiving live packets
        if receive_port is not None or reserve_reverse_ip_tag:
            self._reverse_iptags = [ReverseIPtagResource(
                port=receive_port, sdp_port=receive_sdp_port,
                tag=receive_tag)]
            if board_address is not None:
                self.add_constraint(PlacerBoardConstraint(board_address))
        self._receive_rate = receive_rate
        self._receive_sdp_port = receive_sdp_port

        # Work out if buffers are being sent
        self._send_buffer = None
        self._send_buffer_partition_id = send_buffer_partition_id
        if send_buffer_times is None:
            self._send_buffer_times = None
            self._send_buffer_max_space = send_buffer_max_space
            self._send_buffers = None
        else:
            self._send_buffer_max_space = send_buffer_max_space
            self._send_buffer = BufferedSendingRegion(send_buffer_max_space)
            self._send_buffer_times = send_buffer_times

            self._iptags = [IPtagResource(
                ip_address=buffer_notification_ip_address,
                port=buffer_notification_port, strip_sdp=True,
                tag=buffer_notification_tag,
                traffic_identifier=BufferManager.TRAFFIC_IDENTIFIER)]
            if board_address is not None:
                self.add_constraint(PlacerBoardConstraint(board_address))
            self._send_buffers = {
                self._REGIONS.SEND_BUFFER.value:
                self._send_buffer
            }

        # buffered out parameters
        self._send_buffer_space_before_notify = send_buffer_space_before_notify
        if self._send_buffer_space_before_notify > send_buffer_max_space:
            self._send_buffer_space_before_notify = send_buffer_max_space

        # Set up for recording (if requested)
        self._record_buffer_size = 0
        self._buffer_size_before_receive = 0
        self._time_between_triggers = 0
        self._maximum_recording_buffer = 0

        # Set up for buffering
        self._buffer_notification_ip_address = buffer_notification_ip_address
        self._buffer_notification_port = buffer_notification_port
        self._buffer_notification_tag = buffer_notification_tag

        # set flag for checking if in injection mode
        self._in_injection_mode = receive_port is not None

        # Sort out the keys to be used
        self._n_keys = n_keys
        self._virtual_key = virtual_key
        self._mask = None
        self._prefix = prefix
        self._prefix_type = prefix_type
        self._check_keys = check_keys

        # Work out the prefix details
        if self._prefix is not None:
            if self._prefix_type is None:
                self._prefix_type = EIEIOPrefix.UPPER_HALF_WORD
            if self._prefix_type == EIEIOPrefix.UPPER_HALF_WORD:
                self._prefix = prefix << 16

        # If the user has specified a virtual key
        if self._virtual_key is not None:

            # check that virtual key is valid
            if self._virtual_key < 0:
                raise ConfigurationException(
                    "Virtual keys must be positive")

            # Get a mask and maximum number of keys for the number of keys
            # requested
            self._mask, max_key = self._calculate_mask(n_keys)

            # Check that the number of keys and the virtual key don't interfere
            if n_keys > max_key:
                raise ConfigurationException(
                    "The mask calculated from the number of keys will "
                    "not work with the virtual key specified")

            if self._prefix is not None:

                # Check that the prefix doesn't change the virtual key in the
                # masked area
                masked_key = (self._virtual_key | self._prefix) & self._mask
                if self._virtual_key != masked_key:
                    raise ConfigurationException(
                        "The number of keys, virtual key and key prefix"
                        " settings don't work together")
            else:

                # If no prefix was generated, generate one
                self._prefix_type = EIEIOPrefix.UPPER_HALF_WORD
                self._prefix = self._virtual_key

    @property
    @overrides(ProvidesProvenanceDataFromMachineImpl._provenance_region_id)
    def _provenance_region_id(self):
        return self._REGIONS.PROVENANCE_REGION.value

    @property
    @overrides(ProvidesProvenanceDataFromMachineImpl._n_additional_data_items)
    def _n_additional_data_items(self):
        return 5

    @property
    @overrides(MachineVertex.resources_required)
    def resources_required(self):
        resources = ResourceContainer(
            dtcm=DTCMResource(self.get_dtcm_usage()),
            sdram=SDRAMResource(self.get_sdram_usage(
                self._send_buffer_times, self._send_buffer_max_space,
                self._record_buffer_size > 0)),
            cpu_cycles=CPUCyclesPerTickResource(self.get_cpu_usage()),
            iptags=self._iptags,
            reverse_iptags=self._reverse_iptags)
        if self._iptags is None:
            resources.extend(recording_utilities.get_recording_resources(
                [self._record_buffer_size],
                self._buffer_notification_ip_address,
                self._buffer_notification_port, self._buffer_notification_tag))
        else:
            resources.extend(recording_utilities.get_recording_resources(
                [self._record_buffer_size]))
        return resources

    @staticmethod
    def get_sdram_usage(
            send_buffer_times, send_buffer_max_space, recording_enabled):
        send_buffer_size = 0
        if send_buffer_times is not None:
            send_buffer_size = send_buffer_max_space

        mallocs = \
            ReverseIPTagMulticastSourceMachineVertex.n_regions_to_allocate(
                send_buffer_times is not None, recording_enabled)
        allocation_size = mallocs * constants.SARK_PER_MALLOC_SDRAM_USAGE

        return (
            constants.SYSTEM_BYTES_REQUIREMENT +
            (ReverseIPTagMulticastSourceMachineVertex.
                _CONFIGURATION_REGION_SIZE) +
            send_buffer_size + allocation_size +
            (ReverseIPTagMulticastSourceMachineVertex.
                get_provenance_data_size(0)))

    @staticmethod
    def get_dtcm_usage():
        return 1

    @staticmethod
    def get_cpu_usage():
        return 1

    @staticmethod
    def n_regions_to_allocate(send_buffering, recording):
        """ Get the number of regions that will be allocated
        """
        if recording and send_buffering:
            return 5
        elif recording or send_buffering:
            return 4
        return 3

    @property
    def send_buffer_times(self):
        return self._send_buffer_times

    @send_buffer_times.setter
    def send_buffer_times(self, send_buffer_times):
        self._send_buffer_times = send_buffer_times

    def _is_in_range(
            self, time_stamp_in_ticks,
            first_machine_time_step, n_machine_time_steps):
        return (
            (n_machine_time_steps is None) or (
                first_machine_time_step <= time_stamp_in_ticks <
                n_machine_time_steps))

    def _fill_send_buffer(
            self, machine_time_step, first_machine_time_step,
            n_machine_time_steps):
        """ Fill the send buffer with keys to send
        """

        key_to_send = self._virtual_key
        if self._virtual_key is None:
            key_to_send = 0

        if self._send_buffer is not None:
            self._send_buffer.clear()
        if (self._send_buffer_times is not None and
                len(self._send_buffer_times) != 0):
            if hasattr(self._send_buffer_times[0], "__len__"):

                # Works with a list-of-lists
                for key in range(self._n_keys):
                    for timeStamp in sorted(self._send_buffer_times[key]):
                        time_stamp_in_ticks = int(math.ceil(
                            float(int(timeStamp * 1000.0)) /
                            machine_time_step))
                        if self._is_in_range(
                                time_stamp_in_ticks, first_machine_time_step,
                                n_machine_time_steps):
                            self._send_buffer.add_key(
                                time_stamp_in_ticks, key_to_send + key)
            else:

                # Work with a single list
                key_list = [
                    key + key_to_send for key in range(self._n_keys)]
                for timeStamp in sorted(self._send_buffer_times):
                    time_stamp_in_ticks = int(math.ceil(
                        float(int(timeStamp * 1000.0)) /
                        machine_time_step))

                    # add to send_buffer collection
                    if self._is_in_range(
                            time_stamp_in_ticks, first_machine_time_step,
                            n_machine_time_steps):
                        self._send_buffer.add_keys(
                            time_stamp_in_ticks, key_list)

    @staticmethod
    def _generate_prefix(virtual_key, prefix_type):
        if prefix_type == EIEIOPrefix.LOWER_HALF_WORD:
            return virtual_key & 0xFFFF
        return (virtual_key >> 16) & 0xFFFF

    @staticmethod
    def _calculate_mask(n_neurons):
        if n_neurons == 1:
            return 0xFFFFFFFF, 1
        temp_value = int(math.ceil(math.log(n_neurons, 2)))
        max_key = (int(math.pow(2, temp_value)) - 1)
        mask = 0xFFFFFFFF - max_key
        return mask, max_key

    def enable_recording(
            self,
            record_buffer_size=constants.MAX_SIZE_OF_BUFFERED_REGION_ON_CHIP,
            buffer_size_before_receive=(
                constants.DEFAULT_BUFFER_SIZE_BEFORE_RECEIVE),
            time_between_triggers=0):
        """ Enable recording of the keys sent

        :param record_buffer_size:\
            The size of the recording buffer in bytes.  Note that when using\
            automatic pause and resume, this will be used as the minimum size\
            of the buffer
        :type record_buffer_size: int
        :param buffer_size_before_receive:\
            The size that the buffer can grow to before a read request is\
            issued to the host (in bytes)
        :type buffer_size_before_receive: int
        :param time_between_triggers:\
            The minimum time between the sending of read requests
        :type time_between_triggers: int
        """
        self._record_buffer_size = record_buffer_size
        self._buffer_size_before_receive = buffer_size_before_receive
        self._time_between_triggers = time_between_triggers

    def _reserve_regions(self, spec):

        # Reserve system and configuration memory regions:
        spec.reserve_memory_region(
            region=self._REGIONS.SYSTEM.value,
            size=constants.SYSTEM_BYTES_REQUIREMENT, label='SYSTEM')
        spec.reserve_memory_region(
            region=self._REGIONS.CONFIGURATION.value,
            size=self._CONFIGURATION_REGION_SIZE, label='CONFIGURATION')

        # Reserve recording buffer regions if required
        spec.reserve_memory_region(
            region=self._REGIONS.RECORDING.value,
            size=recording_utilities.get_recording_header_size(1),
            label="RECORDING")

        # Reserve send buffer region if required
        if self._send_buffer_times is not None:
            max_buffer_size = self.get_max_buffer_size_possible(
                self._REGIONS.SEND_BUFFER.value)
            spec.reserve_memory_region(
                region=self._REGIONS.SEND_BUFFER.value,
                size=max_buffer_size, label="SEND_BUFFER", empty=True)

        self.reserve_provenance_data_region(spec)

    def _update_virtual_key(self, routing_info, machine_graph):
        if self._virtual_key is None:
            if self._send_buffer_partition_id is not None:

                rinfo = routing_info.get_routing_info_from_pre_vertex(
                    self, self._send_buffer_partition_id)
                self._virtual_key = rinfo.first_key
                self._mask = rinfo.first_mask

            else:
                partitions = machine_graph\
                    .get_outgoing_edge_partitions_starting_at_vertex(self)
                partition = next(iter(partitions), None)

                if partition is not None:
                    rinfo = routing_info.get_routing_info_from_partition(
                        partition)
                    self._virtual_key = rinfo.first_key
                    self._mask = rinfo.first_mask

        if self._virtual_key is not None and self._prefix is None:
            self._prefix_type = EIEIOPrefix.UPPER_HALF_WORD
            self._prefix = self._virtual_key

    def _write_configuration(self, spec, ip_tags):
        spec.switch_write_focus(region=self._REGIONS.CONFIGURATION.value)

        # Write apply_prefix and prefix and prefix_type
        if self._prefix is None:
            spec.write_value(data=0)
            spec.write_value(data=0)
            spec.write_value(data=0)
        else:
            spec.write_value(data=1)
            spec.write_value(data=self._prefix)
            spec.write_value(data=self._prefix_type.value)

        # Write check
        if self._check_keys:
            spec.write_value(data=1)
        else:
            spec.write_value(data=0)

        # Write if you have a key to transmit write it and the mask,
        # otherwise write flags to fill in space
        if self._virtual_key is None:
            spec.write_value(data=0)
            spec.write_value(data=0)
            spec.write_value(data=0)
        else:
            spec.write_value(data=1)
            spec.write_value(data=self._virtual_key)
            spec.write_value(data=self._mask)

        # Write send buffer data
        if self._send_buffer_times is not None:

            this_tag = None

            for tag in ip_tags:
                if tag.traffic_identifier == BufferManager.TRAFFIC_IDENTIFIER:
                    this_tag = tag
                    break
            if this_tag is None:
                raise Exception("Could not find tag for send buffering")

            buffer_space = self.get_max_buffer_size_possible(
                self._REGIONS.SEND_BUFFER.value)

            spec.write_value(data=buffer_space)
            spec.write_value(data=self._send_buffer_space_before_notify)
            spec.write_value(data=this_tag.tag)
            spec.write_value(struct.unpack("<I", struct.pack(
                "<HH", this_tag.destination_y, this_tag.destination_x))[0])
        else:
            spec.write_value(data=0)
            spec.write_value(data=0)
            spec.write_value(data=0)
            spec.write_value(data=0)

        # write SDP port to which SDP packets will be received
        spec.write_value(data=self._receive_sdp_port)

    @inject_items({
        "machine_time_step": "MachineTimeStep",
        "time_scale_factor": "TimeScaleFactor",
        "machine_graph": "MemoryMachineGraph",
        "routing_info": "MemoryRoutingInfos",
        "tags": "MemoryTags",
        "first_machine_time_step": "FirstMachineTimeStep",
        "n_machine_time_steps": "TotalMachineTimeSteps"
    })
    @overrides(
        AbstractGeneratesDataSpecification.generate_data_specification,
        additional_arguments={
            "machine_time_step", "time_scale_factor", "machine_graph",
            "routing_info", "tags", "first_machine_time_step",
            "n_machine_time_steps"
        })
    def generate_data_specification(
            self, spec, placement, machine_time_step, time_scale_factor,
            machine_graph, routing_info, tags, first_machine_time_step,
            n_machine_time_steps):

        self._update_virtual_key(routing_info, machine_graph)
        self._fill_send_buffer(
            machine_time_step, first_machine_time_step, n_machine_time_steps)

        # Reserve regions
        self._reserve_regions(spec)

        # Write the system region
        spec.switch_write_focus(self._REGIONS.SYSTEM.value)
        spec.write_array(simulation_utilities.get_simulation_header_array(
            self.get_binary_file_name(), machine_time_step,
            time_scale_factor))

        # Write the additional recording information
        iptags = tags.get_ip_tags_for_vertex(self)
        spec.switch_write_focus(self._REGIONS.RECORDING.value)
        spec.write_array(recording_utilities.get_recording_header_array(
            [self._record_buffer_size],
            self._time_between_triggers, self._buffer_size_before_receive,
            iptags, self._buffer_notification_tag))

        # Write the configuration information
        self._write_configuration(spec, iptags)

        # End spec
        spec.end_specification()

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return "reverse_iptag_multicast_source.aplx"

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return ExecutableStartType.USES_SIMULATION_INTERFACE

    @overrides(AbstractProvidesOutgoingPartitionConstraints.
               get_outgoing_partition_constraints)
    def get_outgoing_partition_constraints(self, partition):
        if self._virtual_key is not None:
            return list([KeyAllocatorFixedKeyAndMaskConstraint(
                [BaseKeyAndMask(self._virtual_key, self._mask)])])
        return list()

    @property
    def virtual_key(self):
        return self._virtual_key

    @property
    def mask(self):
        return self._mask

    @property
    def is_in_injection_mode(self):
        return self._in_injection_mode

    @overrides(AbstractRecordable.is_recording)
    def is_recording(self):
        return self._record_buffer_size > 0

    @inject("FirstMachineTimeStep")
    @inject_items({
        "machine_time_step": "MachineTimeStep",
        "n_machine_time_steps": "TotalMachineTimeSteps"
    })
    def update_buffer(
            self, first_machine_time_step, machine_time_step,
            n_machine_time_steps):
        self._fill_send_buffer(
            machine_time_step, first_machine_time_step, n_machine_time_steps)

    @overrides(AbstractReceiveBuffersToHost.get_minimum_buffer_sdram_usage)
    def get_minimum_buffer_sdram_usage(self):
        return self._record_buffer_size

    @overrides(AbstractReceiveBuffersToHost.get_n_timesteps_in_buffer_space)
    def get_n_timesteps_in_buffer_space(self, buffer_space, machine_time_step):

        # If not recording, not an issue
        if self._record_buffer_size == 0:
            return sys.maxint

        # If recording and using pre-defined keys, use the maximum
        if self._send_buffer is not None:
            return recording_utilities.get_n_timesteps_in_buffer_space(
                buffer_space, [self._send_buffer.max_packets_in_timestamp])

        # If recording and not using pre-defined keys, use the specified
        # rate to work it out - add 10% for safety
        keys_per_timestep = math.ceil(
            (self._receive_rate / (machine_time_step * 1000.0)) * 1.1
        )

        # 4 bytes per key + 2 byte header + 4 byte timestamp
        bytes_per_timestep = (keys_per_timestep * 4) + 6
        return recording_utilities.get_n_timesteps_in_buffer_space(
            buffer_space, [bytes_per_timestep])

    @overrides(AbstractReceiveBuffersToHost.get_recorded_region_ids)
    def get_recorded_region_ids(self):
        return recording_utilities.get_recorded_region_ids(
            [self._record_buffer_size])

    @overrides(AbstractReceiveBuffersToHost.get_recording_region_base_address)
    def get_recording_region_base_address(self, txrx, placement):
        return helpful_functions.locate_memory_region_for_placement(
            placement, self._REGIONS.RECORDING.value, txrx)

    @property
    def send_buffers(self):
        return self._send_buffers

    @send_buffers.setter
    def send_buffers(self, value):
        self._send_buffers = value

    @overrides(ProvidesProvenanceDataFromMachineImpl.
               get_provenance_data_from_machine)
    def get_provenance_data_from_machine(self, transceiver, placement):
        provenance_data = self._read_provenance_data(transceiver, placement)
        provenance_items = self._read_basic_provenance_items(
            provenance_data, placement)
        provenance_data = self._get_remaining_provenance_data_items(
            provenance_data)
        _, _, _, _, names = self._get_placement_details(placement)

        provenance_items.append(ProvenanceDataItem(
            self._add_name(names, "received_sdp_packets"),
            provenance_data[self._PROVENANCE_ITEMS.N_RECEIVED_PACKETS.value],
            report=(
                provenance_data[
                    self._PROVENANCE_ITEMS.N_RECEIVED_PACKETS.value] == 0 and
                self._send_buffer_times is None),
            message=(
                "No SDP packets were received by {}.  If you expected packets"
                " to be injected, this could indicate an error".format(
                    self._label))))
        provenance_items.append(ProvenanceDataItem(
            self._add_name(names, "send_multicast_packets"),
            provenance_data[self._PROVENANCE_ITEMS.N_SENT_PACKETS.value],
            report=provenance_data[
                self._PROVENANCE_ITEMS.N_SENT_PACKETS.value] == 0,
            message=(
                "No multicast packets were sent by {}.  If you expected"
                " packets to be sent this could indicate an error".format(
                    self._label))))
        provenance_items.append(ProvenanceDataItem(
            self._add_name(names, "incorrect_keys"),
            provenance_data[self._PROVENANCE_ITEMS.INCORRECT_KEYS.value],
            report=provenance_data[
                self._PROVENANCE_ITEMS.INCORRECT_KEYS.value] > 0,
            message=(
                "Keys were received by {} that did not match the key {} and"
                " mask {}".format(
                    self._label, self._virtual_key, self._mask))))
        provenance_items.append(ProvenanceDataItem(
            self._add_name(names, "incorrect_packets"),
            provenance_data[self._PROVENANCE_ITEMS.INCORRECT_PACKETS.value],
            report=provenance_data[
                self._PROVENANCE_ITEMS.INCORRECT_PACKETS.value] > 0,
            message=(
                "SDP Packets were received by {} that were not correct".format(
                    self._label))))
        provenance_items.append(ProvenanceDataItem(
            self._add_name(names, "late_packets"),
            provenance_data[self._PROVENANCE_ITEMS.LATE_PACKETS.value],
            report=provenance_data[
                self._PROVENANCE_ITEMS.LATE_PACKETS.value] > 0,
            message=(
                "SDP Packets were received by {} that were too late to be"
                " transmitted in the simulation".format(self._label))))

        return provenance_items

    def __repr__(self):
        return self._label

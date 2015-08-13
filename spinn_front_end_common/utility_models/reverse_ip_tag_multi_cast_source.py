"""
"""

# data spec imports
from data_specification.data_specification_generator import \
    DataSpecificationGenerator

from pacman.model.partitioned_graph.partitioned_vertex import PartitionedVertex
from pacman.model.resources.cpu_cycles_per_tick_resource import \
    CPUCyclesPerTickResource
from pacman.model.resources.dtcm_resource import DTCMResource
from pacman.model.resources.resource_container import ResourceContainer
from pacman.model.resources.sdram_resource import SDRAMResource
from pacman.model.constraints.tag_allocator_constraints\
    .tag_allocator_require_iptag_constraint\
    import TagAllocatorRequireIptagConstraint
from pacman.model.constraints.tag_allocator_constraints \
    .tag_allocator_require_reverse_iptag_constraint \
    import TagAllocatorRequireReverseIptagConstraint
from pacman.model.constraints.placer_constraints\
    .placer_radial_placement_from_chip_constraint \
    import PlacerRadialPlacementFromChipConstraint

# front end common imports
from spinn_front_end_common.utility_models\
    .reverse_ip_tag_multicast_source_partitionable_vertex \
    import ReverseIPTagMulticastSourcePartitionableVertex
from spinn_front_end_common.abstract_models.\
    abstract_provides_outgoing_edge_constraints \
    import AbstractProvidesOutgoingEdgeConstraints
from spinn_front_end_common.abstract_models\
    .abstract_data_specable_partitioned_vertex \
    import AbstractDataSpecablePartitionedVertex
from spinn_front_end_common.interface.has_n_machine_timesteps \
    import HasNMachineTimesteps
from spinn_front_end_common.abstract_models.abstract_executable \
    import AbstractExecutable
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utilities import simulation_utilities
from spinn_front_end_common.utilities import data_spec_utilities

# spinnman imports
from spinnman.messages.eieio.eieio_prefix import EIEIOPrefix

# general imports
from enum import Enum
import math


class ReverseIpTagMultiCastSource(
        AbstractDataSpecablePartitionedVertex,
        ReverseIPTagMulticastSourcePartitionableVertex,
        AbstractProvidesOutgoingEdgeConstraints,
        PartitionedVertex,
        AbstractExecutable,
        HasNMachineTimesteps):
    """
    ReverseIpTagMultiCastSource: a model which will allow events to be injected
    into a spinnaker machine and converted into multi-cast packets.
    """

    # internal params
    _SPIKE_INJECTOR_REGIONS = Enum(
        value="SPIKE_INJECTOR_REGIONS",
        names=[('HEADER', 0),
               ('CONFIGURATION', 1),
               ('BUFFER', 2)])

    _CONFIGURATION_REGION_SIZE = 36

    def __init__(self, label, n_keys, machine_time_step, timescale_factor,
                 listen=True, port=None, tag=None, sdp_port=1,
                 board_address=None, check_key=True, virtual_key=None,
                 prefix=None, prefix_type=None, key_left_shift=0,
                 buffer_space=0, notify_buffer_space=False,
                 space_before_notification=640, notification_tag=None,
                 notification_ip_address=None, notification_port=None,
                 notification_strip_sdp=True, constraints=None):
        """

        :param label: A label for the vertex
        :param n_keys: The number of keys to be sent with the source
        :param machine_time_step: The machine timestep to use
        :param timescale_factor: The scaling of the machine timestep
        :param listen: True if the source should listen for packets using a \
                reverse iptag (otherwise packets can be sent using SDP)
        :param port: The port that the board should listen on if listen=True
        :param tag: The receive tag that the board should use if listen=True
        :param sdp_port: The SDP port to send received packets to
        :param board_address: The board that the source should be placed on
        :param check_key: True if the keys sent should be checked against the \
                specified virtual key or prefix (depending on which is \
                specified)
        :param virtual_key: The base key of the messages to be sent
        :param prefix: A prefix to apply to all 16-bit keys received
        :param prefix_type: Where the prefix should be added to the keys
        :param key_left_shift: Determines if the key should be shifted left
        :param buffer_space: The amount of space to set up for buffering
        :param notify_buffer_space: True if a message should be sent when\
                there is space in the buffer
        :param space_before_notification: How much space should be available\
                before a notification is sent
        :param notification_tag: The IP tag to use for notification
        :param notification_ip_address: The ip address that will receive the\
                notification
        :param notification_port: The port that will receive the notification
        :param notification_strip_sdp: True if the SDP headers should be\
                stripped from the notification message
        :param constraints: Constraints to be given to the source
        """

        AbstractDataSpecablePartitionedVertex.__init__(self)
        AbstractExecutable.__init__(self)
        PartitionedVertex.__init__(
            self, label=label, resources_required=ResourceContainer(
                cpu=CPUCyclesPerTickResource(123), dtcm=DTCMResource(123),
                sdram=SDRAMResource(123)))
        HasNMachineTimesteps.__init__(self)

        self._machine_time_step = machine_time_step
        self._timescale_factor = timescale_factor

        # set params
        self._port = port
        self._virtual_key = virtual_key
        self._prefix = prefix
        self._check_key = check_key
        self._prefix_type = prefix_type
        self._key_left_shift = key_left_shift
        self._space_before_notification = space_before_notification
        self._notify_buffer_space = notify_buffer_space

        # validate params
        if prefix is not None and prefix_type is None:
            raise exceptions.ConfigurationException(
                "To use a prefix, you must declaire which position to use the "
                "prefix in on the prefix_type parameter.")

        if virtual_key is not None:
            self._mask, max_key = self._calculate_mask(n_keys)

            # key =( key  ored prefix )and mask
            temp_vertual_key = virtual_key
            if self._prefix is not None:
                if self._prefix_type == EIEIOPrefix.LOWER_HALF_WORD:
                    temp_vertual_key |= self._prefix
                if self._prefix_type == EIEIOPrefix.UPPER_HALF_WORD:
                    temp_vertual_key |= (self._prefix << 16)
            else:
                self._prefix = self._generate_prefix(virtual_key, prefix_type)

            if temp_vertual_key is not None:

                # check that mask key combo = key
                masked_key = temp_vertual_key & self._mask
                if self._virtual_key != masked_key:
                    raise exceptions.ConfigurationException(
                        "The mask calculated from your number of neurons has "
                        "the potential to interfere with the key, please "
                        "reduce the number of neurons or reduce the virtual"
                        " key")

                # check that neuron mask does not interfere with key
                if self._virtual_key < 0:
                    raise exceptions.ConfigurationException(
                        "Virtual keys must be positive")
                if n_keys > max_key:
                    raise exceptions.ConfigurationException(
                        "The mask calculated from your number of neurons has "
                        "the capability to interfere with the key due to its "
                        "size please reduce the number of neurons or reduce "
                        "the virtual key")

                if self._key_left_shift > 16 or self._key_left_shift < 0:
                    raise exceptions.ConfigurationException(
                        "the key left shift must be within a range of "
                        "0 and 16. Please change this param and try again")

        ReverseIPTagMulticastSourcePartitionableVertex.__init__(
            self, label, n_keys, self._virtual_key, self._buffer_space,
            constraints)

        # add placement constraint
        placement_constraint = PlacerRadialPlacementFromChipConstraint(0, 0)
        self.add_constraint(placement_constraint)

        if listen:
            self.add_constraint(TagAllocatorRequireReverseIptagConstraint(
                port, sdp_port, board_address, tag))
        if notify_buffer_space:
            self.add_constraint(TagAllocatorRequireIptagConstraint(
                notification_ip_address, notification_port,
                notification_strip_sdp, board_address, notification_tag))

    @staticmethod
    def _generate_prefix(virtual_key, prefix_type):
        if prefix_type == EIEIOPrefix.LOWER_HALF_WORD:
            return virtual_key & 0xFFFF
        return (virtual_key >> 16) & 0xFFFF

    @staticmethod
    def _calculate_mask(n_neurons):
        temp_value = int(math.ceil(math.log(n_neurons, 2)))
        max_key = (int(math.pow(2, temp_value)) - 1)
        mask = 0xFFFFFFFF - max_key
        return mask, max_key

    def get_binary_file_name(self):
        """
        """
        return 'reverse_iptag_multicast_source.aplx'

    def generate_data_spec(
            self, placement, graph, routing_info, ip_tags, reverse_ip_tags,
            report_folder, output_folder, write_text_specs):
        """
        """
        data_path, data_writer = data_spec_utilities.get_data_spec_data_writer(
            placement, output_folder)
        report_writer = None
        if write_text_specs:
            report_writer = data_spec_utilities.get_data_spec_report_writer(
                placement, report_folder)
        spec = DataSpecificationGenerator(data_writer, report_writer)

        spec.comment("\n*** Spec for block of {} neurons ***\n"
                     .format(self.model_name))

        spec.comment("\nReserving memory space for data regions:\n\n")

        # Reserve memory regions:
        simulation_utilities.simulation_reserve_header(
            spec, self._SPIKE_INJECTOR_REGIONS.HEADER.value)
        spec.reserve_memory_region(
            region=self._SPIKE_INJECTOR_REGIONS.CONFIGURATION.value,
            size=ReverseIpTagMultiCastSource._CONFIGURATION_REGION_SIZE,
            label='CONFIGURATION')
        if self._buffer_space is not None and self._buffer_space > 0:
            spec.reserve_memory_region(
                region=self._SPIKE_INJECTOR_REGIONS.BUFFER.value,
                size=self._buffer_space, label="BUFFER", empty=True)

        # set up system region writes
        simulation_utilities.simulation_write_header(
            spec, self._SPIKE_INJECTOR_REGIONS.HEADER.value,
            "reverse_ip_tag_multicast_source", self._machine_time_step,
            self._timescale_factor, self.n_machine_timesteps)

        # set up configuration region writes
        spec.switch_write_focus(
            region=self._SPIKE_INJECTOR_REGIONS.CONFIGURATION.value)

        if self._virtual_key is None:
            subedge_routing_info = \
                routing_info.get_subedge_information_from_subedge(
                    graph.outgoing_subedges_from_subvertex(self)[0])
            key_and_mask = subedge_routing_info.keys_and_masks[0]
            self._mask = key_and_mask.mask
            self._virtual_key = key_and_mask.key

            if self._prefix is None:
                if self._prefix_type is None:
                    self._prefix_type = EIEIOPrefix.UPPER_HALF_WORD
                self._prefix = self._generate_prefix(self._virtual_key,
                                                     self._prefix_type)

        # add prefix boolean value
        if self._prefix is None:
            spec.write_value(data=0)
        else:
            spec.write_value(data=1)

        # add prefix
        if self._prefix is None:
            spec.write_value(data=0)
        else:
            if self._prefix_type is EIEIOPrefix.LOWER_HALF_WORD:
                spec.write_value(data=self._prefix)
            else:
                spec.write_value(data=self._prefix << 16)

        # key left shift
        spec.write_value(data=self._key_left_shift)

        # add key check
        if self._check_key:
            spec.write_value(data=1)
        else:
            spec.write_value(data=0)

        # add key and mask
        spec.write_value(data=self._virtual_key)
        spec.write_value(data=self._mask)

        # Buffering control
        spec.write_value(data=self._buffer_space)
        spec.write_value(data=self._space_before_notification)

        # Notification
        if self._notify_buffer_space:
            ip_tag = iter(ip_tags).next()
            spec.write_value(data=ip_tag.tag)
        else:
            spec.write_value(data=0)

        # close spec
        spec.end_specification()
        data_writer.close()
        if write_text_specs:
            report_writer.close()

        return data_path

    def create_subvertex(self, vertex_slice, resources_required, label=None,
                         constraints=None):
        """
        """
        if vertex_slice.n_atoms != self._n_atoms:
            raise exceptions.ConfigurationException(
                "You cannot partition a reverse multicast source into multiple"
                " partitiooned vertices, therefore this is deemed an error "
                "when the vertex slice is not equal to the number of atoms "
                "for the live packet gather.")
        return self

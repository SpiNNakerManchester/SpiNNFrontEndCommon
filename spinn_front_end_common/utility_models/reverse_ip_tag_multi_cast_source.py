"""
ReverseIpTagMultiCastSource
"""

# data spec imports
from data_specification.data_specification_generator import \
    DataSpecificationGenerator

from pacman.model.partitionable_graph.abstract_partitionable_vertex import \
    AbstractPartitionableVertex
from pacman.model.partitioned_graph.partitioned_vertex import PartitionedVertex
from pacman.model.resources.cpu_cycles_per_tick_resource import \
    CPUCyclesPerTickResource
from pacman.model.resources.dtcm_resource import DTCMResource
from pacman.model.resources.resource_container import ResourceContainer
from pacman.model.resources.sdram_resource import SDRAMResource
from pacman.model.routing_info.key_and_mask import KeyAndMask
from pacman.model.constraints.key_allocator_constraints\
    .key_allocator_fixed_key_and_mask_constraint \
    import KeyAllocatorFixedKeyAndMaskConstraint
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
from spinn_front_end_common.abstract_models.\
    abstract_provides_outgoing_edge_constraints \
    import AbstractProvidesOutgoingEdgeConstraints
from spinn_front_end_common.abstract_models.abstract_data_specable_vertex\
    import AbstractDataSpecableVertex
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utilities.exceptions import ConfigurationException

# spinnman imports
from spinnman.messages.eieio.eieio_prefix import EIEIOPrefix

# general imports
from enum import Enum
import sys
import math


class ReverseIpTagMultiCastSource(
        AbstractPartitionableVertex, AbstractDataSpecableVertex,
        AbstractProvidesOutgoingEdgeConstraints, PartitionedVertex):
    """
    ReverseIpTagMultiCastSource: a model which will allow events to be injected
    into a spinnaker machine and converted into multi-cast packets.
    """

    # internal params
    _SPIKE_INJECTOR_REGIONS = Enum(
        value="SPIKE_INJECTOR_REGIONS",
        names=[('SYSTEM', 0),
               ('CONFIGURATION', 1),
               ('BUFFER', 2)])

    _CONFIGURATION_REGION_SIZE = 36
    _max_atoms_per_core = sys.maxint

    CORE_APP_IDENTIFIER = constants.SPIKE_INJECTOR_CORE_APPLICATION_ID

    def __init__(self, n_neurons, machine_time_step, timescale_factor, port,
                 label, board_address=None, virtual_key=None, check_key=True,
                 prefix=None, prefix_type=None, tag=None, key_left_shift=0,
                 sdp_port=1, buffer_space=0, notify_buffer_space=False,
                 space_before_notification=0, notification_tag=None,
                 notification_ip_address=None, notification_port=None,
                 notification_strip_sdp=True, constraints=None):

        if n_neurons > ReverseIpTagMultiCastSource._max_atoms_per_core:
            raise Exception("This model can currently only cope with {} atoms"
                            .format(ReverseIpTagMultiCastSource
                                    ._max_atoms_per_core))

        AbstractDataSpecableVertex.__init__(
            self, machine_time_step, timescale_factor)
        AbstractPartitionableVertex.__init__(
            self, n_neurons, label,
            ReverseIpTagMultiCastSource._max_atoms_per_core, constraints)
        PartitionedVertex.__init__(
            self, label=label, resources_required=ResourceContainer(
                cpu=CPUCyclesPerTickResource(123), dtcm=DTCMResource(123),
                sdram=SDRAMResource(123)))
        self.add_constraint(TagAllocatorRequireReverseIptagConstraint(
            port, sdp_port, board_address, tag))
        if notify_buffer_space:
            self.add_constraint(TagAllocatorRequireIptagConstraint(
                notification_ip_address, notification_port,
                notification_strip_sdp, board_address, notification_tag))

        # set params
        self._port = port
        self._virtual_key = virtual_key
        self._prefix = prefix
        self._check_key = check_key
        self._prefix_type = prefix_type
        self._key_left_shift = key_left_shift
        self._buffer_space = buffer_space
        self._space_before_notification = space_before_notification
        self._notify_buffer_space = notify_buffer_space

        # validate params
        if self._prefix is not None and self._prefix_type is None:
            raise ConfigurationException(
                "To use a prefix, you must declaire which position to use the "
                "prefix in on the prefix_type parameter.")

        if virtual_key is not None:
            self._mask, max_key = self._calculate_mask(n_neurons)

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
                    raise ConfigurationException(
                        "The mask calculated from your number of neurons has "
                        "the potential to interfere with the key, please "
                        "reduce the number of neurons or reduce the virtual"
                        " key")

                # check that neuron mask does not interfere with key
                if self._virtual_key < 0:
                    raise ConfigurationException(
                        "Virtual keys must be positive")
                if n_neurons > max_key:
                    raise ConfigurationException(
                        "The mask calculated from your number of neurons has "
                        "the capability to interfere with the key due to its "
                        "size please reduce the number of neurons or reduce "
                        "the virtual key")

                if self._key_left_shift > 16 or self._key_left_shift < 0:
                    raise ConfigurationException(
                        "the key left shift must be within a range of "
                        "0 and 16. Please change this param and try again")

        # add placement constraint
        placement_constraint = PlacerRadialPlacementFromChipConstraint(0, 0)
        self.add_constraint(placement_constraint)

    @staticmethod
    def _generate_prefix(virtual_key, prefix_type):
        if prefix_type == EIEIOPrefix.LOWER_HALF_WORD:
            return virtual_key & 0xFFFF
        return (virtual_key >> 16) & 0xFFFF

    def get_outgoing_edge_constraints(self, partitioned_edge, graph_mapper):
        if self._virtual_key is not None:
            return list([KeyAllocatorFixedKeyAndMaskConstraint(
                [KeyAndMask(self._virtual_key, self._mask)])])
        return list()

    @staticmethod
    def _calculate_mask(n_neurons):
        temp_value = int(math.ceil(math.log(n_neurons, 2)))
        max_key = (int(math.pow(2, temp_value)) - 1)
        mask = 0xFFFFFFFF - max_key
        return mask, max_key

    def get_sdram_usage_for_atoms(self, vertex_slice, graph):
        return (constants.DATA_SPECABLE_BASIC_SETUP_INFO_N_WORDS * 4 +
                self._CONFIGURATION_REGION_SIZE + self._buffer_space)

    @property
    def model_name(self):
        return "ReverseIpTagMultiCastSource"

    def is_reverse_ip_tagable_vertex(self):
        return True

    def get_dtcm_usage_for_atoms(self, vertex_slice, graph):
        return self._CONFIGURATION_REGION_SIZE

    def get_binary_file_name(self):
        return 'reverse_iptag_multicast_source.aplx'

    def get_cpu_usage_for_atoms(self, vertex_slice, graph):
        return 1

    def generate_data_spec(self, subvertex, placement, sub_graph, graph,
                           routing_info, hostname, graph_mapper,
                           report_folder, ip_tags, reverse_ip_tags,
                           write_text_specs, application_run_time_folder):
        # Create new DataSpec for this processor:
        data_writer, report_writer = \
            self.get_data_spec_file_writers(
                placement.x, placement.y, placement.p, hostname, report_folder,
                write_text_specs, application_run_time_folder)

        spec = DataSpecificationGenerator(data_writer, report_writer)

        spec.comment("\n*** Spec for block of {} neurons ***\n"
                     .format(self.model_name))

        spec.comment("\nReserving memory space for data regions:\n\n")

        # Reserve memory regions:
        spec.reserve_memory_region(
            region=self._SPIKE_INJECTOR_REGIONS.SYSTEM.value,
            size=constants.DATA_SPECABLE_BASIC_SETUP_INFO_N_WORDS * 4,
            label='SYSTEM')
        spec.reserve_memory_region(
            region=self._SPIKE_INJECTOR_REGIONS.CONFIGURATION.value,
            size=self._CONFIGURATION_REGION_SIZE, label='CONFIGURATION')
        if self._buffer_space is not None and self._buffer_space > 0:
            spec.reserve_memory_region(
                region=self._SPIKE_INJECTOR_REGIONS.BUFFER.value,
                size=self._buffer_space, label="BUFFER", empty=True)

        # set up system region writes
        self._write_basic_setup_info(
            spec, ReverseIpTagMultiCastSource.CORE_APP_IDENTIFIER,
            self._SPIKE_INJECTOR_REGIONS.SYSTEM.value)

        # set up configuration region writes
        spec.switch_write_focus(
            region=self._SPIKE_INJECTOR_REGIONS.CONFIGURATION.value)

        if self._virtual_key is None:
            subedge_routing_info = \
                routing_info.get_subedge_information_from_subedge(
                    sub_graph.outgoing_subedges_from_subvertex(subvertex)[0])
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

    def create_subvertex(self, vertex_slice, resources_required, label=None,
                         constraints=None):
        return self

    def is_data_specable(self):
        return True

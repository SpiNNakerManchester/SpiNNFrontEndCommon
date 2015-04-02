"""
LivePacketGather
"""

# pacman imports
from pacman.model.constraints.placer_constraints\
    .placer_radial_placement_from_chip_constraint \
    import PlacerRadialPlacementFromChipConstraint
from pacman.model.constraints.tag_allocator_constraints\
    .tag_allocator_require_iptag_constraint \
    import TagAllocatorRequireIptagConstraint
from pacman.model.partitionable_graph.abstract_partitionable_vertex \
    import AbstractPartitionableVertex

# spinn front end imports
from pacman.model.partitioned_graph.partitioned_vertex import PartitionedVertex
from pacman.model.resources.cpu_cycles_per_tick_resource import \
    CPUCyclesPerTickResource
from pacman.model.resources.dtcm_resource import DTCMResource
from pacman.model.resources.resource_container import ResourceContainer
from pacman.model.resources.sdram_resource import SDRAMResource
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.abstract_models.\
    abstract_data_specable_vertex import AbstractDataSpecableVertex
from spinn_front_end_common.utilities.exceptions import ConfigurationException

# data spec imports
from data_specification.data_specification_generator import \
    DataSpecificationGenerator

# spinnman imports
from spinnman.messages.eieio.eieio_type import EIEIOType
from spinnman.messages.eieio.eieio_prefix import EIEIOPrefix

# general imports
from enum import Enum


class LivePacketGather(
        AbstractDataSpecableVertex, AbstractPartitionableVertex,
        PartitionedVertex):
    """
    LivePacketGather: a model which stores all the events it recieves during an
    timer tick and then compresses them into ethernet pakcets and sends them
    out of a spinnaker machine.
    """

    CORE_APP_IDENTIFIER = constants.LIVE_GATHERER_CORE_APPLICATION_ID

    _LIVE_DATA_GATHER_REGIONS = Enum(
        value="LIVE_DATA_GATHER_REGIONS",
        names=[('SYSTEM', 0),
               ('CONFIG', 1)])
    _CONFIG_SIZE = 44

    """
    A AbstractConstrainedVertex for the Monitoring application data and
    forwarding them to the host

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
        Creates a new AppMonitor Object.
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
                "spinnman..messages.eieio.eieio_prefix_type")
        if label is None:
            label = "Live Packet Gatherer"

        AbstractDataSpecableVertex.__init__(
            self, machine_time_step=machine_time_step,
            timescale_factor=timescale_factor)
        AbstractPartitionableVertex.__init__(self, n_atoms=1, label=label,
                                             max_atoms_per_core=1,
                                             constraints=constraints)
        PartitionedVertex.__init__(
            self, label=label, resources_required=ResourceContainer(
                cpu=CPUCyclesPerTickResource(
                    self.get_cpu_usage_for_atoms(1, None)),
                dtcm=DTCMResource(self.get_dtcm_usage_for_atoms(1, None)),
                sdram=SDRAMResource(self.get_sdram_usage_for_atoms(1, None))))

        # Try to place this near the ethernet
        self.add_constraint(PlacerRadialPlacementFromChipConstraint(0, 0))

        # Add the IP Tag requirement
        self.add_constraint(TagAllocatorRequireIptagConstraint(
            ip_address, port, strip_sdp, board_address, tag))

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
    def model_name(self):
        return "live packet gather"

    def is_ip_tagable_vertex(self):
        return True

    @property
    def number_of_packets_sent_per_time_step(self):
        return self._number_of_packets_sent_per_time_step

    @number_of_packets_sent_per_time_step.setter
    def number_of_packets_sent_per_time_step(self, new_value):
        """

        :param new_value:
        :return:
        """
        self._number_of_packets_sent_per_time_step = new_value

    def generate_data_spec(self, subvertex, placement, sub_graph, graph,
                           routing_info, hostname, graph_sub_graph_mapper,
                           report_folder, ip_tags, reverse_ip_tags,
                           write_text_specs, application_run_time_folder):
        """
        Model-specific construction of the data blocks necessary to build a
        single Application Monitor on one core.
        """
        data_writer, report_writer = \
            self.get_data_spec_file_writers(
                placement.x, placement.y, placement.p, hostname, report_folder,
                write_text_specs, application_run_time_folder)

        spec = DataSpecificationGenerator(data_writer, report_writer)

        spec.comment("\n*** Spec for AppMonitor Instance ***\n\n")

        # Calculate the size of the tables to be reserved in SDRAM:
        setup_sz = 16

        # Construct the data images needed for the Neuron:
        self.reserve_memory_regions(spec, setup_sz)
        self.write_setup_info(spec)
        self.write_configuration_region(spec, subvertex, ip_tags)

        # End-of-Spec:
        spec.end_specification()
        data_writer.close()

    def reserve_memory_regions(self, spec, setup_sz):
        """
        Reserve SDRAM space for memory areas:
        1) Area for information on what data to record
        """

        spec.comment("\nReserving memory space for data regions:\n\n")

        # Reserve memory:
        spec.reserve_memory_region(
            region=self._LIVE_DATA_GATHER_REGIONS.SYSTEM.value,
            size=setup_sz, label='setup')
        spec.reserve_memory_region(
            region=self._LIVE_DATA_GATHER_REGIONS.CONFIG.value,
            size=self._CONFIG_SIZE, label='setup')

    def write_configuration_region(self, spec, partitioned_vertex, ip_tags):
        """ writes the configuration region to the spec

        :param spec: the spec object for the dsg
        :type spec: \
                    :py:class:`data_specification.file_data_writer.FileDataWriter`
        :param partitioned_vertex: the partitioned vertex to which this dsg is\
                    being generated
        :type partitioned_vertex:\
                    :py:class:`pacman.model.partitioned_graph.partitioned_vertex.PartitionedVertex`
        :param ip_tags: The set of ip tags assigned to the object
        :type ip_tags: iterable of :py:class:`spinn_machine.tags.iptag.IPTag`
        :raises DataSpecificationException: when something goes wrong with the\
                    dsg generation
        """
        spec.switch_write_focus(
            region=self._LIVE_DATA_GATHER_REGIONS.CONFIG.value)

        # has prefix
        if self._use_prefix:
            spec.write_value(data=1)
        else:
            spec.write_value(data=0)

        # prefix
        if self._key_prefix is not None:
            spec.write_value(data=self._key_prefix)
        else:
            spec.write_value(data=0)

        # prefix type
        if self._prefix_type is not None:
            spec.write_value(data=self._prefix_type.value)
        else:
            spec.write_value(data=0)

        # packet type
        spec.write_value(data=self._message_type.value)

        # right shift
        spec.write_value(data=self._right_shift)

        # payload as time stamp
        if self._payload_as_time_stamps:
            spec.write_value(data=1)
        else:
            spec.write_value(data=0)

        # payload has prefix
        if self._use_payload_prefix:
            spec.write_value(data=1)
        else:
            spec.write_value(data=0)

        # payload prefix
        if self._payload_prefix is not None:
            spec.write_value(data=self._payload_prefix)
        else:
            spec.write_value(data=0)

        # right shift
        spec.write_value(data=self._payload_right_shift)

        # sdp tag
        ip_tag = iter(ip_tags).next()
        spec.write_value(data=ip_tag.tag)

        # number of packets to send per time stamp
        spec.write_value(data=self._number_of_packets_sent_per_time_step)

    def write_setup_info(self, spec):
        """
        Write information used to control the simulation and gathering of
        results. Currently, this means the flag word used to signal whether
        information on neuron firing and neuron potential is either stored
        locally in a buffer or passed out of the simulation for storage/display
        as the simulation proceeds.

        The format of the information is as follows:
        Word 0: Flags selecting data to be gathered during simulation.
            Bit 0: Record spike history
            Bit 1: Record neuron potential
            Bit 2: Record gsyn values
            Bit 3: Reserved
            Bit 4: Output spike history on-the-fly
            Bit 5: Output neuron potential
            Bit 6: Output spike rate
        """

        # Write this to the system region (to be picked up by the simulation):
        spec.switch_write_focus(
            region=self._LIVE_DATA_GATHER_REGIONS.SYSTEM.value)
        self._write_basic_setup_info(
            spec, constants.LIVE_GATHERER_CORE_APPLICATION_ID,
            self._LIVE_DATA_GATHER_REGIONS.SYSTEM.value)

    def get_binary_file_name(self):
        return 'live_packet_gather.aplx'

    # inherited from partitionable vertex
    def get_cpu_usage_for_atoms(self, vertex_slice, graph):
        return 0

    def get_sdram_usage_for_atoms(self, vertex_slice, graph):
        return (constants.DATA_SPECABLE_BASIC_SETUP_INFO_N_WORDS +
                self._CONFIG_SIZE)

    def get_dtcm_usage_for_atoms(self, vertex_slice, graph):
        return self._CONFIG_SIZE

    def create_subvertex(self, vertex_slice, resources_required, label=None,
                         constraints=None):
        return self

    def is_data_specable(self):
        return True

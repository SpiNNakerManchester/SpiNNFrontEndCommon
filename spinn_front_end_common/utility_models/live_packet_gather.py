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
from pacman.model.partitioned_graph.partitioned_vertex import PartitionedVertex
from pacman.model.resources.cpu_cycles_per_tick_resource import \
    CPUCyclesPerTickResource
from pacman.model.resources.dtcm_resource import DTCMResource
from pacman.model.resources.resource_container import ResourceContainer
from pacman.model.resources.sdram_resource import SDRAMResource

# spinn front end imports
from spinn_front_end_common.abstract_models.\
    abstract_provides_provenance_data import AbstractProvidesProvenanceData
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utilities import data_spec_utilities
from spinn_front_end_common.utilities import simulation_utilities
from spinn_front_end_common.abstract_models\
    .abstract_data_specable_partitioned_vertex \
    import AbstractDataSpecablePartitionedVertex
from spinn_front_end_common.abstract_models.abstract_executable \
    import AbstractExecutable
from spinn_front_end_common.interface.has_n_machine_timesteps \
    import HasNMachineTimesteps

# spinnman imports
from spinnman.messages.eieio.eieio_type import EIEIOType
from spinnman.messages.eieio.eieio_prefix import EIEIOPrefix

# dataspec imports
from data_specification.data_specification_generator import \
    DataSpecificationGenerator
from data_specification import utility_calls as dsg_utility_calls

# general imports
from enum import Enum
import struct


class LivePacketGather(AbstractPartitionableVertex,
                       AbstractDataSpecablePartitionedVertex,
                       AbstractExecutable,
                       PartitionedVertex,
                       HasNMachineTimesteps,
                       AbstractProvidesProvenanceData):
    """
    LivePacketGather: a model which stores all the events it recieves during an
    timer tick and then compresses them into ethernet pakcets and sends them
    out of a spinnaker machine.
    """

    _LIVE_DATA_GATHER_REGIONS = Enum(
        value="LIVE_DATA_GATHER_REGIONS",
        names=[('HEADER', 0),
               ('CONFIG', 1),
               ('PROVANENCE', 2)])
    _CONFIG_SIZE = 44
    _PROVANENCE_REGION_SIZE = 8

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
            raise exceptions.ConfigurationException(
                "Timestamp can either be included as payload prefix or as "
                "payload to each key, not both")
        if ((message_type == EIEIOType.KEY_32_BIT or
             message_type == EIEIOType.KEY_16_BIT) and
                not use_payload_prefix and payload_as_time_stamps):
            raise exceptions.ConfigurationException(
                "Timestamp can either be included as payload prefix or as"
                " payload to each key, but current configuration does not "
                "specify either of these")
        if (not isinstance(prefix_type, EIEIOPrefix) and
                prefix_type is not None):
            raise exceptions.ConfigurationException(
                "the type of a prefix type should be of a EIEIOPrefix, "
                "which can be located in :"
                "spinnman..messages.eieio.eieio_prefix_type")
        if label is None:
            label = "Live Packet Gatherer"

        AbstractPartitionableVertex.__init__(self, n_atoms=1, label=label,
                                             max_atoms_per_core=1,
                                             constraints=constraints)
        AbstractDataSpecablePartitionedVertex.__init__(self)
        AbstractExecutable.__init__(self)
        PartitionedVertex.__init__(
            self, label=label, resources_required=ResourceContainer(
                cpu=CPUCyclesPerTickResource(
                    self.get_cpu_usage_for_atoms(1, None)),
                dtcm=DTCMResource(self.get_dtcm_usage_for_atoms(1, None)),
                sdram=SDRAMResource(self.get_sdram_usage_for_atoms(1, None))))
        HasNMachineTimesteps.__init__(self)
        AbstractProvidesProvenanceData.__init__(self)

        # Try to place this near the ethernet
        self.add_constraint(PlacerRadialPlacementFromChipConstraint(0, 0))

        # Add the IP Tag requirement
        self.add_constraint(TagAllocatorRequireIptagConstraint(
            ip_address, port, strip_sdp, board_address, tag))

        self._machine_time_step = machine_time_step
        self._timescale_factor = timescale_factor

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
        """ The number of packets expected per time step
        """
        return self._number_of_packets_sent_per_time_step

    @number_of_packets_sent_per_time_step.setter
    def number_of_packets_sent_per_time_step(self, new_value):
        """ Set the number of packets expected per timestep
        """
        self._number_of_packets_sent_per_time_step = new_value

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

        spec.comment("\n*** Spec for AppMonitor Instance ***\n\n")

        # Construct the data images needed for the Neuron:
        self._reserve_memory_regions(spec)
        simulation_utilities.simulation_write_header(
            spec, self._LIVE_DATA_GATHER_REGIONS.HEADER.value,
            "live_packet_gather", self._machine_time_step,
            self._timescale_factor, self.n_machine_timesteps)
        self._write_configuration_region(spec, ip_tags)

        # End-of-Spec:
        spec.end_specification()
        data_writer.close()
        if write_text_specs:
            report_writer.close()

        return data_path

    def _reserve_memory_regions(self, spec):
        """ Reserve memory regions for writing data to
        """

        spec.comment("\nReserving memory space for data regions:\n\n")

        # Reserve memory:
        simulation_utilities.simulation_reserve_header(
            spec, self._LIVE_DATA_GATHER_REGIONS.HEADER.value)
        spec.reserve_memory_region(
            region=self._LIVE_DATA_GATHER_REGIONS.CONFIG.value,
            size=self._CONFIG_SIZE, label='config')
        spec.reserve_memory_region(
            region=self._LIVE_DATA_GATHER_REGIONS.PROVANENCE.value,
            size=self._PROVANENCE_REGION_SIZE, label='provanence')

    def _write_configuration_region(self, spec, ip_tags):
        """ writes the configuration region to the spec

        :param spec: the spec object for the dsg
        :type spec: \
                    :py:class:`data_specification.file_data_writer.FileDataWriter`
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

    def write_provenance_data_in_xml(self, file_path, transceiver,
                                     placement=None):
        """
        extracts provanence data from the sdram of the core and stores it in a
        xml file for end user digestion
        :param file_path: the file path to the xml document
        :param transceiver: the spinnman interface object
        :param placement: the placement object for this subvertex
        :return: None
        """
        if placement is None:
            raise exceptions.ConfigurationException(
                "To acquire provanence data from the live packet gatherer,"
                "you must provide a placement object that points to where the "
                "live packet gatherer resides on the spinnaker machine")
        # Get the App Data for the core
        app_data_base_address = transceiver.get_cpu_information_from_core(
            placement.x, placement.y, placement.p).user[0]
        # Get the provanence region base address
        provanence_data_region_base_address_offset = \
            dsg_utility_calls.get_region_base_address_offset(
                app_data_base_address,
                self._LIVE_DATA_GATHER_REGIONS.PROVANENCE.value)
        provanence_data_region_base_address_buf = \
            transceiver.read_memory(
                placement.x, placement.y,
                provanence_data_region_base_address_offset, 4)
        provanence_data_region_base_address = \
            struct.unpack("I", provanence_data_region_base_address_buf)[0]
        provanence_data_region_base_address += app_data_base_address

        # read in the provanence data
        provanence_data_region_contents_buff = \
            transceiver.read_memory(
                placement.x, placement.y, provanence_data_region_base_address,
                self._PROVANENCE_REGION_SIZE)
        provanence_data_region_contents = \
            struct.unpack("<II", provanence_data_region_contents_buff)

        # create provanence data xml form
        from lxml import etree
        root = etree.Element("Live_packet_gatherer_located_at_{}_{}_{}"
                             .format(placement.x, placement.y, placement.p))
        none_payload_provanence_data = \
            etree.SubElement(root, "lost_packets_without_payload")
        payload_provanence_data = \
            etree.SubElement(root, "lost_packets_with_payload")
        none_payload_provanence_data.text = \
            str(provanence_data_region_contents[0])
        payload_provanence_data.text = \
            str(provanence_data_region_contents[1])

        # write xml form into file provided
        writer = open(file_path, "w")
        writer.write(etree.tostring(root, pretty_print=True))
        writer.flush()
        writer.close()

    def get_binary_file_name(self):
        """
        :param spec: the dsg spec object
        """
        return 'live_packet_gather.aplx'

    # inherited from partitionable vertex
    def get_cpu_usage_for_atoms(self, vertex_slice, graph):
        """
        """
        return 0

    def get_sdram_usage_for_atoms(self, vertex_slice, graph):
        """
        """
        return (simulation_utilities.HEADER_REGION_BYTES + self._CONFIG_SIZE)

    def get_dtcm_usage_for_atoms(self, vertex_slice, graph):
        """
        """
        return self._CONFIG_SIZE

    def create_subvertex(self, vertex_slice, resources_required, label=None,
                         constraints=None):
        """
        """
        if vertex_slice.n_atoms != self.n_atoms:
            raise exceptions.ConfigurationException(
                "You cannot partition a live packet gather into multiple"
                " partitiooned vertices, therefore this is deemed an error "
                "when the vertex slice is not equal to the number of atoms "
                "for the live packet gather.")
        return self

    @property
    def model_name(self):
        """
        """
        return "live packet gather"

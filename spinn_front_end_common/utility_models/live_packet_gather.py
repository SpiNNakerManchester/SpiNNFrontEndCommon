"""
live packet gather file
"""
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.abstract_models.abstract_data_specable_vertex \
    import AbstractDataSpecableVertex
from spinn_front_end_common.abstract_models.abstract_iptagable_vertex \
    import AbstractIPTagableVertex

from pacman.model.constraints.placer_chip_and_core_constraint \
    import PlacerChipAndCoreConstraint
from pacman.model.abstract_classes.abstract_partitionable_vertex \
    import AbstractPartitionableVertex


from data_specification.data_specification_generator import \
    DataSpecificationGenerator


from spinnman.messages.eieio.eieio_type_param import EIEIOTypeParam
from spinnman.messages.eieio.eieio_prefix_type import EIEIOPrefixType


from enum import Enum


class LivePacketGather(
        AbstractDataSpecableVertex, AbstractPartitionableVertex,
        AbstractIPTagableVertex):
    """
    utility model for gathering packets from the SpiNNaker fabric and merging them
    to reduce ethernet bandwidth usage
    """

    CORE_APP_IDENTIFIER = constants.LIVE_GATHERER_CORE_APPLICATION_ID

    _LIVE_DATA_GATHER_REGIONS = Enum(
        value="LIVE_DATA_GATHER_REGIONS",
        names=[('SYSTEM', 0),
               ('CONFIG', 1)])
    _CONFIG_SIZE = 44

    def __init__(self, machine_time_step, timescale_factor, tag, port, address,
                 strip_sdp=True, use_prefix=False, key_prefix=None,
                 prefix_type=None, message_type=EIEIOTypeParam.KEY_32_BIT,
                 right_shift=0, payload_as_time_stamps=True,
                 use_payload_prefix=True, payload_prefix=None,
                 payload_right_shift=0,
                 number_of_packets_sent_per_time_step=0):
        """
        Creates a new AppMonitor Object.
        """
        if ((message_type == EIEIOTypeParam.KEY_PAYLOAD_32_BIT or
                message_type == EIEIOTypeParam.KEY_PAYLOAD_16_BIT) and
                use_payload_prefix and payload_as_time_stamps):
            raise exceptions.ConfigurationException(
                "Timestamp can either be included as payload prefix or as "
                "payload to each key, not both")
        if (message_type == EIEIOTypeParam.KEY_32_BIT or
                message_type == EIEIOTypeParam.KEY_16_BIT) and \
                not use_payload_prefix and payload_as_time_stamps:
            raise exceptions.ConfigurationException(
                "Timestamp can either be included as payload prefix or as"
                " payload to each key, but current configuration does not "
                "specify either of these")
        if (not isinstance(prefix_type, EIEIOPrefixType) and
                prefix_type is not None):
            raise exceptions.ConfigurationException(
                "the type of a prefix type should be of a EIEIOPrefixType, "
                "which can be located in :"
                "spinnman..messages.eieio.eieio_prefix_type")

        AbstractDataSpecableVertex.__init__(
            self, n_atoms=1, label="LivePacketGather",
            machine_time_step=machine_time_step,
            timescale_factor=timescale_factor)
        AbstractPartitionableVertex.__init__(self, n_atoms=1, label="Monitor",
                                             max_atoms_per_core=1)
        AbstractIPTagableVertex.__init__(self, tag, port, address,
                                         strip_sdp=strip_sdp)

        self.add_constraint(PlacerChipAndCoreConstraint(0, 0))
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
        """ inhirrited from abstract data specable

        :return:
        """
        return "live packet gather"

    def is_ip_tagable_vertex(self):
        """ helper method for is instance

        :return:
        """
        return True

    @property
    def number_of_packets_sent_per_time_step(self):
        """ property method

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

    def generate_data_spec(self, subvertex, placement, sub_graph, graph,
                           routing_info, hostname, graph_sub_graph_mapper,
                           report_folder, ip_tags, reverse_ip_tags,
                           write_text_specs, application_run_time_folder):
        """
        Model-specific construction of the data blocks necessary to build a
        single Application Monitor on one core.

        :param subvertex: the partitioned_vertex whcih this live packet gather
        is associated
        :param placement: the placement object associated with this
        partitioned vertex
        :param sub_graph: the partitioned_graph
        :param graph: the partitionable graph
        :param routing_info: the keys for this partitioned vertex
        :param hostname: the hostname associated with this spinnaker machine
        :param graph_sub_graph_mapper: the mapper between the two graphs
        :param report_folder: where reports are to be written
        :param ip_tags: the lsit of iptags allcoated to the machine
        :param reverse_ip_tags: the list of reverse iptags allocated to the
        machine
        :param write_text_specs: boolean to write text specs
        :param application_run_time_folder: location where application data is
               stored.
        :return: Nothing
        """
        data_writer, report_writer = \
            self.get_data_spec_file_writers(
                placement.x, placement.y, placement.p, hostname, report_folder,
                write_text_specs, application_run_time_folder)

        spec = DataSpecificationGenerator(data_writer, report_writer)

        spec.comment("\n*** Spec for AppMonitor Instance ***\n\n")

        # Calculate the size of the tables to be reserved in SDRAM:
        setup_sz = (constants.DATA_SPECABLE_BASIC_SETUP_INFO_N_WORDS * 4)

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

        :param spec:
        :param setup_sz:
        :return:
        """

        spec.comment("\nReserving memory space for data regions:\n\n")

        # Reserve memory:
        spec.reserve_memory_region(
            region=self._LIVE_DATA_GATHER_REGIONS.SYSTEM.value,
            size=setup_sz, label='setup')
        spec.reserve_memory_region(
            region=self._LIVE_DATA_GATHER_REGIONS.CONFIG.value,
            size=self._CONFIG_SIZE, label='setup')

    def write_configuration_region(self, spec, _, ip_tags):
        """ writes the configuration region to the spec

        :param spec: the spec object for the dsg
        :type spec: \
                    :py:class:`data_specification.file_data_writer.FileDataWriter`
        :param _: do not care param
        :type _: whatever
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

        :param spec
        """

        # Write this to the system region (to be picked up by the simulation):
        self._write_basic_setup_info(
            spec, self.CORE_APP_IDENTIFIER,
            self._LIVE_DATA_GATHER_REGIONS.SYSTEM.value)

    def get_binary_file_name(self):
        """

        :return:
        """
        return 'live_packet_gather.aplx'

    # inherited from partitionable vertex
    def get_cpu_usage_for_atoms(self, vertex_slice, graph):
        """

        :param vertex_slice:
        :param graph:
        :return:
        """
        return 0

    def get_sdram_usage_for_atoms(self, vertex_slice, graph):
        """

        :param vertex_slice:
        :param graph:
        :return:
        """
        return ((constants.DATA_SPECABLE_BASIC_SETUP_INFO_N_WORDS * 4) +
                self._CONFIG_SIZE)

    def get_dtcm_usage_for_atoms(self, vertex_slice, graph):
        """

        :param vertex_slice:
        :param graph:
        :return:
        """
        return self._CONFIG_SIZE

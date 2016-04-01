from data_specification.data_specification_generator \
    import DataSpecificationGenerator
from pacman.model.constraints.placer_constraints\
    .placer_radial_placement_from_chip_constraint \
    import PlacerRadialPlacementFromChipConstraint
from pacman.model.constraints.tag_allocator_constraints\
    .tag_allocator_require_iptag_constraint \
    import TagAllocatorRequireIptagConstraint

from pacman.model.partitioned_graph.partitioned_vertex import PartitionedVertex
from pacman.model.resources.cpu_cycles_per_tick_resource \
    import CPUCyclesPerTickResource
from pacman.model.resources.dtcm_resource import DTCMResource
from pacman.model.resources.resource_container import ResourceContainer
from pacman.model.resources.sdram_resource import SDRAMResource

from spinn_front_end_common.interface.provenance\
    .provides_provenance_data_from_machine_impl \
    import ProvidesProvenanceDataFromMachineImpl
from spinn_front_end_common.utilities.utility_objs.provenance_data_item \
    import ProvenanceDataItem
from spinn_front_end_common.abstract_models.\
    abstract_partitioned_data_specable_vertex \
    import AbstractPartitionedDataSpecableVertex
from spinn_front_end_common.utilities import constants

from enum import Enum
from spinnman.messages.eieio.eieio_type import EIEIOType


class LivePacketGatherPartitionedVertex(
        PartitionedVertex, ProvidesProvenanceDataFromMachineImpl,
        AbstractPartitionedDataSpecableVertex):

    _LIVE_DATA_GATHER_REGIONS = Enum(
        value="LIVE_DATA_GATHER_REGIONS",
        names=[('SYSTEM', 0),
               ('CONFIG', 1),
               ('PROVENANCE', 2)])

    N_ADDITIONAL_PROVENANCE_ITEMS = 2
    _CONFIG_SIZE = 44
    _PROVENANCE_REGION_SIZE = 8

    def __init__(
            self, label, machine_time_step, timescale_factor,
            use_prefix=False, key_prefix=None, prefix_type=None,
            message_type=EIEIOType.KEY_32_BIT, right_shift=0,
            payload_as_time_stamps=True, use_payload_prefix=True,
            payload_prefix=None, payload_right_shift=0,
            number_of_packets_sent_per_time_step=0,
            ip_address=None, port=None, strip_sdp=None, board_address=None,
            tag=None,
            constraints=None):

        resources_required = ResourceContainer(
            cpu=CPUCyclesPerTickResource(self.get_cpu_usage()),
            dtcm=DTCMResource(self.get_dtcm_usage()),
            sdram=SDRAMResource(self.get_sdram_usage()))

        if constraints is None:
            constraints = self.get_constraints(
                ip_address, port, strip_sdp, board_address, tag)

        PartitionedVertex.__init__(
            self, resources_required, label, constraints=constraints)
        ProvidesProvenanceDataFromMachineImpl.__init__(
            self, self._LIVE_DATA_GATHER_REGIONS.PROVENANCE.value,
            self.N_ADDITIONAL_PROVENANCE_ITEMS)
        AbstractPartitionedDataSpecableVertex.__init__(
            self, machine_time_step, timescale_factor)

        self._use_prefix = use_prefix
        self._key_prefix = key_prefix
        self._prefix_type = prefix_type
        self._message_type = message_type
        self._right_shift = right_shift
        self._payload_as_time_stamps = payload_as_time_stamps
        self._use_payload_prefix = use_payload_prefix
        self._payload_prefix = payload_prefix
        self._payload_right_shift = payload_right_shift
        self._number_of_packets_sent_per_time_step = \
            number_of_packets_sent_per_time_step

    @staticmethod
    def get_constraints(ip_address, port, strip_sdp, board_address, tag):
        """ Get constraints for this subvertex

        :param ip_address:
        :param port:
        :param strip_sdp:
        :param board_address:
        :param tag:
        :return:
        """
        constraints = list()

        # Try to place this near the Ethernet
        constraints.append(PlacerRadialPlacementFromChipConstraint(0, 0))

        # Add the IP Tag requirement
        constraints.append(TagAllocatorRequireIptagConstraint(
            ip_address, port, strip_sdp, board_address, tag))
        return constraints

    def get_provenance_data_from_machine(self, transceiver, placement):
        """ Get provenance from the machine

        :param transceiver: spinnman interface to the machine
        :param placement: the location of this vertex on the machine
        :return:
        """
        provenance_data = self._read_provenance_data(transceiver, placement)
        provenance_items = self._read_basic_provenance_items(
            provenance_data, placement)
        provenance_data = self._get_remaining_provenance_data_items(
            provenance_data)
        _, _, _, _, names = self._get_placement_details(placement)

        provenance_items.append(ProvenanceDataItem(
            self._add_name(names, "lost_packets_without_payload"),
            provenance_data[0],
            report=provenance_data[0] > 0,
            message=(
                "The live packet gatherer has lost {} packets which have "
                "payloads during its execution. Try increasing the machine "
                "time step or increasing the time scale factor. If you are "
                "running in real time, try reducing the number of vertices "
                "which are feeding this live packet gatherer".format(
                    provenance_data[0]))))
        provenance_items.append(ProvenanceDataItem(
            self._add_name(names, "lost_packets_with_payload"),
            provenance_data[1],
            report=provenance_data[1] > 0,
            message=(
                "The live packet gatherer has lost {} packets which do not "
                "have payloads during its execution. Try increasing the "
                "machine time step or increasing the time scale factor. If "
                "you are running in real time, try reducing the number of "
                "vertices which are feeding this live packet gatherer".format(
                    provenance_data[1]))))

        return provenance_items

    def get_binary_file_name(self):
        """ Get the name of binary which is loaded onto a spinnaker machine to\
            represent this partitionable vertex's functionality.

        :return:
        """
        return 'live_packet_gather.aplx'

    def is_partitioned_data_specable(self):
        return True

    def generate_data_spec(self, placement, sub_graph, routing_info, hostname,
                           report_folder, ip_tags, reverse_ip_tags,
                           write_text_specs, application_run_time_folder):

        data_writer, report_writer = \
            self.get_data_spec_file_writers(
                placement.x, placement.y, placement.p, hostname, report_folder,
                write_text_specs, application_run_time_folder)

        spec = DataSpecificationGenerator(data_writer, report_writer)

        spec.comment("\n*** Spec for LivePacketGather Instance ***\n\n")

        # Construct the data images needed for the Neuron:
        self._reserve_memory_regions(spec)
        self._write_setup_info(spec)
        self._write_configuration_region(spec, ip_tags)

        # End-of-Spec:
        spec.end_specification()
        data_writer.close()

        return data_writer.filename

    def _reserve_memory_regions(self, spec):
        """ Reserve SDRAM space for memory areas
        """

        spec.comment("\nReserving memory space for data regions:\n\n")

        # Reserve memory:
        spec.reserve_memory_region(
            region=(
                LivePacketGatherPartitionedVertex.
                _LIVE_DATA_GATHER_REGIONS.SYSTEM.value),
            size=constants.DATA_SPECABLE_BASIC_SETUP_INFO_N_WORDS * 4,
            label='system')
        spec.reserve_memory_region(
            region=(
                LivePacketGatherPartitionedVertex.
                _LIVE_DATA_GATHER_REGIONS.CONFIG.value),
            size=self._CONFIG_SIZE, label='config')
        self.reserve_provenance_data_region(spec)

    def _write_configuration_region(self, spec, ip_tags):
        """ writes the configuration region to the spec

        :param spec: the spec object for the dsg
        :type spec: \
                    :py:class:`spinn_storage_handlers.file_data_writer.FileDataWriter`
        :param ip_tags: The set of ip tags assigned to the object
        :type ip_tags: iterable of :py:class:`spinn_machine.tags.ipTag.IPTag`
        :raises DataSpecificationException: when something goes wrong with the\
                    dsg generation
        """
        spec.switch_write_focus(
            region=(
                LivePacketGatherPartitionedVertex.
                _LIVE_DATA_GATHER_REGIONS.CONFIG.value))

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

        # SDP tag
        ip_tag = iter(ip_tags).next()
        spec.write_value(data=ip_tag.tag)

        # number of packets to send per time stamp
        spec.write_value(data=self._number_of_packets_sent_per_time_step)

    def _write_setup_info(self, spec):
        """ Write basic info to the system region

        :param spec:
        :return:
        """

        # Write this to the system region (to be picked up by the simulation):
        spec.switch_write_focus(
            region=(
                LivePacketGatherPartitionedVertex.
                _LIVE_DATA_GATHER_REGIONS.SYSTEM.value))
        self._write_basic_setup_info(
            spec,
            LivePacketGatherPartitionedVertex.
            _LIVE_DATA_GATHER_REGIONS.SYSTEM.value)

    @staticmethod
    def get_cpu_usage():
        """ Get the CPU used by this vertex

        :return:
        """
        return 0

    @staticmethod
    def get_sdram_usage():
        """ Get the SDRAM used by this vertex

        :return:
        """
        return (
            constants.DATA_SPECABLE_BASIC_SETUP_INFO_N_WORDS +
            LivePacketGatherPartitionedVertex._CONFIG_SIZE +
            LivePacketGatherPartitionedVertex.get_provenance_data_size(
                LivePacketGatherPartitionedVertex
                .N_ADDITIONAL_PROVENANCE_ITEMS))

    @staticmethod
    def get_dtcm_usage():
        """ Get the DTCM used by this vertex

        :return:
        """
        return LivePacketGatherPartitionedVertex._CONFIG_SIZE

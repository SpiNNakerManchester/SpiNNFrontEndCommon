from pacman.executor.injection_decorator import inject_items
from pacman.model.abstract_classes.impl.constrained_object import \
    ConstrainedObject
from pacman.model.constraints.placer_constraints.placer_board_constraint\
    import PlacerBoardConstraint
from pacman.model.constraints.placer_constraints\
    .placer_radial_placement_from_chip_constraint \
    import PlacerRadialPlacementFromChipConstraint
from pacman.model.decorators.overrides import overrides
from pacman.model.graphs.machine.impl.machine_vertex import MachineVertex
from pacman.model.resources.cpu_cycles_per_tick_resource import \
    CPUCyclesPerTickResource
from pacman.model.resources.dtcm_resource import DTCMResource
from pacman.model.resources.iptag_resource import IPtagResource
from pacman.model.resources.resource_container import ResourceContainer
from pacman.model.resources.sdram_resource import SDRAMResource

from spinn_front_end_common.interface.provenance\
    .provides_provenance_data_from_machine_impl \
    import ProvidesProvenanceDataFromMachineImpl
from spinn_front_end_common.interface.simulation import simulation_utilities
from spinn_front_end_common.abstract_models\
    .abstract_generates_data_specification \
    import AbstractGeneratesDataSpecification
from spinn_front_end_common.abstract_models\
    .abstract_binary_uses_simulation_run import AbstractBinaryUsesSimulationRun
from spinn_front_end_common.abstract_models.abstract_has_associated_binary \
    import AbstractHasAssociatedBinary
from spinn_front_end_common.utilities.utility_objs.provenance_data_item \
    import ProvenanceDataItem
from spinn_front_end_common.utilities import constants

from spinnman.messages.eieio.eieio_type import EIEIOType

from enum import Enum


class LivePacketGatherMachineVertex(
        MachineVertex, ProvidesProvenanceDataFromMachineImpl,
        AbstractGeneratesDataSpecification, AbstractHasAssociatedBinary,
        AbstractBinaryUsesSimulationRun):

    _LIVE_DATA_GATHER_REGIONS = Enum(
        value="LIVE_DATA_GATHER_REGIONS",
        names=[('SYSTEM', 0),
               ('CONFIG', 1),
               ('PROVENANCE', 2)])

    N_ADDITIONAL_PROVENANCE_ITEMS = 2
    _CONFIG_SIZE = 44
    _PROVENANCE_REGION_SIZE = 8

    def __init__(
            self, label, use_prefix=False, key_prefix=None, prefix_type=None,
            message_type=EIEIOType.KEY_32_BIT, right_shift=0,
            payload_as_time_stamps=True, use_payload_prefix=True,
            payload_prefix=None, payload_right_shift=0,
            number_of_packets_sent_per_time_step=0,
            ip_address=None, port=None, strip_sdp=None, board_address=None,
            tag=None,
            constraints=None):

        self._resources_required = ResourceContainer(
            cpu_cycles=CPUCyclesPerTickResource(self.get_cpu_usage()),
            dtcm=DTCMResource(self.get_dtcm_usage()),
            sdram=SDRAMResource(self.get_sdram_usage()),
            iptags=[IPtagResource(ip_address, port, strip_sdp, tag)])

        # implementation for where constraints are stored
        self._constraints = ConstrainedObject()
        self._add_constraints(board_address)

        # inheritance
        MachineVertex.__init__(
            self, self._resources_required, label, constraints=constraints)
        ProvidesProvenanceDataFromMachineImpl.__init__(
            self, self._LIVE_DATA_GATHER_REGIONS.PROVENANCE.value,
            self.N_ADDITIONAL_PROVENANCE_ITEMS)

        # app specific data items
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

    def _add_constraints(self, board_address):
        # Try to place this near the Ethernet
        self._constraints.add_constraint(
            PlacerRadialPlacementFromChipConstraint(0, 0))
        if board_address is not None:
            self._constraints.add_constraint(
                PlacerBoardConstraint(board_address))

    @overrides(ProvidesProvenanceDataFromMachineImpl.
               get_provenance_data_from_machine)
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

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return 'live_packet_gather.aplx'

    @inject_items({
        "machine_time_step": "MachineTimeStep",
        "time_scale_factor": "TimeScaleFactor",
        "tags": "MemoryTags"})
    @overrides(
        AbstractGeneratesDataSpecification.generate_data_specification,
        additional_arguments={
            "machine_time_step", "time_scale_factor", "tags"
        })
    def generate_data_specification(
            self, spec, placement, machine_time_step, time_scale_factor,
            tags):

        spec.comment("\n*** Spec for LivePacketGather Instance ***\n\n")

        # Construct the data images needed for the Neuron:
        self._reserve_memory_regions(spec)
        self._write_setup_info(spec, machine_time_step, time_scale_factor)
        self._write_configuration_region(
            spec, tags.get_ip_tags_for_vertex(self))

        # End-of-Spec:
        spec.end_specification()

    def _reserve_memory_regions(self, spec):
        """ Reserve SDRAM space for memory areas
        """

        spec.comment("\nReserving memory space for data regions:\n\n")

        # Reserve memory:
        spec.reserve_memory_region(
            region=(
                LivePacketGatherMachineVertex.
                _LIVE_DATA_GATHER_REGIONS.SYSTEM.value),
            size=constants.SYSTEM_BYTES_REQUIREMENT,
            label='system')
        spec.reserve_memory_region(
            region=(
                LivePacketGatherMachineVertex.
                _LIVE_DATA_GATHER_REGIONS.CONFIG.value),
            size=self._CONFIG_SIZE, label='config')
        self.reserve_provenance_data_region(spec)

    def _write_configuration_region(self, spec, iptags):
        """ writes the configuration region to the spec

        :param spec: the spec object for the dsg
        :type spec: \
                    :py:class:`spinn_storage_handlers.file_data_writer.FileDataWriter`
        :param iptags: The set of ip tags assigned to the object
        :type iptags: iterable of :py:class:`spinn_machine.tags.ipTag.IPTag`
        :raises DataSpecificationException: when something goes wrong with the\
                    dsg generation
        """
        spec.switch_write_focus(
            region=(
                LivePacketGatherMachineVertex.
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
        iptag = iter(iptags).next()
        spec.write_value(data=iptag.tag)

        # number of packets to send per time stamp
        spec.write_value(data=self._number_of_packets_sent_per_time_step)

    def _write_setup_info(self, spec, machine_time_step, time_scale_factor):
        """ Write basic info to the system region

        :param spec:
        :return:
        """

        # Write this to the system region (to be picked up by the simulation):
        spec.switch_write_focus(
            region=(
                LivePacketGatherMachineVertex.
                _LIVE_DATA_GATHER_REGIONS.SYSTEM.value))
        spec.write_array(simulation_utilities.get_simulation_header_array(
            self.get_binary_file_name(), machine_time_step, time_scale_factor))

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
            constants.SYSTEM_BYTES_REQUIREMENT +
            LivePacketGatherMachineVertex._CONFIG_SIZE +
            LivePacketGatherMachineVertex.get_provenance_data_size(
                LivePacketGatherMachineVertex
                .N_ADDITIONAL_PROVENANCE_ITEMS))

    @staticmethod
    def get_dtcm_usage():
        """ Get the DTCM used by this vertex

        :return:
        """
        return LivePacketGatherMachineVertex._CONFIG_SIZE

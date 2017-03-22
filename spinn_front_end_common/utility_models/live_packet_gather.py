# pacman imports
from pacman.model.constraints.placer_constraints\
    import PlacerRadialPlacementFromChipConstraint
from pacman.model.decorators.overrides import overrides
from pacman.model.graphs.application import ApplicationVertex
from pacman.executor.injection_decorator import inject_items

# spinn front end imports
from pacman.model.resources import CPUCyclesPerTickResource, DTCMResource
from pacman.model.resources import IPtagResource, ResourceContainer
from pacman.model.resources import SDRAMResource
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utility_models\
    .live_packet_gather_machine_vertex \
    import LivePacketGatherMachineVertex
from spinn_front_end_common.abstract_models\
    .abstract_generates_data_specification \
    import AbstractGeneratesDataSpecification
from spinn_front_end_common.abstract_models.abstract_has_associated_binary \
    import AbstractHasAssociatedBinary
from spinn_front_end_common.utilities.utility_objs.executable_start_type \
    import ExecutableStartType

# spinnman imports
from spinnman.messages.eieio.eieio_type import EIEIOType
from spinnman.messages.eieio.eieio_prefix import EIEIOPrefix


class LivePacketGather(
        AbstractGeneratesDataSpecification, AbstractHasAssociatedBinary,
        ApplicationVertex):
    """ A model which stores all the events it receives during a timer tick\
        and then compresses them into Ethernet packets and sends them out of\
        a spinnaker machine.
    """

    def __init__(
            self, ip_address, port, board_address=None, tag=None,
            strip_sdp=True, use_prefix=False, key_prefix=None,
            prefix_type=None, message_type=EIEIOType.KEY_32_BIT, right_shift=0,
            payload_as_time_stamps=True, use_payload_prefix=True,
            payload_prefix=None, payload_right_shift=0,
            number_of_packets_sent_per_time_step=0, constraints=None,
            label=None):
        """
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
                "SpinnMan.messages.eieio.eieio_prefix_type")

        if label is None:
            label = "Live Packet Gatherer"

        ApplicationVertex.__init__(self, label, constraints, 1)

        # Try to place this near the Ethernet
        self.add_constraint(PlacerRadialPlacementFromChipConstraint(0, 0))

        # storage objects
        self._iptags = None

        # tag info
        self._ip_address = ip_address
        self._port = port
        self._board_address = board_address
        self._tag = tag
        self._strip_sdp = strip_sdp

        # eieio info
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

    @inject_items({"machine_time_step": "MachineTimeStep"})
    @overrides(
        ApplicationVertex.create_machine_vertex,
        additional_arguments={"machine_time_step"}
    )
    def create_machine_vertex(
            self, vertex_slice, resources_required, machine_time_step,
            label=None, constraints=None):
        return LivePacketGatherMachineVertex(
            label, self._use_prefix, self._key_prefix, self._prefix_type,
            self._message_type, self._right_shift,
            self._payload_as_time_stamps, self._use_payload_prefix,
            self._payload_prefix, self._payload_right_shift,
            self._number_of_packets_sent_per_time_step,
            ip_address=self._ip_address, port=self._port,
            strip_sdp=self._strip_sdp, board_address=self._board_address,
            constraints=constraints)

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return 'live_packet_gather.aplx'

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return ExecutableStartType.USES_SIMULATION_INTERFACE

    @property
    @overrides(ApplicationVertex.n_atoms)
    def n_atoms(self):
        return 1

    @overrides(ApplicationVertex.get_resources_used_by_atoms)
    def get_resources_used_by_atoms(self, vertex_slice):
        return ResourceContainer(
            sdram=SDRAMResource(
                LivePacketGatherMachineVertex.get_sdram_usage()),
            dtcm=DTCMResource(LivePacketGatherMachineVertex.get_dtcm_usage()),
            cpu_cycles=CPUCyclesPerTickResource(
                LivePacketGatherMachineVertex.get_cpu_usage()),
            iptags=[IPtagResource(
                ip_address=self._ip_address, port=self._port,
                strip_sdp=self._strip_sdp, tag=self._tag,
                traffic_identifier="LPG_EVENT_STREAM")])

    @overrides(AbstractGeneratesDataSpecification.generate_data_specification)
    def generate_data_specification(self, spec, placement):

        # generate spec for the machine vertex
        placement.vertex.generate_data_specification(spec, placement)

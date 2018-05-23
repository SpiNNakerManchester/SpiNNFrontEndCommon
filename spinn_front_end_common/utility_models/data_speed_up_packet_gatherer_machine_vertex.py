from spinn_utilities.overrides import overrides
from spinn_utilities.log import FormatAdapter

from pacman.model.graphs.common import EdgeTrafficType
from pacman.model.graphs.machine import MachineVertex
from pacman.model.resources import ResourceContainer, SDRAMResource, \
    IPtagResource
from spinn_front_end_common.utilities.helpful_functions \
    import convert_vertices_to_core_subset
from spinn_front_end_common.abstract_models \
    import AbstractHasAssociatedBinary, AbstractGeneratesDataSpecification
from spinn_front_end_common.interface.provenance import \
    AbstractProvidesLocalProvenanceData
from spinn_front_end_common.utilities.utility_objs import ExecutableType, \
    ProvenanceDataItem
from spinn_front_end_common.utilities.constants \
    import SDP_PORTS, SYSTEM_BYTES_REQUIREMENT
from spinn_front_end_common.utilities.exceptions import SpinnFrontEndException
from spinn_front_end_common.interface.simulation import simulation_utilities

from spinnman.exceptions import SpinnmanTimeoutException
from spinnman.messages.sdp import SDPMessage, SDPHeader, SDPFlag
from spinnman.connections.udp_packet_connections import SCAMPConnection
from spinnman.model.enums.cpu_state import CPUState

from collections import defaultdict
import os
import logging
import math
import time
import struct
from enum import Enum
from pacman.executor.injection_decorator import inject_items
from six.moves import xrange

log = FormatAdapter(logging.getLogger(__name__))
TIMEOUT_RETRY_LIMIT = 20

# dsg data regions
_DATA_REGIONS = Enum(
    value="DATA_REGIONS",
    names=[('SYSTEM', 0),
           ('CONFIG', 1)])

# precompiled structures
_ONE_WORD = struct.Struct("<I")
_THREE_WORDS = struct.Struct("<III")


class DataSpeedUpPacketGatherMachineVertex(
        MachineVertex, AbstractGeneratesDataSpecification,
        AbstractHasAssociatedBinary, AbstractProvidesLocalProvenanceData):
    __slots__ = [
        "_connection",
        "_last_status",
        "_max_seq_num",
        "_output",
        "_provenance_data_items",
        "_report_path",
        "_write_data_speed_up_report",
        "_view"]

    # TRAFFIC_TYPE = EdgeTrafficType.MULTICAST
    TRAFFIC_TYPE = EdgeTrafficType.FIXED_ROUTE

    # report name for tracking used routers
    REPORT_NAME = "routers_used_in_speed_up_process.txt"

    # size of config region in bytes
    CONFIG_SIZE = 16

    # items of data a SDP packet can hold when SCP header removed
    DATA_PER_FULL_PACKET = 68  # 272 bytes as removed SCP header

    # size of items the sequence number uses
    SEQUENCE_NUMBER_SIZE_IN_ITEMS = 1

    # the size of the sequence number in bytes
    SEQUENCE_NUMBER_SIZE = 4
    END_FLAG_SIZE_IN_BYTES = 4

    # items of data from SDP packet with a sequence number
    DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM = \
        DATA_PER_FULL_PACKET - SEQUENCE_NUMBER_SIZE_IN_ITEMS

    # converter between words and bytes
    WORD_TO_BYTE_CONVERTER = 4

    # time outs used by the protocol for separate bits
    TIMEOUT_PER_RECEIVE_IN_SECONDS = 1
    TIME_OUT_FOR_SENDING_IN_SECONDS = 0.01

    # The SDP port that we use
    SDP_PORT = SDP_PORTS.EXTRA_MONITOR_CORE_DATA_SPEED_UP.value

    # command ids for the SDP packets
    SDP_PACKET_START_SENDING_COMMAND_ID = 100
    SDP_PACKET_START_MISSING_SEQ_COMMAND_ID = 1000
    SDP_PACKET_MISSING_SEQ_COMMAND_ID = 1001

    # number of items used up by the re transmit code for its header
    SDP_RETRANSMISSION_HEADER_SIZE = 2

    # base key (really nasty hack to tie in fixed route keys)
    BASE_KEY = 0xFFFFFFF9
    NEW_SEQ_KEY = 0xFFFFFFF8
    FIRST_DATA_KEY = 0xFFFFFFF7
    END_FLAG_KEY = 0xFFFFFFF6

    # to use with mc stuff
    BASE_MASK = 0xFFFFFFFB
    NEW_SEQ_KEY_OFFSET = 1
    FIRST_DATA_KEY_OFFSET = 2
    END_FLAG_KEY_OFFSET = 3

    # the end flag is set when the high bit of the sequence number word is set
    LAST_MESSAGE_FLAG_BIT_MASK = 0x80000000
    # corresponding mask for the actual sequence numbers
    SEQUENCE_NUMBER_MASK = 0x7fffffff

    # the amount of bytes the n bytes takes up
    N_PACKETS_SIZE = 4

    # the amount of bytes the data length will take up
    LENGTH_OF_DATA_SIZE = 4

    THRESHOLD_WHERE_SDP_BETTER_THAN_DATA_EXTRACTOR_IN_BYTES = 40000

    def __init__(
            self, x, y, ip_address, report_default_directory,
            write_data_speed_up_report, constraints=None):
        super(DataSpeedUpPacketGatherMachineVertex, self).__init__(
            label="mc_data_speed_up_packet_gatherer_on_{}_{}".format(x, y),
            constraints=constraints)

        # data holders for the output, and sequence numbers
        self._view = None
        self._max_seq_num = None
        self._output = None

        # Create a connection to be used
        self._connection = SCAMPConnection(
            chip_x=x, chip_y=y, remote_host=ip_address)

        # local provenance storage
        self._provenance_data_items = defaultdict(list)

        # create report if it doesn't already exist
        self._report_path = \
            os.path.join(report_default_directory, self.REPORT_NAME)
        self._write_data_speed_up_report = write_data_speed_up_report

        # Stored reinjection status for resetting timeouts
        self._last_status = None

    @property
    @overrides(MachineVertex.resources_required)
    def resources_required(self):
        return self.static_resources_required()

    def close_connection(self):
        self._connection.close()

    @staticmethod
    def static_resources_required():
        return ResourceContainer(
            sdram=SDRAMResource(
                SYSTEM_BYTES_REQUIREMENT +
                DataSpeedUpPacketGatherMachineVertex.CONFIG_SIZE),
            iptags=[IPtagResource(
                port=None, strip_sdp=True,
                ip_address="localhost", traffic_identifier="DATA_SPEED_UP")])

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return ExecutableType.SYSTEM

    @inject_items({
        "machine_graph": "MemoryMachineGraph",
        "routing_info": "MemoryRoutingInfos",
        "tags": "MemoryTags",
        "machine_time_step": "MachineTimeStep",
        "time_scale_factor": "TimeScaleFactor"
    })
    @overrides(
        AbstractGeneratesDataSpecification.generate_data_specification,
        additional_arguments={
            "machine_graph", "routing_info", "tags",
            "machine_time_step", "time_scale_factor"
        })
    def generate_data_specification(
            self, spec, placement,  # @UnusedVariable
            machine_graph, routing_info, tags,
            machine_time_step, time_scale_factor):
        # pylint: disable=too-many-arguments, arguments-differ

        # Setup words + 1 for flags + 1 for recording size
        setup_size = SYSTEM_BYTES_REQUIREMENT

        # Create the data regions for hello world
        DataSpeedUpPacketGatherMachineVertex._reserve_memory_regions(
            spec, setup_size)

        # write data for the simulation data item
        spec.switch_write_focus(_DATA_REGIONS.SYSTEM.value)
        spec.write_array(simulation_utilities.get_simulation_header_array(
            self.get_binary_file_name(), machine_time_step, time_scale_factor))

        # the keys for the special cases
        if self.TRAFFIC_TYPE == EdgeTrafficType.MULTICAST:
            base_key = routing_info.get_first_key_for_edge(
                list(machine_graph.get_edges_ending_at_vertex(self))[0])
            new_seq_key = base_key + self.NEW_SEQ_KEY_OFFSET
            first_data_key = base_key + self.FIRST_DATA_KEY_OFFSET
            end_flag_key = base_key + self.END_FLAG_KEY_OFFSET
        else:
            new_seq_key = self.NEW_SEQ_KEY
            first_data_key = self.FIRST_DATA_KEY
            end_flag_key = self.END_FLAG_KEY
        spec.switch_write_focus(_DATA_REGIONS.CONFIG.value)
        spec.write_value(new_seq_key)
        spec.write_value(first_data_key)
        spec.write_value(end_flag_key)

        # locate the tag id for our data and update with port
        iptags = tags.get_ip_tags_for_vertex(self)
        iptag = iptags[0]
        iptag.port = self._connection.local_port
        spec.write_value(iptag.tag)

        # End-of-Spec:
        spec.end_specification()

    @staticmethod
    def _reserve_memory_regions(spec, system_size):
        """ Writes the DSG regions memory sizes. Static so that it can be used\
            by the application vertex.

        :param spec: spec file
        :param system_size: size of system region
        :rtype: None
        """
        spec.reserve_memory_region(
            region=_DATA_REGIONS.SYSTEM.value,
            size=system_size,
            label='systemInfo')
        spec.reserve_memory_region(
            region=_DATA_REGIONS.CONFIG.value,
            size=DataSpeedUpPacketGatherMachineVertex.CONFIG_SIZE,
            label="config")

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return "data_speed_up_packet_gatherer.aplx"

    @overrides(AbstractProvidesLocalProvenanceData.get_local_provenance_data)
    def get_local_provenance_data(self):
        prov_items = list()
        for (placement, memory_address, length_in_bytes) in \
                self._provenance_data_items.keys():

            # handle duplicates of the same calls
            times_extracted_the_same_thing = 0
            top_level_name = "Provenance_for_{}".format(self._label)
            for time_taken, lost_seq_nums in self._provenance_data_items[
                    placement, memory_address, length_in_bytes]:
                # handle time
                chip_name = "chip{}:{}".format(placement.x, placement.y)
                last_name = "Memory_address:{}:Length_in_bytes:{}"\
                    .format(memory_address, length_in_bytes)
                iteration_name = "iteration{}".format(
                    times_extracted_the_same_thing)
                prov_items.append(ProvenanceDataItem(
                    [top_level_name, "extraction_time", chip_name, last_name,
                     iteration_name],
                    time_taken, report=False, message=None))
                times_extracted_the_same_thing += 1

                # handle lost sequence numbers
                for i, n_lost_seq_nums in enumerate(lost_seq_nums):
                    prov_items.append(ProvenanceDataItem(
                        [top_level_name, "lost_seq_nums", chip_name, last_name,
                         iteration_name, "iteration_{}".format(i)],
                        n_lost_seq_nums, report=n_lost_seq_nums > 0,
                        message=(
                            "During the extraction of data of {} bytes from "
                            "memory address {}, attempt {} had {} sequences "
                            "that were lost. These had to be retransmitted and"
                            " will have slowed down the data extraction "
                            "process. Reduce the number of executing "
                            "applications and remove routers between yourself"
                            " and the SpiNNaker machine to reduce the chance "
                            "of this occurring."
                            .format(length_in_bytes, memory_address, i,
                                    n_lost_seq_nums))))
        return prov_items

    def set_cores_for_data_extraction(
            self, transceiver, extra_monitor_cores_for_router_timeout,
            placements):

        # Store the last reinjection status for resetting
        # NOTE: This assumes the status is the same on all cores
        self._last_status = \
            extra_monitor_cores_for_router_timeout[0].get_reinjection_status(
                placements, transceiver)

        # Set to not inject dropped packets
        extra_monitor_cores_for_router_timeout[0].set_reinjection_packets(
            placements, extra_monitor_cores_for_router_timeout, transceiver,
            point_to_point=False, multicast=False, nearest_neighbour=False,
            fixed_route=False)

        # Clear any outstanding packets from reinjection
        extra_monitor_cores_for_router_timeout[0].clear_reinjection_queue(
            transceiver, placements, extra_monitor_cores_for_router_timeout)

        # set time out
        extra_monitor_cores_for_router_timeout[0].set_router_time_outs(
            15, 15, transceiver, placements,
            extra_monitor_cores_for_router_timeout)
        extra_monitor_cores_for_router_timeout[0].\
            set_reinjection_router_emergency_timeout(
                1, 1, transceiver, placements,
                extra_monitor_cores_for_router_timeout)

    def unset_cores_for_data_extraction(
            self, transceiver, extra_monitor_cores_for_router_timeout,
            placements):
        if self._last_status is None:
            log.warning(
                "Cores have not been set for data extraction, so can't be"
                " unset")
        try:
            mantissa, exponent = self._last_status.router_timeout_parameters
            extra_monitor_cores_for_router_timeout[0].set_router_time_outs(
                mantissa, exponent, transceiver, placements,
                extra_monitor_cores_for_router_timeout)
            mantissa, exponent = \
                self._last_status.router_emergency_timeout_parameters
            extra_monitor_cores_for_router_timeout[0].\
                set_reinjection_router_emergency_timeout(
                    mantissa, exponent, transceiver, placements,
                    extra_monitor_cores_for_router_timeout)
            extra_monitor_cores_for_router_timeout[0].set_reinjection_packets(
                placements, extra_monitor_cores_for_router_timeout,
                transceiver,
                point_to_point=self._last_status.is_reinjecting_point_to_point,
                multicast=self._last_status.is_reinjecting_multicast,
                nearest_neighbour=(
                    self._last_status.is_reinjecting_nearest_neighbour),
                fixed_route=self._last_status.is_reinjecting_fixed_route)
        except Exception:
            log.error("Error resetting timeouts", exc_info=True)
            log.error("Checking if the cores are OK...")
            core_subsets = convert_vertices_to_core_subset(
                extra_monitor_cores_for_router_timeout, placements)
            try:
                error_cores = transceiver.get_cores_not_in_state(
                    core_subsets, {CPUState.RUNNING})
                if error_cores:
                    log.error("Cores in an unexpected state: {}".format(
                        error_cores))
            except Exception:
                log.error("Couldn't get core state", exc_info=True)

    def get_data(
            self, transceiver, placement, memory_address, length_in_bytes,
            fixed_routes):
        """ Gets data from a given core and memory address.

        :param transceiver: spinnman instance
        :param placement: placement object for where to get data from
        :param memory_address: the address in SDRAM to start reading from
        :param length_in_bytes: the length of data to read in bytes
        :param fixed_routes: the fixed routes, used in the report of which\
            chips were used by the speed up process
        :return: byte array of the data
        """
        start = float(time.time())

        # if asked for no data, just return a empty byte array
        if length_in_bytes == 0:
            data = bytearray(0)
            end = float(time.time())
            self._provenance_data_items[
                placement, memory_address,
                length_in_bytes].append((end - start, [0]))
            return data

        if (length_in_bytes <
                self.THRESHOLD_WHERE_SDP_BETTER_THAN_DATA_EXTRACTOR_IN_BYTES):
            data = transceiver.read_memory(
                placement.x, placement.y, memory_address, length_in_bytes)
            end = float(time.time())
            self._provenance_data_items[
                placement, memory_address,
                length_in_bytes].append((end - start, [0]))
            return data

        data = _THREE_WORDS.pack(
            self.SDP_PACKET_START_SENDING_COMMAND_ID,
            memory_address, length_in_bytes)

        # logger.debug("sending to core %d:%d:%d",
        #              placement.x, placement.y, placement.p)

        # send
        self._connection.send_sdp_message(SDPMessage(
            sdp_header=SDPHeader(
                destination_chip_x=placement.x,
                destination_chip_y=placement.y,
                destination_cpu=placement.p,
                destination_port=self.SDP_PORT,
                flags=SDPFlag.REPLY_NOT_EXPECTED),
            data=data))

        # receive
        self._output = bytearray(length_in_bytes)
        self._view = memoryview(self._output)
        self._max_seq_num = self.calculate_max_seq_num()
        lost_seq_nums = self._receive_data(transceiver, placement)

        end = float(time.time())
        self._provenance_data_items[
            placement, memory_address, length_in_bytes].append(
                (end - start, lost_seq_nums))

        # create report elements
        if self._write_data_speed_up_report:
            routers_been_in_use = self._determine_which_routers_were_used(
                placement, fixed_routes, transceiver.get_machine_details())
            self._write_routers_used_into_report(
                self._report_path, routers_been_in_use, placement)

        return self._output

    def _receive_data(self, transceiver, placement):
        seq_nums = set()
        lost_seq_nums = list()
        timeoutcount = 0
        finished = False
        while not finished:
            try:
                data = self._connection.receive(
                    timeout=self.TIMEOUT_PER_RECEIVE_IN_SECONDS)
                timeoutcount = 0
                seq_nums, finished = self._process_data(
                    data, seq_nums, finished, placement, transceiver,
                    lost_seq_nums)
            except SpinnmanTimeoutException:
                if timeoutcount > TIMEOUT_RETRY_LIMIT:
                    raise SpinnFrontEndException(
                        "Failed to hear from the machine during {} attempts. "
                        "Please try removing firewalls".format(timeoutcount))

                timeoutcount += 1
                self.__reset_connection()
                if not finished:
                    finished = self._determine_and_retransmit_missing_seq_nums(
                        seq_nums, transceiver, placement, lost_seq_nums)
        return lost_seq_nums

    def __reset_connection(self):
        remote_port = self._connection.remote_port
        local_port = self._connection.local_port
        local_ip = self._connection.local_ip_address
        remote_ip = self._connection.remote_ip_address
        self._connection.close()
        self._connection = SCAMPConnection(
            local_port=local_port, remote_port=remote_port,
            local_host=local_ip, remote_host=remote_ip)

    @staticmethod
    def _determine_which_routers_were_used(placement, fixed_routes, machine):
        """ traverses the fixed route paths from a given location to its\
            destination. used for determining which routers were used

        :param placement: the source to start from
        :param fixed_routes: the fixed routes for each router
        :param machine: the spinnMachine instance
        :return: list of chip ids
        """
        routers = list()
        routers.append((placement.x, placement.y))
        entry = fixed_routes[(placement.x, placement.y)]
        chip_x = placement.x
        chip_y = placement.y
        while len(entry.processor_ids) == 0:
            # can assume one link, as its a minimum spanning tree going to
            # the root
            machine_link = machine.get_chip_at(
                chip_x, chip_y).router.get_link(next(iter(entry.link_ids)))
            chip_x = machine_link.destination_x
            chip_y = machine_link.destination_y
            routers.append((chip_x, chip_y))
            entry = fixed_routes[(chip_x, chip_y)]
        return routers

    @staticmethod
    def _write_routers_used_into_report(
            report_path, routers_been_in_use, placement):
        """ writes the used routers into a report

        :param report_path: the path to the report file
        :param routers_been_in_use: the routers been in use
        :param placement: the first placement used
        :rtype: None
        """
        writer_behaviour = "w"
        if os.path.isfile(report_path):
            writer_behaviour = "a"

        with open(report_path, writer_behaviour) as writer:
            writer.write("[{}:{}:{}] = {}\n".format(
                placement.x, placement.y, placement.p, routers_been_in_use))

    def _calculate_missing_seq_nums(self, seq_nums):
        """ determines which sequence numbers we've missed

        :param seq_nums: the set already acquired
        :return: list of missing sequence numbers
        """
        return [sn for sn in xrange(0, self._max_seq_num)
                if sn not in seq_nums]

    def _determine_and_retransmit_missing_seq_nums(
            self, seq_nums, transceiver, placement, lost_seq_nums):
        """ Determines if there are any missing sequence numbers, and if so\
            retransmits the missing sequence numbers back to the core for\
            retransmission.

        :param seq_nums: the sequence numbers already received
        :param transceiver: spinnman instance
        :param placement: placement instance
        :return: whether all packets are transmitted
        :rtype: bool
        """
        # pylint: disable=too-many-locals

        # locate missing sequence numbers from pile
        missing_seq_nums = self._calculate_missing_seq_nums(seq_nums)
        lost_seq_nums.append(len(missing_seq_nums))
        # self._print_missing(missing_seq_nums)
        if not missing_seq_nums:
            return True

        # figure n packets given the 2 formats
        n_packets = 1
        length_via_format2 = \
            len(missing_seq_nums) - (self.DATA_PER_FULL_PACKET - 2)
        if length_via_format2 > 0:
            n_packets += int(math.ceil(
                float(length_via_format2) /
                float(self.DATA_PER_FULL_PACKET - 1)))

        # transmit missing sequence as a new SDP packet
        first = True
        seq_num_offset = 0
        for _ in xrange(n_packets):
            length_left_in_packet = self.DATA_PER_FULL_PACKET
            offset = 0

            # if first, add n packets to list
            if first:

                # get left over space / data size
                size_of_data_left_to_transmit = min(
                    length_left_in_packet - 2,
                    len(missing_seq_nums) - seq_num_offset)

                # build data holder accordingly
                data = bytearray(
                    (size_of_data_left_to_transmit + 2) *
                    self.WORD_TO_BYTE_CONVERTER)

                # pack flag and n packets
                _ONE_WORD.pack_into(
                    data, offset, self.SDP_PACKET_START_MISSING_SEQ_COMMAND_ID)
                _ONE_WORD.pack_into(
                    data, self.WORD_TO_BYTE_CONVERTER, n_packets)

                # update state
                offset += 2 * self.WORD_TO_BYTE_CONVERTER
                length_left_in_packet -= 2
                first = False

            else:  # just add data
                # get left over space / data size
                size_of_data_left_to_transmit = min(
                    self.DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM,
                    len(missing_seq_nums) - seq_num_offset)

                # build data holder accordingly
                data = bytearray(
                    (size_of_data_left_to_transmit + 1) *
                    self.WORD_TO_BYTE_CONVERTER)

                # pack flag
                _ONE_WORD.pack_into(
                    data, offset, self.SDP_PACKET_MISSING_SEQ_COMMAND_ID)
                offset += 1 * self.WORD_TO_BYTE_CONVERTER
                length_left_in_packet -= 1

            # fill data field
            struct.pack_into(
                "<{}I".format(size_of_data_left_to_transmit), data, offset,
                *missing_seq_nums[
                    seq_num_offset:
                    seq_num_offset + size_of_data_left_to_transmit])
            seq_num_offset += length_left_in_packet

            # build SDP message and send it to the core
            transceiver.send_sdp_message(message=SDPMessage(
                sdp_header=SDPHeader(
                    destination_chip_x=placement.x,
                    destination_chip_y=placement.y,
                    destination_cpu=placement.p,
                    destination_port=self.SDP_PORT,
                    flags=SDPFlag.REPLY_NOT_EXPECTED),
                data=data))

            # sleep for ensuring core doesn't lose packets
            time.sleep(self.TIME_OUT_FOR_SENDING_IN_SECONDS)
            # self._print_packet_num_being_sent(packet_count, n_packets)
        return False

    def _process_data(
            self, data, seq_nums, finished, placement, transceiver,
            lost_seq_nums):
        """ Takes a packet and processes it see if we're finished yet

        :param data: the packet data
        :param seq_nums: the list of sequence numbers received so far
        :param finished: bool which states if finished or not
        :param placement: placement object for location on machine
        :param transceiver: spinnman instance
        :param lost_seq_nums: the list of n sequence numbers lost per iteration
        :return: set of data items, if its the first packet, the list of\
            sequence numbers, the sequence number received and if its finished
        """
        # pylint: disable=too-many-arguments
        # self._print_out_packet_data(data)
        length_of_data = len(data)
        first_packet_element, = _ONE_WORD.unpack_from(data, 0)

        # get flags
        seq_num = first_packet_element & self.SEQUENCE_NUMBER_MASK
        is_end_of_stream = (
            first_packet_element & self.LAST_MESSAGE_FLAG_BIT_MASK) != 0

        # check seq num not insane
        if seq_num > self._max_seq_num:
            raise Exception(
                "got an insane sequence number. got {} when "
                "the max is {} with a length of {}".format(
                    seq_num, self._max_seq_num, length_of_data))

        # figure offset for where data is to be put
        offset = self._calculate_offset(seq_num)

        # write data
        true_data_length = offset + length_of_data - self.SEQUENCE_NUMBER_SIZE
        if not is_end_of_stream or \
                length_of_data != self.END_FLAG_SIZE_IN_BYTES:
            self._write_into_view(
                offset, true_data_length, data, self.SEQUENCE_NUMBER_SIZE,
                length_of_data, seq_num, length_of_data, False)

        # add seq num to list
        seq_nums.add(seq_num)

        # if received a last flag on its own, its during retransmission.
        #  check and try again if required
        if is_end_of_stream:
            if not self._check(seq_nums):
                finished = self._determine_and_retransmit_missing_seq_nums(
                    placement=placement, transceiver=transceiver,
                    seq_nums=seq_nums, lost_seq_nums=lost_seq_nums)
            else:
                finished = True
        return seq_nums, finished

    def _calculate_offset(self, seq_num):
        return (seq_num * self.DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM *
                self.WORD_TO_BYTE_CONVERTER)

    def _write_into_view(
            self, view_start_position, view_end_position,
            data, data_start_position, data_end_position, seq_num,
            packet_length, is_final):
        """ puts data into the view

        :param view_start_position: where in view to start
        :param view_end_position: where in view to end
        :param data: the data holder to write from
        :param data_start_position: where in data holder to start from
        :param data_end_position: where in data holder to end
        :param seq_num: the sequence number to figure
        :rtype: None
        """
        # pylint: disable=too-many-arguments
        if view_end_position > len(self._output):
            raise Exception(
                "I'm trying to add to my output data, but am trying to add "
                "outside my acceptable output positions! max is {} and "
                "I received request to fill to {} for sequence num {} from max"
                " sequence num {} length of packet {} and final {}".format(
                    len(self._output), view_end_position, seq_num,
                    self._max_seq_num, packet_length, is_final))
        self._view[view_start_position: view_end_position] = \
            data[data_start_position:data_end_position]

    def _check(self, seq_nums):
        """ verifying if the sequence numbers are correct.

        :param seq_nums: the received sequence numbers
        :return: bool of true or false given if all the sequence numbers have\
            been received
        """
        # hand back
        seq_nums = sorted(seq_nums)
        max_needed = self.calculate_max_seq_num()
        if len(seq_nums) > max_needed + 1:
            raise Exception("I've received more data than I was expecting!!")
        return len(seq_nums) == max_needed + 1

    def calculate_max_seq_num(self):
        """ deduces the max sequence num expected to be received

        :return: int of the biggest sequence num expected
        """

        n_sequence_nums = float(len(self._output)) / float(
            self.DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM *
            self.WORD_TO_BYTE_CONVERTER)
        n_sequence_nums = math.ceil(n_sequence_nums)
        return int(n_sequence_nums)

    @staticmethod
    def _print_missing(seq_nums):
        """ debug printer for the missing sequence numbers from the pile

        :param seq_nums: the sequence numbers received so far
        :rtype: None
        """
        for seq_num in sorted(seq_nums):
            log.info("from list I'm missing sequence num {}", seq_num)

    def _print_out_packet_data(self, data):
        """ debug prints out the data from the packet

        :param data: the packet data
        :rtype: None
        """
        reread_data = struct.unpack("<{}I".format(
            int(math.ceil(len(data) / self.WORD_TO_BYTE_CONVERTER))),
            data)
        log.info("converted data back into readable form is {}", reread_data)

    @staticmethod
    def _print_length_of_received_seq_nums(seq_nums, max_needed):
        """ debug helper method for figuring out if everything been received

        :param seq_nums: sequence numbers received
        :param max_needed: biggest expected to have
        :rtype: None
        """
        if len(seq_nums) != max_needed:
            log.info("should have received {} sequence numbers, but received "
                     "{} sequence numbers", max_needed, len(seq_nums))

    @staticmethod
    def _print_packet_num_being_sent(packet_count, n_packets):
        """ debug helper for printing missing sequence number packet\
            transmission

        :param packet_count: which packet is being fired
        :param n_packets: how many packets to fire.
        :rtype: None
        """
        log.info("send SDP packet with missing sequence numbers: {} of {}",
                 packet_count + 1, n_packets)

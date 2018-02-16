import os
from collections import defaultdict

from pacman.model.decorators import overrides
from pacman.model.graphs.common import EdgeTrafficType
from pacman.model.graphs.machine import MachineVertex
from pacman.model.resources import ResourceContainer, SDRAMResource, \
    IPtagResource
from spinn_front_end_common.abstract_models \
    import AbstractHasAssociatedBinary, AbstractGeneratesDataSpecification
from spinn_front_end_common.interface.provenance import \
    AbstractProvidesLocalProvenanceData
from spinn_front_end_common.utilities.utility_objs import ExecutableType, \
    ProvenanceDataItem
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.interface.simulation import simulation_utilities
from spinn_storage_handlers import FileDataReader

from spinnman.exceptions import SpinnmanTimeoutException
from spinnman.messages.sdp import SDPMessage, SDPHeader, SDPFlag
from spinnman.connections.udp_packet_connections import SCAMPConnection

import logging
import math
import time
import struct
from enum import Enum
from pacman.executor.injection_decorator import inject_items

TIMEOUT_RETRY_LIMIT = 20
logger = logging.getLogger(__name__)


class DataSpeedUpPacketGatherMachineVertex(
        MachineVertex, AbstractGeneratesDataSpecification,
        AbstractHasAssociatedBinary, AbstractProvidesLocalProvenanceData):

    __slots__ = (

        # data holder for output
        "_view",

        # the max seq num expected given a data retrieval
        "_max_seq_num",

        # holder of data from out
        "_output",

        # store of the extra monitors to location. helpful in data in
        "_extra_monitors_by_chip",

        # connection for comming with the c code
        "_connection",

        # provenance holder
        "_provenance_data_items",

        # spinnMan instance
        "_transceiver",

        # my placement for future lookup
        "_placement",

        # tracker for expected missing seq nums
        "_total_expected_missing_seq_packets",

        # boolean tracker for handling out of order packets
        "_have_received_missing_seq_count_packet",

        # holder for missing seq nums for data in
        "_missing_seq_nums_data_in",
    )

    TRAFFIC_TYPE = EdgeTrafficType.FIXED_ROUTE

    # dsg data regions
    DATA_REGIONS = Enum(
        value="DATA_REGIONS",
        names=[('SYSTEM', 0),
               ('CONFIG', 1),
               ('DATA_IN_CHIP_TO_KEY_SPACE', 2)])

    # size of config region in bytes
    CONFIG_SIZE = 16

    # items of data a SDP packet can hold when SCP header removed
    DATA_PER_FULL_PACKET = 68  # 272 bytes as removed SCP header

    # size of items the sequence number uses
    SEQUENCE_NUMBER_SIZE_IN_ITEMS = 1

    # the size of the sequence number in bytes
    SEQUENCE_NUMBER_SIZE = 4
    END_FLAG_SIZE_IN_BYTES = 4
    COMMAND_ID_SIZE = 4
    MISSING_SEQ_PACKET_COUNT_SIZE = 4

    # items of data from SDP packet with a sequence number
    DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM = \
        DATA_PER_FULL_PACKET - SEQUENCE_NUMBER_SIZE_IN_ITEMS

    # converter between words and bytes
    WORD_TO_BYTE_CONVERTER = 4

    # time outs used by the protocol for separate bits
    TIMEOUT_PER_RECEIVE_IN_SECONDS = 1
    TIME_OUT_FOR_SENDING_IN_SECONDS = 0.01

    # command ids for the SDP packets for data out
    SDP_PACKET_START_SENDING_COMMAND_ID = 100
    SDP_PACKET_START_MISSING_SEQ_COMMAND_ID = 1000
    SDP_PACKET_MISSING_SEQ_COMMAND_ID = 1001

    # command ids for the SDP packets for data in
    SDP_PACKET_SEND_DATA_TO_LOCATION_COMMAND_ID = 200
    SDP_PACKET_SEND_SEQ_DATA_COMMAND_ID = 2000
    SDP_PACKET_SEND_MISSING_SEQ_NUMS_BACK_COMMAND_ID = 2001
    SDP_PACKET_SEND_LAST_DATA_IN_COMMAND_ID = 2002
    SDP_PACKET_RECEIVE_FIRST_MISSING_SEQ_DATA_IN_COMMAND_ID = 2003
    SDP_PACKET_RECEIVE_MISSING_SEQ_DATA_IN_COMMAND_ID = 2004
    SDP_PACKET_RECEIVE_FINISHED_DATA_IN_COMMAND_ID = 2005

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

    # the size in bytes of the end flag
    LAST_MESSAGE_FLAG_BIT_MASK = 0x80000000

    # the amount of bytes the n bytes takes up
    N_PACKETS_SIZE = 4

    # the amount of bytes the data length will take up
    LENGTH_OF_DATA_SIZE = 4

    # point where sdp beats data speed up due to overheads
    THRESHOLD_WHERE_SDP_BETTER_THAN_DATA_EXTRACTOR_IN_BYTES = 40000
    THRESHOLD_WHERE_SDP_BETTER_THAN_DATA_INPUT_IN_BYTES = 300

    # offset where data in starts on first command (
    # command, base_address, x&y, max_seq_number)
    OFFSET_AFTER_COMMAND_AND_ADDRESS = 16

    # offset where data starts after a command id and seq number
    OFFSET_AFTER_COMMAND_AND_SEQUENCE = 8

    # size fo data to store when first packet with command and address
    DATA_IN_FULL_PACKET_WITH_ADDRESS_NUM = \
        DATA_PER_FULL_PACKET - (OFFSET_AFTER_COMMAND_AND_ADDRESS /
                                WORD_TO_BYTE_CONVERTER)

    # size for data in to store when not first packet
    DATA_IN_FULL_PACKET_WITH_NO_ADDRESS_NUM = \
        DATA_PER_FULL_PACKET - OFFSET_AFTER_COMMAND_AND_SEQUENCE

    # SDRAM requirement for storing missing SDP packets seq nums
    SDRAM_FOR_MISSING_SDP_SEQ_NUMS = int(math.ceil(
        (120 * 1024 * 1024) /
        (DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM * WORD_TO_BYTE_CONVERTER)))

    # size of data in key space
    # x, y, key (all ints) for possible 48 chips,
    SIZE_DATA_IN_CHIP_TO_KEY_SPACE = (3 * 4 * 48) + 4

    # end flag for missing seq nums
    MISSING_SEQ_NUMS_END_FLAG = 0xFFFFFFFF

    def __init__(self, x, y, ip_address, extra_monitors_by_chip, transceiver,
                 constraints=None):
        MachineVertex.__init__(
            self,
            label="mc_data_speed_up_packet_gatherer_on_{}_{}".format(x, y),
            constraints=constraints)
        AbstractHasAssociatedBinary.__init__(self)
        AbstractProvidesLocalProvenanceData.__init__(self)

        # data holders for the output, and sequence numbers
        self._view = None
        self._max_seq_num = None
        self._output = None

        # store of the extra monitors to location. helpful in data in
        self._extra_monitors_by_chip = extra_monitors_by_chip
        self._total_expected_missing_seq_packets = None
        self._have_received_missing_seq_count_packet = False
        self._missing_seq_nums_data_in = list()

        # Create a connection to be used
        self._connection = SCAMPConnection(
            chip_x=x, chip_y=y, remote_host=ip_address)

        # local provenance storage
        self._provenance_data_items = defaultdict(list)
        self._transceiver = transceiver
        self._placement = None

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
                constants.SYSTEM_BYTES_REQUIREMENT +
                DataSpeedUpPacketGatherMachineVertex.CONFIG_SIZE +
                DataSpeedUpPacketGatherMachineVertex.
                SDRAM_FOR_MISSING_SDP_SEQ_NUMS +
                DataSpeedUpPacketGatherMachineVertex.
                SIZE_DATA_IN_CHIP_TO_KEY_SPACE),
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
        "time_scale_factor": "TimeScaleFactor",
        "mc_data_chips_to_keys": "DataInMulticastKeyToChipMap",
        "machine": "MemoryExtendedMachine"
    })
    @overrides(
        AbstractGeneratesDataSpecification.generate_data_specification,
        additional_arguments={
            "machine_graph", "routing_info", "tags",
            "machine_time_step", "time_scale_factor",
            "mc_data_chips_to_keys", "machine"
        })
    def generate_data_specification(
            self, spec, placement, machine_graph, routing_info, tags,
            machine_time_step, time_scale_factor, mc_data_chips_to_keys,
            machine):

        # update my placement for future knowledge
        self._placement = placement

        # Setup words + 1 for flags + 1 for recording size
        setup_size = constants.SYSTEM_BYTES_REQUIREMENT

        # Create the data regions for hello world
        DataSpeedUpPacketGatherMachineVertex._reserve_memory_regions(
            spec, setup_size)

        # write data for the simulation data item
        spec.switch_write_focus(self.DATA_REGIONS.SYSTEM.value)
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
        spec.switch_write_focus(self.DATA_REGIONS.CONFIG.value)
        spec.write_value(new_seq_key)
        spec.write_value(first_data_key)
        spec.write_value(end_flag_key)

        # locate the tag id for our data and update with port
        iptags = tags.get_ip_tags_for_vertex(self)
        iptag = iptags[0]
        iptag.port = self._connection.local_port
        spec.write_value(iptag.tag)

        # write mc chip key map
        spec.switch_write_focus(
            self.DATA_REGIONS.DATA_IN_CHIP_TO_KEY_SPACE.value)
        chips_on_board = list(machine.get_chips_on_board(
            machine.get_chip_at(placement.x, placement.y)))

        # write how many chips to read
        spec.write_value(len(chips_on_board))

        # write each chip x and y and base key
        for (chip_x, chip_y) in chips_on_board:
            spec.write_value(chip_x)
            spec.write_value(chip_y)
            spec.write_value(mc_data_chips_to_keys[chip_x, chip_y])

        # End-of-Spec:
        spec.end_specification()

    @staticmethod
    def _reserve_memory_regions(spec, system_size):
        """ writes the dsg regions memory sizes. Static so that it can be used
        by the application vertex.

        :param spec: spec file
        :param system_size: size of system region
        :rtype: None
        """

        spec.reserve_memory_region(
            region=DataSpeedUpPacketGatherMachineVertex.
            DATA_REGIONS.SYSTEM.value,
            size=system_size,
            label='systemInfo')
        spec.reserve_memory_region(
            region=DataSpeedUpPacketGatherMachineVertex.DATA_REGIONS.
            CONFIG.value,
            size=DataSpeedUpPacketGatherMachineVertex.CONFIG_SIZE,
            label="config")
        spec.reserve_memory_region(
            region=DataSpeedUpPacketGatherMachineVertex.DATA_REGIONS.
            DATA_IN_CHIP_TO_KEY_SPACE.value,
            size=DataSpeedUpPacketGatherMachineVertex.
            SIZE_DATA_IN_CHIP_TO_KEY_SPACE,
            label="mc_key_map")

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

    @staticmethod
    def locate_correct_write_data_function_for_chip_location(
            uses_advanced_monitors, machine, x, y, transceiver,
            extra_monitor_cores_to_ethernet_connection_map):
        """ supports other components figuring out which gather and function 
        to call for writing data onto spinnaker
        
        :param uses_advanced_monitors: bool saying if the system is using\ 
         advanced monitors
        :param machine: the SpiNNMachine instance
        :param x: the chip x coordinate to write data to
        :param y: the chip y coordinate to write data to
        :param extra_monitor_cores_to_ethernet_connection_map: 
        :param transceiver: the SpiNNMan instance
        :return: a write function of either a LPG or the spinnMan
        :rtype: function
        """
        if uses_advanced_monitors:
            chip = machine.get_chip_at(x, y)
            ethernet_connected_chip = machine.get_chip_at(
                chip.nearest_ethernet_x, chip.nearest_ethernet_y)
            gatherer = extra_monitor_cores_to_ethernet_connection_map[
                ethernet_connected_chip.x, ethernet_connected_chip.y]
            return gatherer.send_data_into_spinnaker
        else:
            return transceiver.write_memory

    def send_data_into_spinnaker(
            self, x, y, base_address, data, n_bytes=None, offset=0,
            is_filename=False):
        """ sends a block of data into spinnaker to a given chip 
        
        :param x: chip x for data
        :param y: chip y for data
        :param base_address: the address in SDRAM to start writing memory 
        :param data: the data to write
        :param n_bytes: how many bytes to read, or None if not set
        :param offset: where in the data to start from
        :param is_filename: bool stating if data is actually a file.
        :rtype: None 
        """

        # if not worth using extra monitors, send via sdp
        if n_bytes < self.THRESHOLD_WHERE_SDP_BETTER_THAN_DATA_INPUT_IN_BYTES:
            self._transceiver.write_memory(
                x=x, y=y, base_address=base_address, n_bytes=n_bytes,
                data=data, offset=offset, is_filename=is_filename)
        else:
            # if file, read in and then process as normal
            if is_filename:
                if offset is not 0:
                    raise Exception(
                        "when using a file, you can only have a offset of 0")

                reader = FileDataReader(data)
                if n_bytes is None:
                    n_bytes = os.stat(data).st_size
                    data = reader.readall()
                else:
                    data = reader.read(n_bytes)

            # send raw data
            self._send_data_via_extra_monitors(
                x, y, base_address, data[offset:n_bytes + offset])

    def _send_data_via_extra_monitors(
            self, destination_chip_x, destination_chip_y, start_address,
            data_to_write):
        """ sends data using the extra monitor cores
        
        :param destination_chip_x: chip x
        :param destination_chip_y: chip y
        :param start_address: start address in sdram to write data to 
        :param data_to_write: the data to write
        :rtype: None 
        """
        print "SENDING DATA VIA EXTRA MONITORS"

        # where in data we've sent up to
        position_in_data = 0

        # how many packets after first one we need to send
        number_of_packets = int(math.ceil(
            (len(data_to_write) - self.DATA_IN_FULL_PACKET_WITH_ADDRESS_NUM) /
            self.DATA_IN_FULL_PACKET_WITH_NO_ADDRESS_NUM))

        # compressed destination chip data
        chip_data = ((destination_chip_x < 16) & destination_chip_y)

        # send first packet to lpg, stating where to send it to
        data = struct.pack(
            "<IIII", self.SDP_PACKET_SEND_DATA_TO_LOCATION_COMMAND_ID,
            start_address, chip_data, number_of_packets)
        data = struct.pack_into(
            data, self.OFFSET_AFTER_COMMAND_AND_ADDRESS,
            data_to_write[
                position_in_data:self.DATA_IN_FULL_PACKET_WITH_ADDRESS_NUM])

        # update where in data we've sent up to
        position_in_data = self.DATA_IN_FULL_PACKET_WITH_ADDRESS_NUM

        message = SDPMessage(
            sdp_header=SDPHeader(
                destination_chip_x=self._placement.x,
                destination_chip_y=self._placement.y,
                destination_cpu=self._placement.p,
                destination_port=constants.SDP_PORTS.
                EXTRA_MONITOR_CORE_DATA_SPEED_UP.value,
                flags=SDPFlag.REPLY_NOT_EXPECTED),
            data=data)

        # send first message
        self._connection.send_sdp_message(message)

        # send initial attempt at sending all the data
        self._send_all_data(number_of_packets, data_to_write, position_in_data)

        # verify completed
        received_confirmation = False
        time_out_count = 0
        while not received_confirmation:
            try:
                data = self._connection.receive(
                    timeout=self.TIMEOUT_PER_RECEIVE_IN_SECONDS)
                time_out_count = 0
                received_confirmation = self._outgoing_process_packet(
                    data, data_to_write)
            except SpinnmanTimeoutException:
                if time_out_count > TIMEOUT_RETRY_LIMIT:
                    raise exceptions.SpinnFrontEndException(
                        "Failed to hear from the machine during {} attempts. "
                        "Please try removing firewalls".format(time_out_count))
                time_out_count += 1
                remote_port = self._connection.remote_port
                local_port = self._connection.local_port
                local_ip = self._connection.local_ip_address
                remote_ip = self._connection.remote_ip_address
                self._connection.close()
                self._connection = SCAMPConnection(
                    local_port=local_port, remote_port=remote_port,
                    local_host=local_ip, remote_host=remote_ip)
                if not received_confirmation:
                    self._outgoing_retransmit_missing_seq_nums(data_to_write)

    def _read_in_missing_seq_nums(self, data, data_to_write, position):
        """ handles a missing seq num packet from spinnaker
        
        :param data: the data to translate into missing seq nums
        :param data_to_write: the data to write
        :param position: the position in the data to write.
        :rtype: None 
        """
        # find how many elements are in this packet
        n_elements = (len(data) - position) / self.LENGTH_OF_DATA_SIZE

        # store missing
        self._missing_seq_nums_data_in.extend(struct.unpack_from(
            "<{}I".format(n_elements), data, position))

        # determine if last element is end flag
        if self._missing_seq_nums_data_in[-1] == \
                self.MISSING_SEQ_NUMS_END_FLAG:
            del self._missing_seq_nums_data_in[-1]
            self._outgoing_retransmit_missing_seq_nums(data_to_write)
        if (self._total_expected_missing_seq_packets == 0 and
                self._have_received_missing_seq_count_packet):
            self._outgoing_retransmit_missing_seq_nums(data_to_write)

    def _outgoing_process_packet(self, data, data_to_write):
        """ processes a packet from SpiNNaker
        
        :param data: the packet data 
        :param data_to_write: the data to write to spinnaker
        :return: if the packet contains a confirmation of complete
        :rtype: bool
        """
        position = 0
        command_id = struct.unpack("<I", data)
        position += self.COMMAND_ID_SIZE

        # process first missing
        if command_id == \
                self.SDP_PACKET_RECEIVE_FIRST_MISSING_SEQ_DATA_IN_COMMAND_ID:

            # find total missing
            self._total_expected_missing_seq_packets += \
                struct.unpack_from("<I", data, position)
            position += self.MISSING_SEQ_PACKET_COUNT_SIZE
            self._have_received_missing_seq_count_packet = True

            # write missing seq nums and retransmit if needed
            self._read_in_missing_seq_nums(data, data_to_write, position)

        # process missing seq packets
        if command_id == \
                self.SDP_PACKET_RECEIVE_MISSING_SEQ_DATA_IN_COMMAND_ID:
            # write missing seq nums and retransmit if needed
            self._total_expected_missing_seq_packets -= 1

            self._read_in_missing_seq_nums(data, data_to_write, position)

        # process the confirmation of all data received
        if command_id == self.SDP_PACKET_RECEIVE_FINISHED_DATA_IN_COMMAND_ID:
            return True

        # if not confirmation packet, need to carry on
        return False

    def _outgoing_retransmit_missing_seq_nums(self, data_to_write):
        """ transmits back into spinnaker the missing data based off missing\
        seq nums
        
        :param data_to_write: the data to write. 
        :rtype: None 
        """
        for missing_seq_num in self._missing_seq_nums_data_in:
            message, length = self._calculate_data_in_data_from_seq_number(
                data_to_write, missing_seq_num,
                self.SDP_PACKET_SEND_MISSING_SEQ_NUMS_BACK_COMMAND_ID)
            self._connection.send_sdp_message(message)

        self._missing_seq_nums_data_in = list()
        self._total_expected_missing_seq_packets = 0
        self._have_received_missing_seq_count_packet = False
        self._send_end_flag()

    def _calculate_data_in_data_from_seq_number(
            self, data_to_write, seq_num, command_id):
        """ determine the data needed to be sent to the SpiNNaker machine\
         given a seq num
        
        :param data_to_write: the data to write to the spinnaker machine
        :param seq_num: the seq num to ge tthe data for
        :return: SDP message and how much data has been written
        :rtype: SDP message
        """

        # determine offset
        offset = 0
        if seq_num != 0:
            first_message_offset = self.DATA_IN_FULL_PACKET_WITH_ADDRESS_NUM
            rest_of_packets_offset = \
                seq_num * self.DATA_IN_FULL_PACKET_WITH_NO_ADDRESS_NUM
            offset = first_message_offset + rest_of_packets_offset

        # check for last packet
        packet_data_length = self.DATA_IN_FULL_PACKET_WITH_NO_ADDRESS_NUM
        if offset + packet_data_length > len(data_to_write):
            packet_data_length = len(data_to_write) - offset

        # create stuct
        packet_data = struct.pack("<II", command_id, seq_num)
        packet_data = struct.pack_into(
            "<{}I".format(packet_data_length), packet_data, offset,
            data_to_write)

        # send sdp packet
        message = SDPMessage(
            sdp_header=SDPHeader(
                destination_chip_x=self._placement.x,
                destination_chip_y=self._placement.y,
                destination_cpu=self._placement.p,
                destination_port=constants.SDP_PORTS.
                EXTRA_MONITOR_CORE_DATA_SPEED_UP.value,
                flags=SDPFlag.REPLY_NOT_EXPECTED),
            data=packet_data)

        return message, packet_data_length

    def _send_end_flag(self):
        # send end flag as separate message
        packet_data = struct.pack(
            "<I", self.SDP_PACKET_SEND_LAST_DATA_IN_COMMAND_ID)

        # send sdp packet
        message = SDPMessage(
            sdp_header=SDPHeader(
                destination_chip_x=self._placement.x,
                destination_chip_y=self._placement.y,
                destination_cpu=self._placement.p,
                destination_port=constants.SDP_PORTS.
                EXTRA_MONITOR_CORE_DATA_SPEED_UP.value,
                flags=SDPFlag.REPLY_NOT_EXPECTED),
            data=packet_data)
        self._connection.send_sdp_message(message)

    def _send_all_data(
            self, number_of_packets, data_to_write, position_in_data):
        """ sends all the data as one block 
        
        :param number_of_packets: the number of packets expected to send
        :param data_to_write: the data to send
        :param position_in_data: where in the data we are currently up to.
        :rtype: None 
        """
        #  send rest of data
        for seq_num in range(number_of_packets):

            # put in command flag and seq num
            message, length_to_write = \
                self._calculate_data_in_data_from_seq_number(
                    data_to_write, seq_num,
                    self.SDP_PACKET_SEND_SEQ_DATA_COMMAND_ID)
            position_in_data += length_to_write

            self._connection.send_sdp_message(message)

            # check for end flag
            if position_in_data == len(data_to_write):
                self._send_end_flag()

    @staticmethod
    def set_cores_for_data_streaming(
            transceiver, extra_monitor_cores_for_router_timeout,
            placements):
        """ helper method for setting the router timeouts to a state usable\
         for data streaming
        
        :param transceiver: the SpiNNMan instance
        :param extra_monitor_cores_for_router_timeout: the extra monitor cores\
         to set 
        :param placements: placements object
        :rtype: None 
        """
        # set time out
        extra_monitor_cores_for_router_timeout[0].set_router_time_outs(
            15, 15, transceiver, placements,
            extra_monitor_cores_for_router_timeout)
        extra_monitor_cores_for_router_timeout[0].set_router_emergency_timeout(
            0, 0, transceiver, placements,
            extra_monitor_cores_for_router_timeout)

    @staticmethod
    def unset_cores_for_data_streaming(
            transceiver, extra_monitor_cores_for_router_timeout,
            placements):
        """ helper method for setting the router timeouts to a state usable\
         for data streaming

        :param transceiver: the SpiNNMan instance
        :param extra_monitor_cores_for_router_timeout: the extra monitor cores\
         to set 
        :param placements: placements object
        :rtype: None 
        """
        extra_monitor_cores_for_router_timeout[0].set_router_time_outs(
            15, 4, transceiver, placements,
            extra_monitor_cores_for_router_timeout)
        extra_monitor_cores_for_router_timeout[0].set_router_emergency_timeout(
            0, 0, transceiver, placements,
            extra_monitor_cores_for_router_timeout)

    def get_data(
            self, placement, memory_address, length_in_bytes):
        """ gets data from a given core and memory address.

        :param placement: placement object for where to get data from
        :param memory_address: the address in SDRAM to start reading from
        :param length_in_bytes: the length of data to read in bytes
        :return: byte array of the data
        """
        start = float(time.time())
        lost_seq_nums = list()

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
            data = self._transceiver.read_memory(
                placement.x, placement.y, memory_address, length_in_bytes)
            end = float(time.time())
            self._provenance_data_items[
                placement, memory_address,
                length_in_bytes].append((end - start, [0]))
            return data

        data = struct.pack(
            "<III", self.SDP_PACKET_START_SENDING_COMMAND_ID,
            memory_address, length_in_bytes)

        # logger.debug("sending to core %d:%d:%d",
        #              placement.x, placement.y, placement.p)
        message = SDPMessage(
            sdp_header=SDPHeader(
                destination_chip_x=placement.x,
                destination_chip_y=placement.y,
                destination_cpu=placement.p,
                destination_port=constants.
                SDP_PORTS.EXTRA_MONITOR_CORE_DATA_SPEED_UP.value,
                flags=SDPFlag.REPLY_NOT_EXPECTED),
            data=data)

        # send
        self._connection.send_sdp_message(message)

        # receive
        finished = False
        seq_nums = set()
        self._output = bytearray(length_in_bytes)
        self._view = memoryview(self._output)
        self._max_seq_num = self._incoming_calculate_max_seq_num()

        time_out_count = 0
        while not finished:
            try:
                data = self._connection.receive(
                    timeout=self.TIMEOUT_PER_RECEIVE_IN_SECONDS)
                time_out_count = 0
                seq_nums, finished = self._incoming_process_data(
                    data, seq_nums, finished, placement,
                    lost_seq_nums)
            except SpinnmanTimeoutException:
                if time_out_count > TIMEOUT_RETRY_LIMIT:
                    raise exceptions.SpinnFrontEndException(
                        "Failed to hear from the machine during {} attempts. "
                        "Please try removing firewalls".format(time_out_count))
                time_out_count += 1
                remote_port = self._connection.remote_port
                local_port = self._connection.local_port
                local_ip = self._connection.local_ip_address
                remote_ip = self._connection.remote_ip_address
                self._connection.close()
                self._connection = SCAMPConnection(
                    local_port=local_port, remote_port=remote_port,
                    local_host=local_ip, remote_host=remote_ip)
                if not finished:
                    finished = self._incoming_retransmit_missing_seq_nums(
                        seq_nums, placement, lost_seq_nums)

        end = float(time.time())
        self._provenance_data_items[
                placement, memory_address,
                length_in_bytes].append((end - start, lost_seq_nums))
        return self._output

    def _calculate_incoming_missing_seq_nums(self, seq_nums):
        """ determines which sequence numbers we've missed

        :param seq_nums: the set already acquired
        :return: list of missing sequence numbers
        """
        missing_seq_nums = list()
        for seq_num in range(0, self._max_seq_num):
            if seq_num not in seq_nums:
                missing_seq_nums.append(seq_num)
        return missing_seq_nums

    def _incoming_retransmit_missing_seq_nums(
            self, seq_nums, placement, lost_seq_nums):
        """ Determines if there are any missing sequence numbers, and if so \
        retransmits the missing sequence numbers back to the core for \
        retransmission.

        :param seq_nums: the sequence numbers already received
        :param placement: placement instance
        :return: whether all packets are transmitted
        :rtype: bool
        """
        # locate missing sequence numbers from pile
        missing_seq_nums = self._calculate_incoming_missing_seq_nums(seq_nums)
        lost_seq_nums.append(len(missing_seq_nums))
        # self._print_missing(missing_seq_nums)
        if len(missing_seq_nums) == 0:
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
                struct.pack_into(
                    "<I", data, offset,
                    self.SDP_PACKET_START_MISSING_SEQ_COMMAND_ID)
                struct.pack_into(
                    "<I", data, self.WORD_TO_BYTE_CONVERTER, n_packets)

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
                struct.pack_into(
                    "<I", data, offset,
                    self.SDP_PACKET_MISSING_SEQ_COMMAND_ID)
                offset += 1 * self.WORD_TO_BYTE_CONVERTER
                length_left_in_packet -= 1

            # fill data field
            struct.pack_into(
                "<{}I".format(size_of_data_left_to_transmit), data, offset,
                *missing_seq_nums[
                 seq_num_offset:
                 seq_num_offset + size_of_data_left_to_transmit])
            seq_num_offset += length_left_in_packet

            # build SDP message
            message = SDPMessage(
                sdp_header=SDPHeader(
                    destination_chip_x=placement.x,
                    destination_chip_y=placement.y,
                    destination_cpu=placement.p,
                    destination_port=constants.
                    SDP_PORTS.EXTRA_MONITOR_CORE_DATA_SPEED_UP.value,
                    flags=SDPFlag.REPLY_NOT_EXPECTED),
                data=str(data))

            # send message to core
            self._transceiver.send_sdp_message(message=message)

            # sleep for ensuring core doesn't lose packets
            time.sleep(self.TIME_OUT_FOR_SENDING_IN_SECONDS)
            # self._print_packet_num_being_sent(packet_count, n_packets)
        return False

    def _incoming_process_data(
            self, data, seq_nums, finished, placement,
            lost_seq_nums):
        """ Takes a packet and processes it see if we're finished yet

        :param data: the packet data
        :param seq_nums: the list of sequence numbers received so far
        :param finished: bool which states if finished or not
        :param placement: placement object for location on machine
        :param lost_seq_nums: the list of n sequence numbers lost per iteration
        :return: set of data items, if its the first packet, the list of\
            sequence numbers, the sequence number received and if its finished
        """
        # self._print_out_packet_data(data)
        length_of_data = len(data)
        first_packet_element = struct.unpack_from(
            "<I", data, 0)[0]

        # get flags
        seq_num = first_packet_element & 0x7FFFFFFF
        is_end_of_stream = (
            first_packet_element & self.LAST_MESSAGE_FLAG_BIT_MASK) != 0

        # check seq num not insane
        if seq_num > self._max_seq_num:
            raise Exception(
                "got an insane sequence number. got {} when "
                "the max is {} with a length of {}".format(
                    seq_num, self._max_seq_num, length_of_data))

        # figure offset for where data is to be put
        offset = self._incoming_calculate_offset(seq_num)

        # write data
        true_data_length = offset + length_of_data - self.SEQUENCE_NUMBER_SIZE
        if not is_end_of_stream or \
                length_of_data != self.END_FLAG_SIZE_IN_BYTES:
            self._incoming_write_into_view(
                offset, true_data_length, data, self.SEQUENCE_NUMBER_SIZE,
                length_of_data, seq_num, length_of_data, False)

        # add seq num to list
        seq_nums.add(seq_num)

        # if received a last flag on its own, its during retransmission.
        #  check and try again if required
        if is_end_of_stream:
            if not self._incoming_check_recieved_all_seq_nums(seq_nums):
                finished = \
                    self._incoming_retransmit_missing_seq_nums(
                        placement=placement, seq_nums=seq_nums,
                        lost_seq_nums=lost_seq_nums)
            else:
                finished = True
        return seq_nums, finished

    def _incoming_calculate_offset(self, seq_num):
        """ figures where in the view to write data given a seq num
        
        :param seq_num: the seq num to figure the position of
        :return: the position where to start writing
        :rtype: int
        """
        return (seq_num * self.DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM *
                self.WORD_TO_BYTE_CONVERTER)

    def _incoming_write_into_view(
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
        if view_end_position > len(self._output):
            raise Exception(
                "I'm trying to add to my output data, but am trying to add "
                "outside my acceptable output positions!!!! max is {} and "
                "I received request to fill to {} for sequence num {} from max"
                " sequence num {} length of packet {} and final {}".format(
                    len(self._output), view_end_position, seq_num,
                    self._max_seq_num, packet_length, is_final))
        self._view[view_start_position: view_end_position] = \
            data[data_start_position:data_end_position]

    def _incoming_check_recieved_all_seq_nums(self, seq_nums):
        """ verifying if the sequence numbers are correct.

        :param seq_nums: the received sequence numbers
        :return: bool of true or false given if all the sequence numbers have\
            been received
        """
        # hand back
        seq_nums = sorted(seq_nums)
        max_needed = self._incoming_calculate_max_seq_num()
        if len(seq_nums) > max_needed + 1:
            raise Exception("I've received more data than I was expecting!!")
        return len(seq_nums) == max_needed + 1

    def _incoming_calculate_max_seq_num(self):
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
            logger.info("from list i'm missing sequence num %d", seq_num)

    def _print_out_packet_data(self, data):
        """ debug prints out the data from the packet

        :param data: the packet data
        :rtype: None
        """
        reread_data = struct.unpack("<{}I".format(
            int(math.ceil(len(data) / self.WORD_TO_BYTE_CONVERTER))),
            str(data))
        logger.info(
            "converted data back into readable form is %d", reread_data)

    @staticmethod
    def _print_length_of_received_seq_nums(seq_nums, max_needed):
        """ debug helper method for figuring out if everything been received

        :param seq_nums: sequence numbers received
        :param max_needed: biggest expected to have
        :rtype: None
        """
        if len(seq_nums) != max_needed:
            logger.info(
                "should have received %d sequence numbers, but received "
                "%d sequence numbers", max_needed, len(seq_nums))

    @staticmethod
    def _print_packet_num_being_sent(packet_count, n_packets):
        """ debug helper for printing missing sequence number packet\
            transmission

        :param packet_count: which packet is being fired
        :param n_packets: how many packets to fire.
        :rtype: None
        """
        logger.info(
            "send SDP packet with missing sequence numbers: %d of %d",
            packet_count + 1, n_packets)

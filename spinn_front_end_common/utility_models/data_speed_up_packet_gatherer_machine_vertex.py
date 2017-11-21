from collections import defaultdict

from pacman.model.decorators import overrides
from pacman.model.graphs.common import EdgeTrafficType
from pacman.model.graphs.machine import MachineVertex
from pacman.model.resources import ResourceContainer, SDRAMResource, \
    IPtagResource
from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary
from spinn_front_end_common.abstract_models.impl import \
    MachineDataSpecableVertex
from spinn_front_end_common.interface.provenance import \
    AbstractProvidesLocalProvenanceData
from spinn_front_end_common.utilities.utility_objs import ExecutableType, \
    ProvenanceDataItem
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.interface.simulation import simulation_utilities

from spinnman.connections.udp_packet_connections import UDPConnection
from spinnman.exceptions import SpinnmanTimeoutException
from spinnman.messages.sdp import SDPMessage, SDPHeader, SDPFlag

import math
import time
import struct
from enum import Enum


class DataSpeedUpPacketGatherMachineVertex(
        MachineVertex, MachineDataSpecableVertex, AbstractHasAssociatedBinary,
        AbstractProvidesLocalProvenanceData):

    # TRAFFIC_TYPE = EdgeTrafficType.MULTICAST
    TRAFFIC_TYPE = EdgeTrafficType.FIXED_ROUTE

    # dsg data regions
    DATA_REGIONS = Enum(
        value="DATA_REGIONS",
        names=[('SYSTEM', 0),
               ('CONFIG', 1)])

    # size of config region in bytes
    CONFIG_SIZE = 12

    # items of data a SDP packet can hold when SCP header removed
    DATA_PER_FULL_PACKET = 68  # 272 bytes as removed SCP header

    # size of items the sequence number uses
    SEQUENCE_NUMBER_SIZE_IN_ITEMS = 1

    # the size of the sequence number in bytes
    SEQUENCE_NUMBER_SIZE = 4

    # items of data from SDP packet with a sequence number
    DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM = \
        DATA_PER_FULL_PACKET - SEQUENCE_NUMBER_SIZE_IN_ITEMS

    # converter between words and bytes
    WORD_TO_BYTE_CONVERTER = 4

    # time outs used by the protocol for separate bits
    TIMEOUT_PER_RECEIVE_IN_SECONDS = 1
    TIME_OUT_FOR_SENDING_IN_SECONDS = 0.01

    # command ids for the sdp packets
    SDP_PACKET_START_SENDING_COMMAND_ID = 100
    SDP_PACKET_START_MISSING_SEQ_COMMAND_ID = 1000
    SDP_PACKET_MISSING_SEQ_COMMAND_ID = 1001

    # number of items used up by the re transmit code for its header
    SDP_RETRANSMISSION_HEADER_SIZE = 2

    # what governs a end flag
    END_FLAG = 0xFFFFFFFF

    # base key (really nasty hack)
    BASE_KEY = 0xFFFFFFF9
    BASE_MASK = 0xFFFFFFFB

    # the size in bytes of the end flag
    END_FLAG_SIZE = 4

    # the amount of bytes the n bytes takes up
    N_PACKETS_SIZE = 4

    # the amount of bytes the data length will take up
    LENGTH_OF_DATA_SIZE = 4

    THRESHOLD_WHERE_SDP_BETTER_THAN_DATA_EXTRACTOR_IN_BYTES = 40000

    def __init__(self, x, y, connection=None, constraints=None):
        MachineVertex.__init__(
            self,
            label="mc_data_speed_up_packet_gatherer_on_{}_{}".format(x, y),
            constraints=constraints)
        MachineDataSpecableVertex.__init__(self)
        AbstractHasAssociatedBinary.__init__(self)
        AbstractProvidesLocalProvenanceData.__init__(self)

        # data holders for the output, and seq nums
        self._view = None
        self._max_seq_num = None
        self._output = None

        # create socket
        if connection is None:
            self._connection = UDPConnection(local_host=None)
        else:
            self._connection = connection

        # local provenance storage
        self._provenance_data_items = defaultdict(list)

    @property
    @overrides(MachineVertex.resources_required)
    def resources_required(self):
        return self.resources_required_for_connection(self._connection)

    @staticmethod
    def resources_required_for_connection(connection):
        """ used to generate resources required given a UDP connection
        Exists for giving the app vertex access to the data without clones.

        :param connection: UDP connection for transmissions
        :return: resource container
        """
        return ResourceContainer(
            sdram=SDRAMResource(
                constants.SYSTEM_BYTES_REQUIREMENT +
                DataSpeedUpPacketGatherMachineVertex.CONFIG_SIZE),
            iptags=[IPtagResource(
                port=connection.local_port, strip_sdp=True,
                ip_address="localhost")])

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return self.static_get_binary_start_type()

    @staticmethod
    def static_get_binary_start_type():
        """ supports application vertex reading without cloning

        :return: type of start type the data speed up packet gatherer is using
        """
        return ExecutableType.SYSTEM

    @overrides(MachineDataSpecableVertex.generate_machine_data_specification)
    def generate_machine_data_specification(
            self, spec, placement, machine_graph, routing_info, iptags,
            reverse_iptags, machine_time_step, time_scale_factor):

        if self.TRAFFIC_TYPE == EdgeTrafficType.MULTICAST:
            base_key = routing_info.get_first_key_for_edge(
                list(machine_graph.get_edges_ending_at_vertex(self))[0])
        else:
            base_key = self.BASE_KEY
        self.static_generate_machine_data_specification(
            spec, base_key, machine_time_step, time_scale_factor, iptags)

    @staticmethod
    def static_generate_machine_data_specification(
            spec, base_key, machine_time_step, time_scale_factor, iptags):
        """ supports application vertices usage. writes the data spec

        :param spec: the data spec object
        :param base_key: the base key to transmit with
        :param machine_time_step: machine time step
        :param time_scale_factor: time scale factor
        :param iptags: iptags
        :return: None
        """

        # Setup words + 1 for flags + 1 for recording size
        setup_size = constants.SYSTEM_BYTES_REQUIREMENT

        # Create the data regions for hello world
        DataSpeedUpPacketGatherMachineVertex._reserve_memory_regions(
            spec, setup_size)

        # write data for the simulation data item
        spec.switch_write_focus(
            DataSpeedUpPacketGatherMachineVertex.DATA_REGIONS.SYSTEM.value)
        spec.write_array(simulation_utilities.get_simulation_header_array(
            DataSpeedUpPacketGatherMachineVertex.static_get_binary_file_name(),
            machine_time_step, time_scale_factor))
        spec.switch_write_focus(
            DataSpeedUpPacketGatherMachineVertex.DATA_REGIONS.CONFIG.value)

        # the keys for the special cases
        spec.write_value(base_key + 1)
        spec.write_value(base_key + 2)

        # locate the tag id for our data
        spec.write_value(iptags[0].tag)

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

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return self.static_get_binary_file_name()

    @staticmethod
    def static_get_binary_file_name():
        """ used for supporting a application vertex that is used as \
        only a data holder.

        :return: aplex name
        """
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

                # handle lost seq nums
                for i, n_lost_seq_nums in enumerate(lost_seq_nums):
                    prov_items.append(ProvenanceDataItem(
                        [top_level_name, "lost_seq_nums", chip_name, last_name,
                         iteration_name, "iteration_{}".format(i)],
                        n_lost_seq_nums, report=n_lost_seq_nums > 0,
                        message="During the extraction of data, {} sequences "
                                "were lost. These had to be retransmitted and"
                                " will have slowed down the data extraction "
                                "process. Reduce the number of executing "
                                "applications and remove routers between "
                                "yourself and the SpiNNaker machine to reduce"
                                " the chance of this occurring."))
        return prov_items

    @staticmethod
    def set_cores_for_data_extraction(
            transceiver, extra_monitor_cores_for_router_timeout,
            placements):
        # set time out
        extra_monitor_cores_for_router_timeout[0].set_router_time_outs(
            15, 15, transceiver, placements,
            extra_monitor_cores_for_router_timeout)

    @staticmethod
    def unset_cores_for_data_extraction(
            transceiver, extra_monitor_cores_for_router_timeout,
            placements):
        extra_monitor_cores_for_router_timeout[0].set_router_time_outs(
            15, 4, transceiver, placements,
            extra_monitor_cores_for_router_timeout)

    def get_data(
            self, transceiver, placement, memory_address, length_in_bytes):
        """ gets data from a given core and memory address.

        :param transceiver: spinnman instance
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
            data = transceiver.read_memory(
                placement.x, placement.y, memory_address, length_in_bytes)
            end = float(time.time())
            self._provenance_data_items[
                placement, memory_address,
                length_in_bytes].append((end - start, [0]))
            return data

        data = struct.pack(
            "<III", self.SDP_PACKET_START_SENDING_COMMAND_ID,
            memory_address, length_in_bytes)

        # print "sending to core {}:{}:{}".format(
        #    placement.x, placement.y, placement.p)
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
        transceiver.send_sdp_message(message=message)

        # receive
        finished = False
        first = True
        seq_num = 1
        seq_nums = set()
        while not finished:
            try:
                data = self._connection.receive(
                    timeout=self.TIMEOUT_PER_RECEIVE_IN_SECONDS)

                first, seq_num, seq_nums, finished = self._process_data(
                    data, first, seq_num, seq_nums, finished,
                    placement, transceiver, lost_seq_nums)
            except SpinnmanTimeoutException:
                if not finished:
                    finished = self._determine_and_retransmit_missing_seq_nums(
                        seq_nums, transceiver, placement, lost_seq_nums)

        end = float(time.time())
        self._provenance_data_items[
                placement, memory_address,
                length_in_bytes].append((end - start, lost_seq_nums))
        return self._output

    def _calculate_missing_seq_nums(self, seq_nums):
        """ determines which sequence numbers we've missed

        :param seq_nums: the set already acquired
        :return: list of missing seq nums
        """
        missing_seq_nums = list()
        if self._max_seq_num is None:
            raise Exception("Have not heard from the machine")
        for seq_num in range(1, self._max_seq_num):
            if seq_num not in seq_nums:
                missing_seq_nums.append(seq_num)
        return missing_seq_nums

    def _determine_and_retransmit_missing_seq_nums(
            self, seq_nums, transceiver, placement, lost_seq_nums):
        """ Determines if there are any missing sequence numbers, and if so \
        retransmits the missing sequence numbers back to the core for \
        retransmission.

        :param seq_nums: the seq nums already received
        :param transceiver: spinnman instance
        :param placement: placement instance
        :return: whether all packets are transmitted
        :rtype: bool
        """
        # locate missing seq nums from pile

        missing_seq_nums = self._calculate_missing_seq_nums(seq_nums)
        lost_seq_nums.append(len(missing_seq_nums))
        # self._print_missing(seq_nums)
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

        # transmit missing seq as a new sdp packet
        first = True
        seq_num_offset = 0
        for _ in xrange(n_packets):
            length_left_in_packet = self.DATA_PER_FULL_PACKET
            offset = 0
            data = None
            size_of_data_left_to_transmit = None

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

            # build sdp message
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
            transceiver.send_sdp_message(message=message)

            # sleep for ensuring core doesnt lose packets
            time.sleep(self.TIME_OUT_FOR_SENDING_IN_SECONDS)
            # self._print_packet_num_being_sent(packet_count, n_packets)
        return False

    def _process_data(self, data, first, seq_num, seq_nums, finished,
                      placement, transceiver, lost_seq_nums):
        """ Takes a packet and processes it see if we're finished yet

        :param data: the packet data
        :param first: if the packet is the first packet, in which has extra \
            data in header
        :param seq_num: the seq number of the packet
        :param seq_nums: the list of seq nums received so far
        :param finished: bool which states if finished or not
        :param placement: placement object for location on machine
        :param transceiver: spinnman instance
        :param lost_seq_nums: the list of n seq nums lost per iteration
        :return: set of data items, if its the first packet, the list of seq\
            nums, the seq num received and if its finished
        """
        # self._print_out_packet_data(data)
        length_of_data = len(data)
        if first:
            length = struct.unpack_from("<I", data, 0)[0]
            first = False
            self._output = bytearray(length)
            self._view = memoryview(self._output)

            # verify if there are more packets to come or if this is the last
            last_mc_packet = struct.unpack_from(
                "<I", data, length_of_data - self.END_FLAG_SIZE)[0]
            if last_mc_packet == self.END_FLAG:
                self._write_into_view(
                    0,
                    length_of_data - self.LENGTH_OF_DATA_SIZE -
                    self.END_FLAG_SIZE,
                    data, self.LENGTH_OF_DATA_SIZE,
                    length_of_data - self.END_FLAG_SIZE, seq_num,
                    length_of_data, False)
            else:
                self._write_into_view(
                    0, length_of_data - self.LENGTH_OF_DATA_SIZE,
                    data, self.LENGTH_OF_DATA_SIZE, length_of_data, seq_num,
                    length_of_data, False)

            # deduce max seq num for future use
            self._max_seq_num = self.calculate_max_seq_num()

        else:  # some data packet
            first_packet_element = struct.unpack_from(
                "<I", data, 0)[0]
            last_mc_packet = struct.unpack_from(
                "<I", data, length_of_data - self.END_FLAG_SIZE)[0]

            # if received a last flag on its own, its during retransmission.
            #  check and try again if required
            if (last_mc_packet == self.END_FLAG and
                    length_of_data == self.END_FLAG_SIZE):
                if not self._check(seq_nums):
                    finished = self._determine_and_retransmit_missing_seq_nums(
                        placement=placement, transceiver=transceiver,
                        seq_nums=seq_nums, lost_seq_nums=lost_seq_nums)
            else:
                # this flag can be dropped at some point
                seq_num = first_packet_element
                # print "seq num = {}".format(seq_num)
                if seq_num > self._max_seq_num:
                    raise Exception(
                        "got an insane sequence number. got {} when "
                        "the max is {} with a length of {}".format(
                            seq_num, self._max_seq_num, length_of_data))
                seq_nums.add(seq_num)

                # figure offset for where data is to be put
                offset = self._calculate_offset(seq_num)

                # write excess data as required
                if last_mc_packet == self.END_FLAG:

                    # adjust for end flag
                    true_data_length = (
                        length_of_data - self.END_FLAG_SIZE -
                        self.SEQUENCE_NUMBER_SIZE)

                    # write data
                    self._write_into_view(
                        offset, offset + true_data_length, data,
                        self.SEQUENCE_NUMBER_SIZE,
                        length_of_data - self.END_FLAG_SIZE, seq_num,
                        length_of_data, True)

                    # check if need to retry
                    if not self._check(seq_nums):
                        finished = \
                            self._determine_and_retransmit_missing_seq_nums(
                                placement=placement, transceiver=transceiver,
                                seq_nums=seq_nums, lost_seq_nums=lost_seq_nums)
                    else:
                        finished = True

                else:  # full block of data, just write it in
                    true_data_length = (
                        offset + length_of_data - self.SEQUENCE_NUMBER_SIZE)
                    self._write_into_view(
                        offset, true_data_length, data,
                        self.SEQUENCE_NUMBER_SIZE,
                        length_of_data, seq_num, length_of_data, False)
        return first, seq_num, seq_nums, finished

    def _calculate_offset(self, seq_num):
        offset = (seq_num * self.DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM *
                  self.WORD_TO_BYTE_CONVERTER)
        return offset

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
        :param seq_num: the seq number to figure
        :rtype: None
        """
        if view_end_position > len(self._output):
            raise Exception(
                "I'm trying to add to my output data, but am trying to add "
                "outside my acceptable output positions!!!! max is {} and "
                "I received request to fill to {} for seq num {} from max "
                "seq num {} length of packet {} and final {}".format(
                    len(self._output), view_end_position, seq_num,
                    self._max_seq_num, packet_length, is_final))
        self._view[view_start_position: view_end_position] = \
            data[data_start_position:data_end_position]

    def _check(self, seq_nums):
        """ verifying if the sequence numbers are correct.

        :param seq_nums: the received seq nums
        :return: bool of true or false given if all the seq nums been received
        """
        # hand back
        seq_nums = sorted(seq_nums)
        max_needed = self.calculate_max_seq_num()
        if len(seq_nums) > max_needed:
            raise Exception(
                "I've received more data than I was expecting!!")
        return len(seq_nums) == max_needed

    def calculate_max_seq_num(self):
        """ deduces the max seq num expected to be received

        :return: int of the biggest seq num expected
        """
        n_sequence_numbers = 0
        data_left = len(self._output) - (
            (self.DATA_PER_FULL_PACKET - self.SDP_RETRANSMISSION_HEADER_SIZE) *
            self.WORD_TO_BYTE_CONVERTER)

        extra_n_sequences = float(data_left) / float(
            self.DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM *
            self.WORD_TO_BYTE_CONVERTER)
        n_sequence_numbers += math.ceil(extra_n_sequences)
        return int(n_sequence_numbers)

    @staticmethod
    def _print_missing(seq_nums):
        """ debug printer for the missing seq nums from the pile

        :param seq_nums: the seq nums received so far
        :rtype: None
        """
        last_seq_num = 0
        for seq_num in sorted(seq_nums):
            if seq_num != last_seq_num + 1:
                print "from list im missing seq num {}".format(seq_num)
            last_seq_num = seq_num

    def _print_out_packet_data(self, data):
        """ debug prints out the data from the packet

        :param data: the packet data
        :rtype: None
        """
        reread_data = struct.unpack("<{}I".format(
            int(math.ceil(len(data) / self.WORD_TO_BYTE_CONVERTER))),
            str(data))
        print "converted data back into readable form is {}" \
            .format(reread_data)

    @staticmethod
    def _print_length_of_received_seq_nums(seq_nums, max_needed):
        """ debug helper method for figuring out if everything been received

        :param seq_nums: seq nums received
        :param max_needed: biggest expected to have
        :rtype: None
        """
        if len(seq_nums) != max_needed:
            print "should have received {} sequence numbers, but received " \
                  "{} sequence numbers".format(max_needed, len(seq_nums))

    @staticmethod
    def _print_packet_num_being_sent(packet_count, n_packets):
        """ debug helper for printing missing seq num packet transmission

        :param packet_count: which packet is being fired
        :param n_packets: how many packets to fire.
        :rtype: None
        """
        print("send sdp packet with missing seq nums: {} of {}".format(
            packet_count + 1, n_packets))

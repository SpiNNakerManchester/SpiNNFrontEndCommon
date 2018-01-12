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

from spinnman.exceptions import SpinnmanTimeoutException
from spinnman.messages.sdp import SDPMessage, SDPHeader, SDPFlag
from spinnman.connections.udp_packet_connections import SCAMPConnection

import logging
import math
import time
import struct
from enum import Enum
from pacman.executor.injection_decorator import inject_items

#===============================================================================
# from spinn_front_end_common.utility_models.host_data_receiver import host_data_receiver
# from ctypes import *
#===============================================================================

TIMEOUT_RETRY_LIMIT = 20
logger = logging.getLogger(__name__)


class DataSpeedUpPacketGatherMachineVertex(
        MachineVertex, AbstractGeneratesDataSpecification,
        AbstractHasAssociatedBinary, AbstractProvidesLocalProvenanceData):

    # TRAFFIC_TYPE = EdgeTrafficType.MULTICAST
    TRAFFIC_TYPE = EdgeTrafficType.FIXED_ROUTE

    # dsg data regions
    DATA_REGIONS = Enum(
        value="DATA_REGIONS",
        names=[('SYSTEM', 0),
               ('CONFIG', 1)])

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

    # the size in bytes of the end flag
    LAST_MESSAGE_FLAG_BIT_MASK = 0x80000000

    # the amount of bytes the n bytes takes up
    N_PACKETS_SIZE = 4

    # the amount of bytes the data length will take up
    LENGTH_OF_DATA_SIZE = 4

    THRESHOLD_WHERE_SDP_BETTER_THAN_DATA_EXTRACTOR_IN_BYTES = 40000

    def __init__(self, x, y, ip_address, constraints=None):
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

        # Create a connection to be used
        self._connection = SCAMPConnection(
            chip_x=x, chip_y=y, remote_host=ip_address)

        # local provenance storage
        self._provenance_data_items = defaultdict(list)

        self.tag = None

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
            self, spec, placement, machine_graph, routing_info, tags,
            machine_time_step, time_scale_factor):

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
        self.tag = iptag.tag
        iptag.port = self._connection.local_port
        spec.write_value(iptag.tag)

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
                        message=
                        "During the extraction of data of {} bytes from "
                        "memory address {}, attempt {} had {} sequences that "
                        "were lost. These had to be retransmitted and will "
                        "have slowed down the data extraction process. "
                        "Reduce the number of executing applications and "
                        "remove routers between yourself and the SpiNNaker "
                        "machine to reduce the chance of this occurring."
                        .format(length_in_bytes, memory_address, i,
                                n_lost_seq_nums)))
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

        message = SDPMessage(
            sdp_header=SDPHeader(
                destination_chip_x=placement.x,
                destination_chip_y=placement.y,
                destination_cpu=placement.p,
                destination_port=0,
                flags=SDPFlag.REPLY_NOT_EXPECTED),
            data=None)

        connection = transceiver.scamp_connection_selector.get_next_connection(message)
        chip_x = connection.chip_x
        chip_y = connection.chip_y


        receiver = host_data_receiver()
        buf = receiver.get_data_for_python(str(connection.remote_ip_address),
                          int(constants.SDP_PORTS.EXTRA_MONITOR_CORE_DATA_SPEED_UP.value),
                          int(placement.x),
                          int(placement.y),
                          int(placement.p),
                          int(length_in_bytes),
                          int(memory_address),
                          int(chip_x),
                          int(chip_y),
                          int(self.tag))


        return bytearray(buf)

    def get_iptag(self):
        return self.tag

    def get_port(self):
        return constants.SDP_PORTS.EXTRA_MONITOR_CORE_DATA_SPEED_UP.value

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

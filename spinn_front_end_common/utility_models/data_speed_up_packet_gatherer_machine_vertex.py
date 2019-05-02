try:
    from collections.abc import defaultdict
except ImportError:
    from collections import defaultdict
import os
import datetime
import logging
import math
import time
import struct
import sys
from enum import Enum
from six.moves import xrange
from six import reraise
from spinn_utilities.overrides import overrides
from spinn_utilities.log import FormatAdapter
from spinnman.exceptions import SpinnmanTimeoutException
from spinnman.messages.sdp import SDPMessage, SDPHeader, SDPFlag
from spinnman.messages.scp.impl.iptag_set import IPTagSet
from spinnman.connections.udp_packet_connections import SCAMPConnection
from spinnman.model.enums.cpu_state import CPUState
from pacman.executor.injection_decorator import inject_items
from pacman.model.graphs.common import EdgeTrafficType
from pacman.model.graphs.machine import MachineVertex
from pacman.model.resources import (
    ResourceContainer, SDRAMResource, IPtagResource)
from spinn_storage_handlers import FileDataReader
from spinn_front_end_common.utilities.globals_variables import get_simulator
from spinn_front_end_common.utilities.helpful_functions import (
    convert_vertices_to_core_subset, emergency_recover_state_from_failure)
from spinn_front_end_common.abstract_models import (
    AbstractHasAssociatedBinary, AbstractGeneratesDataSpecification)
from spinn_front_end_common.interface.provenance import (
    AbstractProvidesLocalProvenanceData)
from spinn_front_end_common.utilities.utility_objs import (
    ExecutableType, ProvenanceDataItem)
from spinn_front_end_common.utilities.constants import (
    SDP_PORTS, SYSTEM_BYTES_REQUIREMENT)
from spinn_front_end_common.utilities.exceptions import SpinnFrontEndException
from spinn_front_end_common.interface.simulation import simulation_utilities

log = FormatAdapter(logging.getLogger(__name__))
TIMEOUT_RETRY_LIMIT = 20
TIMEOUT_MESSAGE = "Failed to hear from the machine during {} attempts. "\
    "Please try removing firewalls."

# number of items used up by the retransmit code for its header
SDP_RETRANSMISSION_HEADER_SIZE = 2

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

# the amount of bytes the n bytes takes up
N_PACKETS_SIZE = 4

# the amount of bytes the data length will take up
LENGTH_OF_DATA_SIZE = 4

# points where SDP beats data speed up due to overheads
THRESHOLD_WHERE_SDP_BETTER_THAN_DATA_EXTRACTOR_IN_BYTES = 40000
THRESHOLD_WHERE_SDP_BETTER_THAN_DATA_INPUT_IN_BYTES = 300

# offset where data in starts on first command
# (command, base_address, x&y, max_seq_number)
OFFSET_AFTER_COMMAND_AND_ADDRESS_IN_BYTES = 16

# offset where data starts after a command id and seq number
OFFSET_AFTER_COMMAND_AND_SEQUENCE_IN_BYTES = 8

# size for data to store when first packet with command and address
DATA_IN_FULL_PACKET_WITH_ADDRESS = \
    DATA_PER_FULL_PACKET - (OFFSET_AFTER_COMMAND_AND_ADDRESS_IN_BYTES //
                            WORD_TO_BYTE_CONVERTER)

# size for data in to store when not first packet
DATA_IN_FULL_PACKET_WITHOUT_ADDRESS = \
    DATA_PER_FULL_PACKET - (OFFSET_AFTER_COMMAND_AND_SEQUENCE_IN_BYTES //
                            WORD_TO_BYTE_CONVERTER)

# size of data in key space
# x, y, key (all ints) for possible 48 chips,
SIZE_DATA_IN_CHIP_TO_KEY_SPACE = (3 * 4 * 48) + 4

# DSG data regions
_DATA_REGIONS = Enum(
    value="DATA_REGIONS",
    names=[('SYSTEM', 0),
           ('CONFIG', 1),
           ('CHIP_TO_KEY_SPACE', 2)])

# precompiled structures
_ONE_WORD = struct.Struct("<I")
_TWO_WORDS = struct.Struct("<II")
_THREE_WORDS = struct.Struct("<III")
_FOUR_WORDS = struct.Struct("<IIII")


def ceildiv(dividend, divisor):
    """ How to divide two possibly-integer numbers and round up.
    """
    return int(math.ceil(float(dividend) / float(divisor)))


# SDRAM requirement for storing missing SDP packets seq nums
SDRAM_FOR_MISSING_SDP_SEQ_NUMS = ceildiv(
    120.0 * 1024 * 1024,
    DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM * WORD_TO_BYTE_CONVERTER)


class DataSpeedUpPacketGatherMachineVertex(
        MachineVertex, AbstractGeneratesDataSpecification,
        AbstractHasAssociatedBinary, AbstractProvidesLocalProvenanceData):
    __slots__ = [
        "_x", "_y",
        "_app_id",
        "_connection",
        # store of the extra monitors to location. helpful in data in
        "_extra_monitors_by_chip",
        # boolean tracker for handling out of order packets
        "_have_received_missing_seq_count_packet",
        # path for the data in report
        "_in_report_path",
        "_ip_address",
        # store for the last reinjection status
        "_last_status",
        # the max seq num expected given a data retrieval
        "_max_seq_num",
        # holder for missing seq nums for data in
        "_missing_seq_nums_data_in",
        # holder of data from out
        "_output",
        # my placement for future lookup
        "_placement",
        # provenance holder
        "_provenance_data_items",
        "_remote_tag",
        # path to the data out report
        "_out_report_path",
        # tracker for expected missing seq nums
        "_total_expected_missing_seq_packets",
        "_write_data_speed_up_reports",
        # data holder for output
        "_view"]

    # base key (really nasty hack to tie in fixed route keys)
    BASE_KEY = 0xFFFFFFF9
    NEW_SEQ_KEY = 0xFFFFFFF8
    FIRST_DATA_KEY = 0xFFFFFFF7
    END_FLAG_KEY = 0xFFFFFFF6

    # to use with multicast stuff
    BASE_MASK = 0xFFFFFFFB
    NEW_SEQ_KEY_OFFSET = 1
    FIRST_DATA_KEY_OFFSET = 2
    END_FLAG_KEY_OFFSET = 3

    # throttle on the transmission
    TRANSMISSION_THROTTLE_TIME = 0.000001

    # TRAFFIC_TYPE = EdgeTrafficType.MULTICAST
    TRAFFIC_TYPE = EdgeTrafficType.FIXED_ROUTE

    # report names for tracking used routers
    OUT_REPORT_NAME = "routers_used_in_speed_up_process.txt"
    IN_REPORT_NAME = "speeds_gained_in_speed_up_process.txt"

    # the end flag is set when the high bit of the sequence number word is set
    LAST_MESSAGE_FLAG_BIT_MASK = 0x80000000
    # corresponding mask for the actual sequence numbers
    SEQUENCE_NUMBER_MASK = 0x7fffffff

    # time outs used by the protocol for separate bits
    TIMEOUT_PER_RECEIVE_IN_SECONDS = 1
    TIME_OUT_FOR_SENDING_IN_SECONDS = 0.01

    # The SDP port that we use
    SDP_PORT = SDP_PORTS.EXTRA_MONITOR_CORE_DATA_SPEED_UP.value

    # command IDs for the SDP packets for data out
    SDP_PACKET_START_SENDING_COMMAND_ID = 100
    SDP_PACKET_START_MISSING_SEQ_COMMAND_ID = 1000
    SDP_PACKET_MISSING_SEQ_COMMAND_ID = 1001
    SDP_PACKET_CLEAR = 2000

    # command IDs for the SDP packets for data in
    SDP_PACKET_SEND_DATA_TO_LOCATION_COMMAND_ID = 200
    SDP_PACKET_SEND_SEQ_DATA_COMMAND_ID = 2000
    SDP_PACKET_SEND_LAST_DATA_IN_COMMAND_ID = 2002
    SDP_PACKET_RECEIVE_FIRST_MISSING_SEQ_DATA_IN_COMMAND_ID = 2003
    SDP_PACKET_RECEIVE_MISSING_SEQ_DATA_IN_COMMAND_ID = 2004
    SDP_PACKET_RECEIVE_FINISHED_DATA_IN_COMMAND_ID = 2005

    # end flag for missing seq nums
    MISSING_SEQ_NUMS_END_FLAG = 0xFFFFFFFF

    _ADDRESS_PACKET_BYTE_FORMAT = struct.Struct(
        "<{}B".format(DATA_IN_FULL_PACKET_WITH_ADDRESS *
                      WORD_TO_BYTE_CONVERTER))

    def __init__(
            self, x, y, extra_monitors_by_chip, ip_address,
            report_default_directory,
            write_data_speed_up_reports, constraints=None):
        super(DataSpeedUpPacketGatherMachineVertex, self).__init__(
            label="mc_data_speed_up_packet_gatherer_on_{}_{}".format(x, y),
            constraints=constraints)

        # data holders for the output, and sequence numbers
        self._view = None
        self._max_seq_num = None
        self._output = None

        # store of the extra monitors to location. helpful in data in
        self._extra_monitors_by_chip = extra_monitors_by_chip
        self._total_expected_missing_seq_packets = 0
        self._have_received_missing_seq_count_packet = False
        self._missing_seq_nums_data_in = list()
        self._missing_seq_nums_data_in.append(list())

        # Create a connection to be used
        self._x = x
        self._y = y
        self._ip_address = ip_address
        self._remote_tag = None
        self._connection = None

        # local provenance storage
        self._provenance_data_items = defaultdict(list)
        self._placement = None
        self._app_id = None

        # create report if it doesn't already exist
        self._out_report_path = \
            os.path.join(report_default_directory, self.OUT_REPORT_NAME)
        self._in_report_path = \
            os.path.join(report_default_directory, self.IN_REPORT_NAME)
        self._write_data_speed_up_reports = write_data_speed_up_reports

        # Stored reinjection status for resetting timeouts
        self._last_status = None

    def __throttled_send(self, message):
        """ slows down transmissions to allow spinnaker to keep up.

        :param message: message to send
        :param connection: the connection to send down
        :rtype: None
        """
        # send first message
        self._connection.send_sdp_message(message)
        time.sleep(self.TRANSMISSION_THROTTLE_TIME)

    @property
    @overrides(MachineVertex.resources_required)
    def resources_required(self):
        return self.static_resources_required()

    @staticmethod
    def static_resources_required():
        return ResourceContainer(
            sdram=SDRAMResource(
                SYSTEM_BYTES_REQUIREMENT + CONFIG_SIZE +
                SDRAM_FOR_MISSING_SDP_SEQ_NUMS +
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
        "machine": "MemoryExtendedMachine",
        "app_id": "APPID"
    })
    @overrides(
        AbstractGeneratesDataSpecification.generate_data_specification,
        additional_arguments={
            "machine_graph", "routing_info", "tags",
            "machine_time_step", "time_scale_factor",
            "mc_data_chips_to_keys", "machine", "app_id"
        })
    def generate_data_specification(
            self, spec, placement, machine_graph, routing_info, tags,
            machine_time_step, time_scale_factor, mc_data_chips_to_keys,
            machine, app_id):
        # pylint: disable=too-many-arguments, arguments-differ

        # update my placement for future knowledge
        self._placement = placement
        self._app_id = app_id

        # Setup words + 1 for flags + 1 for recording size
        setup_size = SYSTEM_BYTES_REQUIREMENT

        # Create the data regions for hello world
        self._reserve_memory_regions(spec, setup_size)

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

        # locate the tag ID for our data and update with a port
        # Note: The port doesn't matter as we are going to override this later
        iptags = tags.get_ip_tags_for_vertex(self)
        iptag = iptags[0]
        iptag.port = 10000
        spec.write_value(iptag.tag)
        self._remote_tag = iptag.tag

        # write mc chip key map
        spec.switch_write_focus(_DATA_REGIONS.CHIP_TO_KEY_SPACE.value)
        chips_on_board = list(machine.get_chips_on_board(
            machine.get_chip_at(placement.x, placement.y)))

        # write how many chips to read
        spec.write_value(len(chips_on_board))

        # write each chip x and y and base key
        for (chip_x, chip_y) in chips_on_board:
            board_chip_x, board_chip_y = self._calculate_fake_chip_id(
                chip_x, chip_y, placement.x, placement.y, machine)
            spec.write_value(board_chip_x)
            spec.write_value(board_chip_y)
            spec.write_value(mc_data_chips_to_keys[chip_x, chip_y])
            # log.info("for chip {}:{} base key is {}".format(
            #    chip_x, chip_y, mc_data_chips_to_keys[chip_x, chip_y]))

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
            size=CONFIG_SIZE,
            label="config")
        spec.reserve_memory_region(
            region=_DATA_REGIONS.CHIP_TO_KEY_SPACE.value,
            size=SIZE_DATA_IN_CHIP_TO_KEY_SPACE,
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
        """ supports other components figuring out which gather and function \
        to call for writing data onto spinnaker

        :param uses_advanced_monitors: \
            Whether the system is using advanced monitors
        :type uses_advanced_monitors: bool
        :param machine: the SpiNNMachine instance
        :param x: the chip x coordinate to write data to
        :param y: the chip y coordinate to write data to
        :param extra_monitor_cores_to_ethernet_connection_map: \
            mapping between cores and connections
        :param transceiver: the SpiNNMan instance
        :return: a write function of either a LPG or the spinnMan
        :rtype: func
        """
        if not uses_advanced_monitors:
            return transceiver.write_memory

        chip = machine.get_chip_at(x, y)
        ethernet_connected_chip = machine.get_chip_at(
            chip.nearest_ethernet_x, chip.nearest_ethernet_y)
        gatherer = extra_monitor_cores_to_ethernet_connection_map[
            ethernet_connected_chip.x, ethernet_connected_chip.y]
        return gatherer.send_data_into_spinnaker

    def _generate_data_in_report(
            self, time_diff, data_size, x, y,
            address_written_to, missing_seq_nums):
        """ writes the data in report for this stage

        :param time_took_ms: the time taken to write the memory
        :param data_size: the size of data that was written in bytes
        :param x: the location in machine where the data was written to X axis
        :param y: the location in machine where the data was written to Y axis
        :param address_written_to: where in SDRAM it was written to
        :param missing_seq_nums: \
            the set of missing sequence numbers per data transmission attempt
        :rtype: None
        """
        if not os.path.isfile(self._in_report_path):
            with open(self._in_report_path, "w") as writer:
                writer.write(
                    "x\t\t y\t\t SDRAM address\t\t size in bytes\t\t\t"
                    " time took \t\t\t Mb/s \t\t\t missing sequence numbers\n")
                writer.write(
                    "------------------------------------------------"
                    "------------------------------------------------"
                    "-------------------------------------------------\n")

        time_took_ms = float(time_diff.microseconds +
                             time_diff.total_seconds() * 1000000)
        megabits = (data_size * 8.0) / (1024.0 * 1024.0)
        if time_took_ms == 0:
            mbs = "unknown, below threshold"
        else:
            mbs = megabits / (float(time_took_ms) / 100000.0)

        with open(self._in_report_path, "a") as writer:
            writer.write(
                "{}\t\t {}\t\t {}\t\t {}\t\t\t\t {}\t\t\t {}\t\t {}\n".format(
                    x, y, address_written_to, data_size, time_took_ms,
                    mbs, missing_seq_nums))

    def sent_via_sdp(self, n_bytes, x, y, base_address, data, offset, cpu):
        """ Send by SDP; if better via speed up, it returns false.

        :param n_bytes: data size
        :param x: placement x
        :param y: placement y
        :param base_address: address to write to
        :param data: data to write
        :param offset: offset in data to start from
        :return: \
            Whether used SDP, otherwise didn't send and should use speed up
        :rtype: bool
        """
        if n_bytes is None or n_bytes >= \
                THRESHOLD_WHERE_SDP_BETTER_THAN_DATA_INPUT_IN_BYTES:
            return False

        transceiver = get_simulator().transceiver

        # start time recording
        start = datetime.datetime.now()
        # write the data
        transceiver.write_memory(
            x=x, y=y, base_address=base_address, n_bytes=n_bytes,
            data=data, offset=offset, is_filename=False, cpu=cpu)
        # record when finished
        end = datetime.datetime.now()

        # write report
        if self._write_data_speed_up_reports:
            self._generate_data_in_report(
                x=x, y=y, time_diff=end - start, data_size=n_bytes,
                address_written_to=base_address, missing_seq_nums=[[]])
        return True

    def send_data_into_spinnaker(
            self, x, y, base_address, data, n_bytes=None, offset=0,
            cpu=0, is_filename=False):
        """ sends a block of data into SpiNNaker to a given chip

        :param x: chip x for data
        :param y: chip y for data
        :param base_address: the address in SDRAM to start writing memory
        :param data: the data to write
        :param n_bytes: how many bytes to read, or None if not set
        :param offset: where in the data to start from
        :param is_filename: whether data is actually a file.
        :type is_filename: bool
        :rtype: None
        """
        # if file, read in and then process as normal
        if is_filename:
            if offset != 0:
                raise Exception(
                    "when using a file, you can only have a offset of 0")

            reader = FileDataReader(data)
            if n_bytes is None:
                n_bytes = os.stat(data).st_size
                data = reader.readall()
            else:
                data = reader.read(n_bytes)
        elif n_bytes is None:
            n_bytes = len(data)

        # if not worth using extra monitors, send via sdp
        if not self.sent_via_sdp(
                base_address=base_address, x=x, y=y, offset=offset,
                data=data, n_bytes=n_bytes, cpu=cpu):
            transceiver = get_simulator().transceiver

            # start time recording
            start = datetime.datetime.now()
            # send data
            self._send_data_via_extra_monitors(
                transceiver, x, y, base_address, data[offset:n_bytes + offset])
            # end time recording
            end = datetime.datetime.now()

            # write report
            if self._write_data_speed_up_reports:
                self._generate_data_in_report(
                    x=x, y=y, time_diff=end - start,
                    data_size=n_bytes, address_written_to=base_address,
                    missing_seq_nums=self._missing_seq_nums_data_in)

    @staticmethod
    def _calculate_fake_chip_id(chip_x, chip_y, eth_x, eth_y, machine):
        """ converts between real and board based fake chip IDs

        :param chip_x: the real chip x in the real machine
        :param chip_y: the chip chip y in the real machine
        :param eth_x: the ethernet x to make board based
        :param eth_y: the ethernet y to make board based
        :param machine: the real machine
        :return: chip x and y for the real chip as if it was 1 board machine
        :rtype: tuple(int,int)
        """
        fake_x = chip_x - eth_x
        if fake_x < 0:
            fake_x += machine.max_chip_x + 1
        fake_y = chip_y - eth_y
        if fake_y < 0:
            fake_y += machine.max_chip_y + 1
        return fake_x, fake_y

    def _send_data_via_extra_monitors(
            self, transceiver, destination_chip_x, destination_chip_y,
            start_address, data_to_write):
        """ sends data using the extra monitor cores

        :param transceiver: the SpiNNMan instance
        :param destination_chip_x: chip x
        :param destination_chip_y: chip y
        :param start_address: start address in sdram to write data to
        :param data_to_write: the data to write
        :rtype: None
        """
        # where in data we've sent up to
        position_in_data = 0

        # how many packets after first one we need to send
        number_of_packets = ceildiv(
            len(data_to_write) - (
                DATA_IN_FULL_PACKET_WITH_ADDRESS * WORD_TO_BYTE_CONVERTER),
            DATA_IN_FULL_PACKET_WITHOUT_ADDRESS *
            WORD_TO_BYTE_CONVERTER) + 1

        # determine board chip IDs, as the LPG does not know machine scope IDs
        board_destination_chip_x, board_destination_chip_y = \
            self._calculate_fake_chip_id(
                destination_chip_x, destination_chip_y,
                self._placement.x, self._placement.y,
                transceiver.get_machine_details())

        # compressed destination chip data
        chip_data = (
            (board_destination_chip_x << 16) | board_destination_chip_y)

        # send first packet to lpg, stating where to send it to
        data = bytearray(DATA_PER_FULL_PACKET * WORD_TO_BYTE_CONVERTER)

        _FOUR_WORDS.pack_into(
            data, 0, self.SDP_PACKET_SEND_DATA_TO_LOCATION_COMMAND_ID,
            start_address, chip_data, number_of_packets)
        self._ADDRESS_PACKET_BYTE_FORMAT.pack_into(
            data, OFFSET_AFTER_COMMAND_AND_ADDRESS_IN_BYTES,
            *data_to_write[position_in_data:(
                DATA_IN_FULL_PACKET_WITH_ADDRESS * WORD_TO_BYTE_CONVERTER)])

        # debug
        # self._print_out_packet_data(data)

        # update where in data we've sent up to
        position_in_data = (
            DATA_IN_FULL_PACKET_WITH_ADDRESS * WORD_TO_BYTE_CONVERTER)

        message = SDPMessage(
            sdp_header=SDPHeader(
                destination_chip_x=self._placement.x,
                destination_chip_y=self._placement.y,
                destination_cpu=self._placement.p,
                destination_port=(
                    SDP_PORTS.EXTRA_MONITOR_CORE_DATA_SPEED_UP.value),
                flags=SDPFlag.REPLY_NOT_EXPECTED),
            data=data)

        # send first message
        self._connection = SCAMPConnection(
            chip_x=self._x, chip_y=self._y, remote_host=self._ip_address)
        self.__reprogram_tag(self._connection)
        self._connection.send_sdp_message(message)

        # send initial attempt at sending all the data
        self._send_all_data_based_packets(
            number_of_packets, data_to_write, position_in_data)

        # verify completed
        received_confirmation = False
        time_out_count = 0
        while not received_confirmation:
            try:
                # try to receive a confirmation of some sort from spinnaker
                data = self._connection.receive(
                    timeout=self.TIMEOUT_PER_RECEIVE_IN_SECONDS)
                time_out_count = 0

                # check which message type we have received
                received_confirmation = self._outgoing_process_packet(
                    data, data_to_write)

            except SpinnmanTimeoutException:  # if time out, keep trying
                # if the timeout has not occurred x times, keep trying
                if time_out_count > TIMEOUT_RETRY_LIMIT:
                    emergency_recover_state_from_failure(
                        transceiver, self._app_id, self, self._placement)
                    raise SpinnFrontEndException(
                        TIMEOUT_MESSAGE.format(time_out_count))

                # reopen the connection and try again
                time_out_count += 1
                remote_port = self._connection.remote_port
                local_port = self._connection.local_port
                local_ip = self._connection.local_ip_address
                remote_ip = self._connection.remote_ip_address
                self._connection.close()
                self._connection = SCAMPConnection(
                    local_port=local_port, remote_port=remote_port,
                    local_host=local_ip, remote_host=remote_ip)

                # if we have not received confirmation of finish, try to
                # retransmit missing seq nums
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
        n_elements = (len(data) - position) // LENGTH_OF_DATA_SIZE

        # store missing
        self._missing_seq_nums_data_in[-1].extend(struct.unpack_from(
            "<{}I".format(n_elements), data, position))

        # determine if last element is end flag
        if self._missing_seq_nums_data_in[-1][-1] == \
                self.MISSING_SEQ_NUMS_END_FLAG:
            del self._missing_seq_nums_data_in[-1][-1]
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
        command_id = _ONE_WORD.unpack_from(data, 0)[0]
        position += COMMAND_ID_SIZE
        # log.info("received packet with id {}\n".format(command_id))

        # process first missing
        if command_id == \
                self.SDP_PACKET_RECEIVE_FIRST_MISSING_SEQ_DATA_IN_COMMAND_ID:

            # find total missing
            self._total_expected_missing_seq_packets += \
                _ONE_WORD.unpack_from(data, position)[0]
            position += MISSING_SEQ_PACKET_COUNT_SIZE
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
        return (command_id ==
                self.SDP_PACKET_RECEIVE_FINISHED_DATA_IN_COMMAND_ID)

    def _outgoing_retransmit_missing_seq_nums(self, data_to_write):
        """ Transmits back into SpiNNaker the missing data based off missing\
            sequence numbers

        :param data_to_write: the data to write.
        :rtype: None
        """
        for missing_seq_num in self._missing_seq_nums_data_in[-1]:
            message, _length = self._calculate_data_in_data_from_seq_number(
                data_to_write, missing_seq_num,
                self.SDP_PACKET_SEND_SEQ_DATA_COMMAND_ID, None)
            self.__throttled_send(message)

        self._missing_seq_nums_data_in.append(list())
        self._total_expected_missing_seq_packets = 0
        self._have_received_missing_seq_count_packet = False
        self._send_end_flag()

    def _calculate_position_from_seq_number(self, seq_num):
        """ Calculates where in the raw data to start reading from, given a\
            sequence number

        :param seq_num: the sequence number to determine position from
        :return: the position in the byte data
        :rtype: int
        """
        if seq_num == 0:
            return 0
        if seq_num == 1:
            return DATA_IN_FULL_PACKET_WITH_ADDRESS * WORD_TO_BYTE_CONVERTER
        return WORD_TO_BYTE_CONVERTER * (
            DATA_IN_FULL_PACKET_WITH_ADDRESS +
            DATA_IN_FULL_PACKET_WITHOUT_ADDRESS * (seq_num - 1))

    def _calculate_data_in_data_from_seq_number(
            self, data_to_write, seq_num, command_id, position):
        """ Determine the data needed to be sent to the SpiNNaker machine\
            given a sequence number

        :param data_to_write: the data to write to the SpiNNaker machine
        :param seq_num: the seq num to ge tthe data for
        :param position: the position in the data to write to spinnaker
        :type position: int or None
        :return: SDP message and how much data has been written
        :rtype: SDP message
        """

        # check for last packet
        packet_data_length = (
            DATA_IN_FULL_PACKET_WITHOUT_ADDRESS * WORD_TO_BYTE_CONVERTER)

        # determine position in data if not given
        if position is None:
            position = self._calculate_position_from_seq_number(seq_num)

        # if less than a full packet worth of data, adjust length
        if position + packet_data_length > len(data_to_write):
            packet_data_length = len(data_to_write) - position

        if packet_data_length < 0:
            raise Exception()

        # determine the true packet length (with header)
        packet_length = (
            packet_data_length + OFFSET_AFTER_COMMAND_AND_SEQUENCE_IN_BYTES)

        # create struct
        packet_data = bytearray(packet_length)
        _TWO_WORDS.pack_into(packet_data, 0, command_id, seq_num)
        struct.pack_into(
            "<{}B".format(packet_data_length), packet_data,
            OFFSET_AFTER_COMMAND_AND_SEQUENCE_IN_BYTES,
            *data_to_write[position:position+packet_data_length])

        # debug
        # self._print_out_packet_data(packet_data)

        # build sdp packet
        message = SDPMessage(
            sdp_header=SDPHeader(
                destination_chip_x=self._placement.x,
                destination_chip_y=self._placement.y,
                destination_cpu=self._placement.p,
                destination_port=SDP_PORTS.
                EXTRA_MONITOR_CORE_DATA_IN_SPEED_UP.value,
                flags=SDPFlag.REPLY_NOT_EXPECTED),
            data=packet_data)

        # return message for sending, and the length in data sent
        return message, packet_data_length

    def _send_end_flag(self):
        # send end flag as separate message
        packet_data = _ONE_WORD.pack(
            self.SDP_PACKET_SEND_LAST_DATA_IN_COMMAND_ID)

        # send sdp packet
        message = SDPMessage(
            sdp_header=SDPHeader(
                destination_chip_x=self._placement.x,
                destination_chip_y=self._placement.y,
                destination_cpu=self._placement.p,
                destination_port=(
                    SDP_PORTS.EXTRA_MONITOR_CORE_DATA_IN_SPEED_UP.value),
                flags=SDPFlag.REPLY_NOT_EXPECTED),
            data=packet_data)
        self._connection.send_sdp_message(message)

    def _send_all_data_based_packets(
            self, number_of_packets, data_to_write, position_in_data):
        """ Send all the data as one block

        :param number_of_packets: the number of packets expected to send
        :param data_to_write: the data to send
        :param position_in_data: where in the data we are currently up to.
        :rtype: None
        """
        #  send rest of data
        total_data_length = len(data_to_write)
        for seq_num in range(1, number_of_packets + 1):

            # put in command flag and seq num
            message, length_to_send = \
                self._calculate_data_in_data_from_seq_number(
                    data_to_write, seq_num,
                    self.SDP_PACKET_SEND_SEQ_DATA_COMMAND_ID,
                    position_in_data)
            position_in_data += length_to_send

            # send the message
            self.__throttled_send(message)

            # check for end flag
            if position_in_data == total_data_length:
                self._send_end_flag()

    def set_cores_for_data_streaming(
            self, transceiver, extra_monitor_cores, placements):
        """ Helper method for setting the router timeouts to a state usable\
            for data streaming

        :param transceiver: the SpiNNMan instance
        :param extra_monitor_cores: the extra monitor cores to set
        :param placements: placements object
        :rtype: None
        """
        # Store the last reinjection status for resetting
        # NOTE: This assumes the status is the same on all cores
        self._last_status = extra_monitor_cores[0].get_reinjection_status(
            placements, transceiver)

        # Set to not inject dropped packets
        extra_monitor_cores[0].set_reinjection_packets(
            placements, extra_monitor_cores, transceiver,
            point_to_point=False, multicast=False, nearest_neighbour=False,
            fixed_route=False)

        # Clear any outstanding packets from reinjection
        extra_monitor_cores[0].clear_reinjection_queue(
            transceiver, placements, extra_monitor_cores)

        # set time outs
        extra_monitor_cores[0].set_router_emergency_timeout(
            1, 1, transceiver, placements, extra_monitor_cores)
        extra_monitor_cores[0].set_router_time_outs(
            15, 15, transceiver, placements, extra_monitor_cores)

    @staticmethod
    def set_application_routing_tables(
            transceiver, extra_monitor_cores, placements):
        """ Set all chips to have application table reloaded

        :param transceiver: the SpiNNMan instance
        :param extra_monitor_cores: the extra monitor cores to set
        :param placements: placements object
        :rtype: None
        """
        extra_monitor_cores[0].set_up_application_mc_routes(
            placements, extra_monitor_cores, transceiver)

    def unset_cores_for_data_streaming(
            self, transceiver, extra_monitor_cores, placements):
        """ Helper method for setting the router timeouts to a state usable\
            for data streaming

        :param transceiver: the SpiNNMan instance
        :param extra_monitor_cores: the extra monitor cores to set
        :param placements: placements object
        :rtype: None
        """
        # Set the routers to temporary values
        extra_monitor_cores[0].set_router_time_outs(
            15, 4, transceiver, placements, extra_monitor_cores)
        extra_monitor_cores[0].set_router_emergency_timeout(
            0, 0, transceiver, placements, extra_monitor_cores)

        if self._last_status is None:
            log.warning(
                "Cores have not been set for data extraction, so can't be"
                " unset")
        try:
            mantissa, exponent = self._last_status.router_timeout_parameters
            extra_monitor_cores[0].set_router_time_outs(
                mantissa, exponent, transceiver, placements,
                extra_monitor_cores)
            mantissa, exponent = \
                self._last_status.router_emergency_timeout_parameters
            extra_monitor_cores[0].set_router_emergency_timeout(
                mantissa, exponent, transceiver, placements,
                extra_monitor_cores)
            extra_monitor_cores[0].set_reinjection_packets(
                placements, extra_monitor_cores, transceiver,
                point_to_point=self._last_status.is_reinjecting_point_to_point,
                multicast=self._last_status.is_reinjecting_multicast,
                nearest_neighbour=(
                    self._last_status.is_reinjecting_nearest_neighbour),
                fixed_route=self._last_status.is_reinjecting_fixed_route)
        except Exception:  # pylint: disable=broad-except
            log.exception("Error resetting timeouts")
            log.error("Checking if the cores are OK...")
            core_subsets = convert_vertices_to_core_subset(
                extra_monitor_cores, placements)
            try:
                error_cores = transceiver.get_cores_not_in_state(
                    core_subsets, {CPUState.RUNNING})
                if error_cores:
                    log.error("Cores in an unexpected state: {}".format(
                        error_cores))
            except Exception:  # pylint: disable=broad-except
                log.exception("Couldn't get core state")

    def __reprogram_tag(self, connection):
        request = IPTagSet(
            self._x, self._y, [0, 0, 0, 0], 0,
            self._remote_tag, strip=True, use_sender=True)
        data = connection.get_scp_data(request)
        einfo = None
        for _ in range(3):
            try:
                connection.send(data)
                _, _, response, offset = \
                    connection.receive_scp_response()
                request.get_scp_response().read_bytestring(response, offset)
                return
            except SpinnmanTimeoutException:
                einfo = sys.exc_info()
        reraise(*einfo)

    def get_data(
            self, placement, memory_address, length_in_bytes, fixed_routes):
        """ Gets data from a given core and memory address.

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

        transceiver = get_simulator().transceiver
        if (length_in_bytes <
                THRESHOLD_WHERE_SDP_BETTER_THAN_DATA_EXTRACTOR_IN_BYTES):
            data = transceiver.read_memory(
                placement.x, placement.y, memory_address, length_in_bytes)
            end = float(time.time())
            self._provenance_data_items[
                placement, memory_address,
                length_in_bytes].append((end - start, [0]))
            return data

        # Update the IP Tag to work through a NAT firewall
        connection = SCAMPConnection(
            chip_x=self._x, chip_y=self._y, remote_host=self._ip_address)
        self.__reprogram_tag(connection)

        data = _THREE_WORDS.pack(
            self.SDP_PACKET_START_SENDING_COMMAND_ID,
            memory_address, length_in_bytes)

        # logger.debug("sending to core %d:%d:%d",
        #              placement.x, placement.y, placement.p)

        # send
        connection.send_sdp_message(SDPMessage(
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
        lost_seq_nums = self._receive_data(transceiver, placement, connection)

        # Stop anything else getting through (and reduce traffic)
        data = _ONE_WORD.pack(self.SDP_PACKET_CLEAR)
        connection.send_sdp_message(SDPMessage(
            sdp_header=SDPHeader(
                destination_chip_x=placement.x,
                destination_chip_y=placement.y,
                destination_cpu=placement.p,
                destination_port=self.SDP_PORT,
                flags=SDPFlag.REPLY_NOT_EXPECTED),
            data=data))
        connection.close()

        end = float(time.time())
        self._provenance_data_items[
            placement, memory_address, length_in_bytes].append(
                (end - start, lost_seq_nums))

        # create report elements
        if self._write_data_speed_up_reports:
            routers_been_in_use = self._determine_which_routers_were_used(
                placement, fixed_routes, transceiver.get_machine_details())
            self._write_routers_used_into_report(
                self._out_report_path, routers_been_in_use, placement)

        return self._output

    def _receive_data(self, transceiver, placement, connection):
        seq_nums = set()
        lost_seq_nums = list()
        timeoutcount = 0
        finished = False
        while not finished:
            try:
                data = connection.receive(
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
                # self.__reset_connection()
                if not finished:
                    finished = self._determine_and_retransmit_missing_seq_nums(
                        seq_nums, transceiver, placement, lost_seq_nums)
        return lost_seq_nums

    @staticmethod
    def _determine_which_routers_were_used(placement, fixed_routes, machine):
        """ Traverse the fixed route paths from a given location to its\
            destination. Used for determining which routers were used.

        :param placement: the source to start from
        :param fixed_routes: the fixed routes for each router
        :param machine: the spinnMachine instance
        :return: list of chip IDs
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
        """ Write the used routers into a report

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
        """ Determine which sequence numbers we've missed

        :param seq_nums: the set already acquired
        :return: list of missing sequence numbers
        """
        return [sn for sn in xrange(0, self._max_seq_num)
                if sn not in seq_nums]

    def _determine_and_retransmit_missing_seq_nums(
            self, seq_nums, transceiver, placement, lost_seq_nums):
        """ Determine if there are any missing sequence numbers, and if so\
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
            len(missing_seq_nums) - (DATA_PER_FULL_PACKET - 2)
        if length_via_format2 > 0:
            n_packets += ceildiv(
                length_via_format2, DATA_PER_FULL_PACKET - 1)

        # transmit missing sequence as a new SDP packet
        first = True
        seq_num_offset = 0
        for _ in xrange(n_packets):
            length_left_in_packet = DATA_PER_FULL_PACKET
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
                    WORD_TO_BYTE_CONVERTER)

                # pack flag and n packets
                _ONE_WORD.pack_into(
                    data, offset, self.SDP_PACKET_START_MISSING_SEQ_COMMAND_ID)
                _ONE_WORD.pack_into(
                    data, WORD_TO_BYTE_CONVERTER, n_packets)

                # update state
                offset += 2 * WORD_TO_BYTE_CONVERTER
                length_left_in_packet -= 2
                first = False

            else:  # just add data
                # get left over space / data size
                size_of_data_left_to_transmit = min(
                    DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM,
                    len(missing_seq_nums) - seq_num_offset)

                # build data holder accordingly
                data = bytearray(
                    (size_of_data_left_to_transmit + 1) *
                    WORD_TO_BYTE_CONVERTER)

                # pack flag
                _ONE_WORD.pack_into(
                    data, offset, self.SDP_PACKET_MISSING_SEQ_COMMAND_ID)
                offset += 1 * WORD_TO_BYTE_CONVERTER
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
        """ Take a packet and processes it see if we're finished yet

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
        true_data_length = offset + length_of_data - SEQUENCE_NUMBER_SIZE
        if not is_end_of_stream or length_of_data != END_FLAG_SIZE_IN_BYTES:
            self._write_into_view(
                offset, true_data_length, data, SEQUENCE_NUMBER_SIZE,
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
        return (seq_num * DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM *
                WORD_TO_BYTE_CONVERTER)

    def _write_into_view(
            self, view_start_position, view_end_position,
            data, data_start_position, data_end_position, seq_num,
            packet_length, is_final):
        """ Puts data into the view

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
        """ Verify if the sequence numbers are correct.

        :param seq_nums: the received sequence numbers
        :return: Whether all the sequence numbers have been received
        :rtype: bool
        """
        # hand back
        seq_nums = sorted(seq_nums)
        max_needed = self.calculate_max_seq_num()
        if len(seq_nums) > max_needed + 1:
            raise Exception("I've received more data than I was expecting!!")
        return len(seq_nums) == max_needed + 1

    def calculate_max_seq_num(self):
        """ Deduce the max sequence number expected to be received

        :return: int of the biggest sequence num expected
        """

        return ceildiv(
            len(self._output),
            DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM * WORD_TO_BYTE_CONVERTER)

    @staticmethod
    def _print_missing(seq_nums):
        """ Debug printer for the missing sequence numbers from the pile

        :param seq_nums: the sequence numbers received so far
        :rtype: None
        """
        for seq_num in sorted(seq_nums):
            log.info("from list I'm missing sequence num {}", seq_num)

    def _print_out_packet_data(self, data):
        """ Debug prints out the data from the packet

        :param data: the packet data
        :rtype: None
        """
        reread_data = struct.unpack("<{}I".format(
            ceildiv(len(data), WORD_TO_BYTE_CONVERTER)), data)
        log.info("converted data back into readable form is {}", reread_data)

    @staticmethod
    def _print_length_of_received_seq_nums(seq_nums, max_needed):
        """ Debug helper method for figuring out if everything been received

        :param seq_nums: sequence numbers received
        :param max_needed: biggest expected to have
        :rtype: None
        """
        if len(seq_nums) != max_needed:
            log.info("should have received {} sequence numbers, but received "
                     "{} sequence numbers", max_needed, len(seq_nums))

    @staticmethod
    def _print_packet_num_being_sent(packet_count, n_packets):
        """ Debug helper for printing missing sequence number packet\
            transmission

        :param packet_count: which packet is being fired
        :param n_packets: how many packets to fire.
        :rtype: None
        """
        log.info("send SDP packet with missing sequence numbers: {} of {}",
                 packet_count + 1, n_packets)

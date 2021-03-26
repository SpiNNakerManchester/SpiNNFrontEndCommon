# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from collections import defaultdict
import os
import datetime
import logging
import time
import struct
from enum import Enum
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
    ConstantSDRAM, IPtagResource, ResourceContainer)
from spinn_front_end_common.utilities.globals_variables import get_simulator
from spinn_front_end_common.utilities.helpful_functions import (
    convert_vertices_to_core_subset, n_word_struct)
from spinn_front_end_common.utilities.emergency_recovery import (
    emergency_recover_state_from_failure)
from spinn_front_end_common.abstract_models import (
    AbstractHasAssociatedBinary, AbstractGeneratesDataSpecification)
from spinn_front_end_common.interface.provenance import (
    AbstractProvidesLocalProvenanceData)
from spinn_front_end_common.utilities.utility_objs import (
    ExecutableType, ProvenanceDataItem)
from spinn_front_end_common.utilities.constants import (
    SDP_PORTS, BYTES_PER_WORD, BYTES_PER_KB)
from spinn_front_end_common.utilities.exceptions import SpinnFrontEndException
from spinn_front_end_common.utilities.utility_objs.\
    extra_monitor_scp_processes import (
        SetRouterTimeoutProcess, ClearQueueProcess)

log = FormatAdapter(logging.getLogger(__name__))

# shift by for the destination x coord in the word.
DEST_X_SHIFT = 16

TIMEOUT_RETRY_LIMIT = 100
TIMEOUT_MESSAGE = "Failed to hear from the machine during {} attempts. "\
    "Please try removing firewalls."
_MINOR_LOSS_MESSAGE = (
    "During the extraction of data of {} bytes from memory address {}, "
    "attempt {} had {} sequences that were lost.")
_MINOR_LOSS_THRESHOLD = 10
_MAJOR_LOSS_MESSAGE = (
    "During the extraction of data from chip {}, there were {} cases of "
    "serious data loss. The system recovered, but the speed of download "
    "was compromised. Reduce the number of executing applications and remove "
    "routers between yourself and the SpiNNaker machine to reduce the chance "
    "of this occurring.")
_MAJOR_LOSS_THRESHOLD = 100

# cap for stopping wrap arounds
TRANSACTION_ID_CAP = 0xFFFFFFFF

#: number of items used up by the retransmit code for its header
SDP_RETRANSMISSION_HEADER_SIZE = 2

#: size of config region in bytes
#: 1.new seq key, 2.first data key, 3. transaction id key 4.end flag key,
# 5.base key, 6.iptag tag
CONFIG_SIZE = 6 * BYTES_PER_WORD

#: items of data a SDP packet can hold when SCP header removed
WORDS_PER_FULL_PACKET = 68  # 272 bytes as removed SCP header

#: size of items the sequence number uses
SEQUENCE_NUMBER_SIZE_IN_ITEMS = 1

#: transaction id size in words
TRANSACTION_ID_SIZE_IN_ITEMS = 1

#: the size in words of the command flag
COMMAND_SIZE_IN_ITEMS = 1

#: offset for missing seq starts in first packet
WORDS_FOR_COMMAND_N_MISSING_TRANSACTION = 3

#: offset for missing seq starts in more packet
WORDS_FOR_COMMAND_TRANSACTION = (
    COMMAND_SIZE_IN_ITEMS + TRANSACTION_ID_SIZE_IN_ITEMS)

BYTES_FOR_SEQ_AND_TRANSACTION_ID = (
    (SEQUENCE_NUMBER_SIZE_IN_ITEMS + TRANSACTION_ID_SIZE_IN_ITEMS) *
    BYTES_PER_WORD)

#: items of data from SDP packet with a sequence number
WORDS_PER_FULL_PACKET_WITH_SEQUENCE_NUM = (
    WORDS_PER_FULL_PACKET - SEQUENCE_NUMBER_SIZE_IN_ITEMS -
    TRANSACTION_ID_SIZE_IN_ITEMS)

#: offset where data in starts on commands
#: (command, transaction_id, seq num)
WORDS_FOR_COMMAND_AND_KEY = 3
BYTES_FOR_COMMAND_AND_ADDRESS_HEADER = (
    WORDS_FOR_COMMAND_AND_KEY * BYTES_PER_WORD)

#: offset where data in starts in reception (command, transaction id)
WORDS_FOR_RECEPTION_COMMAND_AND_ADDRESS_HEADER = 2
BYTES_FOR_RECEPTION_COMMAND_AND_ADDRESS_HEADER = (
    WORDS_FOR_RECEPTION_COMMAND_AND_ADDRESS_HEADER * BYTES_PER_WORD)

#: size for data to store when first packet with command and address
WORDS_IN_FULL_PACKET_WITH_KEY = (
    WORDS_PER_FULL_PACKET - WORDS_FOR_COMMAND_AND_KEY)
BYTES_IN_FULL_PACKET_WITH_KEY = (
    WORDS_IN_FULL_PACKET_WITH_KEY * BYTES_PER_WORD)

#: size of data in key space
#: x, y, key (all ints) for possible 48 chips, plus n chips to read,
# the reinjector base key.
SIZE_DATA_IN_CHIP_TO_KEY_SPACE = ((3 * 48) + 2) * BYTES_PER_WORD


class _DATA_REGIONS(Enum):
    """DSG data regions"""
    CONFIG = 0
    CHIP_TO_KEY_SPACE = 1


class DATA_OUT_COMMANDS(Enum):
    """command IDs for the SDP packets for data out"""
    START_SENDING = 100
    START_MISSING_SEQ = 1000
    MISSING_SEQ = 1001
    CLEAR = 2000


class DATA_IN_COMMANDS(Enum):
    """command IDs for the SDP packets for data in"""
    SEND_DATA_TO_LOCATION = 200
    SEND_SEQ_DATA = 2000
    SEND_TELL = 2001
    RECEIVE_MISSING_SEQ_DATA = 2002
    RECEIVE_FINISHED = 2003


# precompiled structures
_ONE_WORD = struct.Struct("<I")
_TWO_WORDS = struct.Struct("<II")
_THREE_WORDS = struct.Struct("<III")
_FOUR_WORDS = struct.Struct("<IIII")
_FIVE_WORDS = struct.Struct("<IIIII")

# Set to true to check that the data is correct after it has been sent in.
# This is expensive, and only works in Python 3.5 or later.
VERIFY_SENT_DATA = False


def ceildiv(dividend, divisor):
    """ How to divide two possibly-integer numbers and round up.
    """
    assert divisor > 0
    q, r = divmod(dividend, divisor)
    return int(q) + (r != 0)


# SDRAM requirement for storing missing SDP packets seq nums
SDRAM_FOR_MISSING_SDP_SEQ_NUMS = ceildiv(
    120.0 * 1024 * BYTES_PER_KB,
    WORDS_PER_FULL_PACKET_WITH_SEQUENCE_NUM * BYTES_PER_WORD)


class DataSpeedUpPacketGatherMachineVertex(
        MachineVertex, AbstractGeneratesDataSpecification,
        AbstractHasAssociatedBinary, AbstractProvidesLocalProvenanceData):
    """ Machine vertex for handling fast data transfer between host and \
        SpiNNaker. This machine vertex is only ever placed on chips with a \
        working Ethernet connection; it collaborates with the \
        :py:class:`ExtraMonitorSupportMachineVertex` to write data on other \
        chips..
    """
    __slots__ = [
        # x coordinate
        "_x",
        # y coordinate
        "_y",
        # word with x and y
        "_coord_word",
        # transaction id
        "_transaction_id",
        # app id
        "_app_id",
        # socket
        "_connection",
        # store of the extra monitors to location. helpful in data in
        "_extra_monitors_by_chip",
        # path for the data in report
        "_in_report_path",
        # ipaddress
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
        # Count of the runs for provenance data
        "_run",
        "_remote_tag",
        # path to the data out report
        "_out_report_path",
        # bool flag for writing reports
        "_write_data_speed_up_reports",
        # data holder for output
        "_view"]

    #: base key (really nasty hack to tie in fixed route keys)
    BASE_KEY = 0xFFFFFFF9
    NEW_SEQ_KEY = 0xFFFFFFF8
    FIRST_DATA_KEY = 0xFFFFFFF7
    END_FLAG_KEY = 0xFFFFFFF6
    TRANSACTION_ID_KEY = 0xFFFFFFF5

    #: to use with multicast stuff (reinjection acks have to be fixed route)
    BASE_MASK = 0xFFFFFFFB
    NEW_SEQ_KEY_OFFSET = 1
    FIRST_DATA_KEY_OFFSET = 2
    END_FLAG_KEY_OFFSET = 3
    TRANSACTION_ID_KEY_OFFSET = 4

    # throttle on the transmission
    _TRANSMISSION_THROTTLE_TIME = 0.000001

    # TRAFFIC_TYPE = EdgeTrafficType.MULTICAST
    TRAFFIC_TYPE = EdgeTrafficType.FIXED_ROUTE

    #: report name for tracking used routers
    OUT_REPORT_NAME = "routers_used_in_speed_up_process.rpt"
    #: report name for tracking performance gains
    IN_REPORT_NAME = "speeds_gained_in_speed_up_process.rpt"

    # the end flag is set when the high bit of the sequence number word is set
    _LAST_MESSAGE_FLAG_BIT_MASK = 0x80000000
    # corresponding mask for the actual sequence numbers
    _SEQUENCE_NUMBER_MASK = 0x7fffffff

    # time outs used by the protocol for separate bits
    _TIMEOUT_PER_RECEIVE_IN_SECONDS = 2
    _TIMEOUT_FOR_SENDING_IN_SECONDS = 0.01

    # end flag for missing seq nums
    _MISSING_SEQ_NUMS_END_FLAG = 0xFFFFFFFF

    # flag for saying missing all SEQ numbers
    FLAG_FOR_MISSING_ALL_SEQUENCES = 0xFFFFFFFE

    _ADDRESS_PACKET_BYTE_FORMAT = struct.Struct(
        "<{}B".format(BYTES_IN_FULL_PACKET_WITH_KEY))

    # Router timeouts, in mantissa,exponent form. See datasheet for details
    _LONG_TIMEOUT = (14, 14)
    _SHORT_TIMEOUT = (1, 1)
    _TEMP_TIMEOUT = (15, 4)
    _ZERO_TIMEOUT = (0, 0)

    # Initial port for the reverse IP tag (to be replaced later)
    _TAG_INITIAL_PORT = 10000

    def __init__(
            self, x, y, extra_monitors_by_chip, ip_address,
            report_default_directory,
            write_data_speed_up_reports, app_vertex=None, constraints=None):
        """
        :param int x: Where this gatherer is.
        :param int y: Where this gatherer is.
        :param extra_monitors_by_chip: UNUSED
        :type extra_monitors_by_chip:
            dict(tuple(int,int), ExtraMonitorSupportMachineVertex)
        :param str ip_address:
            How to talk directly to the chip where the gatherer is.
        :param str report_default_directory: Where reporting is done.
        :param bool write_data_speed_up_reports:
            Whether to write low-level reports on data transfer speeds.
        :param constraints:
        :type constraints:
            iterable(~pacman.model.constraints.AbstractConstraint) or None
        :param app_vertex:
            The application vertex that caused this machine vertex to be
            created. If None, there is no such application vertex.
        :type app_vertex:
            ~pacman.model.graphs.application.ApplicationVertex or None
        """
        super().__init__(
            label="SYSTEM:PacketGatherer({},{})".format(x, y),
            constraints=constraints, app_vertex=app_vertex)

        # data holders for the output, and sequence numbers
        self._view = None
        self._max_seq_num = None
        self._output = None
        self._transaction_id = 0

        # store of the extra monitors to location. helpful in data in
        self._extra_monitors_by_chip = extra_monitors_by_chip
        self._missing_seq_nums_data_in = list()

        # Create a connection to be used
        self._x = x
        self._y = y
        self._coord_word = None
        self._ip_address = ip_address
        self._remote_tag = None
        self._connection = None

        # local provenance storage
        self._provenance_data_items = defaultdict(list)
        self._run = 0
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

        :param ~.SDPMessage message: message to send
        :rtype: None
        """
        # send first message
        self._connection.send_sdp_message(message)
        time.sleep(self._TRANSMISSION_THROTTLE_TIME)

    @property
    @overrides(MachineVertex.resources_required)
    def resources_required(self):
        return self.static_resources_required()

    def update_transaction_id_from_machine(self, txrx):
        """ Looks up from the machine what the current transaction ID is\
            and updates the data speed up gatherer.

        :param ~spinnman.transceiver.Transceiver txrx: SpiNNMan instance
        """
        self._transaction_id = txrx.read_user_1(
            self._placement.x, self._placement.y, self._placement.p)

    @classmethod
    def static_resources_required(cls):
        """
        :rtype: ~pacman.model.resources.ResourceContainer
        """
        return ResourceContainer(
            sdram=ConstantSDRAM(
                CONFIG_SIZE + SDRAM_FOR_MISSING_SDP_SEQ_NUMS +
                SIZE_DATA_IN_CHIP_TO_KEY_SPACE),
            iptags=[IPtagResource(
                port=cls._TAG_INITIAL_PORT, strip_sdp=True,
                ip_address="localhost", traffic_identifier="DATA_SPEED_UP")])

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return ExecutableType.SYSTEM

    @inject_items({
        "machine_graph": "MemoryMachineGraph",
        "routing_info": "MemoryRoutingInfos",
        "tags": "MemoryTags",
        "mc_data_chips_to_keys": "DataInMulticastKeyToChipMap",
        "machine": "MemoryExtendedMachine",
        "app_id": "APPID",
        "router_timeout_key": "SystemMulticastRouterTimeoutKeys"
    })
    @overrides(
        AbstractGeneratesDataSpecification.generate_data_specification,
        additional_arguments={
            "machine_graph", "routing_info", "tags",
            "mc_data_chips_to_keys", "machine", "app_id",
            "router_timeout_key"
        })
    def generate_data_specification(
            self, spec, placement, machine_graph, routing_info, tags,
            mc_data_chips_to_keys, machine, app_id, router_timeout_key):
        """
        :param ~pacman.model.graphs.machine.MachineGraph machine_graph:
            (injected)
        :param ~pacman.model.routing_info.RoutingInfo routing_info: (injected)
        :param ~pacman.model.tags.Tags tags: (injected)
        :param dict(tuple(int,int),int) mc_data_chips_to_keys: (injected)
        :param ~spinn_machine.Machine machine: (injected)
        :param int app_id: (injected)
        :param dict(tuple(int,int),int) router_timeout_key: (injected)
        """
        # pylint: disable=too-many-arguments, arguments-differ

        # update my placement for future knowledge
        self._placement = placement
        self._app_id = app_id

        # Create the data regions for hello world
        self._reserve_memory_regions(spec)

        # the keys for the special cases
        if self.TRAFFIC_TYPE == EdgeTrafficType.MULTICAST:
            base_key = routing_info.get_first_key_for_edge(
                list(machine_graph.get_edges_ending_at_vertex(self))[0])
            new_seq_key = base_key + self.NEW_SEQ_KEY_OFFSET
            first_data_key = base_key + self.FIRST_DATA_KEY_OFFSET
            end_flag_key = base_key + self.END_FLAG_KEY_OFFSET
            transaction_id_key = base_key + self.TRANSACTION_ID_KEY_OFFSET
        else:
            new_seq_key = self.NEW_SEQ_KEY
            first_data_key = self.FIRST_DATA_KEY
            end_flag_key = self.END_FLAG_KEY
            base_key = self.BASE_KEY
            transaction_id_key = self.TRANSACTION_ID_KEY

        spec.switch_write_focus(_DATA_REGIONS.CONFIG.value)
        spec.write_value(new_seq_key)
        spec.write_value(first_data_key)
        spec.write_value(transaction_id_key)
        spec.write_value(end_flag_key)
        spec.write_value(base_key)

        # locate the tag ID for our data and update with a port
        # Note: The port doesn't matter as we are going to override this later
        iptags = tags.get_ip_tags_for_vertex(self)
        iptag = iptags[0]
        spec.write_value(iptag.tag)
        self._remote_tag = iptag.tag

        # write mc chip key map
        spec.switch_write_focus(_DATA_REGIONS.CHIP_TO_KEY_SPACE.value)
        chips_on_board = list(machine.get_existing_xys_on_board(
            machine.get_chip_at(placement.x, placement.y)))

        # write how many chips to read
        spec.write_value(len(chips_on_board))

        # write the broad cast keys for timeouts
        reinjection_base_key = router_timeout_key[(placement.x, placement.y)]
        spec.write_value(reinjection_base_key)

        # write each chip x and y and base key
        for chip_xy in chips_on_board:
            board_chip_x, board_chip_y = machine.get_local_xy(
                machine.get_chip_at(*chip_xy))
            spec.write_value(board_chip_x)
            spec.write_value(board_chip_y)
            spec.write_value(mc_data_chips_to_keys[chip_xy])
            log.debug("for chip {}:{} base key is {}",
                      chip_xy[0], chip_xy[1], mc_data_chips_to_keys[chip_xy])

        # End-of-Spec:
        spec.end_specification()

    @staticmethod
    def _reserve_memory_regions(spec):
        """ Writes the DSG regions memory sizes. Static so that it can be used\
            by the application vertex.

        :param ~.DataSpecificationGenerator spec: spec file
        """
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
        self._run += 1
        prov_items = list()
        significant_losses = defaultdict(list)
        top_level_name = "Provenance_for_{}".format(self._label)
        for (placement, memory_address, length_in_bytes) in \
                self._provenance_data_items.keys():

            # handle duplicates of the same calls
            times_extracted_the_same_thing = 0
            for time_taken, lost_seq_nums in self._provenance_data_items[
                    placement, memory_address, length_in_bytes]:
                # handle time
                chip_name = "chip{}:{}".format(placement.x, placement.y)
                last_name = "Memory_address:{}:Length_in_bytes:{}"\
                    .format(memory_address, length_in_bytes)
                if times_extracted_the_same_thing == 0:
                    iteration_name = "run{}".format(
                        self._run)
                else:
                    iteration_name = "run{}iteration{}".format(
                        self._run, times_extracted_the_same_thing)
                prov_items.append(ProvenanceDataItem(
                    [top_level_name, "extraction_time", chip_name, last_name,
                     iteration_name],
                    time_taken, report=False))
                times_extracted_the_same_thing += 1

                # handle lost sequence numbers
                for i, n_lost_seq_nums in enumerate(lost_seq_nums):
                    # Zeroes are not reported at all
                    if n_lost_seq_nums:
                        prov_items.append(ProvenanceDataItem(
                            [top_level_name, "lost_seq_nums", chip_name,
                             last_name, iteration_name,
                             "iteration_{}".format(i)],
                            n_lost_seq_nums, report=(
                                n_lost_seq_nums > _MINOR_LOSS_THRESHOLD),
                            message=_MINOR_LOSS_MESSAGE.format(
                                length_in_bytes, memory_address, i,
                                n_lost_seq_nums)))
                    if n_lost_seq_nums > _MAJOR_LOSS_THRESHOLD:
                        significant_losses[placement.x, placement.y] += [i]
        for chip in significant_losses:
            n_times = len(significant_losses[chip])
            chip_name = "chip{}:{}".format(*chip)
            prov_items.append(ProvenanceDataItem(
                [top_level_name, "serious_lost_seq_num_count", chip_name],
                n_times, report=True, message=_MAJOR_LOSS_MESSAGE.format(
                    chip, n_times)))
        self._provenance_data_items = defaultdict(list)
        return prov_items

    @staticmethod
    def locate_correct_write_data_function_for_chip_location(
            uses_advanced_monitors, machine, x, y, transceiver,
            extra_monitor_cores_to_ethernet_connection_map):
        """ Supports other components figuring out which gatherer and function\
            to call for writing data onto SpiNNaker.

        :param bool uses_advanced_monitors:
            Whether the system is using advanced monitors
        :param ~spinn_machine.Machine machine: the SpiNNMachine instance
        :param int x: the chip x coordinate to write data to
        :param int y: the chip y coordinate to write data to
        :param ~spinnman.transceiver.Transceiver transceiver:
            the SpiNNMan instance
        :param extra_monitor_cores_to_ethernet_connection_map:
            mapping between cores and connections
        :type extra_monitor_cores_to_ethernet_connection_map:
            dict(tuple(int,int), DataSpeedUpPacketGatherMachineVertex)
        :return: a write function of either a LPG or the spinnMan
        :rtype: callable
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
        """ Writes the data in report for this stage.

        :param ~datetime.timedelta time_diff:
            the time taken to write the memory
        :param int data_size: the size of data that was written in bytes
        :param int x:
            the location in machine where the data was written to X axis
        :param int y:
            the location in machine where the data was written to Y axis
        :param int address_written_to: where in SDRAM it was written to
        :param list(set(int)) missing_seq_nums:
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
        megabits = (data_size * 8.0) / (1024 * BYTES_PER_KB)
        if time_took_ms == 0:
            mbs = "unknown, below threshold"
        else:
            mbs = megabits / (float(time_took_ms) / 100000.0)

        with open(self._in_report_path, "a") as writer:
            writer.write(
                "{}\t\t {}\t\t {}\t\t {}\t\t\t\t {}\t\t\t {}\t\t {}\n".format(
                    x, y, address_written_to, data_size, time_took_ms,
                    mbs, missing_seq_nums))

    def send_data_into_spinnaker(
            self, x, y, base_address, data, n_bytes=None, offset=0,
            cpu=0, is_filename=False):  # pylint: disable=unused-argument
        """ Sends a block of data into SpiNNaker to a given chip.

        :param int x: chip x for data
        :param int y: chip y for data
        :param int base_address: the address in SDRAM to start writing memory
        :param data: the data to write (or filename to load data from,
            if ``is_filename`` is True; that's the only time this is a str)
        :type data: bytes or bytearray or memoryview or str
        :param int n_bytes: how many bytes to read, or None if not set
        :param int offset: where in the data to start from
        :param int cpu:
        :param bool is_filename: whether data is actually a file.
        """
        # if file, read in and then process as normal
        if is_filename:
            if offset != 0:
                raise Exception(
                    "when using a file, you can only have a offset of 0")

            with open(data, "rb") as reader:
                # n_bytes=None already means 'read everything'
                data = reader.read(n_bytes)  # pylint: disable=no-member
            # Number of bytes to write is now length of buffer we have
            n_bytes = len(data)
        elif n_bytes is None:
            n_bytes = len(data)
        transceiver = get_simulator().transceiver

        # start time recording
        start = datetime.datetime.now()
        # send data
        self._send_data_via_extra_monitors(
            transceiver, x, y, base_address, data[offset:n_bytes + offset])
        # end time recording
        end = datetime.datetime.now()

        if VERIFY_SENT_DATA:
            original_data = bytes(data[offset:n_bytes + offset])
            verified_data = bytes(transceiver.read_memory(
                x, y, base_address, n_bytes))
            self.__verify_sent_data(
                original_data, verified_data, x, y, base_address, n_bytes)

        # write report
        if self._write_data_speed_up_reports:
            self._generate_data_in_report(
                x=x, y=y, time_diff=end - start,
                data_size=n_bytes, address_written_to=base_address,
                missing_seq_nums=self._missing_seq_nums_data_in)

    @staticmethod
    def __verify_sent_data(
            original_data, verified_data, x, y, base_address, n_bytes):
        if original_data != verified_data:
            log.error("VARIANCE: chip:{},{} address:{} len:{}",
                      x, y, base_address, n_bytes)
            log.error("original:{}", original_data.hex())
            log.error("verified:{}", verified_data.hex())
            for i, (a, b) in enumerate(zip(original_data, verified_data)):
                if a != b:
                    raise Exception("damn at " + str(i))

    @staticmethod
    def __make_sdp_message(placement, port, payload):
        """
        :param ~.Placement placement:
        :param SDP_PORTS port:
        :param bytearray payload:
        :rtype: ~.SDPMessage
        """
        return SDPMessage(
            sdp_header=SDPHeader(
                destination_chip_x=placement.x,
                destination_chip_y=placement.y,
                destination_cpu=placement.p,
                destination_port=port.value,
                flags=SDPFlag.REPLY_NOT_EXPECTED),
            data=payload)

    def _send_data_via_extra_monitors(
            self, transceiver, destination_chip_x, destination_chip_y,
            start_address, data_to_write):
        """ sends data using the extra monitor cores

        :param ~.Transceiver transceiver: the SpiNNMan instance
        :param int destination_chip_x: chip x
        :param int destination_chip_y: chip y
        :param int start_address: start address in SDRAM to write data to
        :param bytearray data_to_write: the data to write
        :param int start_address: the base SDRAM address
        """
        # Set up the connection
        self._connection = SCAMPConnection(
            chip_x=self._x, chip_y=self._y, remote_host=self._ip_address)
        self.__reprogram_tag(self._connection)

        # how many packets after first one we need to send
        self._max_seq_num = ceildiv(
            len(data_to_write), BYTES_IN_FULL_PACKET_WITH_KEY)

        # determine board chip IDs, as the LPG does not know machine scope IDs
        machine = transceiver.get_machine_details()
        chip = machine.get_chip_at(destination_chip_x, destination_chip_y)
        dest_x, dest_y = machine.get_local_xy(chip)
        self._coord_word = (dest_x << DEST_X_SHIFT) | dest_y

        # for safety, check the transaction id from the machine before updating
        self.update_transaction_id_from_machine(transceiver)
        self._transaction_id = (self._transaction_id + 1) & TRANSACTION_ID_CAP
        time_out_count = 0

        # verify completed
        received_confirmation = False
        while not received_confirmation:

            # send initial attempt at sending all the data
            self._send_all_data_based_packets(data_to_write, start_address)

            # Don't create a missing buffer until at least one packet has
            # come back.
            missing = None

            while not received_confirmation:
                try:
                    # try to receive a confirmation of some sort from spinnaker
                    data = self._connection.receive(
                        timeout=self._TIMEOUT_PER_RECEIVE_IN_SECONDS)
                    time_out_count = 0

                    # Read command and transaction id
                    (cmd, transaction_id) = _TWO_WORDS.unpack_from(data, 0)

                    # If wrong transaction id, ignore packet
                    if self._transaction_id != transaction_id:
                        continue

                    # Decide what to do with the packet
                    if cmd == DATA_IN_COMMANDS.RECEIVE_FINISHED.value:
                        received_confirmation = True
                        break

                    if cmd != DATA_IN_COMMANDS.RECEIVE_MISSING_SEQ_DATA.value:
                        raise Exception("Unknown command {} received".format(
                            cmd))

                    # The currently received packet has missing sequence
                    # numbers. Accumulate and dispatch transactionId when
                    # we've got them all.
                    if missing is None:
                        missing = set()
                        self._missing_seq_nums_data_in.append(missing)
                    seen_last, seen_all = self._read_in_missing_seq_nums(
                        data, BYTES_FOR_RECEPTION_COMMAND_AND_ADDRESS_HEADER,
                        missing)

                    # Check that you've seen something that implies ready
                    # to retransmit.
                    if seen_all or seen_last:
                        self._outgoing_retransmit_missing_seq_nums(
                            data_to_write, missing)
                        missing.clear()

                except SpinnmanTimeoutException as e:
                    # if the timeout has not occurred x times, keep trying
                    time_out_count += 1
                    if time_out_count > TIMEOUT_RETRY_LIMIT:
                        emergency_recover_state_from_failure(
                            transceiver, self._app_id, self, self._placement)
                        raise SpinnFrontEndException(
                            TIMEOUT_MESSAGE.format(
                                time_out_count)) from e

                    # If we never received a packet, we will never have
                    # created the buffer, so send everything again
                    if missing is None:
                        break

                    self._outgoing_retransmit_missing_seq_nums(
                            data_to_write, missing)
                    missing.clear()

        # Close the connection
        self._connection.close()

    def _read_in_missing_seq_nums(self, data, position, seq_nums):
        """ handles a missing seq num packet from spinnaker

        :param data: the data to translate into missing seq nums
        :type data: bytearray or bytes
        :param int position: the position in the data to write.
        :param set(int) seq_nums: a set of sequence numbers to add to
        :return: seen_last flag and seen_all flag
        :rtype: tuple(bool, bool)
        """
        # find how many elements are in this packet
        n_elements = (len(data) - position) // BYTES_PER_WORD

        # store missing
        new_seq_nums = n_word_struct(n_elements).unpack_from(
            data, position)

        # add missing seqs accordingly
        seen_last = False
        seen_all = False
        if new_seq_nums[-1] == self._MISSING_SEQ_NUMS_END_FLAG:
            new_seq_nums = new_seq_nums[:-1]
            seen_last = True
        if new_seq_nums[-1] == self.FLAG_FOR_MISSING_ALL_SEQUENCES:
            for missing_seq in range(0, self._max_seq_num):
                seq_nums.add(missing_seq)
            seen_all = True
        else:
            seq_nums.update(new_seq_nums)

        return seen_last, seen_all

    def _outgoing_retransmit_missing_seq_nums(
            self, data_to_write, missing):
        """ Transmits back into SpiNNaker the missing data based off missing\
            sequence numbers

        :param bytearray data_to_write: the data to write.
        :param set(int) missing: a set of missing sequence numbers
        """

        missing_seqs_as_list = list(missing)
        missing_seqs_as_list.sort()

        # send seq data
        for missing_seq_num in missing_seqs_as_list:
            message, _length = self._calculate_data_in_data_from_seq_number(
                data_to_write, missing_seq_num,
                DATA_IN_COMMANDS.SEND_SEQ_DATA.value, None)
            self.__throttled_send(message)

        # request an update on what is missing
        self._send_tell_flag()

    @staticmethod
    def _calculate_position_from_seq_number(seq_num):
        """ Calculates where in the raw data to start reading from, given a\
            sequence number

        :param int seq_num: the sequence number to determine position from
        :return: the position in the byte data
        :rtype: int
        """
        return BYTES_IN_FULL_PACKET_WITH_KEY * seq_num

    def _calculate_data_in_data_from_seq_number(
            self, data_to_write, seq_num, command_id, position):
        """ Determine the data needed to be sent to the SpiNNaker machine\
            given a sequence number

        :param bytearray data_to_write:
            the data to write to the SpiNNaker machine
        :param int seq_num: the seq num to get the data for
        :param int command_id:
        :param position: the position in the data to write to spinnaker
        :type position: int or None
        :return: SDP message and how much data has been written
        :rtype: tuple(~.SDPMessage, int)
        """

        # check for last packet
        packet_data_length = BYTES_IN_FULL_PACKET_WITH_KEY

        # determine position in data if not given
        if position is None:
            position = self._calculate_position_from_seq_number(seq_num)

        # if less than a full packet worth of data, adjust length
        if position + packet_data_length > len(data_to_write):
            packet_data_length = len(data_to_write) - position

        if packet_data_length < 0:
            raise Exception("weird packet data length.")

        # determine the true packet length (with header)
        packet_length = (
            packet_data_length + BYTES_FOR_COMMAND_AND_ADDRESS_HEADER)

        # create struct
        packet_data = bytearray(packet_length)
        _THREE_WORDS.pack_into(
            packet_data, 0, command_id, self._transaction_id, seq_num)
        struct.pack_into(
            "<{}B".format(packet_data_length), packet_data,
            BYTES_FOR_COMMAND_AND_ADDRESS_HEADER,
            *data_to_write[position:position+packet_data_length])

        # debug
        # self._print_out_packet_data(packet_data, position)

        # build sdp packet
        message = self.__make_sdp_message(
            self._placement, SDP_PORTS.EXTRA_MONITOR_CORE_DATA_IN_SPEED_UP,
            packet_data)

        # return message for sending, and the length in data sent
        return message, packet_data_length

    def _send_location(self, start_address):
        """ Send location as separate message.

        :param int start_address: SDRAM location
        """
        self._connection.send_sdp_message(self.__make_sdp_message(
            self._placement, SDP_PORTS.EXTRA_MONITOR_CORE_DATA_IN_SPEED_UP,
            _FIVE_WORDS.pack(
                DATA_IN_COMMANDS.SEND_DATA_TO_LOCATION.value,
                self._transaction_id, start_address, self._coord_word,
                self._max_seq_num - 1)))
        log.debug(
            "start address for transaction {} is {}".format(
                self._transaction_id, start_address))

    def _send_tell_flag(self):
        """ Send tell flag as separate message.
        """
        self._connection.send_sdp_message(self.__make_sdp_message(
            self._placement, SDP_PORTS.EXTRA_MONITOR_CORE_DATA_IN_SPEED_UP,
            _TWO_WORDS.pack(
                DATA_IN_COMMANDS.SEND_TELL.value, self._transaction_id)))

    def _send_all_data_based_packets(self, data_to_write, start_address):
        """ Send all the data as one block.

        :param bytearray data_to_write: the data to send
        :param int start_address:
        """
        # Send the location
        self._send_location(start_address)

        # where in the data we are currently up to
        position_in_data = 0

        # send rest of data
        for seq_num in range(0, self._max_seq_num):
            # put in command flag and seq num
            message, length_to_send = \
                self._calculate_data_in_data_from_seq_number(
                    data_to_write, seq_num,
                    DATA_IN_COMMANDS.SEND_SEQ_DATA.value, position_in_data)
            position_in_data += length_to_send

            # send the message
            self.__throttled_send(message)
            log.debug("sent seq {} of {} bytes", seq_num, length_to_send)

        # check for end flag
        self._send_tell_flag()
        log.debug("sent end flag")

    @staticmethod
    def streaming(gatherers, transceiver, extra_monitor_cores, placements):
        """ Helper method for setting the router timeouts to a state usable\
            for data streaming via a Python context manager (i.e., using\
            the `with` statement).

        :param list(DataSpeedUpPacketGatherMachineVertex) gatherers:
            All the gatherers that are to be set
        :param ~spinnman.transceiver.Transceiver transceiver:
            the SpiNNMan instance
        :param list(ExtraMonitorSupportMachineVertex) extra_monitor_cores:
            the extra monitor cores to set
        :param ~pacman.model.placements.Placements placements:
            placements object
        :return: a context manager
        """
        return _StreamingContextManager(
            gatherers, transceiver, extra_monitor_cores, placements)

    def set_cores_for_data_streaming(
            self, transceiver, extra_monitor_cores, placements):
        """ Helper method for setting the router timeouts to a state usable\
            for data streaming.

        :param ~spinnman.transceiver.Transceiver transceiver:
            the SpiNNMan instance
        :param list(ExtraMonitorSupportMachineVertex) extra_monitor_cores:
            the extra monitor cores to set
        :param ~pacman.model.placements.Placements placements:
            placements object
        """
        lead_monitor = extra_monitor_cores[0]
        # Store the last reinjection status for resetting
        # NOTE: This assumes the status is the same on all cores
        self._last_status = lead_monitor.get_reinjection_status(
            placements, transceiver)

        # Set to not inject dropped packets
        lead_monitor.set_reinjection_packets(
            placements, extra_monitor_cores, transceiver,
            point_to_point=False, multicast=False, nearest_neighbour=False,
            fixed_route=False)

        # Clear any outstanding packets from reinjection
        self.clear_reinjection_queue(transceiver, placements)

        # set time outs
        self.set_router_wait2_timeout(
            self._SHORT_TIMEOUT, transceiver, placements)
        self.set_router_wait1_timeout(
            self._LONG_TIMEOUT, transceiver, placements)

    @staticmethod
    def load_application_routing_tables(
            transceiver, extra_monitor_cores, placements):
        """ Set all chips to have application table loaded in the router.

        :param ~spinnman.transceiver.Transceiver transceiver:
            the SpiNNMan instance
        :param list(ExtraMonitorSupportMachineVertex) extra_monitor_cores:
            the extra monitor cores to set
        :param ~pacman.model.placements.Placements placements:
            placements object
        """
        extra_monitor_cores[0].load_application_mc_routes(
            placements, extra_monitor_cores, transceiver)

    @staticmethod
    def load_system_routing_tables(
            transceiver, extra_monitor_cores, placements):
        """ Set all chips to have the system table loaded in the router

        :param ~spinnman.transceiver.Transceiver transceiver:
            the SpiNNMan instance
        :param list(ExtraMonitorSupportMachineVertex) extra_monitor_cores:
            the extra monitor cores to set
        :param ~pacman.model.placements.Placements placements:
            placements object
        """
        extra_monitor_cores[0].load_system_mc_routes(
            placements, extra_monitor_cores, transceiver)

    def set_router_wait1_timeout(self, timeout, transceiver, placements):
        """ Set the wait1 field for a set of routers.

        :param tuple(int,int) timeout:
        :param ~spinnman.transceiver.Transceiver transceiver:
        :param ~pacman.model.placements.Placements placements:
        """
        mantissa, exponent = timeout
        core_subsets = convert_vertices_to_core_subset([self], placements)
        process = SetRouterTimeoutProcess(
            transceiver.scamp_connection_selector)
        try:
            process.set_wait1_timeout(mantissa, exponent, core_subsets)
        except:  # noqa: E722
            emergency_recover_state_from_failure(
                transceiver, self._app_id, self,
                placements.get_placement_of_vertex(self))
            raise

    def set_router_wait2_timeout(self, timeout, transceiver, placements):
        """ Set the wait2 field for a set of routers.

        :param tuple(int,int) timeout:
        :param ~spinnman.transceiver.Transceiver transceiver:
        :param ~pacman.model.placements.Placements placements:
        """
        mantissa, exponent = timeout
        core_subsets = convert_vertices_to_core_subset([self], placements)
        process = SetRouterTimeoutProcess(
            transceiver.scamp_connection_selector)
        try:
            process.set_wait2_timeout(mantissa, exponent, core_subsets)
        except:  # noqa: E722
            emergency_recover_state_from_failure(
                transceiver, self._app_id, self,
                placements.get_placement_of_vertex(self))
            raise

    def clear_reinjection_queue(self, transceiver, placements):
        """ Clears the queues for reinjection.

        :param ~spinnman.transceiver.Transceiver transceiver:
            the spinnMan interface
        :param ~pacman.model.placements.Placements placements:
            the placements object
        """
        core_subsets = convert_vertices_to_core_subset([self], placements)
        process = ClearQueueProcess(transceiver.scamp_connection_selector)
        try:
            process.reset_counters(core_subsets)
        except:  # noqa: E722
            emergency_recover_state_from_failure(
                transceiver, self._app_id, self,
                placements.get_placement_of_vertex(self))
            raise

    def unset_cores_for_data_streaming(
            self, transceiver, extra_monitor_cores, placements):
        """ Helper method for restoring the router timeouts to normal after\
            being in a state usable for data streaming.

        :param ~spinnman.transceiver.Transceiver transceiver:
            the SpiNNMan instance
        :param list(ExtraMonitorSupportMachineVertex) extra_monitor_cores:
            the extra monitor cores to set
        :param ~pacman.model.placements.Placements placements:
            placements object
        """
        # Set the routers to temporary values
        self.set_router_wait1_timeout(
            self._TEMP_TIMEOUT, transceiver, placements)
        self.set_router_wait2_timeout(
            self._ZERO_TIMEOUT, transceiver, placements)

        if self._last_status is None:
            log.warning(
                "Cores have not been set for data extraction, so can't be"
                " unset")
        try:
            self.set_router_wait1_timeout(
                self._last_status.router_wait1_timeout_parameters,
                transceiver, placements)
            self.set_router_wait2_timeout(
                self._last_status.router_wait2_timeout_parameters,
                transceiver, placements)

            lead_monitor = extra_monitor_cores[0]
            lead_monitor.set_reinjection_packets(
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
        """ Make our tag deliver to the given connection.

        :param ~.SCAMPConnection connection: The connection to deliver to.
        """
        request = IPTagSet(
            self._x, self._y, [0, 0, 0, 0], 0,
            self._remote_tag, strip=True, use_sender=True)
        data = connection.get_scp_data(request)
        exn = None
        for _ in range(3):
            try:
                connection.send(data)
                _, _, response, offset = connection.receive_scp_response()
                request.get_scp_response().read_bytestring(response, offset)
                return
            except SpinnmanTimeoutException as e:
                exn = e
        raise exn or SpinnmanTimeoutException

    def get_data(
            self, extra_monitor, extra_monitor_placement, memory_address,
            length_in_bytes, fixed_routes):
        """ Gets data from a given core and memory address.

        :param ExtraMonitorSupportMachineVertex extra_monitor:
            the extra monitor used for this data
        :param ~pacman.model.placements.Placement extra_monitor_placement:
            placement object for where to get data from
        :param int memory_address: the address in SDRAM to start reading from
        :param int length_in_bytes: the length of data to read in bytes
        :param fixed_routes: the fixed routes, used in the report of which
            chips were used by the speed up process
        :type fixed_routes: dict(tuple(int,int),~spinn_machine.FixedRouteEntry)
        :return: byte array of the data
        :rtype: bytearray
        """
        start = float(time.time())

        # if asked for no data, just return a empty byte array
        if length_in_bytes == 0:
            data = bytearray(0)
            end = float(time.time())
            self._provenance_data_items[
                extra_monitor_placement, memory_address,
                length_in_bytes].append((end - start, [0]))
            return data

        transceiver = get_simulator().transceiver

        # Update the IP Tag to work through a NAT firewall
        connection = SCAMPConnection(
            chip_x=self._x, chip_y=self._y, remote_host=self._ip_address)
        self.__reprogram_tag(connection)

        # update transaction id for extra monitor
        extra_monitor.update_transaction_id()
        transaction_id = extra_monitor.transaction_id

        # send
        connection.send_sdp_message(self.__make_sdp_message(
            extra_monitor_placement,
            SDP_PORTS.EXTRA_MONITOR_CORE_DATA_SPEED_UP,
            _FOUR_WORDS.pack(
                DATA_OUT_COMMANDS.START_SENDING.value, transaction_id,
                memory_address, length_in_bytes)))

        # receive
        self._output = bytearray(length_in_bytes)
        self._view = memoryview(self._output)
        self._max_seq_num = self.calculate_max_seq_num()
        lost_seq_nums = self._receive_data(
            transceiver, extra_monitor_placement, connection, transaction_id)

        # Stop anything else getting through (and reduce traffic)
        connection.send_sdp_message(self.__make_sdp_message(
            extra_monitor_placement,
            SDP_PORTS.EXTRA_MONITOR_CORE_DATA_SPEED_UP,
            _TWO_WORDS.pack(DATA_OUT_COMMANDS.CLEAR.value, transaction_id)))
        connection.close()

        end = float(time.time())
        self._provenance_data_items[
            extra_monitor_placement, memory_address, length_in_bytes].append(
                (end - start, lost_seq_nums))

        # create report elements
        if self._write_data_speed_up_reports:
            routers_been_in_use = self._determine_which_routers_were_used(
                extra_monitor_placement, fixed_routes,
                transceiver.get_machine_details())
            self._write_routers_used_into_report(
                self._out_report_path, routers_been_in_use,
                extra_monitor_placement)

        return self._output

    def _receive_data(
            self, transceiver, placement, connection, transaction_id):
        """
        :param ~.Transceiver transceiver:
        :param ~.Placement placement:
        :param ~.UDPConnection connection:
        :param int transaction_id:
        :rtype: list(int)
        """
        seq_nums = set()
        lost_seq_nums = list()
        timeoutcount = 0
        finished = False
        while not finished:
            try:
                data = connection.receive(
                    timeout=self._TIMEOUT_PER_RECEIVE_IN_SECONDS)
                response_transaction_id, = _ONE_WORD.unpack_from(data, 4)
                if transaction_id == response_transaction_id:
                    timeoutcount = 0
                    seq_nums, finished = self._process_data(
                        data, seq_nums, finished, placement, transceiver,
                        lost_seq_nums, transaction_id)
                else:
                    log.info(
                        "ignoring packet as transaction id should be {}"
                        " but is {}".format(
                            transaction_id, response_transaction_id))
            except SpinnmanTimeoutException as e:
                if timeoutcount > TIMEOUT_RETRY_LIMIT:
                    raise SpinnFrontEndException(
                        "Failed to hear from the machine during {} attempts. "
                        "Please try removing firewalls".format(
                            timeoutcount)) from e

                timeoutcount += 1
                # self.__reset_connection()
                if not finished:
                    finished = self._determine_and_retransmit_missing_seq_nums(
                        seq_nums, transceiver, placement, lost_seq_nums,
                        transaction_id)
        return lost_seq_nums

    @staticmethod
    def _determine_which_routers_were_used(placement, fixed_routes, machine):
        """ Traverse the fixed route paths from a given location to its\
            destination. Used for determining which routers were used.

        :param ~.Placement placement: the source to start from
        :param dict(tuple(int,int),~.MulticastRoutingEntry) fixed_routes:
            the fixed routes for each router
        :param ~.Machine machine: the spinnMachine instance
        :return: list of chip locations
        :rtype: list(tuple(int,int))
        """
        routers = [(placement.x, placement.y)]
        entry = fixed_routes[placement.x, placement.y]
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
            entry = fixed_routes[chip_x, chip_y]
        return routers

    @staticmethod
    def _write_routers_used_into_report(
            report_path, routers_been_in_use, placement):
        """ Write the used routers into a report

        :param str report_path: the path to the report file
        :param list(tuple(int,int)) routers_been_in_use:
            the routers been in use
        :param ~.Placement placement: the first placement used
        """
        writer_behaviour = "w"
        if os.path.isfile(report_path):
            writer_behaviour = "a"

        with open(report_path, writer_behaviour) as writer:
            writer.write("[{}:{}:{}] = {}\n".format(
                placement.x, placement.y, placement.p, routers_been_in_use))

    def _calculate_missing_seq_nums(self, seq_nums):
        """ Determine which sequence numbers we've missed

        :param set(int) seq_nums: the set already acquired
        :return: list of missing sequence numbers
        :rtype: list(int)
        """
        return [sn for sn in range(self._max_seq_num) if sn not in seq_nums]

    def _determine_and_retransmit_missing_seq_nums(
            self, seq_nums, transceiver, placement, lost_seq_nums,
            transaction_id):
        """ Determine if there are any missing sequence numbers, and if so\
            retransmits the missing sequence numbers back to the core for\
            retransmission.

        :param set(int) seq_nums: the sequence numbers already received
        :param ~.Transceiver transceiver: spinnman instance
        :param ~.Placement placement: placement instance
        :param list(int) lost_seq_nums:
        :param int transaction_id: transaction_id
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
        length_via_format2 = len(missing_seq_nums) - (
            WORDS_PER_FULL_PACKET - WORDS_FOR_COMMAND_N_MISSING_TRANSACTION)
        if length_via_format2 > 0:
            n_packets += ceildiv(
                length_via_format2,
                WORDS_PER_FULL_PACKET - WORDS_FOR_COMMAND_TRANSACTION)
        # self._print_missing_n_packets(n_packets)

        # transmit missing sequence as a new SDP packet
        first = True
        seq_num_offset = 0
        for _ in range(n_packets):
            length_left_in_packet = WORDS_PER_FULL_PACKET
            offset = 0

            # if first, add n packets to list
            if first:

                # get left over space / data size
                size_of_data_left_to_transmit = min(
                    length_left_in_packet -
                    WORDS_FOR_COMMAND_N_MISSING_TRANSACTION,
                    len(missing_seq_nums) - seq_num_offset)

                # build data holder accordingly
                data = bytearray(
                    (size_of_data_left_to_transmit +
                     WORDS_FOR_COMMAND_N_MISSING_TRANSACTION) * BYTES_PER_WORD)

                # pack flag and n packets
                _ONE_WORD.pack_into(
                    data, offset, DATA_OUT_COMMANDS.START_MISSING_SEQ.value)
                _TWO_WORDS.pack_into(
                    data, BYTES_PER_WORD, transaction_id, n_packets)

                # update state
                offset += (
                    WORDS_FOR_COMMAND_N_MISSING_TRANSACTION * BYTES_PER_WORD)
                length_left_in_packet -= (
                    WORDS_FOR_COMMAND_N_MISSING_TRANSACTION)
                first = False

            else:  # just add data
                # get left over space / data size
                size_of_data_left_to_transmit = min(
                    WORDS_PER_FULL_PACKET_WITH_SEQUENCE_NUM,
                    len(missing_seq_nums) - seq_num_offset)

                # build data holder accordingly
                data = bytearray(
                    (size_of_data_left_to_transmit +
                     WORDS_FOR_COMMAND_TRANSACTION) * BYTES_PER_WORD)

                # pack flag
                _TWO_WORDS.pack_into(
                    data, offset,
                    DATA_OUT_COMMANDS.MISSING_SEQ.value, transaction_id)
                offset += BYTES_PER_WORD * WORDS_FOR_COMMAND_TRANSACTION
                length_left_in_packet -= WORDS_FOR_COMMAND_TRANSACTION

            # fill data field
            n_word_struct(size_of_data_left_to_transmit).pack_into(
                data, offset, *missing_seq_nums[
                    seq_num_offset:
                    seq_num_offset + size_of_data_left_to_transmit])
            seq_num_offset += length_left_in_packet

            # build SDP message and send it to the core
            transceiver.send_sdp_message(self.__make_sdp_message(
                placement, SDP_PORTS.EXTRA_MONITOR_CORE_DATA_SPEED_UP, data))

            # sleep for ensuring core doesn't lose packets
            time.sleep(self._TIMEOUT_FOR_SENDING_IN_SECONDS)
            # self._print_packet_num_being_sent(packet_count, n_packets)
        return False

    def _process_data(
            self, data, seq_nums, finished, placement, transceiver,
            lost_seq_nums, transaction_id):
        """ Take a packet and processes it see if we're finished yet.

        :param bytearray data: the packet data
        :param set(int) seq_nums: the list of sequence numbers received so far
        :param bool finished: bool which states if finished or not
        :param ~.Placement placement:
            placement object for location on machine
        :param ~.Transceiver transceiver: spinnman instance
        :param int transaction_id: the transaction ID for this stream
        :param list(int) lost_seq_nums:
            the list of n sequence numbers lost per iteration
        :return: set of data items, if its the first packet, the list of
            sequence numbers, the sequence number received and if its finished
        :rtype: tuple(set(int), bool)
        """
        # pylint: disable=too-many-arguments
        # self._print_out_packet_data(data)
        length_of_data = len(data)
        first_packet_element, = _ONE_WORD.unpack_from(data, 0)

        # get flags
        seq_num = first_packet_element & self._SEQUENCE_NUMBER_MASK
        is_end_of_stream = (
            first_packet_element & self._LAST_MESSAGE_FLAG_BIT_MASK) != 0

        # check seq num not insane
        if seq_num > self._max_seq_num:
            raise Exception(
                "got an insane sequence number. got {} when "
                "the max is {} with a length of {}".format(
                    seq_num, self._max_seq_num, length_of_data))

        # figure offset for where data is to be put
        offset = self._calculate_offset(seq_num)

        # write data

        # read offset from data is at byte 8. as first 4 is seq num,
        # second 4 is transaction id
        true_data_length = (
                offset + length_of_data - BYTES_FOR_SEQ_AND_TRANSACTION_ID)
        if (not is_end_of_stream or
                length_of_data != BYTES_FOR_SEQ_AND_TRANSACTION_ID):
            self._write_into_view(
                offset, true_data_length, data,
                BYTES_FOR_SEQ_AND_TRANSACTION_ID, length_of_data, seq_num,
                length_of_data, False)

        # add seq num to list
        seq_nums.add(seq_num)

        # if received a last flag on its own, its during retransmission.
        #  check and try again if required
        if is_end_of_stream:
            if not self._check(seq_nums):
                finished = self._determine_and_retransmit_missing_seq_nums(
                    placement=placement, transceiver=transceiver,
                    seq_nums=seq_nums, lost_seq_nums=lost_seq_nums,
                    transaction_id=transaction_id)
            else:
                finished = True
        return seq_nums, finished

    @staticmethod
    def _calculate_offset(seq_num):
        """
        :param int seq_num:
        :rtype: int
        """
        return (seq_num * WORDS_PER_FULL_PACKET_WITH_SEQUENCE_NUM *
                BYTES_PER_WORD)

    def _write_into_view(
            self, view_start_position, view_end_position,
            data, data_start_position, data_end_position, seq_num,
            packet_length, is_final):
        """ Puts data into the view

        :param int view_start_position: where in view to start
        :param int view_end_position: where in view to end
        :param bytearray data: the data holder to write from
        :param int data_start_position: where in data holder to start from
        :param int data_end_position: where in data holder to end
        :param int seq_num: the sequence number to figure
        :raises Exception: If the position to write to is crazy
        """
        # pylint: disable=too-many-arguments
        if view_end_position > len(self._output):
            raise Exception(
                "I'm trying to add to my output data, but am trying to add "
                "outside my acceptable output positions! max is {} and I "
                "received a request to fill to {} from {} for sequence num "
                "{} from max sequence num {} length of packet {} and "
                "final {}".format(
                    len(self._output), view_end_position, view_start_position,
                    seq_num, self._max_seq_num - 1, packet_length, is_final))
        self._view[view_start_position: view_end_position] = \
            data[data_start_position:data_end_position]

    def _check(self, seq_nums):
        """ Verify if the sequence numbers are correct.

        :param list(int) seq_nums: the received sequence numbers
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

        :return: the biggest sequence num expected
        :rtype: int
        """
        return ceildiv(
            len(self._output),
            WORDS_PER_FULL_PACKET_WITH_SEQUENCE_NUM * BYTES_PER_WORD)

    @staticmethod
    def _print_missing(seq_nums):
        """ Debug printer for the missing sequence numbers from the pile.

        :param list(int) seq_nums: the sequence numbers received so far
        """
        for seq_num in sorted(seq_nums):
            log.info("from list I'm missing sequence num {}", seq_num)

    @staticmethod
    def _print_missing_n_packets(n_packets):
        """ Debug printer for the number of missing packets from the pile.

        :param n_packets: the number of packets
        """
        log.info("missing packets = {}", n_packets)

    @staticmethod
    def _print_out_packet_data(data, position):
        """ Debug prints out the data from the packet.

        :param bytearray data: the packet data
        """
        reread_data = struct.unpack("<{}B".format(len(data)), data)
        output = ""
        position2 = position
        log.debug("size of data is {}".format((len(data) / 4) - 3))
        for index, reread_data_element in enumerate(reread_data):
            if index >= 12:
                output += "{}:{},".format(position2, reread_data_element)
                position2 += 1
        log.debug("converted data back into readable form is {}", output)

    @staticmethod
    def _print_length_of_received_seq_nums(seq_nums, max_needed):
        """ Debug helper method for figuring out if everything been received.

        :param list(int) seq_nums: sequence numbers received
        :param int max_needed: biggest expected to have
        """
        if len(seq_nums) != max_needed:
            log.info("should have received {} sequence numbers, but received "
                     "{} sequence numbers", max_needed, len(seq_nums))

    @staticmethod
    def _print_packet_num_being_sent(packet_count, n_packets):
        """ Debug helper for printing missing sequence number packet\
            transmission.

        :param int packet_count: which packet is being fired
        :param int n_packets: how many packets to fire.
        """
        log.debug("send SDP packet with missing sequence numbers: {} of {}",
                  packet_count + 1, n_packets)


class _StreamingContextManager(object):
    """ The implementation of the context manager object for streaming \
        configuration control.
    """
    __slots__ = ["_gatherers", "_monitors", "_placements", "_txrx"]

    def __init__(self, gatherers, txrx, monitors, placements):
        """
        :param iterable(DataSpeedUpPacketGatherMachineVertex) gatherers:
        :param ~spinnman.transceiver.Transceiver txrx:
        :param list(ExtraMonitorSupportMachineVertex) monitors:
        :param ~pacman.model.placements.Placements placements:
        """
        self._gatherers = list(gatherers)
        self._txrx = txrx
        self._monitors = monitors
        self._placements = placements

    def __enter__(self):
        for gatherer in self._gatherers:
            gatherer.load_system_routing_tables(
                self._txrx, self._monitors, self._placements)
        for gatherer in self._gatherers:
            gatherer.set_cores_for_data_streaming(
                self._txrx, self._monitors, self._placements)

    def __exit__(self, _type, _value, _tb):
        for gatherer in self._gatherers:
            gatherer.unset_cores_for_data_streaming(
                self._txrx, self._monitors, self._placements)
        for gatherer in self._gatherers:
            gatherer.load_application_routing_tables(
                self._txrx, self._monitors, self._placements)
        return False

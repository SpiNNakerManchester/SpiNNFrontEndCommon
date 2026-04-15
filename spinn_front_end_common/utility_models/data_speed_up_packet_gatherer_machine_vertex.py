# Copyright (c) 2017 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations
import os
import datetime
import logging
import time
import struct
from enum import Enum, IntEnum
from typing import (
    Any, BinaryIO, Iterable, List, Optional, Set, Tuple, Union,
    TYPE_CHECKING)

from spinn_utilities.config_holder import get_config_bool, get_report_path
from spinn_utilities.overrides import overrides
from spinn_utilities.log import FormatAdapter
from spinn_utilities.typing.coords import XY

from spinn_machine import Chip

from spinnman.exceptions import SpinnmanTimeoutException
from spinnman.messages.sdp import SDPMessage, SDPHeader, SDPFlag
from spinnman.model.enums import (
    CPUState, ExecutableType, SDP_PORTS, UserRegister)
from spinnman.connections.udp_packet_connections import SCAMPConnection
from spinnman.spalloc.spalloc_allocator import SpallocJobController

from pacman.model.graphs.machine import MachineVertex
from pacman.model.resources import ConstantSDRAM, IPtagResource
from pacman.model.placements import Placement

from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.provenance import ProvenanceWriter
from spinn_front_end_common.utilities.helpful_functions import (
    convert_vertices_to_core_subset, n_word_struct)
from spinn_front_end_common.utilities.emergency_recovery import (
    emergency_recover_state_from_failure)
from spinn_front_end_common.abstract_models import (
    AbstractHasAssociatedBinary, AbstractGeneratesDataSpecification)
from spinn_front_end_common.interface.provenance import (
    AbstractProvidesProvenanceDataFromMachine)
from spinn_front_end_common.utilities.constants import (
    BYTES_PER_WORD, BYTES_PER_KB)
from spinn_front_end_common.utilities.utility_calls import (
    get_region_base_address_offset, retarget_tag)
from spinn_front_end_common.utilities.exceptions import SpinnFrontEndException
from spinn_front_end_common.utilities.scp import ReinjectorControlProcess
from spinn_front_end_common.utilities.utility_objs import ReInjectionStatus
from spinn_front_end_common.interface.ds import DataSpecificationGenerator
if TYPE_CHECKING:
    from .extra_monitor_support_machine_vertex import \
        ExtraMonitorSupportMachineVertex

log = FormatAdapter(logging.getLogger(__name__))

# shift by for the destination x coordinate in the word.
DEST_X_SHIFT = 16

TIMEOUT_RETRY_LIMIT = 100
_MINOR_LOSS_THRESHOLD = 10

# cap for stopping wrap arounds
TRANSACTION_ID_CAP = 0xFFFFFFFF

#: number of items used up by the retransmit code for its header
SDP_RETRANSMISSION_HEADER_SIZE = 2

#: size of config region in bytes
#: 1.new sequence key, 2.first data key, 3. transaction id key
# 4.end flag key, 5.base key, 6.iptag tag
CONFIG_SIZE = 6 * BYTES_PER_WORD

#: items of data a SDP packet can hold when SCP header removed
WORDS_PER_FULL_PACKET = 68  # 272 bytes as removed SCP header

#: size of items the sequence number uses
SEQUENCE_NUMBER_SIZE_IN_ITEMS = 1

#: transaction id size in words
TRANSACTION_ID_SIZE_IN_ITEMS = 1

#: the size in words of the command flag
COMMAND_SIZE_IN_ITEMS = 1

#: offset for missing sequence starts in first packet
WORDS_FOR_COMMAND_N_MISSING_TRANSACTION = 3

#: offset for missing sequence starts in more packet
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
#: (command, transaction_id, sequence number)
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
#: x, y, key (all int values) for possible 48 chips, plus n chips to read,
# the reinjector base key.
SIZE_DATA_IN_CHIP_TO_KEY_SPACE = ((3 * 48) + 2) * BYTES_PER_WORD


class _DataRegions(IntEnum):
    """
    DSG data regions.
    """
    CONFIG = 0
    CHIP_TO_KEY_SPACE = 1
    PROVENANCE_REGION = 2


class _ProvLabels(str, Enum):
    SENT = "Sent_SDP_Packets"
    RECEIVED = "Received_SDP_Packets"
    IN_STREAMS = "Speed_Up_Input_Streams"
    OUT_STREAMS = "Speed_Up_Output_Streams"


class _DataOutCommands(IntEnum):
    """
    Command IDs for the SDP packets for data out.
    """
    START_SENDING = 100
    START_MISSING_SEQ = 1000
    MISSING_SEQ = 1001
    CLEAR = 2000


class _DataInCommands(IntEnum):
    """
    Command IDs for the SDP packets for data in.
    """
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

# provenance data size
_PROVENANCE_DATA_SIZE = int(_FOUR_WORDS.size)


def ceildiv(dividend: float, divisor: int) -> int:
    """
    How to divide two possibly-integer numbers and round up.

    :returns: dividend / divisor rounded UP to the nearest integer
    """
    assert divisor > 0
    q, r = divmod(dividend, divisor)
    return int(q) + (r != 0)


# SDRAM requirement for storing missing SDP packets sequence numbers
SDRAM_FOR_MISSING_SDP_SEQ_NUMS = ceildiv(
    120.0 * 1024 * BYTES_PER_KB,
    WORDS_PER_FULL_PACKET_WITH_SEQUENCE_NUM * BYTES_PER_WORD)


class DataSpeedUpPacketGatherMachineVertex(
        MachineVertex, AbstractGeneratesDataSpecification,
        AbstractHasAssociatedBinary,
        AbstractProvidesProvenanceDataFromMachine):
    """
    Machine vertex for handling fast data transfer between host and  SpiNNaker.
    This machine vertex is only ever placed on chips with a working Ethernet
    connection; it collaborates with the
    :py:class:`ExtraMonitorSupportMachineVertex` to write data on other chips.

    .. note::
        This is an unusual machine vertex, in that it has no associated
        application vertex.
    """
    __slots__ = (
        # x coordinate
        "_x",
        # y coordinate
        "_y",
        # word with x and y
        "_coord_word",
        # transaction id
        "_transaction_id",
        # IP address
        "_ip_address",
        # store for the last reinjection status
        "_last_status",
        # the max sequence number expected given a data retrieval
        "_max_seq_num",
        # holder for missing sequence numbers for data in
        "_missing_seq_nums_data_in",
        # holder of data from out
        "_output",
        # my placement for future lookup
        "__placement",
        # Count of the runs for provenance data
        "_run",
        "_remote_tag",
        # data holder for output
        "_view")

    #: base key (really nasty hack to tie in fixed route keys)
    BASE_KEY = 0xFFFFFFF9
    NEW_SEQ_KEY = 0xFFFFFFF8
    FIRST_DATA_KEY = 0xFFFFFFF7
    END_FLAG_KEY = 0xFFFFFFF6
    TRANSACTION_ID_KEY = 0xFFFFFFF5

    #: to use with multicast stuff
    # (reinjection acknowledgements have to be fixed route)
    BASE_MASK = 0xFFFFFFFB
    NEW_SEQ_KEY_OFFSET = 1
    FIRST_DATA_KEY_OFFSET = 2
    END_FLAG_KEY_OFFSET = 3
    TRANSACTION_ID_KEY_OFFSET = 4

    # throttle on the transmission
    _TRANSMISSION_THROTTLE_TIME = 0.000001

    # the end flag is set when the high bit of the sequence number word is set
    _LAST_MESSAGE_FLAG_BIT_MASK = 0x80000000
    # corresponding mask for the actual sequence numbers
    _SEQUENCE_NUMBER_MASK = 0x7fffffff

    # time outs used by the protocol for separate bits
    _TIMEOUT_PER_RECEIVE_IN_SECONDS = 2
    _TIMEOUT_FOR_SENDING_IN_SECONDS = 0.01

    # end flag for missing sequence numbers
    _MISSING_SEQ_NUMS_END_FLAG = 0xFFFFFFFF

    # flag for saying missing all sequence numbers
    FLAG_FOR_MISSING_ALL_SEQUENCES = 0xFFFFFFFE

    _ADDRESS_PACKET_BYTE_FORMAT = struct.Struct(
        f"<{BYTES_IN_FULL_PACKET_WITH_KEY}B")

    # Router timeouts, in mantissa,exponent form. See datasheet for details
    _LONG_TIMEOUT = (14, 14)
    _SHORT_TIMEOUT = (1, 1)
    _TEMP_TIMEOUT = (15, 4)
    _ZERO_TIMEOUT = (0, 0)

    # Initial port for the reverse IP tag (to be replaced later)
    _TAG_INITIAL_PORT = 10000

    def __init__(self, x: int, y: int, ip_address: str):
        """
        :param x: Where this gatherer is.
        :param y: Where this gatherer is.
        :param ip_address:
            How to talk directly to the chip where the gatherer is.
        """
        super().__init__(
            label=f"SYSTEM:PacketGatherer({x},{y})", app_vertex=None)

        # data holders for the output, and sequence numbers
        self._view: Optional[memoryview] = None
        self._max_seq_num = 0
        self._output: Optional[bytearray] = None

        self._transaction_id = 0

        self._missing_seq_nums_data_in: List[Set[int]] = list()

        # Create a connection to be used
        self._x, self._y = x, y
        self._coord_word: Optional[int] = None
        self._ip_address = ip_address
        self._remote_tag: Optional[int] = None

        # local provenance storage
        self._run = 0
        self.__placement: Optional[Placement] = None

        # Stored reinjection status for resetting timeouts
        self._last_status: Optional[ReInjectionStatus] = None

    def __throttled_send(
            self, message: SDPMessage, connection: SCAMPConnection) -> None:
        """
        Slows down transmissions to allow SpiNNaker to keep up.

        :param message: message to send
        """
        # send first message
        connection.send_sdp_message(message)
        time.sleep(self._TRANSMISSION_THROTTLE_TIME)

    @property
    @overrides(MachineVertex.sdram_required)
    def sdram_required(self) -> ConstantSDRAM:
        return ConstantSDRAM(
                CONFIG_SIZE + SDRAM_FOR_MISSING_SDP_SEQ_NUMS +
                SIZE_DATA_IN_CHIP_TO_KEY_SPACE + _PROVENANCE_DATA_SIZE)

    @property
    @overrides(MachineVertex.iptags)
    def iptags(self) -> List[IPtagResource]:
        return [IPtagResource(
            port=self._TAG_INITIAL_PORT, strip_sdp=True,
            ip_address="localhost", traffic_identifier="DATA_SPEED_UP")]

    def _read_transaction_id_from_machine(self) -> None:
        """
        Looks up from the machine what the current transaction ID is
        and updates the data speed up gatherer.
        """
        self._transaction_id = FecDataView.get_transceiver().read_user(
            self._placement.x, self._placement.y, self._placement.p,
            UserRegister.USER_1)

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self) -> ExecutableType:
        return ExecutableType.SYSTEM

    @overrides(AbstractGeneratesDataSpecification.generate_data_specification)
    def generate_data_specification(self, spec: DataSpecificationGenerator,
                                    placement: Placement) -> None:
        # update my placement for future knowledge
        self.__placement = placement

        # Create the data regions for hello world
        self._reserve_memory_regions(spec)

        # the keys for the special cases
        new_seq_key = self.NEW_SEQ_KEY
        first_data_key = self.FIRST_DATA_KEY
        end_flag_key = self.END_FLAG_KEY
        base_key = self.BASE_KEY
        transaction_id_key = self.TRANSACTION_ID_KEY

        spec.switch_write_focus(_DataRegions.CONFIG)
        spec.write_value(new_seq_key)
        spec.write_value(first_data_key)
        spec.write_value(transaction_id_key)
        spec.write_value(end_flag_key)
        spec.write_value(base_key)

        # locate the tag ID for our data and update with a port
        # Note: The port doesn't matter as we are going to override this later
        iptags = FecDataView.get_tags().get_ip_tags_for_vertex(self)
        if iptags is None:
            raise SpinnFrontEndException("no allocated IPTag")
        iptag = iptags[0]
        spec.write_value(iptag.tag)
        self._remote_tag = iptag.tag

        # write multi cast chip key map
        machine = FecDataView.get_machine()
        spec.switch_write_focus(_DataRegions.CHIP_TO_KEY_SPACE)
        chip_xys_on_board = list(machine.get_existing_xys_on_board(
            machine[placement.xy]))

        # write how many chips to read
        spec.write_value(len(chip_xys_on_board))

        # write the broad cast keys for timeouts
        router_timeout_key = (
            FecDataView.get_system_multicast_router_timeout_keys())
        spec.write_value(router_timeout_key[placement.xy])

        mc_data_chips_to_keys = (
            FecDataView.get_data_in_multicast_key_to_chip_map())
        # write each chip x and y and base key
        for chip_xy in chip_xys_on_board:
            local_x, local_y = machine.get_local_xy(machine[chip_xy])
            spec.write_value(local_x)
            spec.write_value(local_y)
            spec.write_value(mc_data_chips_to_keys[chip_xy])
            log.debug("for chip {}:{} base key is {}",
                      chip_xy[0], chip_xy[1], mc_data_chips_to_keys[chip_xy])

        # End-of-Spec:
        spec.end_specification()

    @property
    def _placement(self) -> Placement:
        if self.__placement is None:
            raise SpinnFrontEndException("placement not known")
        return self.__placement

    def _reserve_memory_regions(
            self, spec: DataSpecificationGenerator) -> None:
        """
        Writes the DSG regions memory sizes. Static so that it can be used
        by the application vertex.

        :param spec: spec file
        """
        spec.reserve_memory_region(
            region=_DataRegions.CONFIG,
            size=CONFIG_SIZE,
            label="config")
        spec.reserve_memory_region(
            region=_DataRegions.CHIP_TO_KEY_SPACE,
            size=SIZE_DATA_IN_CHIP_TO_KEY_SPACE,
            label="mc_key_map")
        spec.reserve_memory_region(
            region=_DataRegions.PROVENANCE_REGION,
            size=_PROVENANCE_DATA_SIZE, label="Provenance")

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self) -> str:
        return "data_speed_up_packet_gatherer.aplx"

    def _generate_data_in_report(
            self, time_diff: datetime.timedelta, data_size: int, x: int,
            y: int, address_written_to: int) -> None:
        """
        Writes the data in report for this stage.

        :param time_diff: the time taken to write the memory
        :param data_size: the size of data that was written in bytes
        :param x:
            the location in machine where the data was written to X axis
        :param y:
            the location in machine where the data was written to Y axis
        :param address_written_to: where in SDRAM it was written to
        """
        in_report_path = get_report_path("path_data_speed_up_reports_speeds")
        if not os.path.isfile(in_report_path):
            with open(in_report_path, "w", encoding="utf-8") as writer:
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
            mbs: Any = "unknown, below threshold"
        else:
            mbs = megabits / (float(time_took_ms) / 100000.0)

        with open(in_report_path, "a", encoding="utf-8") as writer:
            writer.write(
                f"{x}\t\t {y}\t\t {address_written_to}\t\t {data_size}\t\t"
                f"\t\t {time_took_ms}\t\t\t {mbs}\t\t "
                f"{self._missing_seq_nums_data_in}\n")

    def send_data_into_spinnaker(
            self, x: int, y: int, base_address: int,
            data: Union[BinaryIO, bytes, str, int], *,
            n_bytes: Optional[int] = None, offset: int = 0) -> None:
        """
        Sends a block of data into SpiNNaker to a given chip.

        :param x: chip x for data
        :param y: chip y for data
        :param base_address: the address in SDRAM to start writing memory
        :param data:
            the data to write or filename to load data from (if a string)
        :param n_bytes: how many bytes to read, or `None` if not set
        :param offset: where in the data to start from
        """
        # if file, read in and then process as normal
        if isinstance(data, str):
            if offset != 0:
                raise ValueError(
                    "when using a file, you can only have a offset of 0")

            with open(data, "rb") as reader:
                # n_bytes=None already means 'read everything'
                data = reader.read(n_bytes)
            # Number of bytes to write is now length of buffer we have
            if n_bytes is None:
                n_bytes = len(data)
            else:
                n_bytes = min(n_bytes, len(data))
        elif not isinstance(data, (bytes, bytearray)):
            raise ValueError("that type of data not supported")
        if n_bytes is None:
            n_bytes = len(data)
        if n_bytes < 0:
            raise ValueError("cannot write a negative amount of data")

        destination = FecDataView.get_chip_at(x, y)
        # start time recording
        start = datetime.datetime.now()
        # send data
        self._send_data_via_extra_monitors(
            destination, base_address, data[offset:n_bytes + offset])
        # end time recording
        end = datetime.datetime.now()

        if VERIFY_SENT_DATA:
            original_data = bytes(data[offset:n_bytes + offset])
            transceiver = FecDataView.get_transceiver()
            verified_data = bytes(transceiver.read_memory(
                x, y, base_address, n_bytes))
            self.__verify_sent_data(
                original_data, verified_data, x, y, base_address, n_bytes)

        # write report
        if get_config_bool("Reports", "write_data_speed_up_reports"):
            self._generate_data_in_report(
                x=x, y=y, time_diff=end - start,
                data_size=n_bytes, address_written_to=base_address)

    @staticmethod
    def __verify_sent_data(
            original_data: bytes, verified_data: bytes, x: int, y: int,
            base_address: int, n_bytes: int) -> None:
        if original_data != verified_data:
            log.error("VARIANCE: chip:{},{} address:{} len:{}",
                      x, y, base_address, n_bytes)
            log.error("original:{}", original_data.hex())
            log.error("verified:{}", verified_data.hex())
            for i, (a, b) in enumerate(zip(original_data, verified_data)):
                if a != b:
                    raise ValueError(f"Mismatch found as position {i}")

    def __make_data_in_message(self, payload: bytes) -> SDPMessage:
        return SDPMessage(
            sdp_header=SDPHeader(
                destination_chip_x=self._placement.x,
                destination_chip_y=self._placement.y,
                destination_cpu=self._placement.p,
                destination_port=(
                    SDP_PORTS.EXTRA_MONITOR_CORE_DATA_IN_SPEED_UP.value),
                flags=SDPFlag.REPLY_NOT_EXPECTED),
            data=payload)

    @staticmethod
    def __make_data_out_message(
            placement: Placement, payload: bytes) -> SDPMessage:
        return SDPMessage(
            sdp_header=SDPHeader(
                destination_chip_x=placement.x,
                destination_chip_y=placement.y,
                destination_cpu=placement.p,
                destination_port=(
                    SDP_PORTS.EXTRA_MONITOR_CORE_DATA_SPEED_UP.value),
                flags=SDPFlag.REPLY_NOT_EXPECTED),
            data=payload)

    def __open_connection(self) -> SCAMPConnection:
        """
        Open an SCP connection and make our tag target it.

        :return: The opened connection, ready for use.
        """
        connection: Optional[SCAMPConnection] = None
        if FecDataView.has_allocation_controller():
            controller = FecDataView.get_allocation_controller()
            if isinstance(controller, SpallocJobController):
                # See if the allocation controller wants to do it
                connection = controller.open_sdp_connection(
                    self._x, self._y)
        if connection is None:
            connection = SCAMPConnection(
                self._x, self._y, remote_host=self._ip_address)

        assert self._remote_tag is not None
        retarget_tag(connection, self._x, self._y, self._remote_tag)
        return connection

    def _send_data_via_extra_monitors(
            self, destination_chip: Chip, start_address: int,
            data_to_write: bytes) -> None:
        """
        Sends data using the extra monitor cores.

        :param destination_chip: chip to send to
        :param start_address: start address in SDRAM to write data to
        :param data_to_write: the data to write
        """
        # Set up the connection
        with self.__open_connection() as connection:
            # how many packets after first one we need to send
            self._max_seq_num = ceildiv(
                len(data_to_write), BYTES_IN_FULL_PACKET_WITH_KEY)

            # determine board chip IDs, as the LPG does not know
            # machine scope IDs
            machine = FecDataView.get_machine()
            dest_x, dest_y = machine.get_local_xy(destination_chip)
            self._coord_word = (dest_x << DEST_X_SHIFT) | dest_y

            # for safety, check the transaction id from the machine before
            # updating
            self._read_transaction_id_from_machine()
            self._transaction_id = (
                self._transaction_id + 1) & TRANSACTION_ID_CAP
            time_out_count = 0

            # verify completed
            received_confirmation = False
            while not received_confirmation:
                # send initial attempt at sending all the data
                self._send_all_data_based_packets(
                    data_to_write, start_address, connection)

                # Don't create a missing buffer until at least one packet has
                # come back.
                missing: Optional[Set[int]] = None

                while not received_confirmation:
                    try:
                        # try to receive a confirmation of some sort from
                        # spinnaker
                        data = connection.receive(
                            timeout=self._TIMEOUT_PER_RECEIVE_IN_SECONDS)
                        time_out_count = 0

                        # Read command and transaction id
                        (cmd, transaction_id) = _TWO_WORDS.unpack_from(data, 0)

                        # If wrong transaction id, ignore packet
                        if self._transaction_id != transaction_id:
                            continue

                        # Decide what to do with the packet
                        if cmd == _DataInCommands.RECEIVE_FINISHED:
                            received_confirmation = True
                            break

                        if cmd != _DataInCommands.RECEIVE_MISSING_SEQ_DATA:
                            raise ValueError(f"Unknown command {cmd} received")

                        # The currently received packet has missing sequence
                        # numbers. Accumulate and dispatch transactionId when
                        # we've got them all.
                        if missing is None:
                            missing = set()
                            self._missing_seq_nums_data_in.append(missing)
                        seen_last, seen_all = self._read_in_missing_seq_nums(
                            data,
                            BYTES_FOR_RECEPTION_COMMAND_AND_ADDRESS_HEADER,
                            missing)

                        # Check that you've seen something that implies ready
                        # to retransmit.
                        if seen_all or seen_last:
                            self._outgoing_retransmit_missing_seq_nums(
                                data_to_write, missing, connection)
                            missing.clear()

                    except SpinnmanTimeoutException as e:
                        # if the timeout has not occurred x times, keep trying
                        time_out_count += 1
                        if time_out_count > TIMEOUT_RETRY_LIMIT:
                            emergency_recover_state_from_failure(
                                self, self._placement)
                            raise SpinnFrontEndException(
                                "Failed to hear from the machine during "
                                f"{time_out_count} attempts. "
                                "Please try removing firewalls.") from e

                        # If we never received a packet, we will never have
                        # created the buffer, so send everything again
                        if missing is None:
                            break

                        self._outgoing_retransmit_missing_seq_nums(
                                data_to_write, missing, connection)
                        missing.clear()

    def _read_in_missing_seq_nums(
            self, data: bytes, position: int,
            seq_nums: Set[int]) -> Tuple[bool, bool]:
        """
        Handles a missing sequence number packet from SpiNNaker.

        :param data: the data to translate into missing sequence numbers
        :param position: the position in the data to write.
        :param seq_nums: a set of sequence numbers to add to
        :return: seen_last flag and seen_all flag
        """
        # find how many elements are in this packet
        n_elements = (len(data) - position) // BYTES_PER_WORD

        # store missing
        new_seq_nums = n_word_struct(n_elements).unpack_from(
            data, position)

        # add missing sequence numbers accordingly
        seen_last = False
        seen_all = False
        if new_seq_nums[-1] == self._MISSING_SEQ_NUMS_END_FLAG:
            new_seq_nums = new_seq_nums[:-1]
            seen_last = True
        if new_seq_nums[-1] == self.FLAG_FOR_MISSING_ALL_SEQUENCES:
            for missing_seq in range(self._max_seq_num or 0):
                seq_nums.add(missing_seq)
            seen_all = True
        else:
            seq_nums.update(new_seq_nums)

        return seen_last, seen_all

    def _outgoing_retransmit_missing_seq_nums(
            self, data_to_write: bytes, missing: Set[int],
            connection: SCAMPConnection) -> None:
        """
        Transmits back into SpiNNaker the missing data based off missing
        sequence numbers.

        :param data_to_write: the data to write.
        :param missing: a set of missing sequence numbers
        """
        missing_seqs_as_list = list(missing)
        missing_seqs_as_list.sort()

        # send sequence data
        for missing_seq_num in missing_seqs_as_list:
            message, _length = self.__make_data_in_stream_message(
                data_to_write, missing_seq_num, None)
            self.__throttled_send(message, connection)

        # request an update on what is missing
        self.__send_tell_flag(connection)

    @staticmethod
    def __position_from_seq_number(seq_num: int) -> int:
        """
        Calculates where in the raw data to start reading from, given a
        sequence number.

        :param seq_num: the sequence number to determine position from
        :return: the position in the byte data
        """
        return BYTES_IN_FULL_PACKET_WITH_KEY * seq_num

    def __make_data_in_stream_message(
            self, data_to_write: bytes, seq_num: int,
            position: Optional[int]) -> Tuple[SDPMessage, int]:
        """
        Determine the data needed to be sent to the SpiNNaker machine
        given a sequence number.

        :param data_to_write:
            the data to write to the SpiNNaker machine
        :param seq_num: the sequence number to get the data for
        :param position:
            the position in the data to write to SpiNNaker,
            or None to infer from the sequence number
        :return: SDP message and how much data has been written
        """
        # check for last packet
        packet_data_length = BYTES_IN_FULL_PACKET_WITH_KEY

        # determine position in data if not given
        if position is None:
            position = self.__position_from_seq_number(seq_num)

        # if less than a full packet worth of data, adjust length
        if position + packet_data_length > len(data_to_write):
            packet_data_length = len(data_to_write) - position

        if packet_data_length < 0:
            raise ValueError("weird packet data length")

        # create message body
        packet_data = _THREE_WORDS.pack(
            _DataInCommands.SEND_SEQ_DATA, self._transaction_id,
            seq_num) + data_to_write[position:position+packet_data_length]

        # return message for sending, and the length in data sent
        return self.__make_data_in_message(packet_data), packet_data_length

    def __send_location(
            self, start_address: int, connection: SCAMPConnection) -> None:
        """
        Send location as separate message.

        :param start_address: SDRAM location
        """
        connection.send_sdp_message(self.__make_data_in_message(
            _FIVE_WORDS.pack(
                _DataInCommands.SEND_DATA_TO_LOCATION,
                self._transaction_id, start_address, self._coord_word,
                self._max_seq_num - 1)))
        log.debug(
            "start address for transaction {} is {}",
            self._transaction_id, start_address)

    def __send_tell_flag(self, connection: SCAMPConnection) -> None:
        """
        Send tell flag as separate message.
        """
        connection.send_sdp_message(self.__make_data_in_message(
            _TWO_WORDS.pack(
                _DataInCommands.SEND_TELL, self._transaction_id)))

    def _send_all_data_based_packets(
            self, data_to_write: bytes, start_address: int,
            connection: SCAMPConnection) -> None:
        """
        Send all the data as one block.

        :param data_to_write: the data to send
        :param start_address:
        """
        # Send the location
        self.__send_location(start_address, connection)

        # where in the data we are currently up to
        position_in_data = 0

        # send rest of data
        for seq_num in range(self._max_seq_num or 0):
            # put in command flag and sequence number
            message, length_to_send = self.__make_data_in_stream_message(
                data_to_write, seq_num, position_in_data)
            position_in_data += length_to_send

            # send the message
            self.__throttled_send(message, connection)
            log.debug("sent sequence {} of {} bytes", seq_num, length_to_send)

        # check for end flag
        self.__send_tell_flag(connection)
        log.debug("sent end flag")

    def set_cores_for_data_streaming(self) -> None:
        """
        Helper method for setting the router timeouts to a state usable
        for data streaming.
        """
        lead_monitor = FecDataView.get_monitor_by_xy(0, 0)
        # Store the last reinjection status for resetting
        # NOTE: This assumes the status is the same on all cores
        self._last_status = lead_monitor.get_reinjection_status()

        # Set to not inject dropped packets
        lead_monitor.set_reinjection_packets(
            point_to_point=False, multicast=False, nearest_neighbour=False,
            fixed_route=False)

        # Clear any outstanding packets from reinjection
        self.clear_reinjection_queue()

        # set time outs
        self.set_router_wait2_timeout(self._SHORT_TIMEOUT)
        self.set_router_wait1_timeout(self._LONG_TIMEOUT)

    @staticmethod
    def load_application_routing_tables() -> None:
        """
        Set all chips to have application table loaded in the router.
        """
        FecDataView.get_monitor_by_xy(0, 0).load_application_mc_routes()

    @staticmethod
    def load_system_routing_tables() -> None:
        """
        Set all chips to have the system table loaded in the router.
        """
        FecDataView.get_monitor_by_xy(0, 0).load_system_mc_routes()

    def set_router_wait1_timeout(self, timeout: Tuple[int, int]) -> None:
        """
        Set the wait1 field for a set of routers.

        :param timeout:
            The mantissa and exponent of the timeout value, each between
            0 and 15
        """
        mantissa, exponent = timeout
        core_subsets = convert_vertices_to_core_subset([self])
        process = ReinjectorControlProcess(
            FecDataView.get_scamp_connection_selector())
        try:
            process.set_wait1_timeout(mantissa, exponent, core_subsets)
        except:  # noqa: E722
            emergency_recover_state_from_failure(
                self, FecDataView.get_placement_of_vertex(self))
            raise

    def set_router_wait2_timeout(self, timeout: Tuple[int, int]) -> None:
        """
        Set the wait2 field for a set of routers.

        :param timeout:
            The mantissa and exponent of the timeout value, each between
            0 and 15
        """
        mantissa, exponent = timeout
        core_subsets = convert_vertices_to_core_subset([self])
        process = ReinjectorControlProcess(
            FecDataView.get_scamp_connection_selector())
        try:
            process.set_wait2_timeout(mantissa, exponent, core_subsets)
        except:  # noqa: E722
            emergency_recover_state_from_failure(
                self, FecDataView.get_placement_of_vertex(self))
            raise

    def clear_reinjection_queue(self) -> None:
        """
        Clears the queues for reinjection.
        """
        core_subsets = convert_vertices_to_core_subset([self])
        process = ReinjectorControlProcess(
            FecDataView.get_scamp_connection_selector())
        try:
            process.clear_queue(core_subsets)
        except:  # noqa: E722
            emergency_recover_state_from_failure(
                self, FecDataView.get_placement_of_vertex(self))
            raise

    def unset_cores_for_data_streaming(self) -> None:
        """
        Helper method for restoring the router timeouts to normal after
        being in a state usable for data streaming.
        """
        # Set the routers to temporary values
        self.set_router_wait1_timeout(self._TEMP_TIMEOUT)
        self.set_router_wait2_timeout(self._ZERO_TIMEOUT)

        if self._last_status is None:
            log.warning(
                "Cores have not been set for data extraction, so can't be"
                " unset")
            return
        try:
            self.set_router_wait1_timeout(
                self._last_status.router_wait1_timeout_parameters)
            self.set_router_wait2_timeout(
                self._last_status.router_wait2_timeout_parameters)

            lead_monitor = FecDataView.get_monitor_by_xy(0, 0)
            lead_monitor.set_reinjection_packets(
                point_to_point=self._last_status.is_reinjecting_point_to_point,
                multicast=self._last_status.is_reinjecting_multicast,
                nearest_neighbour=(
                    self._last_status.is_reinjecting_nearest_neighbour),
                fixed_route=self._last_status.is_reinjecting_fixed_route)
        except Exception:  # pylint: disable=broad-except
            log.exception("Error resetting timeouts")
            log.error("Checking if the cores are OK...")
            core_subsets = convert_vertices_to_core_subset(
                FecDataView.iterate_monitors())
            try:
                transceiver = FecDataView.get_transceiver()
                error_cores = transceiver.get_cpu_infos(
                    core_subsets, CPUState.RUNNING, include=False)
                if error_cores:
                    log.error("Cores in an unexpected state: {}", error_cores)
            except Exception:  # pylint: disable=broad-except
                log.exception("Couldn't get core state")

    def get_data(
            self, extra_monitor: ExtraMonitorSupportMachineVertex,
            placement: Placement, memory_address: int,
            length_in_bytes: int) -> bytes:
        """
        Gets data from a given core and memory address.

        :param extra_monitor:
            the extra monitor used for this data
        :param placement:
            placement object for where to get data from
        :param memory_address: the address in SDRAM to start reading from
        :param length_in_bytes: the length of data to read in bytes
        :return: byte array of the data
        """
        # create report elements
        if (get_config_bool("Reports", "write_data_speed_up_reports")
                and FecDataView.has_fixed_routes()):
            self._report_routers_used_for_out(placement)

        start = float(time.time())
        # if asked for no data, just return a empty byte array
        if length_in_bytes == 0:
            data = bytearray(0)
            end = float(time.time())
            with ProvenanceWriter() as db:
                # TODO Why log the time to not read???
                db.insert_gatherer(
                    placement.x, placement.y, memory_address, length_in_bytes,
                    self._run, "No Extraction time", end - start)
            return data

        # Update the IP Tag to work through a NAT firewall
        with self.__open_connection() as connection:
            # update transaction id for extra monitor
            extra_monitor.update_transaction_id()
            transaction_id = extra_monitor.transaction_id

            # send
            connection.send_sdp_message(self.__make_data_out_message(
                placement, _FOUR_WORDS.pack(
                    _DataOutCommands.START_SENDING, transaction_id,
                    memory_address, length_in_bytes)))

            # receive
            self._output = bytearray(length_in_bytes)
            self._view = memoryview(self._output)
            self._max_seq_num = self.__calculate_max_seq_num()
            lost_seq_nums = self._receive_data(
                placement, connection, transaction_id)

            # Stop anything else getting through (and reduce traffic)
            connection.send_sdp_message(self.__make_data_out_message(
                placement, _TWO_WORDS.pack(
                    _DataOutCommands.CLEAR, transaction_id)))

        end = float(time.time())
        with ProvenanceWriter() as db:
            db.insert_gatherer(
                placement.x, placement.y, memory_address, length_in_bytes,
                self._run, "Extraction time", end - start)
            for lost_seq_num in lost_seq_nums:
                if lost_seq_num > _MINOR_LOSS_THRESHOLD:
                    db.insert_report(
                        f"During the extraction of data of {length_in_bytes} "
                        f"bytes from memory address {memory_address} on "
                        f"chip ({placement.x}, {placement.y}), "
                        f"{lost_seq_num} sequences were lost.")
                if lost_seq_num > 0:
                    db.insert_gatherer(
                        placement.x, placement.y, memory_address,
                        length_in_bytes, self._run, "Lost_seq_nums",
                        lost_seq_num)

        return self._output

    def _receive_data(
            self, placement: Placement, connection: SCAMPConnection,
            transaction_id: int) -> List[int]:
        seq_nums: Set[int] = set()
        lost_seq_nums: List[int] = list()
        timeoutcount = 0
        finished = False
        while not finished:
            try:
                data = connection.receive(self._TIMEOUT_PER_RECEIVE_IN_SECONDS)
                response_transaction_id, = _ONE_WORD.unpack_from(data, 4)
                if transaction_id == response_transaction_id:
                    timeoutcount = 0
                    seq_nums, finished = self._process_data(
                        data, seq_nums, finished, placement,
                        lost_seq_nums, transaction_id, connection)
                else:
                    log.info(
                        "ignoring packet as transaction id should be {}"
                        " but is {}", transaction_id, response_transaction_id)
            except SpinnmanTimeoutException as e:
                if timeoutcount > TIMEOUT_RETRY_LIMIT:
                    raise SpinnFrontEndException(
                        "Failed to hear from the machine during "
                        f"{timeoutcount} attempts. "
                        "Please try removing firewalls") from e

                timeoutcount += 1
                # self.__reset_connection()
                if not finished:
                    finished = self._determine_and_retransmit_missing_seq_nums(
                        seq_nums, placement, lost_seq_nums, transaction_id,
                        connection)
        return lost_seq_nums

    @staticmethod
    def __describe_fixed_route_from(placement: Placement) -> List[XY]:
        """
        Traverse the fixed route paths from a given location to its
        destination. Used for determining which routers were used.

        :param placement: the source to start from
        :return: list of chip locations
        """
        routers = [placement.xy]
        fixed_routes = FecDataView.get_fixed_routes()
        chip = placement.chip
        entry = fixed_routes[(placement.xy)]
        while not entry.processor_ids:
            # can assume one link, as its a minimum spanning tree going to
            # the root
            link = chip.router.get_link(next(iter(entry.link_ids)))
            assert link is not None
            chip = FecDataView.get_chip_at(
                link.destination_x, link.destination_y)
            routers.append((link.destination_x, link.destination_y))
            entry = fixed_routes[(link.destination_x, link.destination_y)]
        return routers

    def _report_routers_used_for_out(self, placement: Placement) -> None:
        """
        Write the used routers into a report.

        :param placement:
            The placement that we have been routing data out from
        """
        routers_used = self.__describe_fixed_route_from(placement)
        out_report_path = get_report_path("path_data_speed_up_reports_routers")
        with open(out_report_path, "a", encoding="utf-8") as writer:
            writer.write(
                f"[{placement.x}:{placement.y}:{placement.p}] "
                f"= {routers_used}\n")

    def __missing_seq_nums(self, seq_nums: Set[int]) -> List[int]:
        """
        Determine which sequence numbers we've missed.

        :param seq_nums: the set already acquired
        :return: list of missing sequence numbers
        """
        return [sn for sn in range(self._max_seq_num) if sn not in seq_nums]

    def _determine_and_retransmit_missing_seq_nums(
            self, seq_nums: Set[int], placement: Placement,
            lost_seq_nums: List[int], transaction_id: int,
            connection: SCAMPConnection) -> bool:
        """
        Determine if there are any missing sequence numbers, and if so
        retransmits the missing sequence numbers back to the core for
        retransmission.

        :param seq_nums: the sequence numbers already received
        :param placement: placement instance
        :param lost_seq_nums:
        :param transaction_id: transaction_id
        :param connection: how to talk to the board
        :return: whether all packets are transmitted
        """
        # locate missing sequence numbers from pile
        missing_seq_nums = self.__missing_seq_nums(seq_nums)

        lost_seq_nums.append(len(missing_seq_nums))
        # for seq_num in sorted(seq_nums):
        #     log.debug("from list I'm missing sequence number {}", seq_num)
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
        # log.debug("missing packets = {}", n_packets)

        # transmit missing sequence as a new SDP packet
        first = True
        seq_num_offset = 0
        for _packet_count in range(n_packets):
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
                _THREE_WORDS.pack_into(
                    data, 0, _DataOutCommands.START_MISSING_SEQ,
                    transaction_id, n_packets)

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
                    data, offset, _DataOutCommands.MISSING_SEQ,
                    transaction_id)
                offset += BYTES_PER_WORD * WORDS_FOR_COMMAND_TRANSACTION
                length_left_in_packet -= WORDS_FOR_COMMAND_TRANSACTION

            # fill data field
            n_word_struct(size_of_data_left_to_transmit).pack_into(
                data, offset, *missing_seq_nums[
                    seq_num_offset:
                    seq_num_offset + size_of_data_left_to_transmit])
            seq_num_offset += length_left_in_packet

            # build SDP message and send it to the core
            connection.send_sdp_message(self.__make_data_out_message(
                placement, data))

            # sleep for ensuring core doesn't lose packets
            time.sleep(self._TIMEOUT_FOR_SENDING_IN_SECONDS)
            # log.debug(
            #     "send SDP packet with missing sequence numbers: {} of {}",
            #     _packet_count + 1, n_packets)
        return False

    def _process_data(
            self, data: bytes, seq_nums: Set[int], finished: bool,
            placement: Placement, lost_seq_nums: List[int],
            transaction_id: int,
            connection: SCAMPConnection) -> Tuple[Set[int], bool]:
        """
        Take a packet and process it see if we're finished yet.

        :param data: the packet data
        :param seq_nums: the list of sequence numbers received so far
        :param finished: bool which states if finished or not
        :param placement:
            placement object for location on machine
        :param transaction_id: the transaction ID for this stream
        :param lost_seq_nums:
            the list of n sequence numbers lost per iteration
        :return: set of data items, if its the first packet, the list of
            sequence numbers, the sequence number received and if its finished
        """
        length_of_data = len(data)
        first_packet_element, = _ONE_WORD.unpack_from(data, 0)

        # get flags
        seq_num = first_packet_element & self._SEQUENCE_NUMBER_MASK
        is_end_of_stream = (
            first_packet_element & self._LAST_MESSAGE_FLAG_BIT_MASK) != 0

        # check sequence number not insane
        if seq_num > self._max_seq_num:
            raise ValueError(
                f"got an insane sequence number. got {seq_num} when "
                f"the max is {self._max_seq_num} "
                f"with a length of {length_of_data}")

        # figure offset for where data is to be put
        offset = self.__offset(seq_num)

        # write data

        # read offset from data is at byte 8. as first 4 is sequence number,
        # second 4 is transaction id
        true_data_length = (
                offset + length_of_data - BYTES_FOR_SEQ_AND_TRANSACTION_ID)
        if (not is_end_of_stream or
                length_of_data != BYTES_FOR_SEQ_AND_TRANSACTION_ID):
            self.__write_into_view(
                offset, true_data_length, data,
                BYTES_FOR_SEQ_AND_TRANSACTION_ID, length_of_data)

        # add sequence number to list
        seq_nums.add(seq_num)

        # if received a last flag on its own, its during retransmission.
        #  check and try again if required
        if is_end_of_stream:
            if not self.__check(seq_nums):
                finished = self._determine_and_retransmit_missing_seq_nums(
                    seq_nums, placement, lost_seq_nums,
                    transaction_id, connection)
            else:
                finished = True
        return seq_nums, finished

    @staticmethod
    def __offset(seq_num: int) -> int:
        return (seq_num * WORDS_PER_FULL_PACKET_WITH_SEQUENCE_NUM *
                BYTES_PER_WORD)

    def __write_into_view(
            self, view_start_position: int, view_end_position: int,
            data: bytes, data_start_position: int,
            data_end_position: int) -> None:
        """
        Puts data into the view.

        :param view_start_position: where in view to start
        :param view_end_position: where in view to end
        :param data: the data holder to write from
        :param data_start_position: where in data holder to start from
        :param data_end_position: where in data holder to end
        :raises Exception: If the position to write to is crazy
        """
        if self._view is None or self._output is None:
            raise SpinnFrontEndException("no current target buffer")
        if view_end_position > len(self._output):
            raise ValueError(
                f"End position {view_end_position} > "
                f"output length {len(self._output)}")
        self._view[view_start_position: view_end_position] = \
            data[data_start_position:data_end_position]

    def __check(self, seq_nums: Iterable[int]) -> bool:
        """
        Verify if the sequence numbers are correct.

        :param seq_nums: the received sequence numbers
        :return: Whether all the sequence numbers have been received
        """
        # hand back
        seq_nums = sorted(seq_nums)
        max_needed = self.__calculate_max_seq_num()
        if len(seq_nums) > max_needed + 1:
            raise ValueError(f"too many seq_nums: {len(seq_nums)}")
        return len(seq_nums) == max_needed + 1

    def __calculate_max_seq_num(self) -> int:
        """
        Deduce the max sequence number expected to be received.

        :return: the biggest sequence number expected
        """
        if self._output is None:
            raise SpinnFrontEndException("no receiving buffer")
        return ceildiv(
            len(self._output),
            WORDS_PER_FULL_PACKET_WITH_SEQUENCE_NUM * BYTES_PER_WORD)

    @staticmethod
    def __provenance_address(x: int, y: int, p: int) -> int:
        txrx = FecDataView.get_transceiver()
        region_table = txrx.get_region_base_address(x, y, p)

        # Get the provenance region base address
        prov_region_entry_address = get_region_base_address_offset(
            region_table, _DataRegions.PROVENANCE_REGION)
        return txrx.read_word(x, y, prov_region_entry_address)

    @overrides(AbstractProvidesProvenanceDataFromMachine
               .get_provenance_data_from_machine)
    def get_provenance_data_from_machine(self, placement: Placement) -> None:
        x, y, p = placement.x, placement.y, placement.p
        # Get the App Data for the core
        data = FecDataView.read_memory(
            x, y, self.__provenance_address(x, y, p), _PROVENANCE_DATA_SIZE)
        n_sdp_sent, n_sdp_recvd, n_in_streams, n_out_streams = (
            _FOUR_WORDS.unpack_from(data))
        with ProvenanceWriter() as db:
            db.insert_core(x, y, p, _ProvLabels.SENT, n_sdp_sent)
            db.insert_core(x, y, p, _ProvLabels.RECEIVED, n_sdp_recvd)
            db.insert_core(x, y, p, _ProvLabels.IN_STREAMS, n_in_streams)
            db.insert_core(x, y, p, _ProvLabels.OUT_STREAMS, n_out_streams)

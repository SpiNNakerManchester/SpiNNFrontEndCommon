# Copyright (c) 2014 The University of Manchester
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

from enum import Enum
from data_specification.constants import APP_PTR_TABLE_BYTE_SIZE

# conversion from words to bytes
BYTES_PER_WORD = 4
BYTES_PER_4_WORDS = 16
BYTES_PER_SHORT = 2
BYTES_PER_KB = 1024

LIVE_GATHERER_CORE_APPLICATION_ID = 0xAC0
COMMAND_SENDER_CORE_APPLICATION_ID = 0xAC6
SPIKE_INJECTOR_CORE_APPLICATION_ID = 0xAC9

# how many bits there are in a word
BITS_PER_WORD = 32.0

#: start of where SDRAM starts (either unbuffered or buffered)
SDRAM_BASE_ADDR = 0x70000000

#: the ITCM max safe limit for a binary
MAX_SAFE_BINARY_SIZE = 32 * BYTES_PER_KB

#: the ITCM max limit for a binary
MAX_POSSIBLE_BINARY_SIZE = 33 * BYTES_PER_KB

# converts between micro and milli seconds
MICRO_TO_MILLISECOND_CONVERSION = 1000.0
MICRO_TO_SECOND_CONVERSION = 1000000.0  # (1e6)

#: max size expected to be used by the reverse ip_tag multicast source
#: during buffered operations.
MAX_SIZE_OF_BUFFERED_REGION_ON_CHIP = 1 * 1024 * BYTES_PER_KB

#: The default size of a recording buffer before receive request is sent
DEFAULT_BUFFER_SIZE_BEFORE_RECEIVE = 16 * BYTES_PER_KB

#: The number of bytes used by SARK per memory allocation
SARK_PER_MALLOC_SDRAM_USAGE = 2 * BYTES_PER_WORD

#: The number of words in the AbstractDataSpecable basic setup information.
#: This is the amount required by the pointer table plus a SARK allocation.
DATA_SPECABLE_BASIC_SETUP_INFO_N_BYTES = (
    APP_PTR_TABLE_BYTE_SIZE + SARK_PER_MALLOC_SDRAM_USAGE)

#: The number of bytes used by the simulation interface.
#: This is one word for the machine_time_step, one for the SDP port, and one
#: for the application hash.
SIMULATION_N_BYTES = 3 * BYTES_PER_WORD

#: the number of bytes used by the multicast data speed up interface
# 4 for the first key used by multicast protocol
MULTICAST_SPEEDUP_N_BYTES = BYTES_PER_WORD

#: The number of bytes used by the DSG and simulation interfaces
SYSTEM_BYTES_REQUIREMENT = (
    DATA_SPECABLE_BASIC_SETUP_INFO_N_BYTES + SIMULATION_N_BYTES)

#: Database file path maximum length for database notification messages.
#: Note that this is *not* sent to SpiNNaker and so is not subject to the
#: usual SDP limit.
MAX_DATABASE_PATH_LENGTH = 50000

#: size of the on-chip DSE data structure required, in bytes
DSE_DATA_STRUCT_SIZE = 4 * BYTES_PER_WORD


class SDP_RUNNING_MESSAGE_CODES(Enum):
    """
    Codes for sending control messages to spin1_api.
    """
    SDP_STOP_ID_CODE = 6
    SDP_NEW_RUNTIME_ID_CODE = 7
    SDP_UPDATE_PROVENCE_REGION_AND_EXIT = 8
    SDP_CLEAR_IOBUF_CODE = 9


class SDP_PORTS(Enum):
    """
    SDP port handling output buffering data streaming.
    """

    #: Command port for the buffered in functionality.
    INPUT_BUFFERING_SDP_PORT = 1
    #: Command port for the buffered out functionality.
    OUTPUT_BUFFERING_SDP_PORT = 2
    #: Command port for resetting runtime, etc.
    #: See :py:class:`SDP_RUNNING_MESSAGE_CODES`
    RUNNING_COMMAND_SDP_PORT = 3
    #: Extra monitor core reinjection control protocol.
    #: See :py:class:`ReinjectorSCPCommands`
    EXTRA_MONITOR_CORE_REINJECTION = 4
    #: Extra monitor core outbound data transfer protocol
    EXTRA_MONITOR_CORE_DATA_SPEED_UP = 5
    #: Extra monitor core inbound data transfer protocol
    #: See :py:class:`SpeedupInSCPCommands`
    EXTRA_MONITOR_CORE_DATA_IN_SPEED_UP = 6


# output buffering operations
class BUFFERING_OPERATIONS(Enum):
    """
    A listing of what SpiNNaker specific EIEIO commands there are.
    """

    #: Database handshake with external program
    BUFFER_READ = 0
    #: Host confirming data being read form SpiNNaker memory
    BUFFER_WRITE = 1


#: partition IDs preallocated to functionality
PARTITION_ID_FOR_MULTICAST_DATA_SPEED_UP = "DATA_SPEED_UP_ROAD"

#: The default local port that the toolchain listens on for the notification
#: protocol.
NOTIFY_PORT = 19999

#: The number of clock cycles per micro-second (at 200Mhz)
CLOCKS_PER_US = 200

PROVENANCE_DB = "provenance.sqlite3"

#: SDRAM Tag used by the compressor to find the routing tables
COMPRESSOR_SDRAM_TAG = 1

#: SDRAM Tags used for bitfield compressor
BIT_FIELD_COMMS_SDRAM_TAG = 2
BIT_FIELD_USABLE_SDRAM_TAG = 3
BIT_FIELD_ADDRESSES_SDRAM_TAG = 4
BIT_FIELD_ROUTING_TABLE_SDRAM_TAG = 5

#: Base SDRAM tag used by SDRAM edges when allocating
#: (allows up to 100 edges per chip)
SDRAM_EDGE_BASE_TAG = 100

#: Base SDRAM tag used by cores when loading data
#: (tags 201-217 will be used by cores 1-17)
CORE_DATA_SDRAM_BASE_TAG = 200

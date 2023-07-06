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
import numpy

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

#: Application data magic number.
APPDATA_MAGIC_NUM = 0xAD130AD6

#: Version of the file produced by the DSE.
DSE_VERSION = 0x00010000

#: Maximum number of memory regions in DSG virtual machine.
MAX_MEM_REGIONS = 32

#: Size of header of data spec pointer table produced by DSE, in bytes.
#: Note that the header consists of 2 uint32_t variables
#: (magic_number, version)
APP_PTR_TABLE_HEADER_BYTE_SIZE = 2 * BYTES_PER_WORD
#: Size of a region description in the pointer table.
#: Note that the description consists of a pointer and 2 uint32_t variables:
#: (pointer, checksum, n_words)
APP_PTR_TABLE_REGION_BYTE_SIZE = 3 * BYTES_PER_WORD
#: Size of data spec pointer table produced by DSE, in bytes.
APP_PTR_TABLE_BYTE_SIZE = (
    APP_PTR_TABLE_HEADER_BYTE_SIZE +
    (MAX_MEM_REGIONS * APP_PTR_TABLE_REGION_BYTE_SIZE))

TABLE_TYPE = numpy.dtype(
    [("pointer", "<u4"), ("checksum", "<u4"), ("n_words", "<u4")])

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

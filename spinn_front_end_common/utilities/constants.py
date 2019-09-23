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

from enum import Enum
from data_specification.constants import APP_PTR_TABLE_BYTE_SIZE

LIVE_GATHERER_CORE_APPLICATION_ID = 0xAC0
COMMAND_SENDER_CORE_APPLICATION_ID = 0xAC6
SPIKE_INJECTOR_CORE_APPLICATION_ID = 0xAC9

BITS_PER_WORD = 32.0
SDRAM_BASE_ADDR = 0x70000000
MAX_SAFE_BINARY_SIZE = 32 * 1024
MAX_POSSIBLE_BINARY_SIZE = 33 * 1024

# converts between micro and milli seconds
MICRO_TO_MILLISECOND_CONVERSION = 1000

# max size expected to be used by the reverse ip_tag multicast source
# during buffered operations
MAX_SIZE_OF_BUFFERED_REGION_ON_CHIP = 1 * 1024 * 1024

# The default size of a recording buffer before receive request is sent
DEFAULT_BUFFER_SIZE_BEFORE_RECEIVE = 16 * 1024

# The number of bytes used by SARK per memory allocation
SARK_PER_MALLOC_SDRAM_USAGE = 8

# The number of words in the AbstractDataSpecable basic setup information
# This is the amount required by the pointer table plus a SARK allocation
DATA_SPECABLE_BASIC_SETUP_INFO_N_BYTES = (
    APP_PTR_TABLE_BYTE_SIZE + SARK_PER_MALLOC_SDRAM_USAGE)

# conversion from words to bytes
WORD_TO_BYTE_MULTIPLIER = 4

# The number of words used by the simulation interface
# 4 for machine_time_step,
# 4 for SDP port
# 4 for application hash
SIMULATION_N_BYTES = 12

# the number of words used by the multicast data speed up interface
# 4 for the first key used by multicast protocol
MULTICAST_SPEEDUP_N_BYTES = 4

# The number of bytes used by the DSG and simulation interfaces
SYSTEM_BYTES_REQUIREMENT = (
    DATA_SPECABLE_BASIC_SETUP_INFO_N_BYTES + SIMULATION_N_BYTES)

# database cap file path
MAX_DATABASE_PATH_LENGTH = 50000

# size of the on-chip DSE data structure required in bytes
DSE_DATA_STRUCT_SIZE = 16

SDP_RUNNING_MESSAGE_CODES = Enum(
    value="SDP_RUNNING_MESSAGE_ID_CODES",
    names=[
        ("SDP_STOP_ID_CODE", 6),
        ("SDP_NEW_RUNTIME_ID_CODE", 7),
        ("SDP_UPDATE_PROVENCE_REGION_AND_EXIT", 8),
        ("SDP_CLEAR_IOBUF_CODE", 9)])


# SDP port handling output buffering data streaming
SDP_PORTS = Enum(
    value="SDP_PORTS",
    names=[
        # command port for the buffered in functionality
        ("INPUT_BUFFERING_SDP_PORT", 1),
        # command port for the buffered out functionality
        ("OUTPUT_BUFFERING_SDP_PORT", 2),
        # command port for resetting runtime etc
        ("RUNNING_COMMAND_SDP_PORT", 3),
        # extra monitor core reinjection functionality
        ("EXTRA_MONITOR_CORE_REINJECTION", 4),
        # extra monitor core data transfer functionality
        ("EXTRA_MONITOR_CORE_DATA_SPEED_UP", 5),
        # extra monitor core data in speed up functionality
        ("EXTRA_MONITOR_CORE_DATA_IN_SPEED_UP", 6)])

# output buffering operations
# a listing of what SpiNNaker specific EIEIO commands there are.
BUFFERING_OPERATIONS = Enum(
    value="BUFFERING_OPERATIONS",
    names=[

        # Database handshake with external program
        ("BUFFER_READ", 0),

        # Host confirming data being read form SpiNNaker memory
        ("BUFFER_WRITE", 1)]
)

# partition IDs preallocated to functionality
PARTITION_ID_FOR_MULTICAST_DATA_SPEED_UP = "DATA_SPEED_UP_ROAD"

# The default local port that the toolchain listens on for the notification
# protocol.
NOTIFY_PORT = 19999

from enum import Enum

LIVE_GATHERER_CORE_APPLICATION_ID = 0xAC0
COMMAND_SENDER_CORE_APPLICATION_ID = 0xAC6
SPIKE_INJECTOR_CORE_APPLICATION_ID = 0xAC9

BITS_PER_WORD = 32.0
SDRAM_BASE_ADDR = 0x70000000
MAX_SAFE_BINARY_SIZE = 28 * 1024
MAX_POSSIBLE_BINARY_SIZE = 33 * 1024

# mas size expected to be used by the reverse iptag multicast source
# during buffered opperations
MAX_SIZE_OF_BUFFERED_REGION_ON_CHIP = 1 * 1024 * 1024

# destination ports for sdp messages for different types of application control
SDP_BUFFER_MANAGEMENT_DESTINATION_PORT = 2
SDP_RUNNING_COMMAND_DESTINATION_PORT = 1

# The number of words in the AbstractDataSpecable basic setup information
DATA_SPECABLE_BASIC_SETUP_INFO_N_WORDS = 5

# database cap file path
MAX_DATABASE_PATH_LENGTH = 50000

SDP_RUNNING_MESSAGE_CODES = Enum(
    value="SDP_RUNNING_MESSAGE_ID_CODES",
    names=[
        ("SDP_STOP_ID_CODE", 6),
        ("SDP_NEW_RUNTIME_ID_CODE", 7),
        ("SDP_SWITCH_STATE", 8)]
)

from enum import Enum

LIVE_GATHERER_CORE_APPLICATION_ID = 0xAC0
COMMAND_SENDER_CORE_APPLICATION_ID = 0xAC6
SPIKE_INJECTOR_CORE_APPLICATION_ID = 0xAC9

BITS_PER_WORD = 32.0
SDRAM_BASE_ADDR = 0x70000000
MAX_SAFE_BINARY_SIZE = 32 * 1024
MAX_POSSIBLE_BINARY_SIZE = 33 * 1024

# max size expected to be used by the reverse iptag multicast source
# during buffered operations
MAX_SIZE_OF_BUFFERED_REGION_ON_CHIP = 1 * 1024 * 1024

# The default size of a recording buffer before receive request is sent
DEFAULT_BUFFER_SIZE_BEFORE_RECEIVE = 16 * 1024

# The number of words in the AbstractDataSpecable basic setup information
DATA_SPECABLE_BASIC_SETUP_INFO_N_WORDS = 4

# database cap file path
MAX_DATABASE_PATH_LENGTH = 50000

# size of the on-chip DSE data structure required in bytes
DSE_DATA_STRUCT_SIZE = 16

# SDP port handling output buffering data streaming
SDP_PORTS = Enum(
    value="SDP_PORTS",
    names=[
        ("INPUT_BUFFERING_SDP_PORT", 1),
        ("OUTPUT_BUFFERING_SDP_PORT", 2)]
)

# output buffering operations
# a listing of what spinnaker specific EIEIO commands there are.
BUFFERING_OPERATIONS = Enum(
    value="BUFFERING_OPERATIONS",
    names=[

        # Database handshake with external program
        ("BUFFER_READ", 0),

        # Host confirming data being read form SpiNNaker memory
        ("BUFFER_WRITE", 1)]
)

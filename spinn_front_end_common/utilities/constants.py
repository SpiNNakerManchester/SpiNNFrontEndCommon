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

# The number of words in the AbstractDataSpecable basic setup information
DATA_SPECABLE_BASIC_SETUP_INFO_N_WORDS = 5

# database cap file path
MAX_DATABASE_PATH_LENGTH = 50000

# sdp port handling output buffering data streaming
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


"""
constants file
"""

COMMAND_SENDER_MAGIC_NUMBER = 0xAD3
LIVE_PACKET_GATHERER_MAGIC_NUMBER = 0xAD4
REVERSE_IP_TAG_MULTICAST_SOURCE_MAGIC_NUMBER = 0xAD5

BITS_PER_WORD = 32.0
SDRAM_BASE_ADDR = 0x70000000
MAX_SAFE_BINARY_SIZE = 28 * 1024
MAX_POSSIBLE_BINARY_SIZE = 33 * 1024

TIMINGS_REGION_BYTES = 8  # time scale factor and no_iterations

# The number of words in the AbstractDataSpecable basic setup information
DATA_SPECABLE_BASIC_SETUP_INFO_N_WORDS = 3

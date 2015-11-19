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
DATA_SPECABLE_BASIC_SETUP_INFO_N_WORDS = 4

# database cap file path
MAX_DATABASE_PATH_LENGTH = 50000
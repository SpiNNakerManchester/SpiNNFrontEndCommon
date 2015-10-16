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

# number of buffering output channels
OUTPUT_BUFFERING_CHANNELS = 3

# sdp port handling output buffering data streaming
OUTPUT_BUFFERING_SDP_PORT = 2

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

CORE_REGIONS = Enum(
    value="CORE_REGIONS",
    names=[
        ("SYSTEM_REGION", 0),
        ("NEURON_PARAMS_REGION", 1),
        ("SYNAPSE_PARAMS_REGION", 2),
        ("POPULATION_TABLE_REGION", 3),
        ("SYNAPTIC_MATRIX_REGION", 4),
        ("SYNAPSE_DYNAMICS_REGION", 5),
        ("BUFFERING_OUT_SPIKE_RECORDING_REGION", 6),
        ("BUFFERING_OUT_POTENTIAL_RECORDING_REGION", 7),
        ("BUFFERING_OUT_GSYN_RECORDING_REGION", 8),
        ("BUFFERING_OUT_CONTROL_REGION", 9)]
    )

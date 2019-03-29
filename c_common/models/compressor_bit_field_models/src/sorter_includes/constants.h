#ifndef __SORTER_CONSTANTS_H__

//! max number of processors on chip used for app purposes
#define MAX_PROCESSORS 18

//! max number of links on a router
#define MAX_LINKS_PER_ROUTER 6

//! neuron level mask
#define NEURON_LEVEL_MASK 0xFFFFFFFF

//! flag for saying compression core doing nowt
#define DOING_NOWT -1

//! enum mapping top elements of the addresses space
typedef enum top_level_addresses_space_elements{
    THRESHOLD = 0, N_PAIRS = 1, START_OF_ADDRESSES_DATA = 2
} top_level_addresses_space_elements;

//! enum mapping user register to data that's in there (only used by
//! programmer for documentation)
typedef enum user_register_maps{
    APPLICATION_POINTER_TABLE = 0, UNCOMP_ROUTER_TABLE = 1,
    REGION_ADDRESSES = 2, USABLE_SDRAM_REGIONS = 3,
    USER_REGISTER_LENGTH = 4
} user_register_maps;

//! enum mapping for elements in uncompressed routing table region
typedef enum uncompressed_routing_table_region_elements{
    APPLICATION_APP_ID = 0, N_ENTRIES = 1, START_OF_UNCOMPRESSED_ENTRIES = 2
} uncompressed_routing_table_region_elements;

//! enum for the compressor cores data elements (used for programmer debug)
typedef enum compressor_core_elements{
    N_COMPRESSOR_CORES = 0, START_OF_COMP_CORE_IDS = 1
} compressor_core_elements;

//! enum mapping of elements in the key to atom mapping
typedef enum key_to_atom_map_elements{
    SRC_BASE_KEY = 0, SRC_N_ATOMS = 1, LENGTH_OF_KEY_ATOM_PAIR = 2
} key_to_atom_map_elements;

//! enum mapping addresses in addresses region
typedef enum addresses_elements{
    BITFIELD_REGION = 0, KEY_TO_ATOM_REGION = 1, PROCESSOR_ID = 2,
    ADDRESS_PAIR_LENGTH = 3
} addresses_elements;

//! enum mapping bitfield region top elements
typedef enum bit_field_data_top_elements{
    N_BIT_FIELDS = 0, START_OF_BIT_FIELD_TOP_DATA = 1
} bit_field_data_top_elements;

//! enum stating the components of a bitfield struct
typedef enum bit_field_data_elements{
    BIT_FIELD_BASE_KEY = 0, BIT_FIELD_N_WORDS = 1, START_OF_BIT_FIELD_DATA = 2
} bit_field_data_elements;

//! callback priorities
typedef enum priorities{
    COMPRESSION_START_PRIORITY = 3, SDP_PRIORITY = -1, TIMER_TICK_PRIORITY = 2
}priorities;


#define __SORTER_CONSTANTS_H__
#endif  // __SORTER_CONSTANTS_H__
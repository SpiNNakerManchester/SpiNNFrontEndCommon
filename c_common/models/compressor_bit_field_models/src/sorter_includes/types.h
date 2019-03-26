#ifndef __SORTER__TYPES_H__
#define __SORTER__TYPES_H__

#include "common-typedefs.h"

//! enum mapping for elements in uncompressed routing table region
typedef enum uncompressed_routing_table_region_elements {
    APPLICATION_APP_ID = 0,
    N_ENTRIES = 1,
    START_OF_UNCOMPRESSED_ENTRIES = 2
} uncompressed_routing_table_region_elements;

//! the compressor cores data elements
typedef struct compressor_cores_t {
    uint32_t n_cores;
    uint32_t core_id[];
} compressor_cores_t;

//! enum mapping of elements in the key to atom mapping
typedef enum key_to_atom_map_elements {
    SRC_BASE_KEY = 0,
    SRC_N_ATOMS = 1,
    LENGTH_OF_KEY_ATOM_PAIR = 2
} key_to_atom_map_elements;
typedef struct key_atom_pair_t {
    uint32_t base_key;
    uint32_t n_atoms;
} key_atom_pair_t;
typedef struct key_atom_map_t {
    uint32_t n_pairs;
    key_atom_pair_t pairs[];
} key_atom_map_t;

//! enum mapping addresses in addresses region
typedef enum addresses_elements {
    BITFIELD_REGION = 0,
    KEY_TO_ATOM_REGION = 1,
    PROCESSOR_ID = 2,
    ADDRESS_PAIR_LENGTH = 3
} addresses_elements;

//! enum mapping bitfield region top elements
typedef enum bit_field_data_top_elements {
    N_BIT_FIELDS = 0,
    START_OF_BIT_FIELD_TOP_DATA = 1
} bit_field_data_top_elements;

//! enum mapping top elements of the addresses space
typedef enum top_level_addresses_space_elements {
    THRESHOLD = 0,
    N_PAIRS = 1,
    START_OF_ADDRESSES_DATA = 2
} top_level_addresses_space_elements;

//! enum stating the components of a bitfield struct
typedef enum bit_field_data_elements {
    BIT_FIELD_BASE_KEY = 0,
    BIT_FIELD_N_WORDS = 1,
    START_OF_BIT_FIELD_DATA = 2
} bit_field_data_elements;
typedef struct bit_field_data_t {
    uint32_t base_key;
    uint32_t n_words;
    uint32_t data[];
} bit_field_data_t;
typedef struct bit_field_top_t {
    uint32_t n_bitfields;
    bit_field_data_t bitfields[];
} bit_field_top_t;

//! callback priorities
typedef enum priorities {
    COMPRESSION_START_PRIORITY = 3,
    SDP_PRIORITY = -1
} priorities;

typedef struct pairs_t {
    address_t bitfield;
    key_atom_map_t *key_atom;
    uint32_t processor;
} pairs_t;

typedef struct region_addresses_t {
    uint32_t threshold;
    uint32_t n_pairs;
    pairs_t pairs[];
} region_addresses_t;

#endif //__SORTER__TYPES_H__

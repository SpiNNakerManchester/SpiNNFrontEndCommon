#ifndef __COMPRESSOR_SORTER_STRUCTS_H__
#define __COMPRESSOR_SORTER_STRUCTS_H__

#include <filter_info.h>
#include <key_atom_map.h>

//! holds data for each compressor core, used to free stuff properly when
//! requried
typedef struct comp_core_store_t{
    // how many rt tables used here
    int n_elements;
    // how many bit fields were used to make those tables
    int n_bit_fields;
    // compressed table location
    address_t compressed_table;
    // elements
    address_t *elements;
} comp_core_store_t;

//! \brief the compressor cores data elements in sdram
typedef struct compressor_cores_top_t {
    uint32_t n_cores;
    uint32_t core_id[];
} compressor_cores_top_t;

//! \brief struct for figuring keys from bitfields, used for removal tracking
typedef struct proc_bit_field_keys_t{
    // processor id
    int processor_id;
    // length of the list
    int length_of_list;
    // list of the keys to remove bitfields for.
    uint32_t *master_pop_keys;
} proc_bit_field_keys_t;

//! \brief struct for bitfield by processor
typedef struct bit_field_by_processor_t{
    // processor id
    int processor_id;
    // length of list
    int length_of_list;
    // list of addresses where the bitfields start
    address_t *bit_field_addresses;
} bit_field_by_processor_t;

//! \brief struct holding keys and n bitfields with key
typedef struct master_pop_bit_field_t{
    // the master pop key
    uint32_t master_pop_key;
    // the number of bitfields with this key
    int n_bitfields_with_key;
} master_pop_bit_field_t;

//! \brief uncompressed routing table region
typedef struct uncompressed_table_region_data_t{
    // the app id
    uint32_t app_id;
    // table struct
    table_t uncompressed_table;
} uncompressed_table_region_data_t;

//! \brief compressor core data region
typedef struct compressor_cores_region_data_t{
    // how many compressor cores
    int n_compressor_cores;
    // the processor ids
    int *processor_ids;
} compressor_cores_region_data_t;

//! \brief holder for the bitfield addresses and the processor ids
typedef struct sorted_bit_fields_t{
    //! list of bitfield associated processor ids. sorted order based off best
    //! effort linked to sorted_bit_fields, but separate to avoid sdram
    //! rewrites
    int* processor_ids;
    //! the list of bitfields in sorted order based off best effect.
    address_t* bit_fields;
} sorted_bit_fields_t;

//! \brief a single mapping in the addresses area
typedef struct pairs_t {
    filter_region_t *filter;
    key_atom_data_t *key_atom;
    int processor;
} pairs_t;

//! \brief top-level structure in the addresses area
typedef struct region_addresses_t {
    int threshold;
    int n_pairs;
    pairs_t pairs[];
} region_addresses_t;

#endif  // __COMPRESSOR_SORTER_STRUCTS_H__
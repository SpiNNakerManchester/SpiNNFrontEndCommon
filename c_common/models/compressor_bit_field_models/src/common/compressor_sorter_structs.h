/*
 * Copyright (c) 2019-2020 The University of Manchester
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#ifndef __COMPRESSOR_SORTER_STRUCTS_H__
#define __COMPRESSOR_SORTER_STRUCTS_H__

#include <filter_info.h>
#include <key_atom_map.h>

//!===========================================================================
//! enums

//! \brief the acceptable finish states
typedef enum compressor_states {
   UNUSED = 30, PREPARED = 31, COMPRESSING = 32, FAILED_MALLOC = 33,
   FORCED_BY_COMPRESSOR_CONTROL = 34,
   SUCCESSFUL_COMPRESSION = 35, FAILED_TO_COMPRESS = 36,
   RAN_OUT_OF_TIME = 37
} compressor_states;

typedef enum instrucions_to_compressor {
    NONE = 40, PREPARE = 41,  RUN = 42, FORCE_TO_STOP = 44
} instrucions_to_compressor;

typedef enum processor_status_values {
    // flag for saying processor is not a compressor
    NOT_COMPRESSOR = -4,
    // flag for saying compression processor should not be used any more
    DO_NOT_USE = -3,
    // flag for saying compression processor needs to be prepared for the first time
    TO_BE_PREPARED = -2,
    // flag to say compression processor has been asked to prepare/ clear previous
    PREPARING = -1
    // zero or higher is the midpoint the compressor processor has been asked to run
    // This includes compressors that have been forced to stop but not check yet.
} processor_status_values;

//! \brief the command codes in human readable form
typedef enum command_codes_for_sdp_packet {
    START_DATA_STREAM = 20,
    COMPRESSION_RESPONSE = 21,
    STOP_COMPRESSION_ATTEMPT = 22
} command_codes_for_sdp_packet;

//!=========================================================================
//! structs

//! \brief struct holding key and mask
typedef struct key_mask_t {
    // Key for the key_mask
    uint32_t key;

    // Mask for the key_mask
    uint32_t mask;
} key_mask_t;

//! \brief struct holding routing table entry data
typedef struct entry_t {
    // Key and mask
    key_mask_t key_mask;

    // Routing direction
    uint32_t route;

    // Source of packets arriving at this entry
    uint32_t source;
} entry_t;

//! \brief struct for holding table entries
typedef struct table_t {

    // Number of entries in the table
    uint32_t size;

    // Entries in the table
    entry_t entries[];
} table_t;

//! holds data for each compressor processor, used to free stuff properly when
//! required
typedef struct comp_processor_store_t{
    // how many rt tables used here
    int n_elements;
    // how many bit fields were used to make those tables
    int n_bit_fields;
    // compressed table location
    table_t *compressed_table;
    // elements
    table_t **elements;
} comp_processor_store_t;

typedef struct comp_instruction_t{
    // how many rt tables used here
    int n_elements;
    // how many bit fields were used to make those tables
    int n_bit_fields;
    // compressed table location
    table_t *compressed_table;
    // elements
    table_t **elements;
    // initialise value for malloc_extras_
    heap_t *fake_heap_data;
} comp_instruction_t;

//! \brief the compressor processor data elements in SDRAM
typedef struct compressor_processors_top_t {
    uint32_t n_processors;
    uint32_t processor_id[];
} compressor_processors_top_t;

//! \brief struct to hide the VLA'ness of the proc bit field keys.
typedef struct master_pop_key_list_t {
    // length of the list
    int length_of_list;
    // list of the keys to remove bitfields for.
    uint32_t *master_pop_keys;
} master_pop_key_list_t;

//! \brief struct for figuring keys from bitfields, used for removal tracking
typedef struct proc_bit_field_keys_t{
    // processor id
    int processor_id;
    // length of the list
    master_pop_key_list_t *key_list;
} proc_bit_field_keys_t;

//! \brief struct for bitfield by processor
typedef struct bit_field_by_processor_t{
    // processor id
    int processor_id;
    // length of list
    int length_of_list;
    // list of addresses where the bitfields start
    filter_info_t *bit_field_addresses;
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

//! \brief compressor processor data region
typedef struct compressor_processors_region_data_t{
    // how many compressor processors
    int n_compressor_processors;
    // the processor ids
    int *processor_ids;
} compressor_processors_region_data_t;

//! \brief holder for the list of bitfield associated processor ids.
//! sorted order based off best effort linked to sorted_bit_fields,
//! but separate to avoid sdram rewrites
typedef struct sorted_bit_fields_t{
    //! len of the arrays
    int n_bit_fields;
    //! list of bitfield associated processor ids.
    int* processor_ids;
    //! the list of bitfields in sorted order based off best effect.
    filter_info_t** bit_fields;
    //! the sort order based on best contribution to reducing redundancy
    int* sort_order;
} sorted_bit_fields_t;

//! \brief a single mapping in the addresses area
typedef struct triples_t {
    filter_region_t *filter;
    key_atom_data_t *key_atom;
    int processor;
} triples_t;

//! \brief top-level structure in the addresses area
typedef struct region_addresses_t {
    int threshold;
    int n_triples;
    triples_t triples[];
} region_addresses_t;

//! \brief the elements in the sdp packet (control for setting off a minimise
//! attempt)
typedef struct start_sdp_packet_t {
    uint32_t command_code;
    heap_t *fake_heap_data;
    comp_processor_store_t *table_data;
} start_sdp_packet_t;

//! \brief the elements in the sdp packet when response to compression attempt.
typedef struct response_sdp_packet_t {
    uint32_t command_code;
    uint32_t response_code;
} response_sdp_packet_t;

//! \brief all the types of SDP messages that we receive, as one
typedef union {
    command_codes_for_sdp_packet command;
    start_sdp_packet_t start;
    response_sdp_packet_t response;
} compressor_payload_t;


#endif  // __COMPRESSOR_SORTER_STRUCTS_H__

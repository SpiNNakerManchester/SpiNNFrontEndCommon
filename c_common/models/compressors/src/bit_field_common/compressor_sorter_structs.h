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

//! \file
//! \brief Structures and enumerations for the bitfield compressor sorter.
#ifndef __COMPRESSOR_SORTER_STRUCTS_H__
#define __COMPRESSOR_SORTER_STRUCTS_H__

#include <filter_info.h>
#include <key_atom_map.h>
#include "../common/routing_table.h"

//!===========================================================================
//! enums

//! \brief The acceptable finish states
typedef enum compressor_states {
   //! Flag to say this core has never been used or prepared
   UNUSED_CORE = 30,
   //! Flag to say compressor is ready to run.  This clears previous results
   PREPARED = 31,
   //! Flag to say compressor is acticvely compressing
   COMPRESSING = 32,
   //! Flag to say the last compression run ended due to a malloc failure
   FAILED_MALLOC = 33,
   //! Flag to say sorter force seen and compression has ended or been stopped
   //! Note: It use may be replaced with the PREPARED flag
   FORCED_BY_COMPRESSOR_CONTROL = 34,
   //! Flag to say previous run was successful
   SUCCESSFUL_COMPRESSION = 35,
   //! Flag to say previous run finished but without a small enough table
   FAILED_TO_COMPRESS = 36,
   //! Flag to say previous run was aborted as it ran out of time
   RAN_OUT_OF_TIME = 37
} compressor_states;

//! \brief The commands sent to a compressor core
typedef enum instructions_to_compressor {
    //! Flag for saying processor is not a compressor
    NOT_COMPRESSOR = 40,
    //! Flag for saying compression processor will not be used any more
    DO_NOT_USE = 41,
    //! Flag for saying compression processor needs to be prepared for the
    //! first time
    TO_BE_PREPARED = 42,
    //! Flag to ask compressor to setup and clear any previous result
    PREPARE = 43,
    //! Flag to say processor shoukd run
    RUN = 44,
    //! Flag to say processor should stop as result no longer needed
    FORCE_TO_STOP = 45
} instructions_to_compressor;

//!=========================================================================
//! structs

//! \brief Holds the data to initialise routing_table.h
typedef struct multi_table_t {
    //! The individual subtables
    table_t **sub_tables;
    //! The number of individual subtables
    uint32_t n_sub_tables;
    //! The number of entry_t entries actually in the tables.
    // NOTE: is a int because ordered covering uses ints for len of tables
    // and we did not feel safe to change that.
    uint32_t n_entries;
    //! The max number of entries supported by this multitable.
    uint32_t max_entries;
} multi_table_t;

//! \brief The list of cores that can be used as compressor processor
typedef struct compressor_processors_top_t {
    //! The number of processor_id(s) in the list
    uint32_t n_processors;
    //! List of the ids of processors that can be used as compressors
    uint32_t processor_id[];
} compressor_processors_top_t;

//! \brief Uncompressed routing table region
typedef struct uncompressed_table_region_data_t {
    //! the application ID
    uint32_t app_id;
    //! table struct
    table_t uncompressed_table;
} uncompressed_table_region_data_t;

//! \brief Holds the list of bitfield associated processor IDs.
//! \details sorted order based off best effort linked to sorted_bit_fields(),
//!     but separate to avoid SDRAM rewrites
typedef struct sorted_bit_fields_t {
    //! length of the arrays
    uint32_t n_bit_fields;
    //! list of bitfield associated processor IDs.
    uint32_t *processor_ids;
    //! the list of bitfields in sorted order based off best effect.
    filter_info_t **bit_fields;
    //! the sort order based on best contribution to reducing redundancy
    int *sort_order;
} sorted_bit_fields_t;

//! \brief SDRAM area to communicate between sorter and compressor
typedef struct comms_sdram_t {
    //! The state the compressor is in
    volatile compressor_states compressor_state;
    //! The last instruction passed from the sorter to the compressor
    volatile instructions_to_compressor sorter_instruction;
    //! how many bit fields were used to make those tables
    int mid_point;
    //! Pointer to the shared version of the uncompressed routing table
    table_t *uncompressed_router_table;
    //! Pointer to the uncompressed tables metadata
    multi_table_t *routing_tables;
    //! Pointer to the whole sorted_bit_fields data
    sorted_bit_fields_t *sorted_bit_fields;
    //! initialise value for malloc_extras (Same for all compressors)
    heap_t *fake_heap_data;
} comms_sdram_t;

//! \brief A single mapping in the addresses area
typedef struct triples_t {
    //! The bitfield wrapper
    filter_region_t *filter;
    //! Key and mask associated with the bitfield
    key_atom_data_t *key_atom;
    //! The core associated with the bitfield
    uint32_t processor;
} triples_t;

//! \brief Top-level structure in the addresses area
typedef struct region_addresses_t {
    //! Minimum percentage of bitfields to be merge in (currently ignored)
    uint32_t threshold;
    //! Pointer to the area malloced to hold the comms_sdram
    comms_sdram_t *comms_sdram;
    //! Number of triples in the list
    uint32_t n_triples;
    //! The mappings
    triples_t triples[];
} region_addresses_t;

#endif  // __COMPRESSOR_SORTER_STRUCTS_H__

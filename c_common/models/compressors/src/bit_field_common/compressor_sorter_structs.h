/*
 * Copyright (c) 2019 The University of Manchester
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

//! \file
//! \brief Structures and enumerations for the bitfield compressor sorter.
#ifndef __COMPRESSOR_SORTER_STRUCTS_H__
#define __COMPRESSOR_SORTER_STRUCTS_H__

#include <filter_info.h>
#include <key_atom_map.h>
#include <common/routing_table.h>

//!===========================================================================
//! enums

//! \brief the acceptable finish states
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
    table_t** sub_tables;
    //! The number of individual subtables
    uint32_t n_sub_tables;
    //! The number of entry_t entries actually in the tables.
    // NOTE: is a int because ordered covering uses ints for len of tables
    // and we did not feel safe to change that.
    int n_entries;
    //! The max number of entries supported by this multitable.
    uint32_t max_entries;
} multi_table_t;

//! \brief the list of cores that can be used as compressor processor
typedef struct compressor_processors_top_t {
    //! The number of processor_id(s) in the list
    uint32_t n_processors;
    //! List of the ids of processors that can be used as compressors
    uint32_t processor_id[];
} compressor_processors_top_t;

//! \brief uncompressed routing table region
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
    int n_bit_fields;
    //! list of bitfield associated processor IDs.
    int* processor_ids;
    //! the list of bitfields in sorted order based off best effect.
    filter_info_t** bit_fields;
    //! the sort order based on best contribution to reducing redundancy
    int* sort_order;
} sorted_bit_fields_t;

//! \brief SDRAM area to communicate between sorter and compressor
typedef struct comms_sdram_t {
    //! The state the compressor is in
    compressor_states compressor_state;
    //! The last instruction passed from the sorter to the compressor
    instructions_to_compressor sorter_instruction;
    //! how many bit fields were used to make those tables
    int mid_point;
    //! Pointer to the shared version of the uncompressed routing table
    table_t* uncompressed_router_table;
    //! Pointer to the uncompressed tables metadata
    multi_table_t *routing_tables;
    //! Pointer to the whole sorted_bit_fields data
    sorted_bit_fields_t  *sorted_bit_fields;
    //! initialise value for malloc_extras (Same for all compressors)
    heap_t *fake_heap_data;
} comms_sdram_t;

//! \brief a single mapping in the addresses area
typedef struct bitfield_proc_t {
    //! The bitfield wrapper
    filter_region_t *filter;
    //! The core associated with the bitfield
    int processor;
} bitfield_proc_t;

//! \brief top-level structure in the addresses area
typedef struct region_addresses_t {
    //! Minimum percentage of bitfields to be merge in (currently ignored)
    uint32_t threshold;
    //! Number of times that the sorters should set of the compressions again
    uint32_t retry_count;
    //! Pointer to the area malloced to hold the comms_sdram
    comms_sdram_t* comms_sdram;
    //! Number of processors in the list
    int n_processors;
    //! The data for the processors
    bitfield_proc_t processors[];
} region_addresses_t;

#endif  // __COMPRESSOR_SORTER_STRUCTS_H__

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

#ifndef __HELPFUL_FUNCTIONS_H__
#define __HELPFUL_FUNCTIONS_H__

#include "../common/constants.h"
#include <filter_info.h>
#include <malloc_extras.h>

//! \brief frees SDRAM from the compressor processor.
//! \param[in] processor_index: the compressor processor index to clear
//! SDRAM usage from
//! \param[in] processor_bf_tables: the map of what tables that processor used
//! \return bool stating that it was successful in clearing SDRAM
bool helpful_functions_free_sdram_from_compression_attempt(
        int processor_id, comp_processor_store_t* processor_bf_tables) {
    int elements = processor_bf_tables[processor_id].n_elements;

    log_error("method needs checking and not surigually removed");
    return true;

    // free the individual elements
    for (int bit_field_id = 0; bit_field_id < elements; bit_field_id++) {
        FREE(processor_bf_tables[processor_id].elements[bit_field_id]);
    }

    // only try freeing if its not been freed already. (safety feature)
    if (processor_bf_tables[processor_id].elements != NULL){
        FREE(processor_bf_tables[processor_id].elements);
    }

    processor_bf_tables[processor_id].elements = NULL;
    processor_bf_tables[processor_id].n_elements = 0;
    processor_bf_tables[processor_id].n_bit_fields = 0;
    return true;
}

//! \brief clones the un compressed routing table, to another sdram location
//! \param[in] uncompressed_router_table: sdram location for uncompressed table
//! \return: address of new clone, or null if it failed to clone
static inline table_t* helpful_functions_clone_un_compressed_routing_table(
        uncompressed_table_region_data_t *uncompressed_router_table){

    uint32_t sdram_used = routing_table_sdram_size_of_table(
        uncompressed_router_table->uncompressed_table.size);
    log_debug("sdram used is %d", sdram_used);

    // allocate sdram for the clone
    table_t* where_was_cloned = MALLOC_SDRAM(sdram_used);
    if (where_was_cloned == NULL) {
        log_error(
            "failed to allocate sdram for the cloned routing table for "
            "uncompressed compression attempt of bytes %d",
            sdram_used);
        return NULL;
    }

    bool check = malloc_extras_check(where_was_cloned);
    if (!check){
        log_info("failed");
        malloc_extras_terminate(DETECTED_MALLOC_FAILURE);
    }

    // copy the table data over correctly
    routing_table_copy_table(
        &uncompressed_router_table->uncompressed_table, where_was_cloned);
    log_debug("cloned routing table entries is %d", where_was_cloned->size);

    check = malloc_extras_check(where_was_cloned);
    if (!check){
        log_info("failed");
        malloc_extras_terminate(DETECTED_MALLOC_FAILURE);
    }

    return where_was_cloned;
}

//! \brief secret stealth function for saving ITCM. use sparingly.
#define NO_INLINE	__attribute__((noinline))
//NO_INLINE uint32_t do_the_thing(uint32_t foo, uint32_t bar) { .... }

#endif  // __HELPFUL_FUNCTIONS_H__

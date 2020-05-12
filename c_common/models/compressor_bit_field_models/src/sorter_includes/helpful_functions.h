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

//! \brief gets data about the bitfields being considered
//! \param[in/out] keys: the data holder to populate
//! \param[in] mid_point: the point in the sorted bit fields to look for
//! \param[in] sorted_bit_fields: the pointer to the sorted bitfields struct.
//! \return the number of unique keys founds.
uint32_t helpful_functions_population_master_pop_bit_field_ts(
        master_pop_bit_field_t *keys, int mid_point,
        sorted_bit_fields_t* sorted_bit_fields){

    int n_keys = 0;
    log_debug("in population_master_pop_bit_field_ts");
    // check each bitfield to see if the key been recorded already
    for (int bit_field_index = 0; bit_field_index < mid_point;
            bit_field_index++) {
        // get key
        filter_info_t* bf_pointer =
            sorted_bit_fields->bit_fields[bit_field_index];

        // start cycle looking for a clone
        bool found = false;
        for (int keys_index = 0; keys_index < n_keys; keys_index++) {
            if (keys[keys_index].master_pop_key == bf_pointer->key) {
                keys[keys_index].n_bitfields_with_key += 1;
                found = true;
            }
        }

        if (!found) {
            keys[n_keys].master_pop_key = bf_pointer->key;
            keys[n_keys].n_bitfields_with_key = 1;
            n_keys++;
        }
    }
    log_debug("out population_master_pop_bit_field_ts");
    return n_keys;
}

//! \brief clones the un compressed routing table, to another sdram location
//! \param[in] uncompressed_router_table: sdram location for uncompressed table
//! \return: address of new clone, or null if it failed to clone
int attempts2 = 0;
table_t* helpful_functions_clone_un_compressed_routing_table(
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

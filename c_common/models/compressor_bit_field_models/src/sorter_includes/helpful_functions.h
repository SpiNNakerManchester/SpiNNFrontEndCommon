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

//! \brief finds the processor id of a given bitfield address (search though
//! the bit field by processor
//! \param[in] filter: the location in sdram where the bitfield starts
//! \param[in] region_addresses: the sdram where the data on regions is
//! \param[in] bit_field_by_processor:  map between processor and bitfields
//! \return the processor id that this bitfield address is associated.
static inline uint32_t helpful_functions_locate_proc_id_from_bf_address(
        filter_info_t filter, region_addresses_t *region_addresses,
        bit_field_by_processor_t* bit_field_by_processor){

    int n_triples = region_addresses->n_triples;
    for (int bf_by_proc = 0; bf_by_proc < n_triples; bf_by_proc++) {
        bit_field_by_processor_t element = bit_field_by_processor[bf_by_proc];
        for (int addr_i = 0; addr_i < element.length_of_list; addr_i++) {
            if (element.bit_field_addresses[addr_i].data == filter.data) {
                return element.processor_id;
            }
        }
    }
    malloc_extras_terminate(EXIT_FAIL);
    return 0;
}

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

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

#ifndef __BIT_FIELD_READER_H__
#define __BIT_FIELD_READER_H__

#include "helpful_functions.h"

//! \brief reads in bitfields
//! \param[in/out] n_bf_pointer: the pointer to store how many bf addresses
//!  there are.
// \param[in] region_addresses: the addresses of the regions to read
//! \param[in/out] success: bool that helps decide if method finished
//! successfully or not
//! \return bool that states if it succeeded or not.
bit_field_by_processor_t* bit_field_reader_read_in_bit_fields(
        int* n_bf_pointer, region_addresses_t *region_addresses,
        bool* success){

    // count how many bitfields there are in total
    *n_bf_pointer = 0;
    int n_pairs_of_addresses = region_addresses->n_pairs;
    log_info("n pairs of addresses = %d", n_pairs_of_addresses);

    if (n_pairs_of_addresses == 0) {
        log_info("no bitfields to read in, so just return");
        *success = true;
        return NULL;
    }

    // malloc the bt fields by processor
    bit_field_by_processor_t* bit_field_by_processor = MALLOC(
        n_pairs_of_addresses * sizeof(bit_field_by_processor_t));
    if (bit_field_by_processor == NULL) {
        log_error("failed to allocate memory for pairs, if it fails here. "
                  "might as well give up");
        return NULL;
    }

    log_info("check all");
    check_all();
    log_info("checked all");

    // iterate through a processors bitfield region and add to the bf by
    // processor struct, whilst updating n bf total param.
    for (int r_id = 0; r_id < n_pairs_of_addresses; r_id++) {

        // track processor id
        bit_field_by_processor[r_id].processor_id =
            region_addresses->pairs[r_id].processor;
        log_info(
            "bit_field_by_processor in region %d processor id = %d",
            r_id, bit_field_by_processor[r_id].processor_id);

        // locate data for malloc memory calcs
        filter_region_t *filter_region = region_addresses->pairs[r_id].filter;
        log_info("bit_field_region = %x", filter_region);

        int core_n_filters = filter_region->n_filters;
        log_info("there are %d core bit fields", core_n_filters);
        *n_bf_pointer += core_n_filters;

        // track lengths
        bit_field_by_processor[r_id].length_of_list = core_n_filters;
        log_info(
            "bit field by processor with region %d, has length of %d",
            r_id, core_n_filters);

        // malloc for bitfield region addresses
        if (core_n_filters != 0) {
            log_info(
                "before malloc of %d bytes",
                core_n_filters * sizeof(filter_info_t));

            bit_field_by_processor[r_id].bit_field_addresses =
                MALLOC_SDRAM(core_n_filters * sizeof(filter_info_t));
            log_info("after malloc");
            if (bit_field_by_processor[r_id].bit_field_addresses == NULL) {
                log_error(
                    "failed to allocate memory for bitfield addresses for "
                    "region %d, might as well fail", r_id);
                return NULL;
            }
        }

        log_info("check all");
        check_all();
        log_info("checked all");

        // populate table for addresses where each bitfield component starts
        log_info("before populate");
        for (int bf_id = 0; bf_id < core_n_filters; bf_id++) {
            if (r_id > 8){
                check_all();
                log_info(
                    "just try extyracting key %d for cycle %d",
                    filter_region->filters[bf_id].key, bf_id);
            }
            bit_field_by_processor[r_id].bit_field_addresses[bf_id].key =
                filter_region->filters[bf_id].key;
            if (r_id > 8){
                check_all();
                log_info("just try extyracting2");
            }
            bit_field_by_processor[r_id].bit_field_addresses[bf_id].n_words =
                filter_region->filters[bf_id].n_words;
            if (r_id > 8){
                check_all();
                log_info("just try extyracting 3");
            }
            bit_field_by_processor[r_id].bit_field_addresses[bf_id].data =
                filter_region->filters[bf_id].data;
            if (r_id > 8){
                check_all();
                log_info("just try extyracting4");
            }
            check_all();
        }
        log_info("after populate");

        log_info("check all");
        check_all();
        log_info("checked all");

        log_info("check specxific address");
        if (core_n_filters != 0) {
            bool check = platform_check(
                bit_field_by_processor[r_id].bit_field_addresses);
            if (!check){
                log_error("failed");
            }
        }
        log_info("chekced");
    }

    log_info("check processor");
    bool check = platform_check(bit_field_by_processor);
    if (!check){
        log_error("failed");
    }
    log_info("checked");

    log_info("check all");
    check_all();
    log_info("checked all");

    *success = true;
    return bit_field_by_processor;
}

#endif  // __BIT_FIELD_READER_H__

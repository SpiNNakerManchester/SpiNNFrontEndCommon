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

#ifndef __BIT_FIELD_CREATER_H__
#define __BIT_FIELD_CREATER_H__

#include <debug.h>
#include "common/platform.h"
#include "common/compressor_sorter_structs.h"

void _log_bitfield(bit_field_t bit_field){
    log_info("0:%u 1:%u 2:%u 3:%u 4:%u 5:%u 6:%u 7:%u 8:%u 9:%u 10:%u 11:%u 12:%u",
        bit_field_test(bit_field, 0),
        bit_field_test(bit_field, 1),
        bit_field_test(bit_field, 2),
        bit_field_test(bit_field, 3),
        bit_field_test(bit_field, 4),
        bit_field_test(bit_field, 5),
        bit_field_test(bit_field, 6),
        bit_field_test(bit_field, 7),
        bit_field_test(bit_field, 8),
        bit_field_test(bit_field, 9),
        bit_field_test(bit_field, 10),
        bit_field_test(bit_field, 11),
        bit_field_test(bit_field, 12));
}

sorted_bit_fields_t* _malloc_sorted_bit_fields(uint32_t n_bf_addresses){
    sorted_bit_fields_t* sorted_bit_fields =
       MALLOC(sizeof(sorted_bit_fields_t));
    if (sorted_bit_fields == NULL){
        log_error("failed to allocate dtcm for sorted bitfields.");
        return NULL;
    }

    // malloc the separate bits of the sorted bitfield struct
    sorted_bit_fields->bit_fields = MALLOC(
        n_bf_addresses * sizeof(filter_info_t*));
    if (sorted_bit_fields->bit_fields == NULL){
        log_error("cannot allocate memory for the sorted bitfield addresses");
        return NULL;
    }

    sorted_bit_fields->processor_ids =
        MALLOC(n_bf_addresses * sizeof(uint32_t));
    if (sorted_bit_fields->processor_ids == NULL){
        log_error("cannot allocate memory for the sorted bitfields with "
                  "processors ids");
        return NULL;
    }

    sorted_bit_fields->sort_order =
        MALLOC(n_bf_addresses * sizeof(uint32_t));
    if (sorted_bit_fields->processor_ids == NULL){
        log_error("cannot allocate memory for the sorted bitfields with "
                  "sort_order");
        return NULL;
    }

    return sorted_bit_fields;
}

static inline uint32_t _locate_key_atom_map(
        uint32_t key, key_atom_data_t *key_atom_map){

    // read how many keys atom pairs there are
    uint32_t n_key_atom_pairs = key_atom_map->n_pairs;

    // cycle through keys in this region looking for the key find atoms of
    for (uint32_t i = 0; i < n_key_atom_pairs; i++) {
        // if key is correct, return atoms
        if (key_atom_map->pairs[i].key == key) {
            log_debug("n atoms is %d", key_atom_map->pairs[i].n_atoms);
            return key_atom_map->pairs[i].n_atoms;
        }
    }

    log_error("cannot find the key %d at all?! WTF", key);
    terminate(EXIT_FAIL);
    return 0;
}

//! \brief reads a bitfield and deduces how many bits are not set
//! \param[in] filter_info_struct: the struct holding a bitfield
//! \param[in] the addresses of the regions to read
//! \return how many redundant packets there are
uint32_t _detect_redundant_packet_count(
    filter_info_t filter_info, key_atom_data_t *key_atom_map){

    uint32_t n_filtered_packets = 0;
    uint32_t n_neurons = _locate_key_atom_map(filter_info.key, key_atom_map);
    for (uint neuron_id = 0; neuron_id < n_neurons; neuron_id++) {
        if (!bit_field_test(filter_info.data, neuron_id)) {
            n_filtered_packets += 1;
        }
    }
    int count = count_bit_field(filter_info.data, filter_info.n_words);
    int calc = filter_info.n_words * 32 - count;
    if (n_filtered_packets!= calc){
        log_info("n filtered packets = %d out of %d", n_filtered_packets,  n_neurons);
        _log_bitfield(filter_info.data);
        log_info("count = %d words = %d calc = %d", count, filter_info.n_words, calc);
    }

    return n_filtered_packets;
}

//! \brief reads in bitfields
//! \param[out] n_bf_pointer: the pointer to store how many bf addresses
//!  there are.
// \param[in] region_addresses: the addresses of the regions to read
//! \param[in/out] success: bool that helps decide if method finished
//! successfully or not
//! \return bool that states if it succeeded or not.
sorted_bit_fields_t* bit_field_creater_read_in_bit_fields(int* n_bf_pointer,
    region_addresses_t *region_addresses){

    int n_bf_addresses = 0;
    int n_pairs_of_addresses = region_addresses->n_pairs;
    log_info("n pairs of addresses = %d", n_pairs_of_addresses);

    // find out how many bit_fields there are
    for (int r_id = 0; r_id < n_pairs_of_addresses; r_id++) {
        n_bf_addresses += region_addresses->pairs[r_id].filter->n_filters;
    }
    log_info("Number of bitfields found is %u", n_bf_addresses);
    sorted_bit_fields_t* sorted_bit_fields = _malloc_sorted_bit_fields(
        n_bf_addresses);

    uint32_t* redundant = MALLOC(n_bf_addresses * sizeof(uint32_t));
    if (redundant  == NULL){
        log_error("cannot allocate memory redundant");
        return NULL;
    }

    // iterate through a processors bitfield region and add to the bf by
    // processor struct, whilst updating n bf total param.
    int index = 0;
    for (int r_id = 0; r_id < n_pairs_of_addresses; r_id++) {
        log_debug("%d %u %u %u %u %u", r_id,
            platform_check(sorted_bit_fields->bit_fields),
            platform_check(sorted_bit_fields->processor_ids),
            platform_check(sorted_bit_fields->sort_order),
            platform_check(sorted_bit_fields),
            platform_check(redundant)
        );
        // locate data for malloc memory calcs
        filter_region_t *filter_region = region_addresses->pairs[r_id].filter;
        key_atom_data_t *key_atom_map = region_addresses->pairs[r_id].key_atom;
        log_debug("index %u %u", index, filter_region->n_filters);
        for (int bf_id = 0; bf_id < filter_region->n_filters; bf_id++) {
             sorted_bit_fields->processor_ids[index] =
                region_addresses->pairs[r_id].processor;
            log_debug("index: %d, key %u words %u data %u" , index, filter_region->filters[bf_id].key, filter_region->filters[bf_id].n_words, filter_region->filters[bf_id].data);
            sorted_bit_fields->bit_fields[index] = &filter_region->filters[bf_id];
            log_debug("index: %d, key %u words %u data %u pointer %u" , index, sorted_bit_fields->bit_fields[index]->key, sorted_bit_fields->bit_fields[index]->n_words, sorted_bit_fields->bit_fields[index]->data, sorted_bit_fields->bit_fields[index]);
            if (index > 0){
                log_debug("index: %d, key %u words %u data %u pointer %u" , index-1, sorted_bit_fields->bit_fields[index-1]->key, sorted_bit_fields->bit_fields[index-1]->n_words, sorted_bit_fields->bit_fields[index-1]->data, sorted_bit_fields->bit_fields[index-1]);
            }
            redundant[index] = _detect_redundant_packet_count(
                filter_region->filters[bf_id], key_atom_map);
            platform_check_all_marked(60001);
            index++;
        }
    }
    log_info("read in");
    for (index = 0; index < n_bf_addresses; index++) {
        log_info("index %u processor: %u, key: %u, redundant %u", index,
            sorted_bit_fields->processor_ids[index],
            sorted_bit_fields->bit_fields[index]->key,
            redundant[index]);
    }
    log_info("printed");
    log_info("%u %u %u %u %u",
        platform_check(sorted_bit_fields->bit_fields),
        platform_check(sorted_bit_fields->processor_ids),
        platform_check(sorted_bit_fields->sort_order),
        platform_check(sorted_bit_fields),
        platform_check(redundant)
        );
    FREE(redundant);
    log_info("freed redundant");

    *n_bf_pointer = n_bf_addresses;
    return sorted_bit_fields;
}

//! sort out bitfields into processors and the keys of the bitfields to remove
//! \param[out] sorted_bf_by_processor: the sorted stuff
//! \param[in] region_addresses: addresses of the regions
//! \param[in] best_search_point: best search point
//! \param[in] sorted_bit_fields: the bitfields in sort order
//! \return list of master pop keys for a given processor
proc_bit_field_keys_t* sorter_sort_sorted_to_cores(
        region_addresses_t *region_addresses, int best_search_point,
        sorted_bit_fields_t* sorted_bit_fields) {
    proc_bit_field_keys_t *sorted_bf_by_processor =
            MALLOC(region_addresses->n_pairs * sizeof(proc_bit_field_keys_t));
    if (sorted_bf_by_processor == NULL) {
        log_error(
            "failed to allocate memory for the sorting of bitfield to keys");
        return NULL;
    }

    // malloc the lists
    for (int r_id = 0; r_id < region_addresses->n_pairs; r_id++){
        sorted_bf_by_processor[r_id].key_list =
            MALLOC(sizeof(master_pop_key_list_t));
        if (sorted_bf_by_processor[r_id].key_list == NULL){
            log_error("failed to alloc memory for master pop key list.");
            return NULL;
        }
    }

    //locate how many bitfields in the search space accepted that are of a
    // given core.
    for (int r_id = 0; r_id < region_addresses->n_pairs; r_id++){

        // locate processor id for this region
        int region_proc_id = region_addresses->pairs[r_id].processor;
        sorted_bf_by_processor[r_id].processor_id = region_proc_id;

        // count entries
        int n_entries = 0;
        for (int bf_index = 0; bf_index < best_search_point; bf_index++) {
            if (sorted_bit_fields->processor_ids[bf_index] == region_proc_id) {
                n_entries ++;
            }
        }

        // update length
        sorted_bf_by_processor[r_id].key_list->length_of_list = n_entries;

        // alloc for keys
        if (n_entries != 0){
            sorted_bf_by_processor[r_id].key_list->master_pop_keys =
                MALLOC(n_entries * sizeof(int));
            if (sorted_bf_by_processor[r_id].key_list->master_pop_keys ==
                    NULL) {
                log_error(
                    "failed to allocate memory for the master pop keys for "
                    "processor %d in the sorting of successful bitfields to "
                    "remove.", region_proc_id);
                for (int free_id =0; free_id < r_id; free_id++) {
                    FREE(sorted_bf_by_processor[free_id].key_list->master_pop_keys);
                }
                for (int free_id = 0; free_id < region_addresses->n_pairs;
                        free_id++){
                    FREE(sorted_bf_by_processor[free_id].key_list);
                }
                FREE(sorted_bf_by_processor);
                return NULL;
            }

            // put keys in the array
            int a_index = 0;
            for (int bf_index = 0; bf_index < best_search_point; bf_index++) {
                if (sorted_bit_fields->processor_ids[bf_index] ==
                        region_proc_id) {
                    filter_info_t* bf_pointer =
                        sorted_bit_fields->bit_fields[bf_index];
                    sorted_bf_by_processor[r_id].key_list->master_pop_keys[
                        a_index] = bf_pointer->key;
                    a_index ++;
                }
            }
         }
    }

    return sorted_bf_by_processor;
}


#endif  // __BIT_FIELD_CREATER_H__
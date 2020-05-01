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
#include <malloc_extras.h>
#include "common/constants.h"
#include "common/compressor_sorter_structs.h"

//! \brief For each possible processor the first index of a row for that
//! processor
int processor_heads[MAX_PROCESSORS];

//! \brief Sum of packets per processor for bitfields with redundancy not yet
//! ordered
uint32_t processor_totals[MAX_PROCESSORS];

//! /brief debug method to rpint a bit of a bitfeild on one line
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

//! sort out bitfields into processors and the keys of the bitfields to remove
//! \param[out] sorted_bf_by_processor: the sorted stuff
//! \param[in] region_addresses: addresses of the regions
//! \param[in] best_search_point: best search point
//! \param[in] sorted_bit_fields: the bitfields in sort order
//! \return list of master pop keys for a given processor
static inline proc_bit_field_keys_t* bit_field_reader_sort_by_processors(
        region_addresses_t *region_addresses, int best_search_point,
        sorted_bit_fields_t* sorted_bit_fields) {
    proc_bit_field_keys_t *sorted_bf_by_processor = MALLOC(
        region_addresses->n_triples * sizeof(proc_bit_field_keys_t));
    if (sorted_bf_by_processor == NULL) {
        log_error(
            "failed to allocate memory for the sorting of bitfield to keys");
        return NULL;
    }

    // malloc the lists
    for (int r_id = 0; r_id < region_addresses->n_triples; r_id++) {
        sorted_bf_by_processor[r_id].key_list =
            MALLOC(sizeof(master_pop_key_list_t));
        if (sorted_bf_by_processor[r_id].key_list == NULL){
            log_error("failed to alloc memory for master pop key list.");
            return NULL;
        }
    }

    //locate how many bitfields in the search space accepted that are of a
    // given processor.
    for (int r_id = 0; r_id < region_addresses->n_triples; r_id++){

        // locate processor id for this region
        int region_proc_id = region_addresses->triples[r_id].processor;
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
                for (int free_id = 0; free_id < region_addresses->n_triples;
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

//! \brief reads a bitfield and deduces how many bits are not set
//! \param[in] filter_info_struct: the struct holding a bitfield
//! \return how many redundant packets there are
static uint32_t detect_redundant_packet_count(filter_info_t *filter_info) {
    uint32_t n_filtered_packets = 0;
    uint32_t n_neurons = filter_info->n_atoms;
    for (uint neuron_id = 0; neuron_id < n_neurons; neuron_id++) {
        if (!bit_field_test(filter_info->data, neuron_id)) {
            n_filtered_packets += 1;
        }
    }
    return n_filtered_packets;
}

//! \brief Fills in the order column based on packet reduction
//! \param[in] sorted_bit_fields: data to be ordered
static inline void order_bitfields(sorted_bit_fields_t* sorted_bit_fields) {
    // Semantic sugar to avoid extra lookup all the time
    int* processor_ids = sorted_bit_fields->processor_ids;
    int* sort_order =  sorted_bit_fields->sort_order;
    filter_info_t** bit_fields = sorted_bit_fields->bit_fields;

    // To label each row in sort order
    for (int sorted_index = 0; sorted_index < sorted_bit_fields->n_bit_fields;
            sorted_index++) {
        // Find the processor with highest number of packets coming in
        int worst_processor = 0;
        uint32_t highest_neurons = 0;
        for (int c = 0; c < MAX_PROCESSORS; c++) {
            if (processor_totals[c] > highest_neurons){
                worst_processor = c;
                highest_neurons = processor_totals[c];
            }
        }
        
        // Label the row pointer to be the header as next
        int index = processor_heads[worst_processor];
        sort_order[index] = sorted_index;
        log_debug(
            "processor %u index %u total %u",
            worst_processor, index, processor_totals[worst_processor]);

        // If there is another row with the same processor
        if ((index < sorted_bit_fields->n_bit_fields - 1) &&
                (processor_ids[index] == processor_ids[index + 1])) {
            log_debug(
                "i %u processor %u index %u more %u total %u",
                sorted_index, worst_processor, index,
                sorted_bit_fields->n_bit_fields,
                 processor_totals[worst_processor]);
                
            // reduce the packet count bu redundancy
            processor_totals[worst_processor] -=
                detect_redundant_packet_count(bit_fields[index]);
                
            // move the pointer
            processor_heads[worst_processor] += 1;
        } else {
            // otherwise set the counters to ignore this processor
            processor_totals[worst_processor] = 0;
            processor_heads[worst_processor] = DO_NOT_USE;

            log_debug(
                "i %u processor %u index %u last %u total %u",
                sorted_index, worst_processor, index,
                sorted_bit_fields->n_bit_fields,
                processor_totals[worst_processor]);
        }
    }
}

//! brief Sorts the data bases on the sort_order array
//! \param[in] sorted_bit_fields: data to be ordered
static inline void sort_by_order(sorted_bit_fields_t* sorted_bit_fields) {
    // Everytime there is a swap at least one of the rows is moved to the
    //         final place.
    //  There is one check per row in the for loop plus if the first fails
    //        up to one more for each row about to be moved to the correct place.

    malloc_extras_check_all_marked(60011);
    int* processor_ids = sorted_bit_fields->processor_ids;
    int* sort_order = sorted_bit_fields->sort_order;
    filter_info_t** bit_fields = sorted_bit_fields->bit_fields;
    // Check each row in the lists
    for (int i = 0; i < sorted_bit_fields->n_bit_fields; i++) {
        // check that the data is in the correct place
        while (sort_order[i] != i) {
            int j = sort_order[i];
            // If not swap the data there into the correct place
            int temp_processor_id = processor_ids[i];
            processor_ids[i] = processor_ids[j];
            processor_ids[j] = temp_processor_id;
            uint32_t temp_sort_order = sort_order[i];
            sort_order[i] = sort_order[j];
            sort_order[j] = temp_sort_order;
            filter_info_t* bit_field_temp = bit_fields[i];
            bit_fields[i] = bit_fields[j];
            bit_fields[j] = bit_field_temp;
        }
    }
    malloc_extras_check_all_marked(60010);
}

//! brief Sorts the data bases on the bitfield key.
//! \param[in] sorted_bit_fields: data to be ordered
static inline void sort_by_key(sorted_bit_fields_t* sorted_bit_fields) {
    malloc_extras_check_all_marked(60031);
    
    // Semantic sugar to avoid extra lookup all the time
    int* processor_ids = sorted_bit_fields->processor_ids;
    int* sort_order = sorted_bit_fields->sort_order;
    filter_info_t** bit_fields = sorted_bit_fields->bit_fields;
    
    // Everytime there is a swap at least one of the rows is moved to the
    //         final place.
    //  There is one check per row in the for loop plus if the first fails
    //      up to one more for each row about to be moved to the correct place.
    for (int i = 0; i < sorted_bit_fields->n_bit_fields - 1; i++) {
        for (int j = i + 1; j < sorted_bit_fields->n_bit_fields; j++) {
           // check location
           if (bit_fields[i]->key > bit_fields[j]->key) {
                // If not swap the data there into the correct place
                int temp_processor_id = processor_ids[i];
                processor_ids[i] = processor_ids[j];
                processor_ids[j] = temp_processor_id;
                uint32_t temp_sort_order = sort_order[i];
                sort_order[i] = sort_order[j];
                sort_order[j] = temp_sort_order;
                filter_info_t* bit_field_temp = bit_fields[i];
                bit_fields[i] = bit_fields[j];
                bit_fields[j] = bit_field_temp;
            }
        }
    }
    malloc_extras_check_all_marked(60032);
}

//! \brief debugger support. prints sorted bitfields and tests malloc.
//! \param[in] sorted_bit_fields: the sorted bitfields
//! \param[in]  marker: the marker to hand to malloc checker.
static void print_structs(sorted_bit_fields_t* sorted_bit_fields, int marker) {
    // useful for debugging
    for (int index = 0; index < sorted_bit_fields->n_bit_fields; index++) {
        log_debug(
            "index %u processor: %u, key: %u, data %u redundant %u order %u",
            index,
            sorted_bit_fields->processor_ids[index],
            sorted_bit_fields->bit_fields[index]->key,
            sorted_bit_fields->bit_fields[index]->data,
            detect_redundant_packet_count(
                sorted_bit_fields->bit_fields[index]),
            sorted_bit_fields->sort_order[index]);
    }
    malloc_extras_check_all_marked(marker);
}

//! \brief fills in the sorted bit-field struct and builds tracker of
//! incoming packet counts.
//! \param[in] region_addresses: the addresses of the regions to read
//! \param[in] sorted_bit_fields: the sorted bitfield struct with bitfields
//! in sorted order.
static inline void fills_in_sorted_bit_fields_and_tracker(
        region_addresses_t *region_addresses, 
        sorted_bit_fields_t* sorted_bit_fields) {
    // iterate through a processors bitfield region and add to the bf by
    // processor struct, whilst updating n bf total param.
    int index = 0;
    for (int r_id = 0; r_id < region_addresses->n_triples; r_id++) {
        
        // locate data for malloc memory calcs
        filter_region_t *filter_region = region_addresses->triples[r_id].filter;
        int processor = region_addresses->triples[r_id].processor;

        // store the index in bitfields list where this processors bitfields
        // start being read in at. (not sorted)
        processor_heads[processor] = index;

        // read in the processors bitfields.
        for (int bf_id = 0; bf_id < filter_region->n_redundancy_filters;
                bf_id++, index++) {

            // update trackers.
            sorted_bit_fields->processor_ids[index] = processor;
            sorted_bit_fields->bit_fields[index] =
                &filter_region->filters[bf_id];
            processor_totals[processor] +=
                filter_region->filters[bf_id].n_atoms;

            print_structs(sorted_bit_fields, 60011);
        }

        // accum the incoming packets from bitfields which have no redundancy
        for (int bf_id = filter_region->n_redundancy_filters;
                bf_id < filter_region->n_filters; bf_id++) {
            processor_totals[processor] +=
                filter_region->filters[bf_id].n_atoms;
        }
    }
}


//! \brief reads in bitfields
// \param[in] region_addresses: the addresses of the regions to read
//! \param[in] sorted_bit_fields_t: the sorted bitfield struct to which
//! bitfields in sorted order will be populated.
//! \return bool that states if it succeeded or not.
static inline void bit_field_reader_read_in_bit_fields(
        region_addresses_t *region_addresses,
        sorted_bit_fields_t* sorted_bit_fields) {

    //init data tracking structures
    for (int i = 0; i < MAX_PROCESSORS; i++) {
        processor_heads[i] = DO_NOT_USE;
        processor_totals[i] = 0;
    }

    // track positions and incoming packet counts.
    fills_in_sorted_bit_fields_and_tracker(region_addresses, sorted_bit_fields);

    //TODO safety code to be removed.
    for (int i = 0; i < MAX_PROCESSORS; i++) {
        log_debug(
            "i: %d, head: %d count: %d",
            i, processor_heads[i], processor_totals[i]);
    }
    print_structs(sorted_bit_fields, 60012);

    // sort bitfields so that bit-fields are in order of most impact on worse
    // affected cores. so that merged bitfields should reduce packet rates
    // fairly across cores on the chip.
    order_bitfields(sorted_bit_fields);

    //TODO safety code to be removed.
    print_structs(sorted_bit_fields, 60015);

    // sort the bitfields by key.
    // NOTE: does not affect previous sort, as this directly affects the index
    // in the bitfield array, whereas the previous sort affects the sort index
    // array.
    sort_by_key(sorted_bit_fields);

    // useful for debugging
    print_structs(sorted_bit_fields, 60016);
}


//! \brief sets up initial sorted bitfield struct
//! \param[in] region_addresses: the address that holds all the chips
//! bitfield addresses
//! \return the pointer to the sorted memory tracker, or NULL if any of the
//! MALLOC's failed for any reason.
static inline sorted_bit_fields_t* bit_field_reader_initialise(
        region_addresses_t *region_addresses) {
    sorted_bit_fields_t* sorted_bit_fields = MALLOC(sizeof(sorted_bit_fields_t));
    if (sorted_bit_fields == NULL) {
        log_error("failed to allocate dtcm for sorted bitfields.");
        return NULL;
    }

    // figure out how many bitfields we need
    log_debug("n triples of addresses = %d", region_addresses->n_triples);
    sorted_bit_fields->n_bit_fields = 0;
    log_info(
        "Number of bitfields found is %u", sorted_bit_fields->n_bit_fields);
    for (int r_id = 0; r_id < region_addresses->n_triples; r_id++) {
        sorted_bit_fields->n_bit_fields = sorted_bit_fields->n_bit_fields +
            region_addresses->triples[r_id].filter->n_redundancy_filters;
    }

    // malloc the separate bits of the sorted bitfield struct
    sorted_bit_fields->bit_fields = MALLOC(
        sorted_bit_fields->n_bit_fields * sizeof(filter_info_t*));
    if (sorted_bit_fields->bit_fields == NULL){
        log_error("cannot allocate memory for the sorted bitfield addresses");
        FREE(sorted_bit_fields);
        return NULL;
    }

    sorted_bit_fields->processor_ids =
        MALLOC(sorted_bit_fields->n_bit_fields * sizeof(int));
    if (sorted_bit_fields->processor_ids == NULL){
        log_error("cannot allocate memory for the sorted bitfields with "
                  "processors ids");
        FREE(sorted_bit_fields->bit_fields);
        FREE(sorted_bit_fields);
        return NULL;
    }

    sorted_bit_fields->sort_order =
        MALLOC(sorted_bit_fields->n_bit_fields * sizeof(int));
    if (sorted_bit_fields->sort_order == NULL){
        log_error("cannot allocate memory for the sorted bitfields with "
                  "sort_order");
        FREE(sorted_bit_fields->bit_fields);
        FREE(sorted_bit_fields->processor_ids);
        FREE(sorted_bit_fields);
        return NULL;
    }

    // init to -1, else random data (used to make prints cleaner)
    for (int sorted_index = 0; sorted_index < sorted_bit_fields->n_bit_fields;
            sorted_index++) {
        sorted_bit_fields->sort_order[sorted_index] = FAILED_TO_FIND;
    }

    // return
    return sorted_bit_fields;
}

#endif  // __BIT_FIELD_CREATER_H__

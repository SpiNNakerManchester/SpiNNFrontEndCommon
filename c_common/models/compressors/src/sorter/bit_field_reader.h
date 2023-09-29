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

//! \dir
//! \brief Support files for the bitfield sorter
//! \file
//! \brief Code for reading bitfields in SDRAM
#ifndef __BIT_FIELD_READER_H__
#define __BIT_FIELD_READER_H__

#include <debug.h>
#include <malloc_extras.h>
#include "common/constants.h"
#include "bit_field_common/compressor_sorter_structs.h"

//! For each possible processor the first index of a row for that processor
static int processor_heads[MAX_PROCESSORS];

//! Sum of packets per processor for bitfields with redundancy not yet ordered
static uint32_t processor_totals[MAX_PROCESSORS];

//! \brief Detemine how many bits are not set in a bit field
//! \param[in] filter: The bitfield to look for redundancy in
//! \return How many redundant packets there are
static uint32_t n_redundant(filter_info_t *restrict filter) {
    uint32_t n_atoms = filter->n_atoms;
    uint32_t n_words = get_bit_field_size(n_atoms);
    return n_atoms - count_bit_field(filter->data, n_words);
}

//! \brief Fill in the order column based on packet reduction
//! \param[in] sorted_bit_fields: Data to be ordered
static inline void order_bitfields(
        sorted_bit_fields_t *restrict sorted_bit_fields) {
    // Semantic sugar to avoid extra lookup all the time
    int *restrict processor_ids = sorted_bit_fields->processor_ids;
    int *restrict sort_order =  sorted_bit_fields->sort_order;
    filter_info_t **restrict bit_fields = sorted_bit_fields->bit_fields;

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
        log_debug("processor %u index %u total %u",
                worst_processor, index, processor_totals[worst_processor]);

        // If there is another row with the same processor
        if ((index < sorted_bit_fields->n_bit_fields - 1) &&
                (processor_ids[index] == processor_ids[index + 1])) {
            log_debug("i %u processor %u index %u more %u total %u",
                    sorted_index, worst_processor, index,
                    sorted_bit_fields->n_bit_fields,
                    processor_totals[worst_processor]);

            // reduce the packet count bu redundancy
            processor_totals[worst_processor] -= n_redundant(bit_fields[index]);

            // move the pointer
            processor_heads[worst_processor] += 1;
        } else {
            // otherwise set the counters to ignore this processor
            processor_totals[worst_processor] = NO_BIT_FIELDS;
            processor_heads[worst_processor] = DO_NOT_USE;

            log_debug("i %u processor %u index %u last %u total %u",
                    sorted_index, worst_processor, index,
                    sorted_bit_fields->n_bit_fields,
                    processor_totals[worst_processor]);
        }
    }
}

//! \brief Sort the data based on the bitfield key
//! \param[in] sorted_bit_fields: Data to be ordered
static inline void sort_by_key(
        sorted_bit_fields_t *restrict sorted_bit_fields) {
    // Semantic sugar to avoid extra lookup all the time
    int *restrict processor_ids = sorted_bit_fields->processor_ids;
    int *restrict sort_order = sorted_bit_fields->sort_order;
    filter_info_t **restrict bit_fields = sorted_bit_fields->bit_fields;
    int i, j;

    for (i = 1; i < sorted_bit_fields->n_bit_fields; i++) {
        const int temp_processor_id = processor_ids[i];
        const uint32_t temp_sort_order = sort_order[i];
        filter_info_t *const bit_field_temp = bit_fields[i];
        register uint32_t key = bit_field_temp->key;

        for (j = i; j > 0 && bit_fields[j - 1]->key > key; j--) {
            processor_ids[j] = processor_ids[j - 1];
            sort_order[j] = sort_order[j - 1];
            bit_fields[j] = bit_fields[j - 1];
        }

        processor_ids[j] = temp_processor_id;
        sort_order[j] = temp_sort_order;
        bit_fields[j] = bit_field_temp;
    }
}

//! \brief Debugging support for bit_field_reader_read_in_bit_fields();
//!     prints sorted bitfields and tests memory allocation
//! \param[in] sorted_bit_fields: The sorted bitfields
static inline void print_structs(
        sorted_bit_fields_t *restrict sorted_bit_fields) {
    // useful for debugging
    for (int i = 0; i < sorted_bit_fields->n_bit_fields; i++) {
        log_debug("index %u processor: %u, key: %u, data %u redundant %u order %u",
                i, sorted_bit_fields->processor_ids[i],
                sorted_bit_fields->bit_fields[i]->key,
                sorted_bit_fields->bit_fields[i]->data,
                n_redundant(sorted_bit_fields->bit_fields[i]),
                sorted_bit_fields->sort_order[i]);
    }
}

//! \brief Sort a subset of the bit fields by the redundancy
//! \param[in,out] sorted_bit_fields:
//!     The bit fields to sort.
//!     The bit field order is actually changed by this function.
//! \param[in] start: The index of the first bit field to sort
//! \param[in] end: The index after the last bit field to sort
static inline void sort_by_redundancy(sorted_bit_fields_t *sorted_bit_fields,
        uint32_t start, uint32_t end) {
    // We only need to sort the bit fields, as this assumes it is called
    // before the index is filled in, and where start and n_items covers items
    // with the same processor id
    filter_info_t **bit_fields = sorted_bit_fields->bit_fields;
    for (uint32_t i = start + 1; i < end; i++) {
        filter_info_t *temp_bf = bit_fields[i];

        uint32_t j;
        for (j = i; j > start && n_redundant(bit_fields[j - 1]) < n_redundant(temp_bf); j--) {
            bit_fields[j] = bit_fields[j - 1];
        }
        bit_fields[j] = temp_bf;
    }
}

//! \brief Fill in the sorted bit-field struct and builds tracker of
//!     incoming packet counts.
//! \param[in] region_addresses: The addresses of the regions to read
//! \param[in] sorted_bit_fields: The sorted bitfield struct with bitfields
//!     in sorted order.
static inline void fills_in_sorted_bit_fields_and_tracker(
        region_addresses_t *restrict region_addresses,
        sorted_bit_fields_t *restrict sorted_bit_fields) {
    // iterate through a processors bitfield region and add to the bf by
    // processor struct, whilst updating num of total param.
    for (int r_id = 0, index = 0; r_id < region_addresses->n_processors; r_id++) {
        // locate data for malloc memory calcs
        filter_region_t *restrict filter_region =
                region_addresses->processors[r_id].filter;
        int processor = region_addresses->processors[r_id].processor;

        // store the index in bitfields list where this processors bitfields
        // start being read in at. (not sorted)
        processor_heads[processor] = index;

        // read in the processors bitfields.
        filter_info_t *filters = filter_region->filters;
        for (uint32_t bf_id = 0; bf_id < filter_region->n_filters; bf_id++) {
            // update trackers.
            if (!filters[bf_id].all_ones) {
                sorted_bit_fields->processor_ids[index] = processor;
                sorted_bit_fields->bit_fields[index] = &filters[bf_id];
                index++;
            }

            // also accum the incoming packets from bitfields which have no
            // redundancy
            processor_totals[processor] += filters[bf_id].n_atoms;
        }
        sort_by_redundancy(sorted_bit_fields, processor_heads[processor], index);
    }
}


//! \brief Read in bitfields
//! \param[in] region_addresses: The addresses of the regions to read
//! \param[in] sorted_bit_fields: The sorted bitfield structure to which
//!     bitfields in sorted order will be populated.
static inline void bit_field_reader_read_in_bit_fields(
        region_addresses_t *restrict region_addresses,
        sorted_bit_fields_t *restrict sorted_bit_fields) {
    //init data tracking structures
    for (int i = 0; i < MAX_PROCESSORS; i++) {
        processor_heads[i] = DO_NOT_USE;
        processor_totals[i] = 0;
    }

    // track positions and incoming packet counts.
    fills_in_sorted_bit_fields_and_tracker(region_addresses, sorted_bit_fields);

    //TODO safety code to be removed.
    for (int i = 0; i < MAX_PROCESSORS; i++) {
        log_debug("i: %d, head: %d count: %d",
                i, processor_heads[i], processor_totals[i]);
    }
#if 0
    print_structs(sorted_bit_fields);
#endif

    // sort bitfields so that bit-fields are in order of most impact on worse
    // affected cores. so that merged bitfields should reduce packet rates
    // fairly across cores on the chip.
    order_bitfields(sorted_bit_fields);

    //TODO safety code to be removed.
#if 0
    print_structs(sorted_bit_fields);
#endif

    // sort the bitfields by key.
    // NOTE: does not affect previous sort, as this directly affects the index
    // in the bitfield array, whereas the previous sort affects the sort index
    // array.
    sort_by_key(sorted_bit_fields);

    // useful for debugging
#if 0
    print_structs(sorted_bit_fields);
#endif
}

//! \brief Sets up the initial sorted bitfield struct
//! \param[in] region_addresses:
//!     The address that holds all the chips' bitfield addresses
//! \return The pointer to the sorted memory tracker, or `NULL` if any of the
//!     #MALLOC's failed for any reason.
static inline sorted_bit_fields_t * bit_field_reader_initialise(
        region_addresses_t *restrict region_addresses) {
    sorted_bit_fields_t *restrict sorted_bit_fields = MALLOC_SDRAM(
            sizeof(sorted_bit_fields_t));
    if (sorted_bit_fields == NULL) {
        log_error("failed to allocate DTCM for sorted bitfields.");
        return NULL;
    }

    // figure out how many bitfields we need
    log_debug("n_processors of addresses = %d", region_addresses->n_processors);
    int n_bit_fields = 0;
    for (int r_id = 0; r_id < region_addresses->n_processors; r_id++) {
        filter_region_t *restrict filter = region_addresses->processors[r_id].filter;
        uint32_t n_filters = filter->n_filters;
        filter_info_t *filters = filter->filters;
        uint32_t n_usable = 0;
        for (uint32_t f_id = 0; f_id < n_filters; f_id++) {
            n_usable += !filters[f_id].all_ones;
        }
        n_bit_fields += n_usable;
        log_debug("Core %d has %u bitfields of which %u have redundancy",
                region_addresses->processors[r_id].processor,
                filter->n_filters, n_usable);
    }
    sorted_bit_fields->n_bit_fields = n_bit_fields;
    log_info("Number of bitfields with redundancy found is %u",
            sorted_bit_fields->n_bit_fields);

    // if there are no bit-fields just return sorted bitfields.
    if (n_bit_fields != 0) {
        // malloc the separate bits of the sorted bitfield struct
        sorted_bit_fields->bit_fields = MALLOC_SDRAM(
                n_bit_fields * sizeof(filter_info_t*));
        if (sorted_bit_fields->bit_fields == NULL) {
            log_error(
                    "cannot allocate memory for the sorted bitfield addresses");
            FREE(sorted_bit_fields);
            return NULL;
        }

        sorted_bit_fields->processor_ids = MALLOC_SDRAM(
                n_bit_fields * sizeof(int));
        if (sorted_bit_fields->processor_ids == NULL) {
            log_error("cannot allocate memory for the sorted bitfields with "
                    "processors ids");
            FREE(sorted_bit_fields->bit_fields);
            FREE(sorted_bit_fields);
            return NULL;
        }

        sorted_bit_fields->sort_order = MALLOC_SDRAM(
                n_bit_fields * sizeof(int));
        if (sorted_bit_fields->sort_order == NULL) {
            log_error("cannot allocate memory for the sorted bitfields with "
                    "sort_order");
            FREE(sorted_bit_fields->bit_fields);
            FREE(sorted_bit_fields->processor_ids);
            FREE(sorted_bit_fields);
            return NULL;
        }

        // init to -1, else random data (used to make prints cleaner)
        for (int sorted_index = 0; sorted_index < n_bit_fields;
                sorted_index++) {
            sorted_bit_fields->sort_order[sorted_index] = FAILED_TO_FIND;
        }
    }

    // return
    return sorted_bit_fields;
}

#endif  // __BIT_FIELD_READER_H__

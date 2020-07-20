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
static uint32_t processor_heads[MAX_PROCESSORS];

//! Sum of packets per processor for bitfields with redundancy not yet ordered
static uint32_t processor_totals[MAX_PROCESSORS];

//! \brief Read a bitfield and deduces how many bits are not set
//! \param[in] filter_info: The bitfield to look for redundancy in
//! \return How many redundant packets there are
static uint32_t detect_redundant_packet_count(
        filter_info_t *restrict filter_info) {
    uint32_t n_filtered_packets = 0;
    uint32_t n_neurons = filter_info->n_atoms;
    for (uint32_t i = 0; i < n_neurons; i++) {
        if (!bit_field_test(filter_info->data, i)) {
            n_filtered_packets++;
        }
    }
    return n_filtered_packets;
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
    for (uint32_t i = 0; i < sorted_bit_fields->n_bit_fields; i++) {
        // Find the processor with highest number of packets coming in
        uint32_t worst_processor = 0;
        uint32_t highest_neurons = 0;
        for (uint32_t c = 0; c < MAX_PROCESSORS; c++) {
            if (processor_totals[c] > highest_neurons){
                worst_processor = c;
                highest_neurons = processor_totals[c];
            }
        }

        // Label the row pointer to be the header as next
        uint32_t index = processor_heads[worst_processor];
        sort_order[index] = i;
        log_debug("processor %u index %u total %u",
                worst_processor, index, processor_totals[worst_processor]);

        // If there is another row with the same processor
        if ((index + 1 < sorted_bit_fields->n_bit_fields) &&
                (processor_ids[index] == processor_ids[index + 1])) {
            log_debug("i %u processor %u index %u more %u total %u",
                    i, worst_processor, index,
                    sorted_bit_fields->n_bit_fields,
                    processor_totals[worst_processor]);

            // reduce the packet count bu redundancy
            processor_totals[worst_processor] -=
                    detect_redundant_packet_count(bit_fields[index]);

            // move the pointer
            processor_heads[worst_processor]++;
        } else {
            // otherwise set the counters to ignore this processor
            processor_totals[worst_processor] = NO_BIT_FIELDS;
            processor_heads[worst_processor] = DO_NOT_USE;

            log_debug("i %u processor %u index %u last %u total %u",
                    i, worst_processor, index,
                    sorted_bit_fields->n_bit_fields,
                    processor_totals[worst_processor]);
        }
    }
}

//! \brief Sort the data bases on the sort_order array
//! \param[in] sorted_bit_fields: Data to be ordered
//! \internal
//!     DEAD code but left as it shows how it could be sorted by order fast
static inline void sort_by_order(
        sorted_bit_fields_t *restrict sorted_bit_fields) {
    // Every time there is a swap at least one of the rows is moved to the
    // final place.
    //
    // There is one check per row in the for loop plus if the first fails
    // up to one more for each row about to be moved to the correct place.

    int *restrict processor_ids = sorted_bit_fields->processor_ids;
    int *restrict sort_order = sorted_bit_fields->sort_order;
    filter_info_t **restrict bit_fields = sorted_bit_fields->bit_fields;

    // Check each row in the lists
    for (uint32_t i = 0; i < sorted_bit_fields->n_bit_fields; i++) {
        // check that the data is in the correct place
        while (sort_order[i] != (int) i) {
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
}

//! \brief Sort the data based on the bitfield key
//! \param[in] sorted_bit_fields: Data to be ordered
static inline void sort_by_key(
        sorted_bit_fields_t *restrict sorted_bit_fields) {
    // Semantic sugar to avoid extra lookup all the time
    int *restrict processor_ids = sorted_bit_fields->processor_ids;
    int *restrict sort_order = sorted_bit_fields->sort_order;
    filter_info_t **restrict bit_fields = sorted_bit_fields->bit_fields;

    for (uint32_t i = 1, j; i < sorted_bit_fields->n_bit_fields ; i++) {
        int temp_proc_id = processor_ids[i];
        uint32_t temp_order = sort_order[i];
        filter_info_t *temp_bf = bit_fields[i];

        for (j = i; (j > 0) && bit_fields[j - 1]->key > temp_bf->key; j--) {
            processor_ids[j] = processor_ids[j - 1];
            sort_order[j] = sort_order[j - 1];
            bit_fields[j] = bit_fields[j - 1];
        }

        processor_ids[j] = temp_proc_id;
        sort_order[j] = temp_order;
        bit_fields[j] = temp_bf;
    }
}

//! \brief Debugging support for bit_field_reader_read_in_bit_fields();
//!     prints sorted bitfields and tests memory allocation
//! \param[in] sorted_bit_fields: The sorted bitfields
static inline void print_structs(
        sorted_bit_fields_t *restrict sorted_bit_fields) {
    // useful for debugging
    for (uint32_t i = 0; i < sorted_bit_fields->n_bit_fields; i++) {
        log_info("index %u processor: %u, key: %u, data %u redundant %u "
                "order %u", i,
                sorted_bit_fields->processor_ids[i],
                sorted_bit_fields->bit_fields[i]->key,
                sorted_bit_fields->bit_fields[i]->data,
                detect_redundant_packet_count(sorted_bit_fields->bit_fields[i]),
                sorted_bit_fields->sort_order[i]);
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
    for (uint32_t i = 0, index = 0; i < region_addresses->n_triples; i++) {
        // locate data for malloc memory calcs
        filter_region_t *restrict filter_region =
                region_addresses->triples[i].filter;
        int processor = region_addresses->triples[i].processor;

        if (filter_region->n_redundancy_filters == 0) {
            // no bitfields to point at or sort so total can stay zero
            continue;
        }

        // store the index in bitfields list where this processors bitfields
        // start being read in at. (not sorted)
        processor_heads[processor] = index;

        // read in the processors bitfields.
        for (uint32_t j = 0; j < filter_region->n_redundancy_filters;
                j++, index++) {
            // update trackers.
            sorted_bit_fields->processor_ids[index] = processor;
            sorted_bit_fields->bit_fields[index] = &filter_region->filters[j];
            processor_totals[processor] += filter_region->filters[j].n_atoms;
        }

        // accum the incoming packets from bitfields which have no redundancy
        for (uint32_t j = filter_region->n_redundancy_filters;
                j < filter_region->n_filters; j++) {
            processor_totals[processor] += filter_region->filters[j].n_atoms;
        }
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
    for (uint32_t i = 0; i < MAX_PROCESSORS; i++) {
        processor_heads[i] = DO_NOT_USE;
        processor_totals[i] = 0;
    }

    // track positions and incoming packet counts.
    fills_in_sorted_bit_fields_and_tracker(region_addresses, sorted_bit_fields);

    //TODO safety code to be removed.
    for (uint32_t i = 0; i < MAX_PROCESSORS; i++) {
        log_debug("i: %u, head: %d count: %d",
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
    log_debug("n triples of addresses = %u", region_addresses->n_triples);
    uint32_t n_bit_fields = 0;
    for (uint32_t i = 0; i < region_addresses->n_triples; i++) {
        const triples_t *triple = &region_addresses->triples[i];
        n_bit_fields += triple->filter->n_redundancy_filters;
        log_info("Core %d has %u bitfields of which %u have redundancy",
                triple->processor, triple->filter->n_filters,
                triple->filter->n_redundancy_filters);
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
            log_error("cannot allocate memory for sorted bitfield addresses");
            FREE(sorted_bit_fields);
            return NULL;
        }

        sorted_bit_fields->processor_ids = MALLOC_SDRAM(
                n_bit_fields * sizeof(int));
        if (sorted_bit_fields->processor_ids == NULL) {
            log_error("cannot allocate memory for sorted bitfield processor ids");
            FREE(sorted_bit_fields->bit_fields);
            FREE(sorted_bit_fields);
            return NULL;
        }

        sorted_bit_fields->sort_order = MALLOC_SDRAM(
                n_bit_fields * sizeof(int));
        if (sorted_bit_fields->sort_order == NULL) {
            log_error("cannot allocate memory for sorted bitfield sort_order");
            FREE(sorted_bit_fields->bit_fields);
            FREE(sorted_bit_fields->processor_ids);
            FREE(sorted_bit_fields);
            return NULL;
        }

        // init to -1, else random data (used to make prints cleaner)
        for (uint32_t i = 0; i < n_bit_fields; i++) {
            sorted_bit_fields->sort_order[i] = FAILED_TO_FIND;
        }
    }

    // return
    return sorted_bit_fields;
}

#endif  // __BIT_FIELD_READER_H__

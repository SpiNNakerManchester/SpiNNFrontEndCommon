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

//! \brief Determine how many bits are not set in a bit field
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
    uint32_t *restrict processor_ids = sorted_bit_fields->processor_ids;
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
            processor_totals[worst_processor] -= n_redundant(bit_fields[index]);

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

//! \brief Sort the data based on the bitfield key
//! \param[in] sorted_bit_fields: Data to be ordered
static inline void sort_by_key(
        sorted_bit_fields_t *restrict sorted_bit_fields) {
    // Semantic sugar to avoid extra lookup all the time
    uint32_t *restrict processor_ids = sorted_bit_fields->processor_ids;
    int *restrict sort_order = sorted_bit_fields->sort_order;
    filter_info_t **restrict bit_fields = sorted_bit_fields->bit_fields;
    uint32_t i, j;

    for (i = 1; i < sorted_bit_fields->n_bit_fields; i++) {
        const uint32_t temp_processor_id = processor_ids[i];
        const int temp_sort_order = sort_order[i];
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
    for (uint32_t i = 0; i < sorted_bit_fields->n_bit_fields; i++) {
        log_info("index %u processor: %u, key: %u, data %u redundant %u "
                "order %u", i,
                sorted_bit_fields->processor_ids[i],
                sorted_bit_fields->bit_fields[i]->key,
                sorted_bit_fields->bit_fields[i]->data,
                n_redundant(sorted_bit_fields->bit_fields[i]),
                sorted_bit_fields->sort_order[i]);
    }
}

//! \brief Sort a subset of the bit fields by the redundancy
//! \param[in/out] sorted_bit_fields: The bit fields to sort.
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
    for (uint32_t i = 0, index = 0; i < region_addresses->n_processors; i++) {
        // locate data for malloc memory calcs
        filter_region_t *restrict filter_region =
                region_addresses->processors[i].filter;
        uint32_t processor = region_addresses->processors[i].processor;

        if (filter_region->n_redundancy_filters == 0) {
            // no bitfields to point at or sort so total can stay zero
            continue;
        }

        // store the index in bitfields list where this processors bitfields
        // start being read in at. (not sorted)
        processor_heads[processor] = index;

        // read in the processors bitfields.
        uint32_t n_filters = filter_region->n_filters;
        for (uint32_t j = 0; j < n_filters; j++) {
            filter_info_t *f_info = &filter_region->filters[j];
            // update trackers.
            if (!f_info->all_ones) {
                sorted_bit_fields->processor_ids[index] = processor;
                sorted_bit_fields->bit_fields[index] = f_info;
                index++;
            }

            // also accum the incoming packets from bitfields which have no
            // redundancy
            processor_totals[processor] += f_info->n_atoms;
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
    log_debug("n_processors of addresses = %d", region_addresses->n_processors);
    uint32_t n_bit_fields = 0;
    for (uint32_t i = 0; i < region_addresses->n_processors; i++) {
        filter_region_t *filter = region_addresses->processors[i].filter;
        uint32_t n_filters = filter->n_filters;
        filter_info_t *f_infos = filter->filters;
        uint32_t n_usable = 0;
        for (uint32_t j = 0; j < n_filters; j++) {
            n_usable += !f_infos[j].all_ones;
        }
        n_bit_fields += n_usable;
        log_info("Core %d has %u bitfields of which %u have redundancy",
                region_addresses->processors[i].processor, n_filters, n_usable);
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
                n_bit_fields * sizeof(uint32_t));
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

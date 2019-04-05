#ifndef __BIT_FIELD_READER_H__
#define __BIT_FIELD_READER_H__

#include "helpful_functions.h"

//! \brief reads in bitfields
//! \return bool that states if it succeeded or not.
bit_field_by_processor_t* bit_field_reader_read_in_bit_fields(
        int* n_bf_addresses, region_addresses_t *region_addresses){

    // count how many bitfields there are in total
    *n_bf_addresses = 0;
    int n_pairs_of_addresses = region_addresses->n_pairs;
    log_info("n pairs of addresses = %d", n_pairs_of_addresses);

    // malloc the bt fields by processor

    bit_field_by_processor_t* bit_field_by_processor = MALLOC(
        n_pairs_of_addresses * sizeof(bit_field_by_processor_t));
    if (bit_field_by_processor == NULL) {
        log_error("failed to allocate memory for pairs, if it fails here. "
                  "might as well give up");
        return NULL;
    }

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
        *n_bf_addresses += core_n_filters;

        // track lengths
        bit_field_by_processor[r_id].length_of_list = core_n_filters;
        log_info(
            "bit field by processor with region %d, has length of %d",
            r_id, core_n_filters);

        // malloc for bitfield region addresses
        bit_field_by_processor[r_id].bit_field_addresses =
            MALLOC(core_n_filters * sizeof(filter_info_t));
        if (bit_field_by_processor[r_id].bit_field_addresses == NULL) {
            log_error("failed to allocate memory for bitfield addresses for "
                      "region %d, might as well fail", r_id);
            return NULL;
        }

        // populate table for addresses where each bitfield component starts
        for (int bf_id = 0; bf_id < core_n_filters; bf_id++) {
            bit_field_by_processor[r_id].bit_field_addresses[bf_id] =
                (address_t) &filter_region->filters[bf_id];
            log_info(
                "bitfield at region %d at index %d is at address %x",
                r_id, bf_id,
                bit_field_by_processor[r_id].bit_field_addresses[bf_id]);
        }
    }
    return bit_field_by_processor;
}

#endif  // __BIT_FIELD_READER_H__
#include "helpful_functions.h"

#ifndef __BIT_FIELD_READER_H__

//! \brief reads a bitfield and deduces how many bits are not set
//! \param[in] bit_field_struct: the location of the bitfield
//! \return how many redundant packets there are
uint32_t detect_redundant_packet_count(
    address_t bit_field_struct, address_t* user_register_content){
    log_debug("address's location is %x", bit_field_struct);
    log_debug(" key is %d", bit_field_struct[BIT_FIELD_BASE_KEY]);
    uint32_t n_filtered_packets = 0;
    uint32_t n_neurons = helpful_functions_locate_key_atom_map(
        bit_field_struct[BIT_FIELD_BASE_KEY], user_register_content);
    for (uint neuron_id = 0; neuron_id < n_neurons; neuron_id++){
        if (!bit_field_test(
                (bit_field_t) &bit_field_struct[START_OF_BIT_FIELD_DATA],
                 neuron_id)){
            n_filtered_packets += 1;
        }
    }
    log_debug("n filtered packets = %d", n_filtered_packets);
    return n_filtered_packets;
}

//! \brief reads in bitfields, makes a few maps, sorts into most priority.
//! \return bool that states if it succeeded or not.
_bit_field_by_processor_t* bit_field_reader_read_in_and_sort_bit_fields(
        int* n_bf_addresses, address_t* user_register_content){

    // count how many bitfields there are in total
    int position_in_region_data = 0;
    *n_bf_addresses = 0;
    int n_pairs_of_addresses = user_register_content[REGION_ADDRESSES][N_PAIRS];
    position_in_region_data = START_OF_ADDRESSES_DATA;
    log_debug("n pairs of addresses = %d", n_pairs_of_addresses);

    // malloc the bt fields by processor

    _bit_field_by_processor_t* bit_field_by_processor = MALLOC(
        n_pairs_of_addresses * sizeof(_bit_field_by_processor_t));
    if (bit_field_by_processor == NULL){
        log_error("failed to allocate memory for pairs, if it fails here. "
                  "might as well give up");
        return NULL;
    }

    // iterate through a processors bitfield region and get n bitfields
    for (int r_id = 0; r_id < n_pairs_of_addresses; r_id++){

        // track processor id
        bit_field_by_processor[r_id].processor_id =
            user_register_content[REGION_ADDRESSES][
                position_in_region_data + PROCESSOR_ID];
        log_debug(
            "bit_field_by_processor in region %d processor id = %d",
            r_id, bit_field_by_processor[r_id].processor_id);

        // locate data for malloc memory calcs
        address_t bit_field_address = (address_t) user_register_content[
            REGION_ADDRESSES][position_in_region_data + BITFIELD_REGION];
        log_debug("bit_field_region = %x", bit_field_address);
        position_in_region_data += ADDRESS_PAIR_LENGTH;

        uint32_t pos_in_bitfield_region = N_BIT_FIELDS;
        uint32_t core_n_bit_fields = bit_field_address[pos_in_bitfield_region];
        log_debug("there are %d core bit fields", core_n_bit_fields);
        pos_in_bitfield_region = START_OF_BIT_FIELD_TOP_DATA;
        *n_bf_addresses += core_n_bit_fields;

        // track lengths
        bit_field_by_processor[r_id].length_of_list = core_n_bit_fields;
        log_debug(
            "bit field by processor with region %d, has length of %d",
            r_id, core_n_bit_fields);

        // malloc for bitfield region addresses
        bit_field_by_processor[r_id].bit_field_addresses = MALLOC(
            core_n_bit_fields * sizeof(address_t));
        if (bit_field_by_processor[r_id].bit_field_addresses == NULL){
            log_error("failed to allocate memory for bitfield addresses for "
                      "region %d, might as well fail", r_id);
            return NULL;
        }

        // populate tables: 1 for addresses where each bitfield component starts
        //                  2 n redundant packets
        for (uint32_t bit_field_id = 0; bit_field_id < core_n_bit_fields;
                bit_field_id++){

            bit_field_by_processor[r_id].bit_field_addresses[bit_field_id] =
                (address_t) &bit_field_address[pos_in_bitfield_region];
            log_debug(
                "bitfield at region %d at index %d is at address %x",
                r_id, bit_field_id,
                bit_field_by_processor[r_id].bit_field_addresses[bit_field_id]);

            log_debug(
                "safety check. bit_field key is %d",
                bit_field_address[pos_in_bitfield_region + BIT_FIELD_BASE_KEY]);

            pos_in_bitfield_region +=
                START_OF_BIT_FIELD_DATA + bit_field_address[
                    pos_in_bitfield_region + BIT_FIELD_N_WORDS];
        }
    }
    return bit_field_by_processor;
}

#define __BIT_FIELD_READER_H__
#endif  // __BIT_FIELD_READER_H__
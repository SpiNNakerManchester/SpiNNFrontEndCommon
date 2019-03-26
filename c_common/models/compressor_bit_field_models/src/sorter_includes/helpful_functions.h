#ifndef __HELPFUL_FUNCTIONS_H__

#include "constants.h"

//! \brief finds the processor id of a given bitfield address (search though
//! the bit field by processor
//! \param[in] bit_field_address: the location in sdram where the bitfield
//! starts
//! \return the processor id that this bitfield address is associated.
uint32_t helpful_functions_locate_processor_id_from_bit_field_address(
        address_t bit_field_address, address_t* user_register_content,
        _bit_field_by_processor_t* bit_field_by_processor){

    uint32_t n_pairs = user_register_content[REGION_ADDRESSES][N_PAIRS];
    for (uint32_t bf_by_proc = 0; bf_by_proc < n_pairs; bf_by_proc++){
        _bit_field_by_processor_t element = bit_field_by_processor[bf_by_proc];
        for (uint32_t addr_index = 0; addr_index < element.length_of_list;
                addr_index ++){
            if (element.bit_field_addresses[addr_index] == bit_field_address){
                return element.processor_id;
            }
        }
    }
    log_error(
        "failed to find the bitfield address %x anywhere.", bit_field_address);
    vcpu_t *sark_virtual_processor_info = (vcpu_t*) SV_VCPU;
    sark_virtual_processor_info[spin1_get_core_id()].user1 = EXIT_FAIL;
    rt_error(RTE_SWERR);
    return 0;
}


//! \brief reads in the addresses region and from there reads in the key atom
// map and from there searches for a given key. when found, returns the n atoms
//! \param[in] key: the key to locate n atoms for
//! \return atom for the key
uint32_t helpful_functions_locate_key_atom_map(
        uint32_t key, address_t* user_register_content){
    // locate n address pairs
    uint32_t position_in_address_region = 0;
    uint32_t n_address_pairs =
        user_register_content[REGION_ADDRESSES][
            position_in_address_region + N_PAIRS];

    // cycle through key to atom regions to locate key
    position_in_address_region += START_OF_ADDRESSES_DATA;
    for (uint32_t r_id = 0; r_id < n_address_pairs; r_id++){
        // get key address region
        address_t key_atom_sdram_address =
            (address_t) user_register_content[REGION_ADDRESSES][
                position_in_address_region + KEY_TO_ATOM_REGION];

        // read how many keys atom pairs there are
        uint32_t position_ka_pair = 0;
        uint32_t n_key_atom_pairs = key_atom_sdram_address[position_ka_pair];
        position_ka_pair += 1;

        // cycle through keys in this region looking for the key find atoms of
        for (uint32_t key_atom_pair_id = 0; key_atom_pair_id <
                n_key_atom_pairs; key_atom_pair_id++){
            uint32_t key_to_check =
                key_atom_sdram_address[position_ka_pair + SRC_BASE_KEY];

            // if key is correct, return atoms
            if (key_to_check == key){
                if (key_atom_sdram_address[
                        position_ka_pair + SRC_N_ATOMS] > 256){
                    log_error("this makes no sense. for key %d", key);
                    rt_error(RTE_SWERR);
                }
                return key_atom_sdram_address[
                    position_ka_pair + SRC_N_ATOMS];
            }

            // move to next key pair
            position_ka_pair += LENGTH_OF_KEY_ATOM_PAIR;
        }

        // move to next key to atom sdram region
        position_in_address_region += ADDRESS_PAIR_LENGTH;
    }

    log_error("cannot find the key %d at all?! WTF", key);
    vcpu_t *sark_virtual_processor_info = (vcpu_t*) SV_VCPU;
    sark_virtual_processor_info[spin1_get_core_id()].user1 = EXIT_FAIL;
    spin1_exit(0);
    return 0;
}



//! \brief gets data about the bitfields being considered
//! \param[in/out] keys: the data holder to populate
//! \param[in] mid_point: the point in the sorted bit fields to look for
//! \return the number of unique keys founds.
uint32_t helpful_functions_population_master_pop_bit_field_ts(
        master_pop_bit_field_t * keys, uint32_t mid_point,
        address_t* sorted_bit_fields){

    uint32_t n_keys = 0;
    // check each bitfield to see if the key been recorded already
    for (uint32_t bit_field_index = 0; bit_field_index < mid_point;
            bit_field_index++){

        // safety feature
        if((uint32_t) sorted_bit_fields[bit_field_index] <= 0x60000000){
            log_error(
                "reading something off at address %x",
                sorted_bit_fields[bit_field_index]);
        }

        // get key
        uint32_t key = sorted_bit_fields[bit_field_index][BIT_FIELD_BASE_KEY];

        // start cycle looking for a clone
        uint32_t keys_index = 0;
        bool found = false;
        while(!found && keys_index < n_keys){
            if (keys[keys_index].master_pop_key == key){
                found = true;
                keys[keys_index].n_bitfields_with_key ++;
            }
            keys_index ++;
        }
        if (!found){
            keys[n_keys].master_pop_key = key;
            keys[n_keys].n_bitfields_with_key = 1;
            n_keys ++;
        }
    }
    return n_keys;
}

//! \brief clones the un compressed routing table, to another sdram location
//! \return: address of new clone, or null if it failed to clone
address_t helpful_functions_clone_un_compressed_routing_table(
        address_t* user_register_content){

    uncompressed_table_region_data_t* region =
        (uncompressed_table_region_data_t*) user_register_content[
            UNCOMP_ROUTER_TABLE];
    uint32_t sdram_used = routing_table_sdram_size_of_table(
        region->uncompressed_table.size);

    // allocate sdram for the clone
    address_t where_was_cloned = MALLOC_SDRAM(sdram_used);
    if (where_was_cloned == NULL){
        log_error("failed to allocate sdram for the cloned routing table for "
                  "uncompressed compression attempt");
        return NULL;
    }

    // copy over data
    sark_mem_cpy(
        where_was_cloned, &region->uncompressed_table.size, sdram_used);
    return where_was_cloned;
}

//secret stealth function. use sparingly.
#define NO_INLINE	__attribute__((noinline))
//NO_INLINE uint32_t do_the_thing(uint32_t foo, uint32_t bar) { .... }



#define __HELPFUL_FUNCTIONS_H__
#endif  // __HELPFUL_FUNCTIONS_H__
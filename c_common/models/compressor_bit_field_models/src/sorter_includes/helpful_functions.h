#ifndef __HELPFUL_FUNCTIONS_H__
#define __HELPFUL_FUNCTIONS_H__

#include "constants.h"
#include <filter_info.h>

//static inline void terminate(uint result_code) __attribute__((noreturn));
//! \brief stops a binary dead
//! \param[in] code to put in user 1
static inline void terminate(uint result_code) {
    vcpu_t *sark_virtual_processor_info = (vcpu_t *) SV_VCPU;
    uint core = spin1_get_core_id();

    sark_virtual_processor_info[core].user1 = result_code;
    spin1_pause();
    spin1_exit(0);
}

//! \brief finds the processor id of a given bitfield address (search though
//! the bit field by processor
//! \param[in] filter: the location in sdram where the bitfield starts
//! \param[in] region_addresses: the sdram where the data on regions is
//! \param[in] bit_field_by_processor:  map between processor and bitfields
//! \return the processor id that this bitfield address is associated.
static inline uint32_t helpful_functions_locate_proc_id_from_bf_address(
        filter_info_t filter, region_addresses_t *region_addresses,
        bit_field_by_processor_t* bit_field_by_processor){

    int n_pairs = region_addresses->n_pairs;
    for (int bf_by_proc = 0; bf_by_proc < n_pairs; bf_by_proc++) {
        bit_field_by_processor_t element = bit_field_by_processor[bf_by_proc];
        for (int addr_i = 0; addr_i < element.length_of_list; addr_i++) {
            if (element.bit_field_addresses[addr_i].data == filter.data) {
                return element.processor_id;
            }
        }
    }
    log_error("failed to find the bitfield address %x anywhere.", filter.data);
    terminate(EXIT_FAIL);
    return 0;
}


//! \brief reads in the addresses region and from there reads in the key atom
// map and from there searches for a given key. when found, returns the n atoms
//! \param[in] key: the key to locate n atoms for
//! \param[in] region_addresses: sdram data for where data regions are
//! \return atom for the key
static inline uint32_t helpful_functions_locate_key_atom_map(
        uint32_t key, region_addresses_t *region_addresses){
    // locate n address pairs
    uint32_t n_address_pairs = region_addresses->n_pairs;
    log_debug("key is %x", key);

    // cycle through key to atom regions to locate key
    for (uint32_t r_id = 0; r_id < n_address_pairs; r_id++){
        // get key address region
        key_atom_data_t *key_atom_map = region_addresses->pairs[r_id].key_atom;

        // read how many keys atom pairs there are
        uint32_t n_key_atom_pairs = key_atom_map->n_pairs;

        // cycle through keys in this region looking for the key find atoms of
        for (uint32_t i = 0; i < n_key_atom_pairs; i++) {
            // if key is correct, return atoms
            if (key_atom_map->pairs[i].key == key) {
                if (key_atom_map->pairs[i].n_atoms > 256) {
                    log_error("this makes no sense. for key %d", key);
                    rt_error(RTE_SWERR);
                }
                log_debug("n atoms is %d", key_atom_map->pairs[i].n_atoms);
                return key_atom_map->pairs[i].n_atoms;
            }
        }
    }

    log_error("cannot find the key %d at all?! WTF", key);
    terminate(EXIT_FAIL);
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
    // check each bitfield to see if the key been recorded already
    for (int bit_field_index = 0; bit_field_index < mid_point;
            bit_field_index++) {

        // get key
        filter_info_t* bf_pointer =
            sorted_bit_fields->bit_fields[bit_field_index];

        // start cycle looking for a clone
        bool found = false;
        for (int keys_index = 0; keys_index < n_keys; keys_index++) {
            if (keys[keys_index].master_pop_key ==  bf_pointer->key) {
                keys[keys_index].n_bitfields_with_key += 1;
                found = true;
            }
        }
        if (!found) {
            keys[n_keys].master_pop_key =  bf_pointer->key;
            keys[n_keys].n_bitfields_with_key = 1;
            n_keys++;
        }
    }
    return n_keys;
}

//! \brief frees sdram from the compressor core.
//! \param[in] comp_core_index: the compressor core index to clear sdram usage
//! from
//! \param[in] comp_cores_bf_tables: the map of what tables that core used
//! \return bool stating that it was successful in clearing sdram
bool helpful_functions_free_sdram_from_compression_attempt(
        int comp_core_index, comp_core_store_t* comp_cores_bf_tables){
    int elements = comp_cores_bf_tables[comp_core_index].n_elements;

    for (int core_bit_field_id = 0; core_bit_field_id < elements;
            core_bit_field_id++) {
        FREE(comp_cores_bf_tables[comp_core_index].elements[core_bit_field_id]);
    }

    // only try freeing if its not been freed already. (safety feature)
    if (comp_cores_bf_tables[comp_core_index].elements != NULL){
        FREE(comp_cores_bf_tables[comp_core_index].elements);
    }

    comp_cores_bf_tables[comp_core_index].elements = NULL;
    comp_cores_bf_tables[comp_core_index].n_elements = 0;
    comp_cores_bf_tables[comp_core_index].n_bit_fields = 0;

    return true;
}

//! \brief clones the un compressed routing table, to another sdram location
//! \param[in] uncompressed_router_table: sdram location for uncompressed table
//! \return: address of new clone, or null if it failed to clone
address_t helpful_functions_clone_un_compressed_routing_table(
        uncompressed_table_region_data_t *uncompressed_router_table){

    uint32_t sdram_used = routing_table_sdram_size_of_table(
        uncompressed_router_table->uncompressed_table.size);

    // allocate sdram for the clone
    address_t where_was_cloned = MALLOC_SDRAM(sdram_used);
    if (where_was_cloned == NULL) {
        log_error("failed to allocate sdram for the cloned routing table for "
                  "uncompressed compression attempt");
        return NULL;
    }

    // copy over data
    sark_mem_cpy(
        where_was_cloned, &uncompressed_router_table->uncompressed_table.size,
        sdram_used);
    return where_was_cloned;
}

//! \brief secret stealth function for saving ITCM. use sparingly.
#define NO_INLINE	__attribute__((noinline))
//NO_INLINE uint32_t do_the_thing(uint32_t foo, uint32_t bar) { .... }

#endif  // __HELPFUL_FUNCTIONS_H__

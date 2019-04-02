#include "helpful_functions.h"
#include "constants.h"
#include "../common/routing_table.h"

#ifndef __BIT_FIELD_TABLE_GENERATOR_H__


//! locates a entry within a routing table, extracts the data, then removes
//! it from the table, updating locations and sizes
//! \param[in] uncompressed_table_address:
//! \param[in] master_pop_key: the key to locate the entry for
//! \param[in/out] entry_to_store: entry to store the found entry in
//! \return: None
void extract_and_remove_entry_from_table(
        address_t uncompressed_table_address, uint32_t master_pop_key,
        entry_t* entry_to_store){

    // cas the address to the struct for easier work
    table_t* table_cast = (table_t*) uncompressed_table_address;

    // flag for when found. no point starting move till after
    bool found = false;

    // iterate through all entries
    for(int entry_id=0; entry_id < table_cast->size; entry_id++){

        // if key matches, sort entry (assumes only 1 entry, otherwise boomed)
        if (table_cast->entries[entry_id].key_mask.key == master_pop_key){
            entry_to_store->route = table_cast->entries[entry_id].route;
            entry_to_store->source = table_cast->entries[entry_id].source;
            entry_to_store->key_mask.key =
                table_cast->entries[entry_id].key_mask.key;
            entry_to_store->key_mask.mask =
                table_cast->entries[entry_id].key_mask.mask;
            found = true;
        }
        else{  // not found entry here. check if already found
            if (found){  // if found, move entry up one. to sort out memory
                table_cast->entries[entry_id - 1].route =
                    table_cast->entries[entry_id].route;
                table_cast->entries[entry_id - 1].source =
                    table_cast->entries[entry_id].source;
                table_cast->entries[entry_id - 1].key_mask.key =
                    table_cast->entries[entry_id].key_mask.key;
                table_cast->entries[entry_id - 1].key_mask.mask =
                    table_cast->entries[entry_id].key_mask.mask;
            }
        }
    }

    // update size by the removal of 1 entry
    table_cast->size -= 1;
}


//! \brief sets a bitfield so that processors within the original route which
//! are not filterable, are added to the new route.
//! \param[in] processors: bitfield processors new route
//! \param[in] original_entry: the original router entry
//! \param[in] bit_field_processors: the processors which are filterable.
//! \param[in] n_bit_fields: the number of bitfields being assessed
void set_new_route_with_fixed_processors(
        bit_field_t processors, entry_t* original_entry,
        uint32_t* bit_field_processors, uint32_t n_bit_fields){

    // cast original entry route to a bitfield for ease of use
    bit_field_t original_route = (bit_field_t) &original_entry->route;

    // only set entries in the new route from the old route if the core has not
    // got a bitfield associated with it.
    for (uint32_t processor_id = 0; processor_id < MAX_PROCESSORS;
            processor_id++){
        // original route has this processor
        if (bit_field_test(
                original_route,
                (MAX_PROCESSORS - processor_id) + MAX_LINKS_PER_ROUTER)){

            // search through the bitfield processors to see if it exists
            bool found = false;
            for (uint32_t bit_field_index = 0; bit_field_index < n_bit_fields;
                    bit_field_index++){
                if(bit_field_processors[bit_field_index] == processor_id){
                    found = true;
                }
            }

            // if not a bitfield core, add to new route, as cant filter this
            // away.
            if (!found){
                bit_field_set(
                    processors,
                    (MAX_PROCESSORS - processor_id) + MAX_LINKS_PER_ROUTER);
            }
        }
    }
}

//! \brief generates the router table entries for the original entry in the
//! original routing table, where the new entries are atom level entries based
//! off the bitfields.
//! \param[in] addresses: the addresses in sdram where the bitfields exist
//! \param[in] n_bit_fields_for_key: the number of bitfields we are considering
//! here
//! \param[in] original_entry: the original routing table entry that is being
//! expanded by the bitfields
//! \param[in] rt_address_ptr: the sdram address where the new atom level table
//! will be put once completed.
//! \return bool that states that if the atom routing table was generated or not
bool generate_entries_from_bitfields(
        address_t* addresses, int n_bit_fields_for_key, entry_t* original_entry,
        address_t* rt_address_ptr, address_t* user_register_content,
        _bit_field_by_processor_t* bit_field_by_processor){

    // get processors by bitfield
    uint32_t * bit_field_processors = MALLOC(
        n_bit_fields_for_key * sizeof(uint32_t));
    if (bit_field_processors == NULL){
        log_error("failed to allocate memory for bitfield processors");
        return false;
    }

    // get the processor ids
    for(int bf_proc = 0; bf_proc < n_bit_fields_for_key; bf_proc++){
        bit_field_processors[bf_proc] =
            helpful_functions_locate_processor_id_from_bit_field_address(
                addresses[bf_proc], user_register_content,
                bit_field_by_processor);
    }

    // create sdram holder for the table we're going to generate
    log_debug("looking for atoms");
    uint32_t n_atoms = helpful_functions_locate_key_atom_map(
        original_entry->key_mask.key, user_register_content);
    *rt_address_ptr = MALLOC_SDRAM(
        (uint) routing_table_sdram_size_of_table(n_atoms));

    if (*rt_address_ptr == NULL){
        FREE(bit_field_processors);
        log_error("can not allocate sdram for the sdram routing table");
        return false;
    }

    // update the tracker for the rt address
    table_t* sdram_table = (table_t*) *rt_address_ptr;

    // update the size of the router table, as we know there will be one entry
    // per atom
    sdram_table->size = n_atoms;

    // set up the new route process
    uint32_t size = get_bit_field_size(MAX_PROCESSORS + MAX_LINKS_PER_ROUTER);
    bit_field_t processors =
        bit_field_alloc(MAX_PROCESSORS + MAX_LINKS_PER_ROUTER);

    if (processors == NULL){
        log_error(
            "could not allocate memory for the processor tracker when "
            "making entries from bitfields");
        FREE(bit_field_processors);
        FREE(sdram_table);
        return false;
    }

    // iterate though each atom and set the route when needed
    for (uint32_t atom = 0; atom < n_atoms; atom++){

        // wipe history
        clear_bit_field(processors, size);

        // update the processors so that the fixed none filtered processors
        // are set
        set_new_route_with_fixed_processors(
            processors, original_entry, bit_field_processors,
            n_bit_fields_for_key);

        // iterate through the bitfield cores and see if they need this atom
        for (int bf_index = 0; bf_index < n_bit_fields_for_key;
                bf_index++){
            bool needed = bit_field_test(
                (bit_field_t) &addresses[bf_index][START_OF_BIT_FIELD_DATA],
                atom);
            if (needed){
                bit_field_set(processors, bit_field_processors[bf_index]);
            }
        }

        // get the entry and fill in details.
        entry_t* new_entry = &sdram_table->entries[atom];
        new_entry->key_mask.key = original_entry->key_mask.key + atom;
        new_entry->key_mask.mask = NEURON_LEVEL_MASK;
        new_entry->source = original_entry->source;
        sark_mem_cpy(
            &new_entry->route, &original_entry->route, sizeof(uint32_t));
    }

    FREE(bit_field_processors);
    FREE(processors);
    // do not remove sdram store, as that's critical to how this stuff works
    return true;

}


//! generates the routing table entries from this set of bitfields
//! \param[in] master_pop_key: the key to locate the bitfields for
//! \param[in] uncompressed_table: the location for the uncompressed table
//! \param[in] n_bfs_for_key: how many bitfields are needed for this key
//! \param[in] mid_point: the point where the search though sorted bit fields
//! ends.
//! \param[in] rt_address_ptr: the location in sdram to store the routing table
//! generated from the bitfields and original entry.
//! \return bool saying if it was successful or not
bool generate_rt_from_bit_field(
        uint32_t master_pop_key, address_t uncompressed_table,
        int n_bfs_for_key, uint32_t mid_point, address_t* rt_address_ptr,
        address_t* user_register_content,
        _bit_field_by_processor_t* bit_field_by_processor,
        sorted_bit_fields_t* sorted_bit_fields){

    // reduce future iterations, by finding the exact bitfield addresses
    address_t* addresses = MALLOC(n_bfs_for_key * sizeof(address_t));

    uint32_t index = 0;
    for (uint32_t bit_field_index = 0; bit_field_index < mid_point;
            bit_field_index++){
        if (sorted_bit_fields->bit_fields[bit_field_index][
                BIT_FIELD_BASE_KEY] == master_pop_key){
            addresses[index] = sorted_bit_fields->bit_fields[bit_field_index];
            index += 1;
        }
    }

    // extract original routing entry from uncompressed table
    entry_t* original_entry = MALLOC(sizeof(entry_t));
    if (original_entry == NULL){
        log_error("can not allocate memory for the original entry.");
        FREE(addresses);
        return false;
    }

    extract_and_remove_entry_from_table(
        uncompressed_table, master_pop_key, original_entry);

    // create table entries with bitfields
    bool success = generate_entries_from_bitfields(
        addresses, n_bfs_for_key, original_entry, rt_address_ptr,
        user_register_content, bit_field_by_processor);
    if (!success){
        log_error(
            "can not create entries for key %d with %x bitfields.",
            master_pop_key, n_bfs_for_key);
        FREE(original_entry);
        FREE(addresses);
        return false;
    }

    FREE(original_entry);
    FREE(addresses);
    return true;
}


//! takes a midpoint and reads the sorted bitfields up to that point generating
//! bitfield routing tables and loading them into sdram for transfer to a
//! compressor core
//! \param[in] mid_point: where in the sorted bitfields to go to
//! \param[out] n_rt_addresses: how many addresses are needed for the
//! tables
//! \return bool saying if it successfully built them into sdram
address_t* bit_field_table_generator_create_bit_field_router_tables(
        uint32_t mid_point, int* n_rt_addresses,
        address_t* user_register_content,
        _bit_field_by_processor_t* bit_field_by_processor,
        sorted_bit_fields_t* sorted_bit_fields){

    // get n keys that exist
    master_pop_bit_field_t * keys = MALLOC(
        mid_point * sizeof(master_pop_bit_field_t));
    if (keys == NULL){
        log_error("cannot allocate memory for keys");
        return NULL;
    }

    // populate the master pop bit field
    *n_rt_addresses = helpful_functions_population_master_pop_bit_field_ts(
        keys, mid_point, sorted_bit_fields);
    log_info("n rts is %d", *n_rt_addresses);

    // add the uncompressed table, for allowing the bitfield table generator to
    // edit accordingly.
    *n_rt_addresses += 1;
    address_t uncompressed_table =
        helpful_functions_clone_un_compressed_routing_table(
            user_register_content);
    if (uncompressed_table == NULL){
        log_error(
            "failed to clone uncompressed tables for attempt %d", mid_point);
        FREE(keys);
        return NULL;
    }

    log_info("looking for %d bytes", *n_rt_addresses * sizeof(address_t));
    address_t* bit_field_routing_tables = MALLOC(
        *n_rt_addresses * sizeof(address_t));
    if (bit_field_routing_tables == NULL){
        log_info("failed to allocate memory for bitfield routing tables");
        FREE(keys);
        FREE(uncompressed_table);
        return NULL;
    }

    // add clone to front of list, to ensure its easily accessible (plus its
    // part of the expected logic)

    bit_field_routing_tables[0] = uncompressed_table;

    // iterate through the keys, accumulating bitfields and turn into routing
    // table entries.
    for(int key_index = 1; key_index < *n_rt_addresses; key_index++){
        // holder for the rt address
        address_t rt_address;

        // create the routing table from the bitfield
        bool success = generate_rt_from_bit_field(
            keys[key_index -1].master_pop_key, uncompressed_table,
            keys[key_index - 1].n_bitfields_with_key, mid_point, &rt_address,
            user_register_content, bit_field_by_processor, sorted_bit_fields);

        // if failed, free stuff and tell above it failed
        if (!success){
            log_info("failed to allocate memory for rt table");
            FREE(keys);
            FREE(bit_field_routing_tables);
            FREE(uncompressed_table);
            return NULL;
        }

        // store the rt address for this master pop key
        bit_field_routing_tables[key_index] = rt_address;
    }

    // free stuff
    FREE(keys);
    return bit_field_routing_tables;
}


#define __BIT_FIELD_TABLE_GENERATOR_H__
#endif  // __BIT_FIELD_TABLE_GENERATOR_H__
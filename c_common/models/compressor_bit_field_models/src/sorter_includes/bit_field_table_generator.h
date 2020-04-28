/*
 * Copyright (c) 2019-2020 The University of Manchester
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the free Software Foundation, either version 3 of the License, or
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

#ifndef __BIT_FIELD_TABLE_GENERATOR_H__
#define __BIT_FIELD_TABLE_GENERATOR_H__

#include "helpful_functions.h"
#include "../common/constants.h"
#include "../common/routing_table.h"
#include <filter_info.h>
#include <malloc_extras.h>

//! max number of links on a router
#define MAX_LINKS_PER_ROUTER 6

//! neuron level mask
#define NEURON_LEVEL_MASK 0xFFFFFFFF


//! locates a entry within a routing table, extracts the data, then removes
//! it from the table, updating locations and sizes
//! \param[in] uncompressed_table_address:
//! \param[in] master_pop_key: the key to locate the entry for
//! \param[in/out] entry_to_store: entry to store the found entry in
//! \return: None
static inline void extract_and_remove_entry_from_table(
        table_t* table, uint32_t master_pop_key,
        entry_t *entry_to_store) {

    // flag for when found. no point starting move till after
    bool found = false;

    // iterate through all entries
    for (uint32_t entry_id=0; entry_id < table->size; entry_id++) {

        // if key matches, sort entry (assumes only 1 entry, otherwise boomed)
        if (table->entries[entry_id].key_mask.key == master_pop_key) {
            entry_to_store->route = table->entries[entry_id].route;
            entry_to_store->source = table->entries[entry_id].source;
            entry_to_store->key_mask.key =
                table->entries[entry_id].key_mask.key;
            entry_to_store->key_mask.mask =
                table->entries[entry_id].key_mask.mask;
            found = true;
        } else {  // not found entry here. check if already found
            if (found) {  // if found, move entry up one. to sort out memory
                table->entries[entry_id - 1].route =
                    table->entries[entry_id].route;
                table->entries[entry_id - 1].source =
                    table->entries[entry_id].source;
                table->entries[entry_id - 1].key_mask.key =
                    table->entries[entry_id].key_mask.key;
                table->entries[entry_id - 1].key_mask.mask =
                    table->entries[entry_id].key_mask.mask;
            }
        }
    }

    // update size by the removal of 1 entry
    table->size -= 1;
}


//! \brief sets a bitfield so that processors within the original route which
//! are not filterable, are added to the new route.
//! \param[in] processors: bitfield processors new route
//! \param[in] original_entry: the original router entry
//! \param[in] bit_field_processors: the processors which are filterable.
//! \param[in] n_bit_fields: the number of bitfields being assessed
static inline void set_new_route_with_fixed_processors(
        bit_field_t processors, entry_t original_entry,
        uint32_t *bit_field_processors, uint32_t n_bit_fields) {

    // cast original entry route to a bitfield for ease of use
    bit_field_t original_route = (bit_field_t) &original_entry.route;

    // copy over link ids as they not debatable
    for (int link_id = 0; link_id < MAX_LINKS_PER_ROUTER; link_id++){
        if (bit_field_test(original_route, link_id)){
            bit_field_set(processors, link_id);
        }
    }

    // only set entries in the new route from the old route if the processor
    // has not got a bitfield associated with it.
    for (uint32_t processor_id = 0; processor_id < MAX_PROCESSORS;
            processor_id++) {

        // original route has this processor
        if (bit_field_test(
                original_route, MAX_LINKS_PER_ROUTER + processor_id)) {

            log_debug(
                "proc %d is set on bit %d",
                processor_id, MAX_LINKS_PER_ROUTER + processor_id);
            // search through the bitfield processors to see if it exists
            bool found = false;
            for (uint32_t bf_i = 0; bf_i < n_bit_fields; bf_i++) {
                if (bit_field_processors[bf_i] == processor_id) {
                    log_debug("found proc %d", processor_id);
                    found = true;
                    break;
                }
            }

            // if not a bitfield processor, add to new route, as cant filter
            // this away.
            if (!found) {
                log_debug("never found proc %d", processor_id);
                bit_field_set(processors, MAX_LINKS_PER_ROUTER + processor_id);
            }
        }
        else{
            log_debug(
                "proc %d not set on bit %d",
                processor_id, MAX_LINKS_PER_ROUTER + processor_id);
        }
    }
}

//! \brief generates the router table entries for the original entry in the
//! original routing table, where the new entries are atom level entries based
//! off the bitfields.
//! \param[in] filters: pointer to the list of bitfields
//! \param[in] bit_field_by_processor: the map between processor to bitfields.
//! \param[in] region_addresses: the addresses in sdram where the bitfields
//! exist
//! \param[in] n_bit_fields_for_key: the number of bitfields we are considering
//! here
//! \param[in] original_entry: the original routing table entry that is being
//! expanded by the bitfields
//! \param[in] sdram_table: the sdram address where the new atom level table
//! will be put once completed.

//! \return bool that states that if the atom routing table was generated or not
static inline bool generate_entries_from_bitfields(
        filter_info_t **filters, int n_bit_fields_for_key,
        entry_t original_entry, table_t **sdram_table,
        region_addresses_t *region_addresses,
        bit_field_by_processor_t* bit_field_by_processor) {
    // get processors by bitfield
    log_debug(
        "mallocing %d bytes for bit_field_processors",
        n_bit_fields_for_key * sizeof(uint32_t));
    uint32_t *bit_field_processors =
        MALLOC(n_bit_fields_for_key * sizeof(uint32_t));
    if (bit_field_processors == NULL) {
        log_error(
            "failed to allocate memory for bitfield processors on %d "
            "bitfields", n_bit_fields_for_key);
        return false;
    }

    // get the processor ids
    for (int bf_proc = 0; bf_proc < n_bit_fields_for_key; bf_proc++) {
        bit_field_processors[bf_proc] =
            helpful_functions_locate_proc_id_from_bf_address(
                *filters[bf_proc], region_addresses,
                bit_field_by_processor);
    }

    // create sdram holder for the table we're going to generate
    log_debug("looking for atoms");
    uint32_t n_atoms = helpful_functions_locate_key_atom_map(
        original_entry.key_mask.key, region_addresses);

    *sdram_table = MALLOC_SDRAM(routing_table_sdram_size_of_table(n_atoms));
    log_debug("%x for sdram table", sdram_table);

    if (*sdram_table == NULL) {
        FREE(bit_field_processors);
        log_error("can not allocate sdram for the sdram routing table");
        return false;
    }

    // update the size of the router table, as we know there will be one entry
    // per atom
    table_t* table = *sdram_table;
    table->size = n_atoms;
    log_debug(" n atoms is %d, size %d", n_atoms, table->size);

    // set up the new route process
    uint32_t size = get_bit_field_size(MAX_PROCESSORS + MAX_LINKS_PER_ROUTER);
    bit_field_t processors = (bit_field_t) MALLOC(size * sizeof(bit_field_t));
    if (processors == NULL) {
        log_error(
            "could not allocate memory for the processor tracker when "
            "making entries from bitfields");
        FREE(bit_field_processors);
        FREE(*sdram_table);
        return false;
    }

    // ensure its clear
    clear_bit_field(processors, size);

    // create memory holder for atom based route
    bit_field_t atom_processors = (bit_field_t) MALLOC(size * sizeof(bit_field_t));
    if (atom_processors == NULL) {
        log_error(
            "could not allocate memory for the atom processor tracker when "
            "making entries from bitfields");
        FREE(bit_field_processors);
        FREE(sdram_table);
        FREE(processors);
        return false;
    }

    // update the processors so that the fixed none filtered processors
    // are set
    set_new_route_with_fixed_processors(
        processors, original_entry, bit_field_processors,
        n_bit_fields_for_key);

    // iterate though each atom and set the route when needed
    for (uint32_t atom = 0; atom < n_atoms; atom++) {

        // reset with filtered routes.
        spin1_memcpy(
            atom_processors, processors, size * WORD_TO_BYTE_MULTIPLIER);

        // iterate through the bitfield processors and see if they need this
        // atom
        for (int bf_index = 0; bf_index < n_bit_fields_for_key; bf_index++) {
            log_debug("data address is %x", filters[bf_index]->data);
            if (bit_field_test(filters[bf_index]->data, atom)){
                log_debug(
                    "setting for atom %d from bitfield index %d so proc %d",
                    atom, bf_index, bit_field_processors[bf_index]);
                bit_field_set(
                    atom_processors,
                    MAX_LINKS_PER_ROUTER + bit_field_processors[bf_index]);
            }
        }

        // get the entry and fill in details.
        entry_t *new_entry = &table->entries[atom];
        new_entry->key_mask.key = original_entry.key_mask.key + atom;
        new_entry->key_mask.mask = NEURON_LEVEL_MASK;
        new_entry->source = original_entry.source;
        spin1_memcpy(
            &new_entry->route, atom_processors,
            size * WORD_TO_BYTE_MULTIPLIER);
        log_debug(
            "key is %x route in entry %d is %x",
             table->entries[atom].key_mask.key, atom,
             table->entries[atom].route);

    }

    // do not remove sdram store, as that's critical to how this stuff works
    FREE(bit_field_processors);
    FREE(processors);
    FREE(atom_processors);
    return true;

}


//! generates the routing table entries from this set of bitfields
//! \param[in] master_pop_key: the key to locate the bitfields for
//! \param[in] uncompressed_table: the location for the uncompressed table
//! \param[in] n_bfs_for_key: how many bitfields are needed for this key
//! \param[in] mid_point: the point where the search though sorted bit fields
//! ends.
//! \param[in] sdram_table: the location in sdram to store the routing table
//! generated from the bitfields and original entry.
//! \param[in] region_addresses: the sdram store for data regions
//! \param[in] bit_field_by_processor: the map between processor and bitfields
//! \param[in] sorted_bit_fields: the pointer to the sorted bit field struct.
//! \return bool saying if it was successful or not
static inline bool generate_rt_from_bit_field(
        uint32_t master_pop_key, table_t* uncompressed_table,
        int n_bfs_for_key, int mid_point, table_t **sdram_table,
        region_addresses_t *region_addresses,
        bit_field_by_processor_t* bit_field_by_processor,
        sorted_bit_fields_t* sorted_bit_fields){

    log_debug(
        "generate_rt_from_bit_field key %u n_bfs_for_key %u",
        master_pop_key, n_bfs_for_key);
    // reduce future iterations, by finding the exact bitfield filter
    filter_info_t **filters = MALLOC(n_bfs_for_key * sizeof(filter_info_t*));
    if (filters == NULL) {
        return false;
    }

    int index = 0;
    for (int bit_field_index = 0; bit_field_index < mid_point;
            bit_field_index++) {
        filter_info_t* bf_pointer =
            sorted_bit_fields->bit_fields[bit_field_index];
        if (bf_pointer->key == master_pop_key){
            filters[index] = sorted_bit_fields->bit_fields[bit_field_index];
            log_debug(
                "filter in index %d is at address %x",
                index, filters[index]->data);
            index += 1;
        }
    }

    // extract original routing entry from uncompressed table
    entry_t original_entry;

    // init the original entry
    original_entry.source = 0;
    original_entry.route = 0;
    original_entry.key_mask.key = 0;
    original_entry.key_mask.mask = 0;

    extract_and_remove_entry_from_table(
        uncompressed_table, master_pop_key, &original_entry);

    // create table entries with bitfields
    bool success = generate_entries_from_bitfields(
        filters, n_bfs_for_key, original_entry, sdram_table,
        region_addresses, bit_field_by_processor);

    table_t *table = *sdram_table;
    log_debug("sdram table n atoms = %d", table->size);
    if (!success){
        log_error(
            "can not create entries for key %d with %d bitfields.",
            master_pop_key, n_bfs_for_key);
        FREE(filters);
        return false;
    }

    FREE(filters);
    return true;
}

int count_unigue_keys(sorted_bit_fields_t *sorted_bit_fields, int midpoint) {
    filter_info_t** bit_fields = sorted_bit_fields->bit_fields;
    int* sort_order =  sorted_bit_fields->sort_order;
    int n_bit_fields = sorted_bit_fields->n_bit_fields;
    int count = 0;
    uint32_t last_key = -1;
    for (int i = 0; i < n_bit_fields; i++) {
        if ((sort_order[i] < midpoint) && (last_key != bit_fields[i]->key)) {
            count++;
            last_key = bit_fields[i]->key;
        }
    }
    return count;
}

//! Generates a routing tables by merging an entry and a list of bitfields
//! by processor
//! \param[in] original_entry: The Routing Table entry in the original table
//! \param[in] filters: List of the bitfields to me merged in
//! \param[in] bit_field_processor: List of the processors for each bitfield
//! \param[in] bf_found: Number of bitfields found.
table_t* generate_table(
    entry_t original_entry, filter_info_t** filters,
    uint32_t* bit_field_processors, int bf_found) {

    uint32_t n_atoms = filters[0]->n_atoms;

    // create sdram holder for the table we're going to generate
    table_t* sdram_table = MALLOC_SDRAM(routing_table_sdram_size_of_table(n_atoms));
    log_debug("%x for sdram table", sdram_table);
    if (sdram_table == NULL) {
        log_error("can not allocate sdram for the sdram routing table");
        return false;
    }

    // update the size of the router table, as we know there will be one entry
    // per atom
    sdram_table->size = n_atoms;
    log_debug(" n atoms is %d, size %d", n_atoms, sdram_table->size);

    uint32_t stripped_route = original_entry.route;
    bit_field_t stripped_bf = &stripped_route;
    for (int i =0; i < bf_found; i++) {
        if (!bit_field_test(
                stripped_bf, bit_field_processors[i] + MAX_LINKS_PER_ROUTER)) {
            log_error("WHAT THE FUCK!");
        }
        bit_field_clear(
            stripped_bf, bit_field_processors[i] + MAX_LINKS_PER_ROUTER);
    }

    // iterate though each atom and set the route when needed
    for (uint32_t atom = 0; atom < n_atoms; atom++) {
        // Assigning to a uint32 creates a copy
        uint32_t new_route = stripped_route;
        bit_field_t new_bf = &new_route;

        // iterate through the bitfield processor's and see if they need this
        // atom
        for (int bf_index = 0; bf_index < bf_found; bf_index++) {
            log_debug("data address is %x", filters[bf_index]->data);
            if (bit_field_test(filters[bf_index]->data, atom)){
                log_debug(
                    "setting for atom %d from bitfield index %d so proc %d",
                    atom, bf_index, bit_field_processors[bf_index]);
                bit_field_set(
                    new_bf,
                    MAX_LINKS_PER_ROUTER + bit_field_processors[bf_index]);
            }
        }

        // get the entry and fill in details.
        entry_t *new_entry = &sdram_table->entries[atom];
        new_entry->key_mask.key = original_entry.key_mask.key + atom;
        new_entry->key_mask.mask = NEURON_LEVEL_MASK;
        new_entry->source = original_entry.source;
        new_entry->route = new_route;
        log_debug(
            "key is %x route in entry %d is %x",
             sdram_table->entries[atom].key_mask.key, atom,
             sdram_table->entries[atom].route);
    }

    // do not remove sdram store, as that's critical to how this stuff works
    return sdram_table;

}

void insert_entry(entry_t original_entry, table_t* no_bitfield_table) {
    entry_t *new_entry =
       &no_bitfield_table->entries[no_bitfield_table->size];
    new_entry->key_mask.key = original_entry.key_mask.key;
    new_entry->key_mask.mask = original_entry.key_mask.mask;
    new_entry->source = original_entry.source;
    new_entry->route = original_entry.route;
    no_bitfield_table->size ++;
}

//! takes a midpoint and reads the sorted bitfields up to that point generating
//! bitfield routing tables and loading them into sdram for transfer to a
//! compressor processor
//! \param[in] mid_point: where in the sorted bitfields to go to
//! \param[out] n_rt_addresses: how many addresses are needed for the
//! tables
//! \param[in] uncompressed_router_table: the uncompressed router table
//! \param[in] sorted_bit_fields: the pointer to the sorted bit field struct.
//! \return bool saying if it successfully built them into sdram
static inline table_t** bit_field_table_generator_create_bit_field_router_tables(
        int mid_point, int *n_rt_addresses,
        uncompressed_table_region_data_t *uncompressed_router_table,
        sorted_bit_fields_t *sorted_bit_fields){

    malloc_extras_check_all_marked(7001);
    // semantic sugar to avoid referencing
    filter_info_t** bit_fields = sorted_bit_fields->bit_fields;
    int* processor_ids = sorted_bit_fields->processor_ids;
    int* sort_order =  sorted_bit_fields->sort_order;
    entry_t* original = uncompressed_router_table->uncompressed_table.entries;
    uint32_t original_size =  uncompressed_router_table->uncompressed_table.size;
    int n_bit_fields = sorted_bit_fields->n_bit_fields;

    *n_rt_addresses = count_unigue_keys(sorted_bit_fields, mid_point);
    log_info("n_rt_addresses %u", *n_rt_addresses);
    // add the uncompressed table, for allowing the bitfield table generator to
    // edit accordingly.
    *n_rt_addresses += 1;

    table_t* no_bitfield_table = MALLOC_SDRAM(
        routing_table_sdram_size_of_table(original_size));
    if (no_bitfield_table == NULL) {
        log_error(
            "failed to create no_bitfield_table for attempt %d", mid_point);
        return NULL;
    }
    no_bitfield_table->size = 0;

    log_debug(
        "looking for %d bytes from %d tables",
        *n_rt_addresses * sizeof(table_t*), *n_rt_addresses);
    table_t** bit_field_routing_tables =
        MALLOC_SDRAM(*n_rt_addresses * sizeof(table_t*));
    if (bit_field_routing_tables == NULL) {
        log_error("failed to allocate memory for bitfield routing tables");
        FREE(no_bitfield_table);
        return NULL;
    }

    bit_field_routing_tables[*n_rt_addresses - 1] = no_bitfield_table;
    malloc_extras_check_all_marked(7002);

    filter_info_t* filters[MAX_PROCESSORS];
    uint32_t bit_field_processors[MAX_PROCESSORS];
    int bf_i = 0;
    int key_index =0;
    for (uint32_t rt_i = 0; rt_i < original_size; rt_i++) {
        uint32_t key = original[rt_i].key_mask.key;
        int bf_found = 0;
        while ((bf_i < n_bit_fields) && (bit_fields[bf_i]->key == key)) {
            if (sort_order[bf_i] < mid_point) {
                filters[bf_found] = bit_fields[bf_i];
                bit_field_processors[bf_found] = processor_ids[bf_i];
                bf_found++;
            }
            bf_i++;
        }
        if (bf_found > 0){
            table_t *table = generate_table(
                original[rt_i], filters, bit_field_processors, bf_found);
            bit_field_routing_tables[key_index] = table;
            key_index++;
        } else {
            insert_entry(original[rt_i], no_bitfield_table);
        }
    }
    malloc_extras_check_all_marked(7004);
    return bit_field_routing_tables;
}

void log_table(table_t* table){
   entry_t* entries = table->entries;
   for (uint32_t i = 0; i < table->size; i++){
        log_info("i %u, key %u, mask %u, route %u, source %u",
        i, entries[i].key_mask.key, entries[i].key_mask.mask,
        entries[i].route, entries[i].source);
   }
}


//! \brief sorts a given table so that the entries in the table are by key
//! value.
//! \param[in] table: the table to sort.
void sort_table_by_key(table_t* table) {
    uint32_t size = table->size;
    entry_t* entries = table->entries;
    for (uint32_t i = 0; i < size - 1; i++){
        for (uint32_t j = i + 1; j < size; j++) {
            if (entries[i].key_mask.key > entries[j].key_mask.key) {
                uint32_t temp = entries[i].key_mask.key;
                entries[i].key_mask.key = entries[j].key_mask.key;
                entries[j].key_mask.key = temp;
                temp = entries[i].key_mask.mask;
                entries[i].key_mask.mask = entries[j].key_mask.mask;
                entries[j].key_mask.mask = temp;
                temp = entries[i].route;
                entries[i].route = entries[j].route;
                entries[j].route = temp;
                temp = entries[i].source;
                entries[i].source = entries[j].source;
                entries[j].source = temp;
            }
        }
    }
}

void sort_table_by_route(table_t* table) {
    uint32_t size = table->size;
    entry_t* entries = table->entries;
    for (uint32_t i = 0; i < size - 1; i++){
        for (uint32_t j = i + 1; j < size; j++) {
            if (entries[i].route > entries[j].route) {
                uint32_t temp = entries[i].key_mask.key;
                entries[i].key_mask.key = entries[j].key_mask.key;
                entries[j].key_mask.key = temp;
                temp = entries[i].key_mask.mask;
                entries[i].key_mask.mask = entries[j].key_mask.mask;
                entries[j].key_mask.mask = temp;
                temp = entries[i].route;
                entries[i].route = entries[j].route;
                entries[j].route = temp;
                temp = entries[i].source;
                entries[i].source = entries[j].source;
                entries[j].source = temp;
            }
        }
    }
}

#endif  // __BIT_FIELD_TABLE_GENERATOR_H__

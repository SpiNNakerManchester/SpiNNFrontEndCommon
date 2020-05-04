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

//! brief counts the number of unigue keys in the list up to the midpoint
//! Works on the assumption that the list is grouped (sorted) by key
//! \param[in] sorted_bit_fields: the pointer to the sorted bit field struct.
//! \param[in] mid_point: where in the sorted bitfields to go to
//! \return: the number of unique keys in the sorted list between 0 and
//! midpoint.
int count_unique_keys(sorted_bit_fields_t *sorted_bit_fields, int midpoint) {
    // Semantic sugar to avoid extra lookup all the time
    filter_info_t** bit_fields = sorted_bit_fields->bit_fields;
    int* sort_order =  sorted_bit_fields->sort_order;
    int n_bit_fields = sorted_bit_fields->n_bit_fields;

    // iterate over entire sorted list, looking for sorted index's lower than
    // given midpoint and count key changes. works as bitfields ordered by key.
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
//! \return bit_field table
table_t* generate_table(
    entry_t original_entry, filter_info_t** filters,
    uint32_t* bit_field_processors, int bf_found) {

    uint32_t n_atoms = filters[0]->n_atoms;

    // create sdram holder for the table we're going to generate
    table_t* sdram_table = MALLOC_SDRAM(routing_table_sdram_size_of_table(
        n_atoms));
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
    for (int i =0; i < bf_found; i++) {
        // Safety code to be removed
        if (!bit_field_test(
                &stripped_route,
                bit_field_processors[i] + MAX_LINKS_PER_ROUTER)) {
            log_error("WHAT THE FUCK!");
        }
        bit_field_clear(
            &stripped_route, bit_field_processors[i] + MAX_LINKS_PER_ROUTER);
    }

    // iterate though each atom and set the route when needed
    for (uint32_t atom = 0; atom < n_atoms; atom++) {
        // Assigning to a uint32 creates a copy
        uint32_t new_route = stripped_route;

        // iterate through the bitfield processor's and see if they need this
        // atom
        for (int bf_index = 0; bf_index < bf_found; bf_index++) {
            log_debug("data address is %x", filters[bf_index]->data);
            if (bit_field_test(filters[bf_index]->data, atom)){
                log_debug(
                    "setting for atom %d from bitfield index %d so proc %d",
                    atom, bf_index, bit_field_processors[bf_index]);
                bit_field_set(
                    &new_route,
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

//! Inserts an entry into a table
//! \param[in] original_entry: The Routing Tabkle entry in the original table
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

    *n_rt_addresses = count_unique_keys(sorted_bit_fields, mid_point);
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

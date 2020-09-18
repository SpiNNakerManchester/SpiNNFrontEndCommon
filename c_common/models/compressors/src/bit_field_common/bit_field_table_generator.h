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

//! \dir
//! \brief Support code for working with bitfields (synaptic matrices, etc.)
//! \file
//! \brief The table generator support code
#ifndef __BIT_FIELD_TABLE_GENERATOR_H__
#define __BIT_FIELD_TABLE_GENERATOR_H__

#include "../common/constants.h"
#include "routing_tables.h"
#include <filter_info.h>

//! max number of links on a router
#define MAX_LINKS_PER_ROUTER    6

//! neuron level mask
#define NEURON_LEVEL_MASK       0xFFFFFFFF

//! \brief Count the number of unique keys in the list up to the midpoint.
//! \details Works on the assumption that the list is grouped (sorted) by key
//! \param[in] sorted_bit_fields: the pointer to the sorted bit field struct.
//! \param[in] midpoint: where in the sorted bitfields to go to
//! \return the number of unique keys
int count_unique_keys(
        sorted_bit_fields_t *restrict sorted_bit_fields, int midpoint) {
    // semantic sugar
    filter_info_t **restrict bit_fields = sorted_bit_fields->bit_fields;
    int *restrict sort_order = sorted_bit_fields->sort_order;
    int n_bit_fields = sorted_bit_fields->n_bit_fields;

    // as the sorted bitfields are sorted by key. checking key changes when
    // within the midpoint will work.
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

//! \brief Generate a routing tables by merging an entry and a list of
//!     bitfields by processor.
//! \param[in] original_entry: The Routing Table entry in the original table
//! \param[in] filters: List of the bitfields to me merged in
//! \param[in] bit_field_processors: List of the processors for each bitfield
//! \param[in] bf_found: Number of bitfields found.
void generate_table(
        entry_t original_entry, filter_info_t **restrict filters,
        uint32_t *restrict bit_field_processors, int bf_found) {
    uint32_t n_atoms = filters[0]->n_atoms;

    uint32_t stripped_route = original_entry.route;
    for (int i =0; i < bf_found; i++) {
        // Safety code to be removed
        if (!bit_field_test(&stripped_route,
                bit_field_processors[i] + MAX_LINKS_PER_ROUTER)) {
            log_error("WHAT THE F***!");
        }
        bit_field_clear(&stripped_route,
                bit_field_processors[i] + MAX_LINKS_PER_ROUTER);
    }

    // iterate though each atom and set the route when needed
    for (uint32_t atom = 0; atom < n_atoms; atom++) {
        // Assigning to a uint32 creates a copy
        uint32_t new_route = stripped_route;

        // iterate through the bitfield processor's and see if they need this
        // atom
        for (int bf_index = 0; bf_index < bf_found; bf_index++) {
            log_debug("data address is %x", filters[bf_index]->data);
            if (bit_field_test(filters[bf_index]->data, atom)) {
                log_debug(
                        "setting for atom %d from bitfield index %d so proc %d",
                        atom, bf_index, bit_field_processors[bf_index]);
                bit_field_set(&new_route,
                        MAX_LINKS_PER_ROUTER + bit_field_processors[bf_index]);
            }
        }

        routing_tables_append_new_entry(
                original_entry.key_mask.key + atom,
                NEURON_LEVEL_MASK, new_route, original_entry.source);
    }
    log_debug("key %d atoms %d size %d",
            original_entry.key_mask.key, n_atoms,
            routing_table_get_n_entries());
}

//! \brief Take a midpoint and read the sorted bitfields,
//!     computing the max size of the routing table.
//! \param[in] mid_point: where in the sorted bitfields to go to
//! \param[in] uncompressed_table: the uncompressed router table
//! \param[in] sorted_bit_fields: the pointer to the sorted bit field struct.
//! \return size of table(s) to be generated in entries
static inline uint32_t bit_field_table_generator_max_size(
        int mid_point, table_t *restrict uncompressed_table,
        sorted_bit_fields_t *restrict sorted_bit_fields) {
    // semantic sugar to avoid referencing
    filter_info_t **restrict bit_fields = sorted_bit_fields->bit_fields;
    int *restrict sort_order = sorted_bit_fields->sort_order;

    // Start with the size of the uncompressed table
    uint32_t max_size = uncompressed_table->size;
    log_debug("keys %d",  max_size);

    // Check every bitfield to see if is to be used
    // Only need each key once to track last used as tables is sorted by key
    uint32_t used_key = FAILED_TO_FIND;
    for (int bf_i = sorted_bit_fields->n_bit_fields -1;  bf_i >= 0; bf_i--) {
        if (sort_order[bf_i] < mid_point) {
            if (used_key != bit_fields[bf_i]->key) {
                used_key = bit_fields[bf_i]->key;

                // One entry per atom but we can remove the uncompressed one
                max_size += bit_fields[bf_i]->n_atoms -1;
                log_debug("key %d size %d",
                        used_key, bit_fields[bf_i]->n_atoms);
            }
        }
    }
    log_debug("Using mid_point %d, counted size of table is %d",
            mid_point, max_size);
    return max_size;
}

//! \brief Take a midpoint and read the sorted bitfields up to that point,
//!     generating bitfield routing tables and loading them into SDRAM
//! \param[in] mid_point: where in the sorted bitfields to go to
//! \param[in] uncompressed_table: the uncompressed router table
//! \param[in] sorted_bit_fields: the pointer to the sorted bit field struct.
static inline void bit_field_table_generator_create_bit_field_router_tables(
        int mid_point,
        table_t *restrict uncompressed_table,
        sorted_bit_fields_t *restrict sorted_bit_fields) {
    // semantic sugar to avoid referencing
    filter_info_t **restrict bit_fields = sorted_bit_fields->bit_fields;
    int *restrict processor_ids = sorted_bit_fields->processor_ids;
    int *restrict sort_order =  sorted_bit_fields->sort_order;
    entry_t *restrict original = uncompressed_table->entries;
    uint32_t original_size =  uncompressed_table->size;
    int n_bit_fields = sorted_bit_fields->n_bit_fields;

    filter_info_t * filters[MAX_PROCESSORS];
    uint32_t bit_field_processors[MAX_PROCESSORS];
    int bf_i = 0;
    log_debug("pre size %d", routing_table_get_n_entries());

    for (uint32_t rt_i = 0; rt_i < original_size; rt_i++) {
        uint32_t key = original[rt_i].key_mask.key;
        log_debug("key %d", key);
        int bf_found = 0;

        while ((bf_i < n_bit_fields) && (bit_fields[bf_i]->key == key)) {
            if (sort_order[bf_i] < mid_point) {
                filters[bf_found] = bit_fields[bf_i];
                bit_field_processors[bf_found] = processor_ids[bf_i];
                bf_found++;
            }
            bf_i++;
        }

        if (bf_found > 0) {
            generate_table(original[rt_i], filters, bit_field_processors,
                    bf_found);
        } else {
            routing_tables_append_entry(original[rt_i]);
        }
        log_debug("key %d size %d",
                original[rt_i].key_mask.key, routing_table_get_n_entries());
    }
}

//! \brief Debugging print for a pointer to a table.
//! \param[in] table: the table pointer to print
void print_table(table_t *table) {
   entry_t *entries = table->entries;
   for (uint32_t i = 0; i < table->size; i++) {
        log_info("i %u, key %u, mask %u, route %u, source %u",
                i, entries[i].key_mask.key, entries[i].key_mask.mask,
                entries[i].route, entries[i].source);
   }
}

//! \brief Compare two entries by their keys.
//! \param[in] ent_1: The first entry.
//! \param[in] ent_2: The second entry.
//! \return Whether the first entry is greater than the second entry.
static inline bool compare_entries(const entry_t *ent_1, const entry_t *ent_2) {
    return ent_1->key_mask.key > ent_2->key_mask.key;
}

//! \brief Sort a given table so that the entries in the table are by key.
//! \details Uses insertion sort.
//! \param[in] table: the table to sort.
void sort_table_by_key(table_t *table) {
    uint32_t size = table->size;
    entry_t *entries = table->entries;

    uint32_t i, j;
    for (i = 1; i < size; i++) {
        const entry_t temp = entries[i];
        for (j = i; j > 0 && compare_entries(&entries[j - 1], &temp); j--) {
            entries[j] = entries[j - 1];
        }
        entries[j] = temp;
    }
}

#endif  // __BIT_FIELD_TABLE_GENERATOR_H__

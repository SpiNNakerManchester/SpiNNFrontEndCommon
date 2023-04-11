/*
 * Copyright (c) 2019 The University of Manchester
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

//! \file
//! \brief The table generator support code
#ifndef __BIT_FIELD_TABLE_GENERATOR_H__
#define __BIT_FIELD_TABLE_GENERATOR_H__

#include "../common/constants.h"
#include "routing_tables.h"
#include <filter_info.h>
#include <utils.h>

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
//! \param[in/out] core_atom: The core-atom to start from, updated with where
//!                           we got to
//! \return Whether more calls are needed for the bit field in question
bool generate_table(
        entry_t original_entry, filter_info_t **restrict filters,
        uint32_t *restrict bit_field_processors, int bf_found,
        struct core_atom *core_atom) {

    // Remove the processor bits from the route that match the bitfields
    uint32_t stripped_route = original_entry.route;
    for (int i = 0; i < bf_found; i++) {
        bit_field_clear(&stripped_route,
                bit_field_processors[i] + MAX_LINKS_PER_ROUTER);
    }

    // Go through the atoms, potentially starting where we left off
    uint32_t first_atom = global_atom(filters[0], core_atom);
    uint32_t n_atoms = filters[0]->n_atoms;
    for (uint32_t atom = first_atom; atom < n_atoms; atom++) {

        // Stop when the route no longer matches the key from the bit field,
        // as this will resume with another entry later
        uint32_t atom_key = get_bf_key(filters[0], core_atom);
        if ((atom_key & original_entry.key_mask.mask)
                != original_entry.key_mask.key) {
            // We need to continue this later, so say yes!
            return true;
        }

        // Start with a copy of the stripped route
        uint32_t new_route = stripped_route;

        // Add the processor for each bit field where the bit for the atom is set
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

        // Add a new entry based on the bit fields
        routing_tables_append_new_entry(
                original_entry.key_mask.key + (atom - first_atom),
                NEURON_LEVEL_MASK, new_route, original_entry.source);

        // Get the next core atom for the next round
        next_core_atom(filters[0], core_atom);
    }

    log_debug("key %d atoms %d size %d",
            original_entry.key_mask.key, n_atoms,
            routing_table_get_n_entries());
    // We got through all atoms, so say no!
    return false;
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
    uint32_t last_key = 0xFFFFFFFF;
    bool is_last_key = false;
    for (int bf_i = 0; bf_i < sorted_bit_fields->n_bit_fields; bf_i++) {
        if (sort_order[bf_i] < mid_point) {
            if (!is_last_key || last_key != bit_fields[bf_i]->key) {
                last_key = bit_fields[bf_i]->key;
                is_last_key = true;

                // One entry per atom but we can remove the uncompressed one
                max_size += bit_fields[bf_i]->n_atoms - 1;
                log_debug("key %d size %d",
                        last_key, bit_fields[bf_i]->n_atoms);
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
    uint32_t n_bit_fields = sorted_bit_fields->n_bit_fields;

    filter_info_t * filters[MAX_PROCESSORS];
    uint32_t bit_field_processors[MAX_PROCESSORS];
    log_debug("pre size %d", routing_table_get_n_entries());

    // Go through key-sorted bit fields and routing entries in tandem.
    // Note: there may be multiple routing entries for each bit field,
    // but there must be only one bit field per processor per routing entry!
    uint32_t rt_i = 0;
    uint32_t bf_i = 0;
    while (bf_i < n_bit_fields && rt_i < original_size) {
        // Find a routing entry that starts at the current bit field (there
        // must be one, because combined entries must be from the same source
        // at this point).
        while (rt_i < original_size &&
                original[rt_i].key_mask.key != bit_fields[bf_i]->key) {
            routing_tables_append_entry(original[rt_i++]);
        }

        // Get out while you still can!
        if (rt_i >= original_size) {
            break;
        }

        // Now find all bit fields with the same key, which will have the same
        // remaining properties too (like atoms per core etc.) since they will
        // be from the same source.
        uint32_t key = original[rt_i].key_mask.key;
        uint32_t bf_found = 0;
        while (bf_i < n_bit_fields && bit_fields[bf_i]->key == key) {
            if (sort_order[bf_i] < mid_point) {
                filters[bf_found] = bit_fields[bf_i];
                bit_field_processors[bf_found] = processor_ids[bf_i];
                bf_found++;
            }
            bf_i++;
        }

        // If we found any bit fields that now match, create entries for each
        // routing entry that continues to match the keys
        if (bf_found > 0) {
            // While the bit field is not finished from this entry, keep
            // generating more
            struct core_atom core_atom = {0, 0};
            while (rt_i < original_size
                    && generate_table(original[rt_i], filters,
                            bit_field_processors, bf_found, &core_atom)) {
                rt_i++;
            }
            // The last one will return false, so increment one more time
            rt_i++;
        }
    }

    // At this point, we might still not have finished the routing table;
    // all remaining entries must be outside of the bit fields, so just copy
    // them.
    while (rt_i < original_size) {
        routing_tables_append_entry(original[rt_i++]);
    }
}

//! \brief debugging print for a pointer to a table.
//! \param[in] table: the table pointer to print
void print_table(table_t *table) {
   entry_t *entries = table->entries;
   for (uint32_t i = 0; i < table->size; i++) {
        log_debug("i %u, key %u, mask %u, route %u, source %u",
                i, entries[i].key_mask.key, entries[i].key_mask.mask,
                entries[i].route, entries[i].source);
   }
}

//! \brief How to compare two entries
//! \param[in] ent_1: The first entry
//! \param[in] ent_2: The second entry
//! \return Whether the first entry is greater than the second
static inline bool compare_entries(const entry_t *ent_1, const entry_t *ent_2) {
    return ent_1->key_mask.key > ent_2->key_mask.key;
}

//! \brief Sort a given table so that the entries in the table are by key
//!     value.
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

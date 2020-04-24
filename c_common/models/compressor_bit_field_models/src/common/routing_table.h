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

#ifndef __ROUTING_TABLE_H__
#define __ROUTING_TABLE_H__

#include <stdbool.h>
#include <stdint.h>
#include <debug.h>
#include <malloc_extras.h>
#include "compressor_sorter_structs.h"

//! enum covering top level entries for routing tables in sdram
typedef enum routing_table_top_elements {
    N_TABLE_ENTRIES = 0, START_OF_SDRAM_ENTRIES = 1
} routing_table_top_elements;


//=============================================================================
//state for reduction in parameters being passed around

//! \brief store for addresses for routing entries in sdram
table_t** routing_tables;

//! \brief store of low atom to each table index, to reduce sdram reads
int* table_lo_entry;

//! \brief low entry tracker for above list.
int current_low_entry = 0;

//! the number of addresses currently stored
int n_tables = 0;

//! current filled n tables
int current_n_tables = 0;

//! \brief Get a mask of the Xs in a key_mask
//! \param[in] km: the key mask to get as xs
//! \return a merged mask
static inline uint32_t key_mask_get_xs(key_mask_t km) {
    return ~km.key & ~km.mask;
}


//! \brief Get a count of the Xs in a key_mask
//! \param[in] km: the key mask struct to count
//! \return the number of bits set in the mask
static inline unsigned int key_mask_count_xs(key_mask_t km) {
    return __builtin_popcount(key_mask_get_xs(km));
}


//! \brief Determine if two key_masks would match any of the same keys
//! \param[in] a: key mask struct a
//! \param[in] b: key mask struct b
//! \return bool that says if these key masks intersect
static inline bool key_mask_intersect(key_mask_t a, key_mask_t b) {
    return (a.key & b.mask) == (b.key & a.mask);
}

//! \brief Generate a new key-mask which is a combination of two other key_masks
//! \brief c := a | b
//! \param[in] a: the key mask struct a
//! \param[in] b: the key mask struct b
//! \return a key mask struct when merged
static inline key_mask_t key_mask_merge(key_mask_t a, key_mask_t b) {
    key_mask_t c;
    uint32_t new_xs = ~(a.key ^ b.key);
    c.mask = a.mask & b.mask & new_xs;
    c.key = (a.key | b.key) & c.mask;

    return c;
}

//! \brief resets a routing table set
void routing_table_reset(void) {
    log_debug("have reset!");
    n_tables = 0;
    current_n_tables = 0;
    current_low_entry = 0;
    if (table_lo_entry != NULL){
        FREE(table_lo_entry);
        table_lo_entry = NULL;
    }
    log_debug("finished reset");
}

//! \brief prints out table fully from list
void routing_table_print_list_tables(void) {
    for (int table_index = 0; table_index < current_n_tables; table_index++) {
        table_t *table = routing_tables[table_index];
        for (uint32_t entry_index = 0; entry_index < table->size;
                entry_index ++){
            entry_t entry = table->entries[entry_index];
            log_info(
                "entry %d from table %d index %d has key %x or %d mask %x "
                "route %x source %x",
                table_lo_entry[table_index] + entry_index, table_index,
                entry_index, entry.key_mask.key, entry.key_mask.key,
                entry.key_mask.mask, entry.route, entry.source);
        }
    }
}

//! \brief gets the length of the group of routing tables
//! \param[in] routing_tables: the addresses list
//! \param[in] n_tables: how many in list
//! \return the total number of entries over all the tables.
static inline int routing_table_sdram_get_n_entries(void) {
    return table_lo_entry[n_tables];
}

int binary_search(int min, int max, int entry_id) {
    if (min >= max - 1){
        return min;
    }
    int mid_point = (min + max) / 2;
    if (table_lo_entry[mid_point] <= entry_id &&
            table_lo_entry[mid_point + 1] > entry_id) {
        return mid_point;
    } else if (table_lo_entry[mid_point] < entry_id) {
        return binary_search(mid_point, max, entry_id);
    } else {
        return binary_search(min, mid_point, entry_id);
    }
}

//! \brief finds a router table index from dtcm stuff, to avoid sdram reads
//! \param[in] the entry id to find the table index of
//! \return the table index which has this entry
int find_index_of_table_for_entry(int entry_id) {
    // could do binary search. but start with cyclic
    if (table_lo_entry[n_tables - 1] <= entry_id) {
        return n_tables - 1;
    }
    if (table_lo_entry[1] > entry_id) {
        return 0;
    }

    return binary_search(0, n_tables - 1, entry_id);

    log_error(
        "should never get here. If so WTF! was looking for entry %d when there"
        " are only %d entries", entry_id, routing_table_sdram_get_n_entries());
    rt_error(RTE_SWERR);
    return 0;
}

//! \brief the init for the routing tables
//! \param[in] total_n_tables: the total tables to be stored
//! \return bool saying the routing tables have been initialised.
static inline bool routing_tables_init(
        int total_n_tables, table_t **elements) {
    n_tables = total_n_tables;
    log_debug("n tables = %d", n_tables);

    // set up addresses data holder
    routing_tables = elements;

    log_debug(
        "allocating %d bytes for table lo entry",
        (n_tables + 1) * sizeof(int));
    table_lo_entry = MALLOC((n_tables + 1) * sizeof(int));

    if (table_lo_entry == NULL) {
        log_error(
            "failed to allocate memory for the holding the low entry");
        return false;
    }

    // update the lo entry map
    for (int rt_index = 0; rt_index < total_n_tables; rt_index++) {
        log_debug("n table entries is %d", routing_tables[rt_index]->size);

        // store low entry tracker (reduces sdram requirements)
        table_lo_entry[current_n_tables] = current_low_entry;
            // update current n tables.
        current_n_tables += 1;
        // update low entry
        current_low_entry += routing_tables[rt_index]->size;

        // store what is basically total entries to end of list.
        table_lo_entry[current_n_tables] = current_low_entry;
    }

    bool check = malloc_extras_check(table_lo_entry);
    if (!check){
        log_error("failed");
    }

    return true;
}

//! \brief gets a entry at a given position in the lists of tables in sdram
//! \param[in] entry_id_to_find: the entry your looking for
//! \return the pointer in sdram to the entry
entry_t* routing_table_sdram_stores_get_entry(
        uint32_t entry_id_to_find) {
    int router_index = find_index_of_table_for_entry(entry_id_to_find);
    int router_offset = entry_id_to_find - table_lo_entry[router_index];

    log_debug(
        "for entry %d we say its in table %d and entry %d with address %x",
        entry_id_to_find, router_index, router_offset,
        &routing_tables[router_index]->entries[router_offset]);
    return &routing_tables[router_index]->entries[router_offset];
}

//! \brief stores the routing tables entries into sdram at a specific sdram
//! address as one big router table
//! \param[in] sdram_loc_for_compressed_entries:
//!    the location in sdram to write data to
//! \return bool saying if the entries were stored in sdram successfully or not
bool routing_table_sdram_store(table_t *table_format) {

    // locate n entries overall and write to struct
    int n_entries = routing_table_sdram_get_n_entries();
    log_debug("compressed entries = %d", n_entries);
    log_debug("compressed address = %x", table_format);
    table_format->size = n_entries;

    bool check = malloc_extras_check(table_format);
    if (!check){
        log_error("failed");
        rt_error(RTE_SWERR);
    }

    // iterate though the entries writing to the struct as we go

    log_debug("start copy over");
    uint32_t main_entry_index = 0;
    for (int rt_index = 0; rt_index < n_tables; rt_index++) {
        log_debug("on index %d of %d", rt_index, n_tables);
        // get how many entries are in this block
        int entries_stored_here = routing_tables[rt_index]->size;
        log_debug("copying over %d entries", entries_stored_here);
        if (entries_stored_here != 0) {
            // take entry and plonk data in right sdram location
            log_debug("doing sark copy");

            for (uint32_t local_index = 0;
                    local_index < routing_tables[rt_index]->size;
                    local_index++, main_entry_index++) {
                log_debug("main index = %d", main_entry_index);
                table_format->entries[main_entry_index].key_mask.key =
                    routing_tables[rt_index]->entries[local_index].key_mask.key;
                table_format->entries[main_entry_index].key_mask.mask =
                    routing_tables[rt_index]->entries[local_index].key_mask.mask;
                table_format->entries[main_entry_index].route =
                    routing_tables[rt_index]->entries[local_index].route;
                table_format->entries[main_entry_index].source =
                    routing_tables[rt_index]->entries[local_index].source;
            }

            log_debug("updated the main index to %d", main_entry_index);
            check = malloc_extras_check(table_format);
            if (!check){
                log_error("failed");
            }
        }
    }
    log_debug("finished copy");
    return true;
}

static void routing_tables_print_out_table_sizes(void){
    for (int rt_index = 0; rt_index < n_tables; rt_index++){
        log_debug(
            "n entries in rt index %d at address %x is %d",
            rt_index, routing_tables[rt_index],
            routing_tables[rt_index]->size);
    }
}

void routing_table_print_table_lo_atom(void){
    for (int rt_index = 0; rt_index < n_tables; rt_index++){
        log_debug(
            "low atom for table %d is %d with length %d", rt_index,
            table_lo_entry[rt_index], routing_tables[rt_index]->size);
    }
}

//! \brief updates table stores accordingly.
//! \param[in] routing_tables: the addresses list
//! \param[in] n_tables: how many in list
//! \param[in] size_to_remove: the amount of size to remove from the table sets
void routing_table_remove_from_size(uint32_t size_to_remove) {
    // update dtcm tracker
    table_lo_entry[n_tables] = table_lo_entry[n_tables] - size_to_remove;

    routing_tables_print_out_table_sizes();

    // iterate backwards, as you removing from the bottom, which is the last
    // table upwards
    int rt_index = n_tables - 1;
    while (size_to_remove != 0 && rt_index >= 0) {
        if (routing_tables[rt_index]->size >= size_to_remove) {
            uint32_t diff = routing_tables[rt_index]->size - size_to_remove;
            routing_tables[rt_index]->size = diff;
            size_to_remove = 0;
        } else {
            size_to_remove -= routing_tables[rt_index]->size;
            routing_tables[rt_index]->size = 0;
            table_lo_entry[rt_index] = table_lo_entry[n_tables];
        }
        rt_index -= 1;
    }
    if (size_to_remove != 0) {
        log_error(
            "deleted more than what was available. WTF %d",
            size_to_remove);
        rt_error(RTE_SWERR);
    }

}

//! \brief deduces sdram requirements for a given size of table
//! \param[in] n_entries: the number of entries expected to be in the table.
//! \return the number of bytes needed for this routing table
static inline uint routing_table_sdram_size_of_table(uint32_t n_entries) {
    return sizeof(uint32_t) + (sizeof(entry_t) * n_entries);
}

//! \brief copies over the contents of 1 table_t to another table_t safely
void routing_table_copy_table(table_t* src, table_t* dest){

    log_debug("src size is %d", src->size);
    dest->size = src->size;
    for (uint32_t index = 0; index < dest->size; index ++){
        dest->entries[index].key_mask.key = src->entries[index].key_mask.key;
        dest->entries[index].key_mask.mask = src->entries[index].key_mask.mask;
        dest->entries[index].route = src->entries[index].route;
        dest->entries[index].source = src->entries[index].source;
    }
    log_debug(
        "successfully copied table data from %x to %x",
        src, dest);
    log_debug("size in dest is %d, src size is %d", dest->size, src->size);
}

#endif  // __ROUTING_TABLE_H__

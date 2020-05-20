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

#include <debug.h>
#include <malloc_extras.h>
#include "routing_table_utils.h"

//=============================================================================
//state for reduction in parameters being passed around

//! \brief store for addresses for routing entries in sdram
//! WARNING size of
table_t** sub_tables;

//! the number of sub_tables used
uint32_t n_sub_tables = 0;

//! the number of entries appended to the table
int n_entries = 0;

//! \brief Gets a pointer to where this entry is stored
//!
//! Will not check if there is an entry with this id but
//! may RTE if the id is too large but this behaviour should not be
//! counted on in the future.
//! \param[in] entry_id_to_find: Id of entry to find pointer to
//! \return pointer to the entry's location
entry_t* routing_table_get_entry(uint32_t entry_id_to_find, int marker) {
    uint32_t table_id = entry_id_to_find >> TABLE_SHIFT;
    if (table_id >= n_sub_tables) {
        log_error("Id %d to big for %d tables marker %d", entry_id_to_find, n_sub_tables, marker);
        malloc_extras_terminate(RTE_SWERR);
    }
    uint32_t local_id = entry_id_to_find & LOCAL_ID_ADD;
    if (local_id >= sub_tables[table_id]->size) {
        log_error("Id %d has local_id %d which is too big for table of size %d marker %d",
            entry_id_to_find, local_id, sub_tables[table_id]->size, marker);
        malloc_extras_terminate(RTE_SWERR);
    }
    return &sub_tables[table_id]->entries[local_id];
}

//! \brief Gets a pointer to where this entry is stored
//!
//! Will not check if there is an entry with this id but
//! may RTE if the id is too large but this behaviour should not be
//! counted on in the future.
//! \param[in] entry_id_to_find: Id of entry to find pointer to
//! \return pointer to the entry's location
entry_t* routing_table_append_get_entry() {
    uint32_t table_id = n_entries >> TABLE_SHIFT;
    if (table_id >= n_sub_tables) {
        log_error("Id %d to big for %d tables", n_entries, n_sub_tables);
        malloc_extras_terminate(RTE_SWERR);
    }
    uint32_t local_id = n_entries & LOCAL_ID_ADD;
    if (local_id != sub_tables[table_id]->size) {
        log_error("Id %d has local_id %d which is big for %d table", n_entries, local_id, sub_tables[table_id]->size);
        malloc_extras_terminate(RTE_SWERR);
    }
    n_entries++;
    sub_tables[table_id]->size++;
    return &sub_tables[table_id]->entries[local_id];
}

//! Inserts a deep copy of an entry after the last known entry in the table.
//!
//! May RTE if is this appended is unexpected but this behaviour should not be
//! counted on in the future.
//! \param[in] original_entry: The Routing Table entry to be copied in
void routing_table_append_entry(entry_t original_entry) {
    entry_t *new_entry = routing_table_append_get_entry();
    new_entry->key_mask.key = original_entry.key_mask.key;
    new_entry->key_mask.mask = original_entry.key_mask.mask;
    new_entry->source = original_entry.source;
    new_entry->route = original_entry.route;
}

//! Inserts an new entry after the last known entry in the table.
//!
//! May RTE if is this appended is unexpected but this behaviour should not be
//! counted on in the future.
//! \param[in] key: The key for the new entry to be added
//! \param[in] mask: The key for the new entry to be added
//! \param[in] route: The key for the new entry to be added
//! \param[in] source: The key for the new entry to be added
void routing_table_append_new_entry(
        uint32_t key, uint32_t mask, uint32_t route, uint32_t source) {
    entry_t *new_entry = routing_table_append_get_entry();
    new_entry->key_mask.key = key;
    new_entry->key_mask.mask = mask;
    new_entry->source = source;
    new_entry->route = route;
}

//! \return The number of sub_tables
table_t** routing_table_get_sub_tables(void) {
    return sub_tables;
}

//! \return number of appended entries.
int routing_table_get_n_entries(void) {
    return n_entries;
}

//! \brief Prepares the Routing table based on passed in pointers and counts
//!
//! Will NOT Free the space any previous tables held
//! \param[in] table: Pointer to the metadata to init
void routing_tables_init(multi_table_t* table) {
    sub_tables = table->sub_tables;
    n_sub_tables = table->n_sub_tables;
    n_entries = table->n_entries;
    log_debug("init with n table %d entries %d", n_sub_tables, n_entries);

    for (uint32_t i = 0; i <  n_sub_tables; i++) {
        log_debug("table %d size %d", i, sub_tables[i]->size);
    }
}

//! \brief Saves the Metadata to the multi_table object
//! \param[in] table: Pointer to the metadata to save to
void routing_tables_save(multi_table_t* tables) {
    tables->sub_tables = sub_tables;
    tables->n_sub_tables = n_sub_tables;
    tables->n_entries = n_entries;
    log_info("saved table with %d entries over %d tables", tables->n_sub_tables, tables->n_entries);
}

//! \brief updates table stores accordingly.
//!
//! May RTE if this causes the total entries to become negative this behaviour
//! should not be counted on in the future.
//! \param[in] size_to_remove: the amount of size to remove from the table sets
void routing_table_remove_from_size(int size_to_remove) {
    if (size_to_remove > n_entries) {
        log_error(
            "Remove %d large than n_entries %d", size_to_remove, n_entries);
        malloc_extras_terminate(RTE_SWERR);
    }
    n_entries -= size_to_remove;
}

//! \brief Clones an Original table into this format.
//!
//! Will NOT Free the space any previous tables held
//! Makes a Deep copy of the original
//! \return True if and only if all table(s) could be malloced
void routing_table_clone_table(table_t original) {
    for (uint32_t i = 0; i < original.size; i++) {
        routing_table_append_entry(original.entries[i]);
    }
}

//! \brief Write the routing table to the dest
//!
//! May RTE if the size is large than a compressed table should be
//! however this behaviour should not be counted on
//! \return a Routing table that will fit in the router
table_t* routing_table_convert_to_table_t( void) {
    malloc_extras_check_all_marked(70014);
    if (n_entries > TABLE_SIZE) {
        log_error("With %d entries table is too big to convert", n_entries);
        malloc_extras_terminate(RTE_SWERR);
    }
    table_t* dest = sub_tables[0];
    dest->size = n_entries;
    return dest;
}

#endif  // __ROUTING_TABLE_H__
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
//! \brief Utilities for a single routing table
#ifndef __ROUTING_TABLES_H__
#define __ROUTING_TABLES_H__

#include <debug.h>
#include <malloc_extras.h>
#include <common/routing_table.h>
#include "routing_tables_utils.h"

//=============================================================================
// location for variables

//! holder in DTCM for top level pointers in SDRAM, used for performance.
multi_table_t multi_table;

//! \brief Gets a pointer to where this entry is stored
//!
//! Will not check if there is an entry with this id but will RTE if the id
//! is too large
//! \param[in] entry_id_to_find: Id of entry to find pointer to
//! \param[in] marker: int that should be different in every call so we can
//!     detect where MUNDY was reading past the end of the table
//! \return pointer to the entry's location
entry_t* routing_tables_get_entry_marked(uint32_t entry_id_to_find, int marker) {
    uint32_t table_id = entry_id_to_find >> TABLE_SHIFT;
    if (table_id >= multi_table.n_sub_tables) {
        log_error("Id %d to big for %d tables marker %d",
                entry_id_to_find, multi_table.n_sub_tables, marker);
        malloc_extras_terminate(RTE_SWERR);
    }
    uint32_t local_id = entry_id_to_find & LOCAL_ID_ADD;
    if (local_id >= multi_table.sub_tables[table_id]->size) {
        log_error("Id %d has local_id %d which is too big for "
                "table of size %d marker %d",
                entry_id_to_find, local_id,
                multi_table.sub_tables[table_id]->size, marker);
        malloc_extras_terminate(RTE_SWERR);
    }
    return &multi_table.sub_tables[table_id]->entries[local_id];
}

entry_t* routing_table_get_entry(uint32_t entry_id_to_find) {
    return routing_tables_get_entry_marked(entry_id_to_find, -1);
}

//! \brief Gets a pointer to where to append an entry to the routing table.
//! \return pointer to the entry's location
entry_t* routing_tables_append_get_entry(void) {
    // check that we're not hitting the max entries supported by the table
    if (multi_table.n_entries == (int) multi_table.max_entries) {
        log_error(
                "There is no more space out of %d entries in this multi-table"
                "for this entry.", multi_table.max_entries);
        malloc_extras_terminate(RTE_SWERR);
    }

    // locate right table index
    uint32_t table_id = multi_table.n_entries >> TABLE_SHIFT;
    if (table_id >= multi_table.n_sub_tables) {
        log_error("Id %d to big for %d tables",
                multi_table.n_entries, multi_table.n_sub_tables);
        malloc_extras_terminate(RTE_SWERR);
    }

    // locate entry index
    uint32_t local_id = multi_table.n_entries & LOCAL_ID_ADD;
    if (local_id != multi_table.sub_tables[table_id]->size) {
        log_error("Id %d has local_id %d which is big for %d table",
                multi_table.n_entries, local_id,
                multi_table.sub_tables[table_id]->size);
        malloc_extras_terminate(RTE_SWERR);
    }

    // update trackers.
    multi_table.n_entries++;
    multi_table.sub_tables[table_id]->size++;
    return &multi_table.sub_tables[table_id]->entries[local_id];
}

//! \brief Inserts a deep copy of an entry after the last known entry in the
//!     table.
//! \details will RTE if is this appended fails.
//! \param[in] original_entry: The Routing Table entry to be copied in
void routing_tables_append_entry(entry_t original_entry) {
    entry_t *new_entry = routing_tables_append_get_entry();
    new_entry->key_mask.key = original_entry.key_mask.key;
    new_entry->key_mask.mask = original_entry.key_mask.mask;
    new_entry->source = original_entry.source;
    new_entry->route = original_entry.route;
}

//! Inserts an new entry after the last known entry in the table.
//!
//! will RTE if is this appended fails.
//! \param[in] key: The key for the new entry to be added
//! \param[in] mask: The key for the new entry to be added
//! \param[in] route: The key for the new entry to be added
//! \param[in] source: The key for the new entry to be added
void routing_tables_append_new_entry(
        uint32_t key, uint32_t mask, uint32_t route, uint32_t source) {
    entry_t *restrict new_entry = routing_tables_append_get_entry();
    new_entry->key_mask.key = key;
    new_entry->key_mask.mask = mask;
    new_entry->source = source;
    new_entry->route = route;
}

int routing_table_get_n_entries(void) {
    return multi_table.n_entries;
}

//! \brief Prepares the Routing table based on passed in pointers and counts
//!
//! NOTE: Will NOT Free the space any previous tables held
//! \param[in] table: Pointer to the metadata to init
void routing_tables_init(multi_table_t* table) {
    multi_table.sub_tables = table->sub_tables;
    multi_table.n_sub_tables = table->n_sub_tables;
    multi_table.n_entries = table->n_entries;
    multi_table.max_entries = table->max_entries;
    log_debug("init with n table %d entries %d",
            multi_table.n_sub_tables, multi_table.n_entries);

    for (uint32_t i = 0; i <  multi_table.n_sub_tables; i++) {
        log_debug("table %d size %d", i, multi_table.sub_tables[i]->size);
    }
}

//! \brief Saves the metadata to the multi_table object we are managing
//! \param[in] tables: Pointer to the metadata to save to
void routing_tables_save(multi_table_t *restrict tables) {
    tables->sub_tables = multi_table.sub_tables;
    tables->n_sub_tables = multi_table.n_sub_tables;
    tables->n_entries = multi_table.n_entries;
    tables->max_entries = multi_table.max_entries;
    log_info("saved table with %d entries over %d tables",
            tables->n_entries, tables->n_sub_tables);
}

void routing_table_remove_from_size(int size_to_remove) {
    if (size_to_remove > multi_table.n_entries) {
        log_error("Remove %d large than n_entries %d",
                size_to_remove, multi_table.n_entries);
        malloc_extras_terminate(RTE_SWERR);
    }
    multi_table.n_entries -= size_to_remove;
}

//! \brief Clones an original table into this format.
//! \details Will _not_ free the space any previous tables held.
//!     Makes a Deep copy of the original.
//! \param[in] original: the table to be cloned
void routing_tables_clone_table(table_t *restrict original) {
    for (uint32_t i = 0; i < original->size; i++) {
        routing_tables_append_entry(original->entries[i]);
    }
}

//! \brief Gets a pointer to several entries
//! \param[in] start_entry: The first entry to get
//! \param[in] n_entries: The number of entries to get
//! \param[out] output: Where to put the entries read - must have enough space!
//! \return: Whether the entries are available now, or should be waited for
bool routing_table_get_entries(uint32_t start_entry, uint32_t n_entries,
        entry_t *output) {
    for (uint32_t i = 0; i < n_entries; i++) {
        output[i] = *routing_table_get_entry(start_entry + i);
    }
    return true;
}

//! \brief Waits for the last transfer from routing_table_get_entries to complete
//! \details Returns immediately if the last transfer is already done
void routing_table_wait_for_last_transfer(void) {
    return;
}

#endif  // __ROUTING_TABLES_H__

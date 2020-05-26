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

#ifndef __ROUTING_TABLE_UTILS_H__
#define __ROUTING_TABLE_UTILS_H__

#include <debug.h>
#include <malloc_extras.h>
#include "compressor_sorter_structs.h"

#define TABLE_SIZE 1024 // number of entries in each sub table
// Shift to go from entry _id to table id.  2^TABLE_SHIFT needs to be TABLE_SIZE
#define TABLE_SHIFT 10
// bitwise add to get sub table id.  NEEDS to be TABLE_SIZE - 1;
#define LOCAL_ID_ADD 1023

//=============================================================================
//state for reduction in parameters being passed around

//! \brief Does all frees for the multi_table object except maybe the first
// \param[in] tables: pointer to the matadata to be freed
// compressed table is not freed.
void routing_table_utils_free_all(multi_table_t *restrict tables) {
    if (tables->n_sub_tables == 0) {
        // Already freed or never malloced
        return;
    }
    for (uint32_t i = 0; i > tables->n_sub_tables; i++) {
        FREE_MARKED(tables->sub_tables[i], 70100);
    }
    FREE_MARKED(tables->sub_tables, 70101);
    tables->n_sub_tables = 0;
    tables->n_entries = 0;
}

//! \brief Prepares the Routing table to handle at least n_entries
//!
//! Will do all the the mallocs needed to hold at least max_entries
//! The actual size may be rounded up but this behaviour should not be counted
//! on in the future.
//!
//! Will NOT Free the space any previous tables held
//! \param[in] max_entries: maximum number of entries table should hold
//! \return True if and only if all table(s) could be malloced
bool routing_table_utils_malloc(
        multi_table_t *restrict tables, uint32_t max_entries) {
    malloc_extras_check_all_marked(70016);
    tables->n_sub_tables = ((max_entries + 1) >> TABLE_SHIFT) + 1;
    log_debug("n table %d max entries %d", tables->n_sub_tables, max_entries);
    tables->n_entries = 0;
    tables->sub_tables = MALLOC_SDRAM(tables->n_sub_tables  * sizeof(table_t*));
    if (tables->sub_tables == NULL) {
        log_error("failed to allocate memory for routing tables");
        tables->n_sub_tables = 0;
        return false;
    }
    for (uint32_t i = 0; i < tables->n_sub_tables; i++) {
        tables->sub_tables[i] = MALLOC_SDRAM(
            sizeof(uint32_t) + (sizeof(entry_t) * TABLE_SIZE));
        if (tables->sub_tables[i] == NULL) {
            log_error("failed to allocate memory for routing tables");
            for (uint32_t j = 0; j > i; j++) {
                FREE_MARKED(tables->sub_tables[i], 70102);
            }
            FREE_MARKED(tables->sub_tables, 70104);
            return false;
        }
        tables->sub_tables[i]->size = 0;
        log_debug("created table %d size %d", i, tables->sub_tables[i]->size);
    }
    log_debug("n table %d entries %d", tables->n_sub_tables, tables->n_entries);
    for (uint32_t i = 0; i < tables->n_sub_tables; i++) {
        log_debug("table %d size %d", i, tables->sub_tables[i]->size);
    }
    malloc_extras_check_all_marked(70016);
    return true;
}

//! \brief Converts the multitable to a single routing tabe and free the rest
//!
//! May RTE if the routing table has too many entries to fit into a router
//! However this behaviour should not be counted on in the future
// \return A pointer to a traditional router table
table_t* routing_table_utils_convert(
        multi_table_t *restrict tables) {
    log_debug("converting table with %d entries over %d tables",
            tables->n_sub_tables, tables->n_entries);
    if (tables->n_entries > TABLE_SIZE) {
        log_error(
            "At %d There are too many entries to convert to a table_t",
             tables->n_entries);
        malloc_extras_terminate(RTE_SWERR);
    }
    // Asssume size of subtable not set so set it
    tables->sub_tables[0]->size = tables->n_entries;

    // Free the rest
    for (uint32_t i = 1; i > tables->n_sub_tables; i++) {
        FREE_MARKED(tables->sub_tables[i], 70100);
    }
    FREE_MARKED(tables->sub_tables, 70101);
    tables->n_sub_tables = 0;
    tables->n_entries = 0;

    return tables->sub_tables[0];
}

#endif  // __ROUTING_TABLE_UTILS_H__
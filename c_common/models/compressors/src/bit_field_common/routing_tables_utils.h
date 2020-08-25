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

//! \file
//! \brief Compound routing table utilities.
#ifndef __ROUTING_TABLES_UTILS_H__
#define __ROUTING_TABLES_UTILS_H__

#include <debug.h>
#include <malloc_extras.h>
#include "compressor_sorter_structs.h"

//! number of entries in each sub table
#define TABLE_SIZE 1024

//! \brief Shift to go from entry \p _id to table id.
//! \details 2<sup>TABLE_SHIFT</sup> needs to be ::TABLE_SIZE
#define TABLE_SHIFT 10

//! \brief bitwise add to get sub table id.
//! \details Needs to be ::TABLE_SIZE - 1;
#define LOCAL_ID_ADD 1023

//=============================================================================
//state for reduction in parameters being passed around

//! \brief Do all frees for the multi_table object except for ones before
//!     the start point.
//! \param[in] tables: pointer to the metadata to be freed
//! \param[in] start_point: where in the array to start freeing from.
static void routing_tables_utils_free(
        multi_table_t *restrict tables, uint32_t start_point) {
    if (tables->n_sub_tables == 0) {
        // Already freed or never malloced
        return;
    }
    for (uint32_t i = start_point; i > tables->n_sub_tables; i++) {
        FREE_MARKED(tables->sub_tables[i]->entries, 70999);
        FREE_MARKED(tables->sub_tables[i], 70100);
    }
    FREE_MARKED(tables->sub_tables, 70101);
    tables->n_sub_tables = 0;
    tables->n_entries = 0;
}

//! \brief Do all frees for the multi_table object
//! \param[in] tables: pointer to the metadata to be freed
static void routing_tables_utils_free_all(multi_table_t *restrict tables) {
    routing_tables_utils_free(tables, 0);
}

//! \brief Prepare the routing table to handle at least \p max_entries
//! \details
//!     Will do all the the mallocs needed to hold at least \p max_entries.
//!     The actual size may be rounded up but this behaviour should not be
//!     counted on in the future.
//!
//! Will *not* free the space any previous tables held
//! \param[in] tables: the collection of tables to prepare
//! \param[in] max_entries: maximum number of entries table should hold
//! \return Whether all tables could be allocated
static inline bool routing_tables_utils_malloc(
        multi_table_t *restrict tables, uint32_t max_entries) {
    tables->n_sub_tables = ((max_entries - 1) >> TABLE_SHIFT) + 1;
    tables->max_entries = max_entries;
    log_debug("n table %d max entries %d", tables->n_sub_tables, max_entries);
    tables->n_entries = 0;
    tables->sub_tables = MALLOC_SDRAM(tables->n_sub_tables * sizeof(table_t*));

    // check array malloced successfully
    if (tables->sub_tables == NULL) {
        log_error("failed to allocate memory for routing tables");
        tables->n_sub_tables = 0;
        return false;
    }

    // run through full tables mallocing max sizes.
    int entries_covered = 0;
    for (uint32_t i = 0; i < tables->n_sub_tables - 1; i++) {
        tables->sub_tables[i] = MALLOC_SDRAM(
                sizeof(uint32_t) + (sizeof(entry_t) * TABLE_SIZE));
        if (tables->sub_tables[i] == NULL) {
            log_error("failed to allocate memory for routing tables");
            tables->n_sub_tables = i;
            routing_tables_utils_free_all(tables);
            return false;
        }
        tables->sub_tables[i]->size = 0;
        entries_covered += TABLE_SIZE;
        log_debug("created table %d size %d", i, tables->sub_tables[i]->size);
    }

    // create last table with correct size
    int last_table_size = tables->max_entries - entries_covered;
    tables->sub_tables[tables->n_sub_tables - 1] = MALLOC_SDRAM(
            sizeof(uint32_t) + (sizeof(entry_t) * last_table_size));
    if (tables->sub_tables[tables->n_sub_tables - 1] == NULL) {
        log_error("failed to allocate memory for routing tables");
        tables->n_sub_tables = tables->n_sub_tables - 1;
        routing_tables_utils_free_all(tables);
        return false;
    }
    // init the size
    tables->sub_tables[tables->n_sub_tables - 1]->size = 0;
    log_debug("created table %d size %d",
            tables->n_sub_tables - 1,
            tables->sub_tables[tables->n_sub_tables - 1]->size);

    // debugging please keep.
    log_debug("n table %d entries %d",
            tables->n_sub_tables, tables->n_entries);
    for (uint32_t i = 0; i < tables->n_sub_tables; i++) {
        log_debug("table %d size %d", i, tables->sub_tables[i]->size);
    }
    return true;
}

//! \brief Convert the multitable to a single routing table and free the rest
//! \details Will RTE if the routing table has too many entries to fit into a
//!     router
//! \param[in] tables: the multitable to convert
//! \return A pointer to a traditional router table
static inline table_t* routing_tables_utils_convert(
        multi_table_t *restrict tables) {
    log_debug("converting table with %d entries over %d tables",
            tables->n_sub_tables, tables->n_entries);

    // if table too big for a router. RTE.
    if (tables->n_entries > TABLE_SIZE) {
        log_error("At %d There are too many entries to convert to a table_t",
                tables->n_entries);
        malloc_extras_terminate(RTE_SWERR);
    }

    // Assume size of subtable not set so set it
    tables->sub_tables[0]->size = tables->n_entries;

    // claim the first pointer before freeing to avoid bad memory access
    table_t* first_table = tables->sub_tables[0];

    // Free the rest
    routing_tables_utils_free(tables, 1);
    return first_table;
}

#endif  // __ROUTING_TABLES_UTILS_H__

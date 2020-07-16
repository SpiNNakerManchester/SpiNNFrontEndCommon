/*
 * Copyright (c) 2017-2019 The University of Manchester
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

#include <stdbool.h>
#include <spin1_api.h>
#include <debug.h>
#include <malloc_extras.h>
#include "../common/routing_table.h"

#ifndef __RT_SINGLE_H__
#define __RT_SINGLE_H__

/**
 * \file
 * \brief SpiNNaker routing table minimisation.
 *
 * Minimise a routing table loaded into SDRAM and load the minimised table into
 * the router using the specified application ID.
 *
 * the exit code is stored in the user0 register
 *
 * The memory address with tag "1" is expected contain the following struct
 * (entry_t is defined in `routing_table.h` but is described below).
 */

/* entry_t is defined as:
 *
 *     typedef struct
 *     {
 *       uint32_t keymask;
 *       uint32_t mask;
 *       uint32_t route;   // Routing direction
 *       uint32_t source;  // Source of packets arriving at this entry
 *     } entry_t;
 *
 * The `source` field is used to determine if the entry could be replaced by
 * default routing, it can be left blank if removing default entries is not to
 * be used. Otherwise indicate which links will be used by packets expected to
 * match the specified entry.
 *
 * NOTE: The routing table provided to this application MUST include all of the
 * entries which are expected to arrive at this router (i.e., entries which
 * could be replaced by default routing MUST be included in the table provided
 * to this application).
 *
 * NOTE: The block of memory containing the header and initial routing table
 * will be freed on exit by this application.
 */

//! \brief flag for if a rtr_mc_set() failure.
#define RTR_MC_SET_FAILED 0

//! \brief The table being manipulated.
//!
//! This is common across all the functions in this file.
table_t *table;

//! \brief The header of the routing table information in the input data block.
//!
//! This is found looking for a memory block with the right tag.
typedef struct {
    //! Application ID to use to load the routing table. This can be left as `0`
    //! to load routing entries with the same application ID that was used to
    //! load this application.
    uint32_t app_id;

    //! flag that uses the available entries of the router table instead of
    //! compressing as much as possible.
    uint32_t compress_as_much_as_possible;

    //! Initial size of the routing table.
    uint32_t table_size;

    //! Routing table entries
    entry_t entries[];
} header_t;

int routing_table_get_n_entries(void) {
    return table->size;
}

void routing_table_remove_from_size(int size_to_remove) {
    table->size -= size_to_remove;
}

entry_t* routing_table_get_entry(uint32_t entry_id_to_find) {
    return &table->entries[entry_id_to_find];
}

//! \brief Print the header object for debug purposes
//! \param[in] header: the header to print
void print_header(header_t *header) {
    log_info("app_id = %d", header->app_id);
    log_info("compress_as_much_as_possible = %d",
            header->compress_as_much_as_possible);
    log_info("table_size = %d", header->table_size);
}

//! \brief Read a new copy of the routing table from SDRAM.
//! \param[in] header: the header object
static void read_table(header_t *header) {
    table = MALLOC(
        sizeof(uint32_t) + (sizeof(entry_t) * header->table_size));
    if (table == NULL) {
        log_error("failed to allocate memory for routing tables");
        malloc_extras_terminate(EXIT_FAIL);
    }
    // Copy the size of the table
    table->size = header->table_size;

    // Copy in the routing table entries
    spin1_memcpy(table->entries, header->entries,
            sizeof(entry_t) * table->size);
}

//! \brief Load a routing table to the router.
//! \param[in] app_id:
//!     the app id for the routing table entries to be loaded under
//! \return whether the table was loaded into the router
bool load_routing_table(uint32_t app_id) {
    // Try to allocate sufficient room for the routing table.
    uint32_t entry_id = rtr_alloc_id(table->size, app_id);
    if (entry_id == 0) {
        log_info("Unable to allocate routing table of size %u\n", table->size);
        return FALSE;
    }

    // Load entries into the table (provided the allocation succeeded).
    // Note that although the allocation included the specified
    // application ID we also need to include it as the most significant
    // byte in the route (see `sark_hw.c`).
    for (uint32_t i = 0; i < table->size; i++) {
        entry_t entry = table->entries[i];
        uint32_t route = entry.route | (app_id << 24);
        uint success = rtr_mc_set(
            entry_id + i, entry.key_mask.key, entry.key_mask.mask, route);
        if (success == RTR_MC_SET_FAILED) {
            log_error(
                "failed to set a router table entry at index %d",
                entry_id + i);
        }
    }

    // Indicate we were able to allocate routing table entries.
    return TRUE;
}

//! \brief Free memory allocated and call spin1_exit() and sets the user0
//!     error code correctly.
//! \param[in] header: the header object
void cleanup_and_exit(header_t *header) {
    // Free the memory used by the routing table.
    log_debug("free sdram blocks which held router tables");
    FREE(table->entries);
    // Free the block of SDRAM used to load the routing table.
    sark_xfree(sv->sdram_heap, (void *) header, ALLOC_LOCK);

    log_info("completed router compressor");
    malloc_extras_terminate(EXITED_CLEANLY);
}

#endif //__RT_SINGLE_H__

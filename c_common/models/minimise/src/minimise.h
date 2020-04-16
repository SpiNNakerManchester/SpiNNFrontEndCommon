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

#ifndef __MINIMISE_H__
#define __MINIMISE_H__

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

table_t *table;

static inline int Routing_table_sdram_get_n_entries(){
    return table->size;
}

static inline void routing_table_remove_from_size(int size_to_remove){
    table->size -= size_to_remove;
}

static inline entry_t* routing_table_sdram_stores_get_entry(int index){
    return &table->entries[index];
}

static inline void put_entry(entry_t* entry, int index){
    entry_t* e_ptr = routing_table_sdram_stores_get_entry(index);
    e_ptr->keymask = entry->keymask;
    e_ptr->route = entry->route;
    e_ptr->source = entry->source;
}

static inline void copy_entry(int new_index, int old_index){
    entry_t* e_ptr = routing_table_sdram_stores_get_entry(old_index);
    put_entry(e_ptr, new_index);
}

static inline void swap_entries(int a, int b){
    log_debug("swap %u %u", a, b);
    entry_t temp = *routing_table_sdram_stores_get_entry(a);
    log_debug("before %u %u %u %u", temp.keymask.key, temp.keymask.mask,
        temp.route, temp.source);
    put_entry(routing_table_sdram_stores_get_entry(b), a);
    put_entry(&temp, b);
    entry_t temp2 = *routing_table_sdram_stores_get_entry(b);
    log_debug("before %u %u %u %u", temp2.keymask.key, temp2.keymask.mask,
        temp2.route, temp2.source);
}

//! \brief prints the header object for debug purposes
//! \param[in] header: the header to print
void print_header(header_t *header) {
    log_info("app_id = %d", header->app_id);
    log_info(
        "compress_only_when_needed = %d",
        header->compress_only_when_needed);
    log_info(
        "compress_as_much_as_possible = %d",
        header->compress_as_much_as_possible);
    log_info("table_size = %d", header->table_size);
}

//! \brief Read a new copy of the routing table from SDRAM.
//! \param[in] table : the table containing router table entries
//! \param[in] header: the header object
static void read_table(header_t *header) {
    // Copy the size of the table
    table->size = header->table_size;

    // Allocate space for the routing table entries
    table->entries = MALLOC(table->size * sizeof(entry_t));

    // Copy in the routing table entries
    spin1_memcpy((void *) table->entries, (void *) header->entries,
            sizeof(entry_t) * table->size);
}

//! \brief Load a routing table to the router.
//! \param[in] table: the table containing router table entries
//! \param[in] app_id: the app id for the routing table entries to be loaded
//! under
//! \return bool saying if the table was loaded into the router or not
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
        rtr_mc_set(entry_id + i, entry.keymask.key, entry.keymask.mask,
                route);
    }

    // Indicate we were able to allocate routing table entries.
    return TRUE;
}

//! \brief frees memory allocated and calls spin1 exit and sets the user0
//! error code correctly.
//! \param[in] header the header object
//! \param[in] table the data object holding the routing table entries
void cleanup_and_exit(header_t *header) {
    // Free the memory used by the routing table.
    log_debug("free sdram blocks which held router tables");
    FREE(table->entries);
    // Free the block of SDRAM used to load the routing table.
    sark_xfree(sv->sdram_heap, (void *) header, ALLOC_LOCK);

    log_info("completed router compressor");
    sark.vcpu->user0 = 0;
    spin1_exit(0);
}

void minimise(uint32_t target_length);

//! \brief the callback for setting off the router compressor
void compress_start() {
    uint32_t size_original;

    log_info("Starting on chip router compressor");

    // Prepare to minimise the routing tables
    log_debug("looking for header using tag %u app_id %u", 1, sark_app_id());
    header_t *header = (header_t *) sark_tag_ptr(1, sark_app_id());
    log_debug("reading data from 0x%08x", (uint32_t) header);
    print_header(header);

    // set the flag to something none useful
    sark.vcpu->user0 = 20;

    // Load the routing table
    log_debug("start reading table");
    read_table(header);
    log_debug("finished reading table");

    // Store intermediate sizes for later reporting (if we fail to minimise)
    size_original = Routing_table_sdram_get_n_entries();

    // Try to load the table
    log_debug("check if compression is needed and compress if needed");
    if (header->compress_only_when_needed == 1){
        if (load_routing_table(header->app_id)){
            cleanup_and_exit(header);
        } else {
            // Otherwise remove default routes.
            log_debug("remove default routes from minimiser");
            remove_default_routes_minimise(table);
            if (load_routing_table(header->app_id)){
                cleanup_and_exit(header);
            } else {
                //Opps we need the defaults back before trying compression
                log_debug("free the tables entries");
                FREE(table->entries);
               read_table(header);
            }
        }
    }

    // Get the target length of the routing table
    log_debug("acquire target length");
    uint32_t target_length = 0;
    if (header->compress_as_much_as_possible == 0) {
        target_length = rtr_alloc_max();
    }
    log_info("target length of %d", target_length);

    // Perform the minimisation
    log_debug("minimise");
    minimise(target_length);
    log_debug("done minimise");

    // report size to the host for provenance aspects
    log_info("has compressed the router table to %d entries",
        Routing_table_sdram_get_n_entries());

    // Try to load the routing table
    log_debug("try loading tables");
    if (load_routing_table(header->app_id)) {
        cleanup_and_exit(header);
    } else {
        // Otherwise give up and exit with an error
        log_error(
            "Failed to minimise routing table to fit %u entries. "
            "(Original table: %u after compression: %u).",
            rtr_alloc_max(), size_original, Routing_table_sdram_get_n_entries());

        // Free the block of SDRAM used to load the routing table.
        log_debug("free sdram blocks which held router tables");
        FREE((void *) header);

        // set the failed flag and exit
        sark.vcpu->user0 = 1;
        spin1_exit(0);
    }
}

#endif //__MINIMISE_H__

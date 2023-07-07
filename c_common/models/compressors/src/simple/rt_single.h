/*
 * Copyright (c) 2017 The University of Manchester
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

#include <stdbool.h>
#include <spin1_api.h>
#include <spin1_api_params.h>
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

//! DMA read flags
static const uint32_t DMA_READ_FLAGS =
        DMA_WIDTH << 24 | DMA_BURST_SIZE << 21 | DMA_READ << 19;

//! Value of the masked DMA status register when transfer is complete
#define DMA_COMPLETE 0x400

//! Mask to apply to the DMA status register to check for completion
#define DMA_CHECK_MASK 0x401

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
    log_debug("app_id = %d", header->app_id);
    log_debug("compress_as_much_as_possible = %d",
            header->compress_as_much_as_possible);
    log_debug("table_size = %d", header->table_size);
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
        log_error("Unable to allocate routing table of size %u\n", table->size);
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
            log_warning("failed to set a router table entry at index %d",
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

//! \brief Gets a pointer to several entries
//! \param[in] start_entry: The first entry to get
//! \param[in] n_entries: The number of entries to get
//! \param[out] output: Where to put the entries read - must have enough space!
//! \return: Whether the entries are available now, or should be waited for
bool routing_table_get_entries(uint32_t start_entry, uint32_t n_entries,
        entry_t *output) {
    uint32_t length = n_entries * sizeof(entry_t);
    uint32_t desc = DMA_READ_FLAGS | length;
    dma[DMA_ADRS] = (uint32_t) &table->entries[start_entry];
    dma[DMA_ADRT] = (uint32_t) output;
    dma[DMA_DESC] = desc;
    return false;
}


//! \brief Is there a DMA currently running?
//! \return True if there is something transferring now.
static inline bool dma_done(void) {
    return (dma[DMA_STAT] & DMA_CHECK_MASK) == DMA_COMPLETE;
}

//! \brief Waits for the last transfer from routing_table_get_entries to complete
//! \details Returns immediately if the last transfer is already done
void routing_table_wait_for_last_transfer(void) {
    while (!dma_done()) {
        continue;
    }
    dma[DMA_CTRL] = 0x8;
}

#endif //__RT_SINGLE_H__

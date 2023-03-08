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

/**
 * \file
 *
 * \brief SpiNNaker routing table minimisation.
 *
 * Minimises a routing table loaded into SDRAM and load the minimised table into
 * the router using the specified application ID.
 *
 * the exit code is stored in the user0 register
 *
 * The memory address with tag "1" is expected contain the following struct
 * (entry_t is defined in `routing_table.h` but is described below).
 */
#include <stdbool.h>
#include <debug.h>
#include "../common/routing_table.h"
#include "common/minimise.h"

//! Absolute maximum number of routes that we may produce
#define MAX_NUM_ROUTES 1023

//! The index of the next place in the compressed table to write a route.
static uint32_t write_index;

//! The index of the first route after the ones being compressed in this step.
static int remaining_index;

//! Table of routes being produced.
static uint32_t routes[MAX_NUM_ROUTES];

//! Route frequency histogram.
static uint32_t routes_frequency[MAX_NUM_ROUTES] = {0};

//! Count of unique routes (as opposed to routes with just different key_masks).
static uint32_t routes_count;

//! Space for caching routes while going through them
static entry_t route_cache[2][MAX_NUM_ROUTES];

//! \brief Merges a single pair of route entries.
//! \param[in] entry1: The first route to merge.
//! \param[in] entry2: The second route to merge.
//! \return A new merged route that will eventually replace the two inputs.
static inline entry_t merge(const entry_t* entry1, const entry_t* entry2) {
    entry_t result = {
        .key_mask = key_mask_merge(entry1->key_mask, entry2->key_mask),
        .route = entry1->route,
        .source = (entry1->source == entry2->source ? entry1->source : 0)
    };
    return result;
}

//! \brief Write an entry to a specific index
//! \param[in] entry: The entry to write
//! \param[in] index: Where to write it.
static inline void _entry(const entry_t* entry, int index) {
    entry_t* e_ptr = routing_table_get_entry(index);
    e_ptr->key_mask = entry->key_mask;
    e_ptr->route = entry->route;
    e_ptr->source = entry->source;
}

static inline int transfer_next(int start_index, int n_items, uint32_t cache) {
    if (n_items == 0) {
        return 0;
    }
    uint32_t next_items = n_items;
    if (n_items > MAX_NUM_ROUTES) {
        next_items = MAX_NUM_ROUTES;
    }
    routing_table_get_entries(start_index, next_items, route_cache[cache]);
    return next_items;
}

//! \brief Cancel any outstanding DMA transfers
static inline void cancel_dmas(void) {
    dma[DMA_CTRL] = 0x3F;
    while (dma[DMA_STAT] & 0x1) {
        continue;
    }
    dma[DMA_CTRL] = 0xD;
    while (dma[DMA_CTRL] & 0xD) {
        continue;
    }
}

//! \brief Finds if two routes can be merged.
//! \details If they are merged, the entry at the index of left is also
//!     replaced with the merged route.
//! \param[in] left: The index of the first route to consider.
//! \param[in] index: The index of the second route to consider.
//! \return True if the entries were merged
static inline bool find_merge(int left, int index) {
    cancel_dmas();
    const entry_t *entry1 = routing_table_get_entry(left);
    const entry_t *entry2 = routing_table_get_entry(index);
    const entry_t merged = merge(entry1, entry2);

    uint32_t size = routing_table_get_n_entries();
    uint32_t items_to_go = size - remaining_index;
    uint32_t next_n_items = transfer_next(remaining_index, items_to_go, 0);
    uint32_t next_items_to_go = items_to_go - next_n_items;
    uint32_t next_start = remaining_index + next_n_items;
    bool dma_in_progress = true;
    uint32_t read_cache = 0;
    uint32_t write_cache = 1;
    while (items_to_go > 0) {

        // Finish any outstanding transfer
        if (dma_in_progress) {
            routing_table_wait_for_last_transfer();
            dma_in_progress = false;
        }

        // Get the details of the last transfer done
        uint32_t n_items = next_n_items;
        uint32_t cache = read_cache;

        // Start the next transfer if needed
        if (next_items_to_go > 0) {
            next_n_items = transfer_next(next_start, next_items_to_go, write_cache);
            next_items_to_go -= next_n_items;
            next_start += next_n_items;
            dma_in_progress = true;
            write_cache = (write_cache + 1) & 0x1;
            read_cache = (read_cache + 1) & 0x1;
        }

        // Check the items now available
        entry_t *entries = route_cache[cache];
        for (uint32_t i = 0; i < n_items; i++) {
            if (key_mask_intersect(entries[i].key_mask, merged.key_mask)) {
                if (dma_in_progress) {
                    routing_table_wait_for_last_transfer();
                }
                return false;
            }
        }

        items_to_go = next_items_to_go;
    }
    routing_table_put_entry(&merged, left);
    return true;
}

//! \brief Does the actual routing compression
//! \param[in] left: The start of the section of table to compress
//! \param[in] right: The end of the section of table to compress
static inline void compress_by_route(int left, int right) {
    while (left < right) {
        bool merged = false;

        for (int index = left + 1; index <= right; index++) {
            merged = find_merge(left, index);
            if (merged) {
                routing_table_copy_entry(index, right--);
                break;
            }
        }
        if (!merged) {
            routing_table_copy_entry(write_index++, left++);
        }
    }
    if (left == right) {
        routing_table_copy_entry(write_index++, left);
    }
}

//! \brief Implementation of insertion sort for routes based on frequency.
//! \details The routes must be non-overlapping pre-minimisation routes.
static void sort_routes(void) {
    uint32_t i, j;

    for (i = 1; i < routes_count; i++) {
        // The entry we're going to move is "taken out"
        uint32_t r_tmp = routes[i];
        uint32_t rf_tmp = routes_frequency[i];

        // The entries below it that are larger are shuffled up
        for (j = i; j > 0 && routes_frequency[j - 1] > rf_tmp; j--) {
            routes[j] = routes[j - 1];
            routes_frequency[j] = routes_frequency[j - 1];
        }

        // The entry is dropped back into place
        routes[j] = r_tmp;
        routes_frequency[j] = rf_tmp;
    }
}

//! \brief Computes route histogram
//! \param[in] index: The index of the cell to update
//! \return Whether the update succeeded
static inline bool update_frequency(int index) {
    uint32_t route = routing_table_get_entry(index)->route;
    for (uint i = 0; i < routes_count; i++) {
        if (routes[i] == route) {
            routes_frequency[i]++;
            return true;
        }
    }
    routes[routes_count] = route;
    routes_frequency[routes_count] = 1;
    routes_count++;
    if (routes_count >= MAX_NUM_ROUTES) {
        if (standalone()) {
            log_error("Too many different routes to compress found %d "
                      "compared to max legal of %d",
                      routes_count, MAX_NUM_ROUTES);
        }
        return false;
    }
    return true;
}

static inline uint32_t find_route_index(uint32_t route) {
    for (uint32_t i = 0; i < routes_count; i++) {
        if (route == routes[i]) {
            return i;
        }
    }
    log_error("Route 0x%08x not found!", route);
    for (uint32_t i = 0; i < routes_count; i++) {
        log_error("Route %u = 0x%08x", i, routes[i]);
    }
    rt_error(RTE_SWERR);
    return 0xFFFFFFFF;
}

//! \brief Implementation of insertion sort for routes based on route
//!     information
//! \param[in] table_size: The size of the routing table
void sort_table(void) {
    if (routes_count == 0) {
        return;
    }

    // Set up a pointer for each of the routes
    uint16_t route_offset[routes_count];
    uint16_t route_end[routes_count];
    uint32_t offset = 0;
    for (uint32_t i = 0; i < routes_count; i++) {
        route_offset[i] = offset;
        offset += routes_frequency[i];
        route_end[i] = offset - 1;
    }

    // Go through and move things into position
    uint32_t pos = 0;
    uint32_t pos_index = 0;
    uint32_t next_index_offset = routes_frequency[0];
    uint32_t n_entries = routing_table_get_n_entries();
    while (pos < n_entries) {
        // Get the entry
        entry_t entry = *routing_table_get_entry(pos);

        // Where does the route need to go
        uint32_t route_index = find_route_index(entry.route);

        // Where are we reading from?
        uint32_t read_index = pos_index;

        // If we are in the right region
        bool skip = false;
        if (route_index == read_index) {
            // If we already put this item here, don't move it
            if (pos < route_offset[route_index]) {
                skip = true;
            }
        }

        // Keep swapping things until they are in the right place
        while (!skip) {

            // Find the place to put the route in its group
            uint32_t new_pos = route_offset[route_index];
            if (new_pos >= n_entries) {
                log_error("New table position %u out of range!", new_pos);
                rt_error(RTE_SWERR);
            }

            if (new_pos > route_end[route_index]) {
                log_error("New table position %u of region %u is out of range!",
                        new_pos, route_index);
                rt_error(RTE_SWERR);
            }
            route_offset[route_index] += 1;

            // Swap out the existing entry with the new one
            entry_t old_entry = *routing_table_get_entry(new_pos);
            routing_table_put_entry(&entry, new_pos);

            // We can quit because we should have moved this one
            if (new_pos <= pos) {
                break;
            }
            entry = old_entry;
            read_index = route_index;

            // Find the index of the item we swapped out so it can be swapped next
            route_index = find_route_index(entry.route);
        }

        // Where are we next
        pos++;
        if (pos == next_index_offset) {
            pos_index += 1;
            next_index_offset += routes_frequency[pos_index];
        }
    }
}

//! \brief Implementation of minimise()
//! \param[in] target_length: ignored
//! \param[out] failed_by_malloc: Never changed but required by api
//! \param[in] stop_compressing: Variable saying if the compressor should stop
//!    and return false; _set by interrupt_ DURING the run of this method!
//! \return Whether minimisation succeeded
bool minimise_run(int target_length, bool *failed_by_malloc,
        volatile bool *stop_compressing) {
    use(failed_by_malloc);
    use(target_length);

    // Verify constant used to build arrays is correct
    if (MAX_NUM_ROUTES != rtr_alloc_max()){
        log_error("MAX_NUM_ROUTES %d != rtr_alloc_max() %d",
                MAX_NUM_ROUTES, rtr_alloc_max());
        return false;
    }
    int table_size = routing_table_get_n_entries();

    routes_count = 0;

    for (int index = 0; index < table_size; index++) {
        if (!update_frequency(index)) {
            return false;
        }
    }

    log_debug("before sort %u", routes_count);
    for (uint i = 0; i < routes_count; i++) {
        log_debug("%u", routes[i]);
    }

    sort_routes();
    if (*stop_compressing) {
        log_info("Stopping as asked to stop");
        return false;
    }

    log_debug("after sort %u", routes_count);
    for (uint i = 0; i < routes_count; i++) {
        log_debug("%u", routes[i]);
    }

    log_debug("do sort_table by route %u", table_size);
    tc[T2_LOAD] = 0xFFFFFFFF;
    tc[T2_CONTROL] = 0x83;
    sort_table();
    uint32_t duration = 0xFFFFFFFF - tc[T2_COUNT];
    tc[T2_CONTROL] = 0;
    log_info("Sorting table took %u clock cycles", duration);
    if (*stop_compressing) {
        log_info("Stopping before compression as asked to stop");
        return false;
    }

    write_index = 0;
    int max_index = table_size - 1;
    int left = 0;

    while (left <= max_index) {
        int right = left;
        uint32_t left_route = routing_table_get_entry(left)->route;
        log_debug("A %u %u %u %u", left, max_index, right, left_route);
        while ((right < table_size - 1) &&
                routing_table_get_entry(right+1)->route ==
                        left_route) {
            right++;
        }
        remaining_index = right + 1;
        log_debug("compress %u %u", left, right);
        tc[T2_LOAD] = 0xFFFFFFFF;
        tc[T2_CONTROL] = 0x83;
        compress_by_route(left, right);
        duration = 0xFFFFFFFF - tc[T2_COUNT];
        tc[T2_CONTROL] = 0;
        log_info("Compressing %u routes took %u", right - left + 1, duration);
        if (write_index > rtr_alloc_max()){
            if (standalone()) {
                log_error("Compression not possible as already found %d "
                          "entries where max allowed is %d",
                          write_index, rtr_alloc_max());
            }
            return false;
        }
        if (*stop_compressing) {
            log_info("Stopping during compression as asked to stop");
            return false;
        }
        left = right + 1;
    }

    log_debug("done %u %u", table_size, write_index);

    //for (uint i = 0; i < write_index; i++) {
    //    entry_t *entry1 = routing_table_get_entry(i);
    //    log_info("%u route:%u source:%u key:%u mask:%u",i, entry1->route,
    //      entry1->source, entry1->key_mask.key, entry1->key_mask.mask);
    //}
    routing_table_remove_from_size(table_size-write_index);
    log_info("now %u", routing_table_get_n_entries());
    return true;
}

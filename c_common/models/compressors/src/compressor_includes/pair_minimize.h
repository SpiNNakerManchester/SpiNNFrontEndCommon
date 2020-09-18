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

/**
 * \file
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
#include <stdbool.h>
#include "common-typedefs.h"

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

//! \brief Merge a single pair of route entries.
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
static inline void _entry(const entry_t* entry, uint32_t index) {
    entry_t* e_ptr = routing_table_get_entry(index);
    e_ptr->key_mask = entry->key_mask;
    e_ptr->route = entry->route;
    e_ptr->source = entry->source;
}

//! \brief Find if two routes can be merged.
//! \details If they are merged, the entry at the index of left is also
//!     replaced with the merged route.
//! \param[in] left: The index of the first route to consider.
//! \param[in] index: The index of the second route to consider.
//! \return Whether the entries were merged
static inline bool find_merge(uint32_t left, uint32_t index) {
    const entry_t *entry1 = routing_table_get_entry(left);
    const entry_t *entry2 = routing_table_get_entry(index);
    const entry_t merged = merge(entry1, entry2);

    for (uint32_t i = remaining_index; i < routing_table_get_n_entries(); i++) {
        const entry_t *check_entry = routing_table_get_entry(i);
        if (key_mask_intersect(check_entry->key_mask, merged.key_mask)) {
            return false;
        }
    }
    routing_table_put_entry(&merged, left);
    return true;
}

//! \brief Do the actual routing compression
//! \param[in] left: The start of the section of table to compress
//! \param[in] right: The end of the section of table to compress
static inline void compress_by_route(uint32_t left, uint32_t right) {
    while (left < right) {
        bool merged = false;

        for (uint32_t index = left + 1; index <= right; index++) {
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

//! \brief Compare routes based on their index
//! \param[in] route_a: The first route
//! \param[in] route_b: The second route
//! \return Ordering term (-1, 0, 1)
static inline int compare_routes(uint32_t route_a, uint32_t route_b) {
    if (route_a == route_b) {
        return 0;
    }
    for (uint32_t i = 0; i < routes_count; i++) {
        if (routes[i] == route_a) {
            return 1;
        }
        if (routes[i] == route_b) {
            return -1;
        }
    }
    log_error("Routes not found %u %u", route_a, route_b);
    // set the failed flag and exit
    malloc_extras_terminate(EXIT_FAIL);

    return 0;
}

//! \brief Implementation of sort for routes based on route information
//! \details Uses insertion sort.
//! \param[in] table_size: the number of entries in the table
static void sort_table(uint32_t table_size) {
    uint32_t i, j;

    for (i = 1; i < table_size; i++) {
        entry_t tmp = *routing_table_get_entry(i);
        for (j = i; j > 0 && compare_routes(
                routing_table_get_entry(j - 1)->route, tmp.route) > 0; j--) {
            routing_table_put_entry(routing_table_get_entry(j - 1), j);
        }
        routing_table_put_entry(&tmp, j);
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

//! \brief Compute the route histogram
//! \param[in] index: The index of the cell to update
//! \return Whether the update was successful
static inline bool update_frequency(uint32_t index) {
    uint32_t route = routing_table_get_entry(index)->route;
    for (uint32_t i = 0; i < routes_count; i++) {
        if (routes[i] == route) {
            routes_frequency[i]++;
            return true;
        }
    }
    routes[routes_count] = route;
    routes_frequency[routes_count] = 1;
    routes_count++;
    if (routes_count >= MAX_NUM_ROUTES) {
        log_error("Best compression was %d compared to max legal of %d",
                routes_count, MAX_NUM_ROUTES);
        return false;
    }
    return true;
}

//! \brief Implementation of minimise()
//! \param[in] target_length: ignored
//! \param[out] failed_by_malloc: Never changed but required by API
//! \param[in] stop_compressing: Variable saying if the compressor should stop
//!    and return false; _set by interrupt_ DURING the run of this method!
//! \return Whether minimisation succeeded
bool minimise_run(UNUSED uint32_t target_length, UNUSED bool *failed_by_malloc,
        volatile bool *stop_compressing) {
    // Verify constant used to build arrays is correct
    if (MAX_NUM_ROUTES != rtr_alloc_max()) {
        log_error("MAX_NUM_ROUTES %d != rtr_alloc_max() %d",
                MAX_NUM_ROUTES, rtr_alloc_max());
        return false;
    }
    uint32_t table_size = routing_table_get_n_entries();
    if (table_size < 1) {
        log_info("empty routing table; nothing to do");
        return true;
    }

    routes_count = 0;

    for (int index = 0; index < table_size; index++) {
        if (!update_frequency(index)) {
            return false;
        }
    }

    log_debug("before sort %u", routes_count);
    for (uint32_t i = 0; i < routes_count; i++) {
        log_debug("%u", routes[i]);
    }

    sort_routes();
    if (*stop_compressing) {
        log_info("Stopping as asked to stop");
        return false;
    }

    log_debug("after sort %u", routes_count);
    for (uint32_t i = 0; i < routes_count; i++) {
        log_debug("%u", routes[i]);
    }

    log_debug("do sort_table by route %u", table_size);
    sort_table(table_size);
    if (*stop_compressing) {
        log_info("Stopping before compression as asked to stop");
        return false;
    }

    write_index = 0;
    uint32_t max_index = table_size - 1;
    uint32_t left = 0;

    while (left <= max_index) {
        uint32_t right = left;
        uint32_t left_route = routing_table_get_entry(left)->route;
        log_debug("A %u %u %u %u", left, max_index, right, left_route);
        while ((right < table_size - 1) &&
                routing_table_get_entry(right+1)->route == left_route) {
            right++;
        }
        remaining_index = right + 1;
        log_debug("compress %u %u", left, right);
        compress_by_route(left, right);
        if (write_index > rtr_alloc_max()){
            log_error("Compression not possible as already found %d entries "
            "where max allowed is %d", write_index, rtr_alloc_max());
            return false;
        }
        if (*stop_compressing) {
            log_info("Stopping during compression as asked to stop");
            return false;
        }
        left = right + 1;
    }

    log_debug("done %u %u", table_size, write_index);

    routing_table_remove_from_size(table_size-write_index);
    log_debug("now %u", routing_table_get_n_entries());
    return true;
}

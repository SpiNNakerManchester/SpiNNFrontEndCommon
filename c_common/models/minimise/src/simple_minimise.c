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
#include <spin1_api.h>
#include <debug.h>
#include <common-typedefs.h>
#include <malloc_extras.h>
#include "unordered_remove_default_routes.h"
#include "minimise.h"

#include <spin1_api.h>
#include <debug.h>
#include <common-typedefs.h>
#include "unordered_remove_default_routes.h"
#include "minimise.h"

//! Absolute maximum number of routes that we may produce
#define MAX_NUM_ROUTES 1023

//! The index of the next place in the compressed table to write a route.
static int write_index;

//! The index of the first route after the ones being compressed in this step.
static int remaining_index;

//! Table of routes being produced.
static uint32_t routes[MAX_NUM_ROUTES];

//! Route frequency histogram.
static uint32_t routes_frequency[MAX_NUM_ROUTES] = {0};

//! Count of unique routes (as opposed to routes with just different keymasks).
static uint32_t routes_count;

//! \brief Merges a single pair of route entries.
//! \param[in] entry1: The first route to merge.
//! \param[in] entry2: The second route to merge.
//! \return A new merged route that will eventually replace the two inputs.
static inline entry_t merge(const entry_t* entry1, const entry_t* entry2) {
    entry_t result = {
        .keymask = keymask_merge(entry1->keymask, entry2->keymask),
        .route = entry1->route,
        .source = (entry1->source == entry2->source ? entry1->source : 0)
    };
    return result;
}

//! \brief Finds if two routes can be merged.
//! \details If they are merged, the entry at the index of left is also
//!     replaced with the merged route.
//! \param[in] left: The index of the first route to consider.
//! \param[in] index: The index of the second route to consider.
//! \return True if the entries were merged
static inline bool find_merge(int left, int index) {
    const entry_t *entry1 = routing_table_sdram_stores_get_entry(left);
    const entry_t *entry2 = routing_table_sdram_stores_get_entry(index);
    const entry_t merged = merge(entry1, entry2);

    for (int check = remaining_index;
            check < routing_table_sdram_get_n_entries();
            check++) {
        const entry_t *check_entry =
                routing_table_sdram_stores_get_entry(check);
        if (keymask_intersect(check_entry->keymask, merged.keymask)) {
            return false;
        }
    }
    put_entry(&merged, left);
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
                copy_entry(index, right--);
                break;
            }
        }
        if (!merged) {
            copy_entry(write_index++, left++);
        }
    }
    if (left == right) {
        copy_entry(write_index++, left);
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
    for (uint i = 0; i < routes_count; i++) {
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

//! \brief Implementation of quicksort for routes based on route information
//! \param[in] low: the first index into the array of the section to sort;
//!                 inclusive lowest index
//! \param[in] high: the second index into the array of the section to sort;
//!                  exclusive highest index
static void quicksort_table(int low, int high) {
    if (low < high - 1) {
        // pick low entry for the pivot
        uint32_t pivot = routing_table_sdram_stores_get_entry(low)->route;
        // Location of entry currently being checked.
        // At the end check will point to either
        //     the right most entry with a value greater than the pivot
        //     or high indicating there are no entries greater than the pivot
        //Start at low + 1 as entry low is the pivot
        int check = low + 1;
        // Location to write any smaller values to
        // Will always point to most left entry with pivot value
        // If we find any less than swap with the first pivot
        int l_write = low;
        // Location to write any greater values to
        // Until the algorithm ends this will point to an unsorted value
        // if we find any higher swap with last entry in the sort section
        int h_write = high - 1;

        while (check <= h_write) {
            uint32_t check_route =
                    routing_table_sdram_stores_get_entry(check)->route;
            int compare = compare_routes(check_route, pivot);
            if (compare < 0) {
                // swap the check to the left, and then
                // move the check on as known to be pivot value
                swap_entries(l_write++, check++);
            } else if (compare > 0) {
                // swap the check to the right
                // Do not move the check as it has an unknown value
                swap_entries(h_write--, check);
            } else {
                // Move check as it has the pivot value
                check++;
            }
        }
        // Now sort the ones less than or more than the pivot
        quicksort_table(low, l_write);
        quicksort_table(check, high);
    }
}

//! \brief Swap two routes
//!
//! Also swaps the corresponding information in routes_frequency
//!
//! \param[in] index_a: The index of the first route
//! \param[in] index_b: The index of the second route
static inline void swap_routes(int index_a, int index_b) {
    uint32_t temp = routes_frequency[index_a];
    routes_frequency[index_a] = routes_frequency[index_b];
    routes_frequency[index_b] = temp;
    temp = routes[index_a];
    routes[index_a] = routes[index_b];
    routes[index_b] = temp;
}

//! \brief Implementation of quicksort for routes based on frequency.
//!
//! The routes must be non-overlapping pre-minimisation routes.
//!
//! \param[in] low: the first index into the array of the section to sort;
//!                 inclusive low point of range
//! \param[in] high: the second index into the array of the section to sort;
//!                  exclusive high point of range
static void quicksort_route(int low, int high) {
    if (low < high - 1) {
        // pick low entry for the pivot
        uint pivot = routes_frequency[low];
        // Location of entry currently being checked.
        // At the end check will point to either
        //     the right most entry with a value greater than the pivot
        //     or high indicating there are no entries greater than the pivot
        //Start at low + 1 as entry low is the pivot
        int check = low + 1;
        // Location to write any smaller values to
        // Will always point to most left entry with pivot value
        // If we find any less than swap with the first pivot
        int l_write = low;
        // Location to write any greater values to
        // Until the algorithm ends this will point to an unsorted value
        // if we find any higher swap with last entry in the sort section
        int h_write = high -1;

        while (check <= h_write) {
            if (routes_frequency[check] < pivot) {
                // swap the check to the left, and then
                // move the check on as known to be pivot value
                swap_routes(l_write++, check++);
            } else if (routes_frequency[check] > pivot) {
                // swap the check to the right
                swap_routes(h_write--, check);
                // Do not move the check as it has an unknown value
            } else {
                // Move check as it has the pivot value
                check++;
            }
        }
        // Now sort the ones less than or more than the pivot
        quicksort_route(low, l_write);
        quicksort_route(check, high);
    }
}

//! \brief Computes route histogram
//! \param[in] index: The index of the cell to update
static inline void update_frequency(int index) {
    uint32_t route = routing_table_sdram_stores_get_entry(index)->route;
    for (uint i = 0; i < routes_count; i++) {
        if (routes[i] == route) {
            routes_frequency[i]++;
            return;
        }
    }
    routes[routes_count] = route;
    routes_frequency[routes_count] = 1;
    routes_count++;
    if (routes_count >= MAX_NUM_ROUTES) {
        log_error("%d Unigue routes compression IMPOSSIBLE",
                MAX_NUM_ROUTES + 1);
        // set the failed flag and exit
        malloc_extras_terminate(EXITED_CLEANLY);
    }
}

//! \brief Implementation of minimise()
//! \param[in] target_length: ignored
static inline void simple_minimise(uint32_t target_length) {
	use(target_length);
    int table_size = routing_table_sdram_get_n_entries();

    routes_count = 0;

    for (int index = 0; index < table_size; index++) {
        update_frequency(index);
    }

    log_info("before sort %u", routes_count);
    for (uint i = 0; i < routes_count; i++) {
        log_debug("%u", routes[i]);
    }

    quicksort_route(0, routes_count);

    log_info("after sort %u", routes_count);
    for (uint i = 0; i < routes_count; i++) {
        log_debug("%u", routes[i]);
    }

    log_info("do quicksort_table by route %u", table_size);
    quicksort_table(0, table_size);

    write_index = 0;
    int max_index = table_size - 1;
    int left = 0;

    while (left <= max_index) {
        int right = left;
        uint32_t left_route = routing_table_sdram_stores_get_entry(left)->route;
        log_info("A %u %u %u %u", left, max_index, right, left_route);
        while ((right < table_size - 1) &&
                routing_table_sdram_stores_get_entry(right+1)->route ==
                        left_route) {
            right++;
        }
        remaining_index = right + 1;
        log_info("compress %u %u", left, right);
        compress_by_route(left, right);
        left = right + 1;
    }

    log_info("done %u %u", table_size, write_index);

    routing_table_remove_from_size(table_size-write_index);
    log_info("now %u", routing_table_sdram_get_n_entries());
}

//! \brief Minimises the routing table.
//! \param[in] target_length:
//!     How many entries we want the table to have after minimisation
void minimise(uint32_t target_length) {
    simple_minimise(target_length);
}

//! \brief the main entrance.
void c_main(void) {
    log_info("%u bytes of free DTCM", sark_heap_max(sark.heap, 0));
    malloc_extras_turn_off_safety();

    // kick-start the process
    spin1_schedule_callback(compress_start, 0, 0, 3);

    // go
    spin1_start(SYNC_NOWAIT);	//##
}

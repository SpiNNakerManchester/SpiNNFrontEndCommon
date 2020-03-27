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

#include <spin1_api.h>
#include <debug.h>
#include <common-typedefs.h>
#include "platform.h"
#include "unordered_remove_default_routes.h"
#include "minimise.h"
/*****************************************************************************/
/* SpiNNaker routing table minimisation.
 *
 * Minimise a routing table loaded into SDRAM and load the minimised table into
 * the router using the specified application ID.
 *
 * the exit code is stored in the user0 register
 *
 * The memory address with tag "1" is expected contain the following struct
 * (entry_t is defined in `routing_table.h` but is described below).
 */

static int write_index, previous_index, remaining_index, max_index;
static uint32_t routes[1023];
static uint32_t routes_frequency[1023] = {0};
static uint32_t routes_count;

static inline entry_t merge(entry_t* entry1, entry_t* entry2) {
    entry_t result;
    result.keymask = keymask_merge(entry1->keymask, entry2->keymask);
    result.route = entry1->route;
    if (entry1->source == entry2->source){
        result.source = entry1->source;
    } else {
        result.source = 0;
    }
    return result;
}

static inline bool find_merge(int left, int index) {
    entry_t* entry1 = routing_table_sdram_stores_get_entry(left);
    entry_t* entry2 = routing_table_sdram_stores_get_entry(index);

    entry_t merged = merge(entry1, entry2);
    //for (int check = 0; check < previous_index; check++) {
    //    entry_t* check_entry = routing_table_sdram_stores_get_entry(check);
    //    if (keymask_intersect(check_entry->keymask, merged.keymask)) {
    //        return false;
    //    }
    //}
    for (int check = remaining_index; check < Routing_table_sdram_get_n_entries(); check++) {
        entry_t* check_entry = routing_table_sdram_stores_get_entry(check);
        if (keymask_intersect(check_entry->keymask, merged.keymask)) {
            return false;
        }
    }
    put_entry(&merged, left);
    return true;
}

static inline void compress_by_route(int left, int right){
    int index;
    bool merged;
    merged = false;

    while (left < right) {
        index = left + 1;
        while (index <= right){
            merged = find_merge(left, index);
            if (merged) {
                copy_entry(index, right);
                right -= 1;
                break;
            }
            index += 1;
        }
        if (!merged) {
            copy_entry(write_index, left);
            write_index += 1;
            left += 1;
        }
    }
    if (left == right){
        copy_entry(write_index, left);
        write_index += 1;
    }
}

static inline int compare_routes(uint32_t route_a, uint32_t route_b){
    if (route_a == route_b) {
        return 0;
    }
    for (uint i = 0; i < routes_count; i++) {
        if (routes[i] == route_a){
            return 1;
        }
        if (routes[i] == route_b){
            return -1;
        }
    }
    log_error("Routes not found %u %u", route_a, route_b);
    // set the failed flag and exit
    sark.vcpu->user0 = 1;
    spin1_exit(0);

    return 0;
}

static void quicksort_table(int low, int high){
    // Sorts the entries in place based on route
    // param low: Inclusive lowest index to consider
    // param high: Exclusive highest index to consider

    // Location to write any smaller values to
    // Will always point to most left entry with pivot value
    int l_write;

    // Location of entry currently being checked.
    // At the end check will point to either
    //     the right most entry with a value greater than the pivot
    //     or high indicating there are no entries greater than the pivot
    int check;

    // Location to write any greater values to
    // Until the algorithm ends this will point to an unsorted value
    int h_write;

    if (low < high - 1) {
        // pick low entry for the pivot
        uint32_t pivot = routing_table_sdram_stores_get_entry(low)->route;
        //Start at low + 1 as entry low is the pivot
        check = low + 1;
        // If we find any less than swap with the first pivot
        l_write = low;
        // if we find any higher swap with last entry in the sort section
        h_write = high -1;

        while (check <= h_write){
            uint32_t check_route = routing_table_sdram_stores_get_entry(check)->route;
            int compare = compare_routes(check_route, pivot);
            if (compare < 0){
                // swap the check to the left
                swap_entries(l_write, check);
                l_write++;
                // move the check on as known to be pivot value
                check++;
            } else if (compare > 0) {
                // swap the check to the right
                swap_entries(h_write, check);
                h_write--;
                // Do not move the check as it has an unknown value
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

static inline void swap_routes(int index_a, int index_b){
    uint32_t  temp = routes_frequency[index_a];
    routes_frequency[index_a] = routes_frequency[index_b];
    routes_frequency[index_b] = temp;
    temp = routes[index_a];
    routes[index_a] = routes[index_b];
    routes[index_b] = temp;
}

static void quicksort_route(int low, int high){
    // Sorts the routes and frequencies in place based on frequency
    // param low: Inclusive lowest index to consider
    // param high: Exclusive highest index to consider

    // Location to write any smaller values to
    // Will always point to most left entry with pivot value
    int l_write;

    // Location of entry currently being checked.
    // At the end check will point to either
    //     the right most entry with a value greater than the pivot
    //     or high indicating there are no entries greater than the pivot
    int check;

    // Location to write any greater values to
    // Until the algorithm ends this will point to an unsorted value
    int h_write;

    if (low < high - 1) {
        // pick low entry for the pivot
        uint pivot = routes_frequency[low];
        //Start at low + 1 as entry low is the pivot
        check = low + 1;
        // If we find any less than swap with the first pivot
        l_write = low;
        // if we find any higher swap with last entry in the sort section
        h_write = high -1;

        while (check <= h_write){
            if (routes_frequency[check] < pivot){
                // swap the check to the left
                swap_routes(l_write, check);
                l_write++;
                // move the check on as known to be pivot value
                check++;
            } else if (routes_frequency[check] > pivot) {
                // swap the check to the right
                swap_routes(h_write, check);
                h_write--;
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

static inline void update_frequency(int index){
    uint32_t route = routing_table_sdram_stores_get_entry(index)->route;
    for (uint i = 0; i < routes_count; i++) {
        if (routes[i] == route) {
            routes_frequency[i] += 1;
            return;
        }
    }
    routes[routes_count] = route;
    routes_frequency[routes_count] = 1;
    routes_count += 1;
    if (routes_count >= 1023) {
        log_error("1024 Unigue routes compression IMPOSSIBLE");
        // set the failed flag and exit
        sark.vcpu->user0 = 1;
        spin1_exit(0);
    }
}

static inline void simple_minimise(uint32_t target_length){
	use(target_length);
    int left, right;

    int table_size = Routing_table_sdram_get_n_entries();

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
    max_index = table_size - 1;
    previous_index = 0;
    left = 0;

    while (left <= max_index){

        right = left;
        uint32_t left_route = routing_table_sdram_stores_get_entry(left)->route;
        log_info("A %u %u %u %u", left, max_index, right, left_route);
        while (right < (table_size -1) &&
                routing_table_sdram_stores_get_entry(right+1)->route == left_route){
            right += 1;
        }
        remaining_index = right + 1;
        log_info("compress %u %u", left, right);
        compress_by_route(left, right);
        left = right + 1;
        previous_index = write_index;
    }

    log_info("done %u %u", table_size, write_index);

    routing_table_remove_from_size(table_size-write_index);
    log_info("now %u", Routing_table_sdram_get_n_entries());

}

void minimise(uint32_t target_length){
    simple_minimise(target_length);
}

//! \brief the main entrance.
void c_main(void) {
    log_info("%u bytes of free DTCM", sark_heap_max(sark.heap, 0));

    // kick-start the process
    spin1_schedule_callback(compress_start, 0, 0, 3);

    // go
    spin1_start(SYNC_NOWAIT);	//##
}

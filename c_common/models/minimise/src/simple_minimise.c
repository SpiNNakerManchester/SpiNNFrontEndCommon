#include <spin1_api.h>
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
    for (int check = 0; check < previous_index; check++) {
        entry_t* check_entry = routing_table_sdram_stores_get_entry(check);
        if (keymask_intersect(check_entry->keymask, merged.keymask)) {
            return false;
        }
    }
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

static void quicksort(int low, int high){
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
            if (check_route < pivot){
                // swap the check to the left
                swap(l_write, check);
                l_write++;
                // move the check on as known to be pivot value
                check++;
            } else if (check_route > pivot) {
                // swap the check to the right
                swap(h_write, check);
                h_write--;
                // Do not move the check as it has an unknown value
            } else {
                // Move check as it has the pivot value
                check++;
            }
        }
        // Now sort the ones less than or more than the pivot
        quicksort(low, l_write);
        quicksort(check, high);
    }
}

static inline void simple_minimise(uint32_t target_length){
    int left, right;

    int table_size = Routing_table_sdram_get_n_entries();

    log_info("do qsort by route");
    quicksort(0, table_size);

    write_index = 0;
    max_index = table_size - 1;
    previous_index = 0;
    left = 0;

    while (left < max_index){
        right = left;
        uint32_t left_route = routing_table_sdram_stores_get_entry(left)->route;
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

    routing_table_remove_from_size(table_size-write_index);
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

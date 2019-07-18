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

static uint32_t write_index, previous_index, remaining_index, max_index;

//! \brief Method used to sort routing table entries.
//! \param[in] va: ?????
//! \param[in] vb: ??????
//! \return ???????
int compare_rte_by_route(const void *va, const void *vb) {
    entry_t* entry_a = (entry_t *) va;
    entry_t* entry_b = (entry_t *) vb;
    if (entry_a->route < entry_b->route) {
        return -1;
    } else  if (entry_a->route > entry_b->route) {
        return 1;
    } else {
        return 0;
    }
}

static inline entry_t merge(entry_t *entry1, entry_t *entry2) {
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

static inline bool find_merge(table_t *table, uint32_t left, uint32_t index) {
    entry_t merged = merge(&(table->entries[left]), &(table->entries[index]));
    for (uint32_t check = 0; check < previous_index; check++) {
        if (keymask_intersect(table->entries[check].keymask, merged.keymask)) {
            return false;
        }
    }
    for (uint32_t check = remaining_index; check < table->size; check++) {
        if (keymask_intersect(table->entries[check].keymask, merged.keymask)) {
            return false;
        }
    }
    table->entries[left] = merged;
    return true;
}

static inline void compress_by_route(table_t *table, uint32_t left, uint32_t right){
    uint32_t index;
    bool merged;
    merged = false;

    while (left < right) {
        index = left + 1;
        while (index <= right){
            merged = find_merge(table, left, index);
            if (merged) {
                table->entries[index] = table->entries[right];
                right -= 1;
                break;
            }
            index += 1;
        }
        if (!merged) {
            table->entries[write_index] = table->entries[left];
            write_index += 1;
            left += 1;
        }
    }
    if (left == right){
        table->entries[write_index] = table->entries[left];
        write_index += 1;
    }
}

static inline void simple_minimise(table_t *table, uint32_t target_length){
    uint32_t left, right;

    log_info("do qsort by route");
    qsort(table->entries, table->size, sizeof(entry_t), compare_rte_by_route);

    log_info("doing sort");
    write_index = 0;
    previous_index = 0;
    max_index = table->size - 1;
    left = 0;

    while (left < table->size){
        right = left;
        while (right < (table->size -1) &&
                table->entries[right+1].route == table->entries[left].route ){
            right += 1;
        }
        remaining_index = right + 1;
        log_info("compress %u %u", left, right);
        compress_by_route(table, left, right);
        left = right + 1;
        previous_index = write_index;
    }

    table->size = write_index;
}

void minimise(table_t *table, uint32_t target_length){
    simple_minimise(table, target_length);
}

//! \brief the main entrance.
void c_main(void) {
    log_info("%u bytes of free DTCM", sark_heap_max(sark.heap, 0));

    // kick-start the process
    spin1_schedule_callback(compress_start, 0, 0, 3);

    // go
    spin1_start(SYNC_NOWAIT);	//##
}

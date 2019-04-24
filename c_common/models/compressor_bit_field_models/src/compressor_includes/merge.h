#ifndef __MERGE_H__
#define __MERGE_H__

#include "bit_set.h"
#include "../common/routing_table.h"

typedef struct merge_t {
    bit_set_t entries;  // Set of entries included in the merge
    key_mask_t key_mask; // key_mask resulting from the merge
    uint32_t route;    // Route taken by entries in the merge
    uint32_t source;   // Collective source of entries in the route
} merge_t;

#define FULL 0xffffffff
#define EMPTY 0x00000000
#define INIT_SOURCE 0x0
#define INIT_ROUTE 0x0

// Clear a merge
static inline void merge_clear(merge_t *m) {
    // Clear the bit set
    bit_set_clear(&m->entries);

    // Initialise the key_mask and route
    m->key_mask.key  = FULL;  // !!!...
    m->key_mask.mask = EMPTY;  // Matches nothing
    m->route = INIT_ROUTE;
    m->source = INIT_SOURCE;
}

// Initialise a merge
static inline bool merge_init(merge_t *m, uint32_t n_entries_in_table) {
    // Initialise the bit_set
    if (!bit_set_init(&m->entries, n_entries_in_table)) {
        return false;
    }

    merge_clear(m);
    return true;
}

// Destruct a merge
static inline void merge_delete(merge_t *m) {
    // Free the bit set
    bit_set_delete(&(m->entries));
}

// Add an entry to the merge
static inline void merge_add(merge_t *m, unsigned int i) {
    // Add the entry to the bit set contained in the merge
    if (bit_set_add(&m->entries, i)) {
        entry_t *entry = routing_table_sdram_stores_get_entry(i);

        // Get the key_mask
        if (m->key_mask.key == FULL && m->key_mask.mask == EMPTY) {
            // If this is the first entry in the merge then the merge key_mask
            // is a copy of the entry key_mask.
            m->key_mask = entry->key_mask;
        } else {
            // Otherwise update the key and mask associated with the merge
            m->key_mask = key_mask_merge(m->key_mask, entry->key_mask);
        }

        // Add the route
        m->route |= entry->route;
        m->source |= entry->source;
    }
}

//! See if an entry is contained within a merge
static inline bool merge_contains(merge_t *m, unsigned int i) {
  return bit_set_contains(&(m->entries), i);
}


// Remove an entry from the merge
static inline void merge_remove(merge_t *m, unsigned int i) {
    // Remove the entry from the bit_set contained in the merge
    if (bit_set_remove(&m->entries, i)) {
        // Rebuild the key and mask from scratch
        m->route = INIT_ROUTE;
        m->source = INIT_SOURCE;
        m->key_mask.key  = FULL;
        m->key_mask.mask = EMPTY;
        for (int j = 0; j < routing_table_sdram_get_n_entries(); j++) {
            entry_t *e = routing_table_sdram_stores_get_entry(j);

            if (bit_set_contains(&m->entries, j)) {
                m->route |= e->route;
                m->source |= e->source;
                if (m->key_mask.key  == FULL && m->key_mask.mask == EMPTY) {
                    // Initialise the key_mask
                    m->key_mask.key  = e->key_mask.key;
                    m->key_mask.mask = e->key_mask.mask;
                } else {
                    // Merge the key_mask
                    m->key_mask = key_mask_merge(m->key_mask, e->key_mask);
                }
            }
        }
    }
}

//! \brief prints out a merge by bit level
//! \param[in] merge: the merge to print
void merge_print_merge_bit(merge_t *merge){
    log_info(
        "merge key is %x or %d, mask %x, route %x, source %x",
         merge->key_mask.key, merge->key_mask.key, merge->key_mask.mask,
         merge->route, merge->source);
    //print_bit_set(merge->entries);
    log_info("bit set n_elements is %d", merge->entries.n_elements);
    for (int table_index = 0; table_index < current_n_tables; table_index++){
        table_t *table = routing_tables[table_index];
        for (int entry_index = 0; entry_index < table->size; entry_index ++){
            entry_t entry = table->entries[entry_index];
            if (merge_contains(
                    merge, table_lo_entry[table_index] + entry_index)){
                log_info(
                    "entry %d has key %x or %d mask %x route %x source %x",
                    table_lo_entry[table_index] + entry_index, 
                    entry.key_mask.key, entry.key_mask.key,
                    entry.key_mask.mask, entry.route,entry.source);
            }
        }
    }
}

#endif  // __MERGE_H__

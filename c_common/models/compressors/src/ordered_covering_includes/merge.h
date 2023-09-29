/*
 * Copyright (c) 2019 The University of Manchester
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

//! \file
//! \brief How to merge routing table entries
#ifndef __MERGE_H__
#define __MERGE_H__

#include "bit_set.h"
#include "../common/routing_table.h"

//! \brief merge struct. entries which can be merged
typedef struct merge_t {
    //! Set of entries included in the merge
    bit_set_t entries;

    //! key_mask resulting from the merge
    key_mask_t key_mask;

    //! Route taken by entries in the merge
    uint32_t route;

    //! Collective source of entries in the route
    uint32_t source;
} merge_t;

//! \brief the ful key
#define FULL 0xffffffff

//! \brief the empty mask
#define EMPTY 0x00000000

//! \brief the init for sources of entries
#define INIT_SOURCE 0x0

//! \brief the init for routes of entries
#define INIT_ROUTE 0x0

//! \brief Get the goodness for a merge
//! \param[in] merge: the merge
//! \return the goodness of the merge.
static int merge_goodness(merge_t *merge) {
    return merge->entries.count - 1;
}

//! \brief Clear a merge
//! \param[in] m: the merge to clear
static inline void merge_clear(merge_t *m) {
    // Clear the bit set
    bit_set_clear(&m->entries);

    // Initialise the key_mask and route
    m->key_mask.key  = FULL;  // !!!...
    m->key_mask.mask = EMPTY;  // Matches nothing
    m->route = INIT_ROUTE;
    m->source = INIT_SOURCE;
}

//! \brief Initialise a merge
//! \param[in] m: the merge pointer to init
//! \param[in] n_entries_in_table: the possible number of entries in the merge
//! \return whether the merge was initialised
static inline bool merge_init(merge_t *m, uint32_t n_entries_in_table) {
    // Initialise the bit_set
    if (!bit_set_init(&m->entries, n_entries_in_table)) {
        return false;
    }

    merge_clear(m);
    return true;
}

//! \brief Destroy a merge
//! \param[in] m: the merge to delete
static inline void merge_delete(merge_t *m) {
    // Free the bit set
    bit_set_delete(&(m->entries));
}

//! \brief Add an entry to the merge
//! \param[in] m: the merge to add to
//! \param[in] i: the entry bit to flag as potential merge-able entry
static inline void merge_add(merge_t *m, unsigned int i) {
    // Add the entry to the bit set contained in the merge
    if (bit_set_add(&m->entries, i)) {
        entry_t *entry = routing_table_get_entry(i);

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

//! \brief See if an entry is contained within a merge
//! \param[in] m: the merge to check if a bit is set
//! \param[in] i: the bit to check
//! \return true if the bit is set false otherwise.
static inline bool merge_contains(merge_t *m, unsigned int i) {
  return bit_set_contains(&(m->entries), i);
}


//! \brief Remove an entry from the merge
//! \param[in] m: the merge to unset a bit from
//! \param[in] i: the entry id to unset
static inline void merge_remove(merge_t *m, unsigned int i) {
    // Remove the entry from the bit_set contained in the merge
    if (bit_set_remove(&m->entries, i)) {
        // Rebuild the key and mask from scratch
        m->route = INIT_ROUTE;
        m->source = INIT_SOURCE;
        m->key_mask.key  = FULL;
        m->key_mask.mask = EMPTY;
        for (int j = 0; j < routing_table_get_n_entries(); j++) {
            entry_t *e = routing_table_get_entry(j);

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

#endif  // __MERGE_H__

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
//! \brief Utilities for a single routing table
#ifndef __ROUTING_TABLE_H__
#define __ROUTING_TABLE_H__

//=============================================================================

//! \brief Holds key and mask
typedef struct key_mask_t {
    //! Key for the key_mask
    uint32_t key;

    //! Mask for the key_mask
    uint32_t mask;
} key_mask_t;

//! \brief Holds data for a routing table entry
typedef struct entry_t {
    //! Key and mask
    key_mask_t key_mask;

    //! Routing direction
    uint32_t route;

    //! Source of packets arriving at this entry
    uint32_t source;
} entry_t;

//! \brief Holds a routing table description
typedef struct table_t {
    //! Number of entries in the table
    uint32_t size;

    //! Entries in the table
    entry_t entries[];
} table_t;

//! \brief Gets a pointer to where this entry is stored
//! \details Will not check if there is an entry with this id but will RTE if
//!     the id is too large
//! \param[in] entry_id_to_find: Id of entry to find pointer to
//! \return pointer to the entry's location
entry_t* routing_table_get_entry(uint32_t entry_id_to_find);

//! \brief Get the number of entries in the routing table
//! \return number of appended entries.
int routing_table_get_n_entries(void);

//! \brief updates table stores accordingly.
//!
//! will RTE if this causes the total entries to become negative.
//! \param[in] size_to_remove: the amount of size to remove from the table sets
void routing_table_remove_from_size(int size_to_remove);

//! \brief Write an entry to a specific index
//! \param[in] entry: The entry to write
//! \param[in] index: Where to write it.
static inline void routing_table_put_entry(const entry_t* entry, int index) {
    entry_t* e_ptr = routing_table_get_entry(index);
    e_ptr->key_mask.key = entry->key_mask.key;
    e_ptr->key_mask.mask = entry->key_mask.mask;
    e_ptr->route = entry->route;
    e_ptr->source = entry->source;
}

//! \brief Copy an entry from one index to another
//! \param[in] new_index: Where to copy to
//! \param[in] old_index: Where to copy from
static inline void routing_table_copy_entry(int new_index, int old_index) {
    entry_t* e_ptr = routing_table_get_entry(old_index);
    routing_table_put_entry(e_ptr, new_index);
}

//! \brief Swap a pair of entries at the given indices
//! \param[in] a: The first index where an entry is
//! \param[in] b: The second index where an entry is
static inline void swap_entries(int a, int b) {
    log_debug("swap %u %u", a, b);
    entry_t temp = *routing_table_get_entry(a);
    log_debug("before %u %u %u %u",
            temp.key_mask.key, temp.key_mask.mask, temp.route, temp.source);
    routing_table_put_entry(routing_table_get_entry(b), a);
    routing_table_put_entry(&temp, b);
    entry_t temp2 = *routing_table_get_entry(b);
    log_debug("before %u %u %u %u",
            temp2.key_mask.key, temp2.key_mask.mask, temp2.route, temp2.source);
}

//=============================================================================
//state for reduction in parameters being passed around

//! \brief Get a mask of the Xs in a key_mask
//! \param[in] km: the key mask to get as xs
//! \return a merged mask
static inline uint32_t key_mask_get_xs(key_mask_t km) {
    return ~km.key & ~km.mask;
}


//! \brief Get a count of the Xs in a key_mask
//! \param[in] km: the key mask struct to count
//! \return the number of bits set in the mask
static inline unsigned int key_mask_count_xs(key_mask_t km) {
    return __builtin_popcount(key_mask_get_xs(km));
}


//! \brief Determine if two key_masks would match any of the same keys
//! \param[in] a: key mask struct a
//! \param[in] b: key mask struct b
//! \return bool that says if these key masks intersect
static inline bool key_mask_intersect(key_mask_t a, key_mask_t b) {
    return (a.key & b.mask) == (b.key & a.mask);
}

//! \brief Generate a new key-mask which is a combination of two other key_masks
//! \details `c := a | b`
//! \param[in] a: the first key mask struct
//! \param[in] b: the second key mask struct
//! \return the merged key mask struct
static inline key_mask_t key_mask_merge(key_mask_t a, key_mask_t b) {
    uint32_t new_xs = ~(a.key ^ b.key);
    key_mask_t c;
    c.mask = a.mask & b.mask & new_xs;
    c.key = (a.key | b.key) & c.mask;

    return c;
}

#endif  // __ROUTING_TABLE_H__

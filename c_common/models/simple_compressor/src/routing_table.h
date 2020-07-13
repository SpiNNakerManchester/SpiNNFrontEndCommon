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
 * \brief Structures and operations on routing tables and entries.
 */

#include <stdbool.h>
#include <stdint.h>

#ifndef __ROUTING_TABLE_H__
#define __ROUTING_TABLE_H__

//! \brief The key and mask as understood by the SpiNNaker Router.
//!
//! The mask selects which bits of the key are significant for matching.
typedef struct {
    uint32_t key;   //!< Key for the keymask
    uint32_t mask;  //!< Mask for the keymask
} keymask_t;

//! \brief Get a mask of the Xs in a keymask
//! \param[in] km: The keymask
//! \return the ignored bits
static inline uint32_t keymask_get_xs(keymask_t km)
{
    return ~km.key & ~km.mask;
}

//! \brief Get a count of the Xs in a keymask
//! \param[in] km: The keymask
//! \return Count of ignored bits
static inline unsigned int keymask_count_xs(keymask_t km)
{
    return __builtin_popcount(keymask_get_xs(km));
}

//! \brief Determine if two keymasks would match any of the same keys
//! \param[in] a: The first keymask
//! \param[in] b: The second keymask
//! \return True if the keymasks intersect
static inline bool keymask_intersect(keymask_t a, keymask_t b)
{
    return (a.key & b.mask) == (b.key & a.mask);
}

//! \brief Generate a new key-mask which is a combination of two other keymasks
//!
//!     c := a | b
//!
//! \param[in] a: The first keymask
//! \param[in] b: The second keymask
//! \return The merged keymask
static inline keymask_t keymask_merge(keymask_t a, keymask_t b)
{
    keymask_t c;
    uint32_t new_xs = ~(a.key ^ b.key);
    c.mask = a.mask & b.mask & new_xs;
    c.key = (a.key | b.key) & c.mask;

    return c;
}

//! \brief A routing entry that knows where it came from, goes to, and when it
//! enables.
typedef struct {
    keymask_t keymask;  //!< Key and mask
    uint32_t route;     //!< Routing direction
    uint32_t source;    //!< Source of packets arriving at this entry.
                        //!< Used to determine whether this entry can be
                        //!< defaulted.
} entry_t;

//! A routing table is made of an ordered list of entries.
typedef struct {
    uint32_t size;      //!< Number of entries in the table
    entry_t *entries;   //!< Entries in the table
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
    e_ptr->keymask = entry->keymask;
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
            temp.keymask.key, temp.keymask.mask, temp.route, temp.source);
    routing_table_put_entry(routing_table_get_entry(b), a);
    routing_table_put_entry(&temp, b);
    entry_t temp2 = *routing_table_get_entry(b);
    log_debug("before %u %u %u %u",
            temp2.keymask.key, temp2.keymask.mask, temp2.route, temp2.source);
}

#endif  // __ROUTING_TABLE_H__

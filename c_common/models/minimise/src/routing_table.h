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

//! Get a mask of the Xs in a keymask
static inline uint32_t keymask_get_xs(keymask_t km)
{
    return ~km.key & ~km.mask;
}

//! Get a count of the Xs in a keymask
static inline unsigned int keymask_count_xs(keymask_t km)
{
    return __builtin_popcount(keymask_get_xs(km));
}

//! Determine if two keymasks would match any of the same keys
static inline bool keymask_intersect(keymask_t a, keymask_t b)
{
    return (a.key & b.mask) == (b.key & a.mask);
}

//! Generate a new key-mask which is a combination of two other keymasks
//!
//!     c := a | b
static inline keymask_t keymask_merge(keymask_t a, keymask_t b)
{
    keymask_t c;
    uint32_t new_xs = ~(a.key ^ b.key);
    c.mask = a.mask & b.mask & new_xs;
    c.key = (a.key | b.key) & c.mask;

    return c;
}

//! A routing entry that knows where it came from, goes to, and when it enables.
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

#if 0
static inline void entry_copy(
        table_t *table, uint32_t old_index, uint32_t new_index)
{
    table->entries[new_index].keymask = table->entries[old_index].keymask;
    table->entries[new_index].route = table->entries[old_index].route;
    table->entries[new_index].source = table->entries[old_index].source;
}
#endif

//! \brief The header of the routing table information in the input data block.
//!
//! This is found looking for a memory block with the right tag.
typedef struct {
    //! Application ID to use to load the routing table. This can be left as `0`
    //! to load routing entries with the same application ID that was used to
    //! load this application.
    uint32_t app_id;

    //! flag for compressing when only needed
    uint32_t compress_only_when_needed;

    //! flag that uses the available entries of the router table instead of
    //! compressing as much as possible.
    uint32_t compress_as_much_as_possible;

    //! Initial size of the routing table.
    uint32_t table_size;

    //! Routing table entries
    entry_t entries[];
} header_t;

#endif  // __ROUTING_TABLE_H__

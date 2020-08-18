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
 * \brief How to remove default routes from a routing table.
 */

#ifndef __REMOVE_DEFAULT_ROUTES_H__
#define __REMOVE_DEFAULT_ROUTES_H__

#include <stdbool.h>
#include "routing_table.h"
#include <debug.h>

//! Picks the bits of a link out of a route
#define LINK_MASK 0x3f

static inline bool _just_a_link(uint32_t direction) {
    return __builtin_popcount(direction) == 1 && // Only one direction...
            (direction & LINK_MASK);             // which is a link.
}

// Test if route's source is opposite to sink
static inline bool _opposite_links(entry_t *entry) {
    uint32_t src = entry->source & LINK_MASK;
    uint32_t dst = entry->route & LINK_MASK;
    // Equivalent to a rotate of 6 bits by 3 places and single compare
    return ((dst >> 3) == (src & 0x7) && (src >> 3) == (dst & 0x7));
}

//! \brief Remove defaultable routes from a routing table if that helps.
//! \param[in] target_length:
//!     The (upper bound) on the desired length of routing table.
//! \return Whether we have managed to get the number of routes within the
//!     given bound.
static inline bool remove_default_routes_minimise(int target_length) {
    if (routing_table_get_n_entries() <= target_length) {
        log_info("No Minimise needed as size %u, is below target of %u",
        routing_table_get_n_entries(),  target_length);
        return true;
    }
    // Work out if removing defaultable links is worthwhile
    int after_size = 0;
    for (int i = 0; i < routing_table_get_n_entries(); i++) {
        // Get the current entry
        entry_t* entry = routing_table_get_entry(i);

        // See if it can be removed
        if (_just_a_link(entry->route) &&      // Only one output, a link
                _just_a_link(entry->source) && // Only one input, a link
                _opposite_links(entry)) {    // Source is opposite to sink
        } else {
            after_size++;
            // If we won't fit afterwards, no sense trying
            if (after_size > target_length) {
                return false;
            }
        }
    }

    uint32_t removed = 0;
    int last = routing_table_get_n_entries();
    // Do the actual removal
    for (int i = 0; i < after_size; i++) {
        // Get the current entry
        entry_t* entry = routing_table_get_entry(i);

        // See if it can be removed
        if (_just_a_link(entry->route) &&      // Only one output, a link
                _just_a_link(entry->source) && // Only one input, a link
                _opposite_links(entry)) {    // Source is opposite to sink
            if (i < last) {
                routing_table_copy_entry(i, last);
                removed++;
                last--;
                // Reuse same i in next pass so reduce before the ++
                i--;
            }
        }
    }
    routing_table_remove_from_size(removed);
    return true;
}

#endif

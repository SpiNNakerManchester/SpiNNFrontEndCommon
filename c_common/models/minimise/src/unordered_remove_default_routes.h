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

#include <stdbool.h>
#include "routing_table.h"

#ifndef __REMOVE_DEFAULT_ROUTES_H__
#define __REMOVE_DEFAULT_ROUTES_H__

static inline bool _just_a_link(uint32_t direction)
{
    return __builtin_popcount(direction) == 1 && // Only one direction...
            (direction & 0x3f);                  // which is a link.
}

static inline bool _opposite_links(entry_t *entry) {
    return
        (entry->route >> 3) == (entry->source & 0x7) && // Source is opposite to sink
        (entry->source >> 3) == (entry->route & 0x7);   // Sink is opposite to source
}

//! \brief Removes defaultable routes from a routing table if that helps.
//! \param[in,out] table: The table to remove the routes from.
static inline void remove_default_routes_minimise(table_t *table)
{
    // Work out if removing defaultable links is worthwhile
    uint32_t after_size = table->size;
    for (uint32_t i = 0; i < table->size; i++) {
        // Get the current entry
        entry_t entry = table->entries[i];

        // See if it can be removed
        if (_just_a_link(entry.route) &&      // Only one output, a link
                _just_a_link(entry.source) && // Only one input, a link
                _opposite_links(&entry)) {    // Source is opposite to sink
            after_size--;
        }
    }

    // If we won't fit afterwards, no sense trying
    if (after_size > rtr_alloc_max()) {
        return;
    }

    // Do the actual removal
    for (uint32_t i = 0; i < table->size; i++) {
        // Get the current entry
        entry_t entry = table->entries[i];

        // See if it can be removed
        if (_just_a_link(entry.route) &&      // Only one output, a link
                _just_a_link(entry.source) && // Only one input, a link
                _opposite_links(&entry)) {    // Source is opposite to sink
            uint32_t last = table->size - 1;
            if (i < last) {
                table->entries[i] = table->entries[last];
                table->size--;
                // Reuse same i in next pass so reduce before the ++
                i--;
            }
        }
    }
}

#endif

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

#include <stdbool.h>
#include "routing_table.h"

#ifndef __REMOVE_DEFAULT_ROUTES_H__
#define __REMOVE_DEFAULT_ROUTES_H__

static inline void remove_default_routes_minimise(table_t *table) {
    uint32_t after_size = table->size;
    for (uint32_t i = 0; i < table->size; i ++) {
        // Get the current entry
        entry_t entry = table->entries[i];

        // See if it can be removed
        if (__builtin_popcount(entry.route) == 1 &&        // Only one output direction
            (entry.route & 0x3f) &&                        // which is a link.
            __builtin_popcount(entry.source) == 1 &&       // Only one input direction
            (entry.source & 0x3f) &&                       // which is a link.
            (entry.route >> 3) == (entry.source & 0x7) &&  // Source is opposite to sink
            (entry.source >> 3) == (entry.route & 0x7)) {   // Source is opposite to sink
            after_size--;
        }
    }

    if (after_size <= rtr_alloc_max()) {
        for (uint32_t i = 0; i < table->size; i ++) {
            // Get the current entry
            entry_t entry = table->entries[i];

            // See if it can be removed
            if (__builtin_popcount(entry.route) == 1 &&        // Only one output direction
                (entry.route & 0x3f) &&                        // which is a link.
                __builtin_popcount(entry.source) == 1 &&       // Only one input direction
                (entry.source & 0x3f) &&                       // which is a link.
                (entry.route >> 3) == (entry.source & 0x7) &&  // Source is opposite to sink
                (entry.source >> 3) == (entry.route & 0x7)) {    // Source is opposite to sink
                uint32_t last = table->size -1;
                if (i < last){
                    table->entries[i] = table->entries[last];
                    table->size--;
                    // Reuse same i in next pass so reduce before the ++
                    i--;
                }
            }
        }
    }
}

#endif

#include <stdio.h>
#include <stdbool.h>
#include "bitset.h"
#include "routing_table.h"

#ifndef __REMOVE_DEFAULT_ROUTES_H__

static inline void remove_default_routes_minimise(table_t *table)
{
  // Mark the entries to be removed from the table
  bitset_t remove;
  bitset_init(&remove, table->size);

  // Work up the table from the bottom, marking entries to remove
  for (unsigned int i = table->size - 1; i < table->size; i--)
  {
    // Get the current entry
    entry_t entry = table->entries[i];
    
    // See if it can be removed
    if (__builtin_popcount(entry.route) == 1 &&        // Only one output direction
        (entry.route & 0x3f) &&                        // which is a link.
        __builtin_popcount(entry.source) == 1 &&       // Only one input direction
        (entry.source & 0x3f) &&                       // which is a link.
        (entry.route >> 3) == (entry.source & 0x7) &&  // Source is opposite to sink
        (entry.source >> 3) == (entry.route & 0x7))    // Source is opposite to sink
    {
      // The entry can be removed iff. it doesn't intersect with any entry
      // further down the table.
      bool remove_entry = true;
      for (unsigned int j = i + 1; j < table->size; j++)
      {
        // If entry we're comparing with is already going to be removed, ignore
        // it.
        if (bitset_contains(&remove, j))
        {
          continue;
        }

        keymask_t a = entry.keymask;
        keymask_t b = table->entries[j].keymask;

        if (keymask_intersect(a, b))
        {
          remove_entry = false;
          break;
        }
      }

      if (remove_entry)
      {
        // Mark this entry as being removed
        bitset_add(&remove, i);
      }
    }
  }

  // Remove the selected entries from the table
  for (unsigned int insert = 0, read = 0; read < table->size; read++)
  {
    // Grab the current entry before we potentially overwrite it
    entry_t current = table->entries[read];

    // Insert the entry if it isn't being removed
    if (!bitset_contains(&remove, read))
    {
      table->entries[insert++] = current;
    }
  }

  // Update the table size
  table->size -= remove.count;

  // Clear up
  bitset_delete(&remove);
}

#define __REMOVE_DEFAULT_ROUTES_H__
#endif  // __REMOVE_DEFAULT_ROUTES_H__

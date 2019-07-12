#include "bitset.h"
#include "routing_table.h"

#ifndef __MERGE_H__

typedef struct _merge_t
{
  bitset_t entries;  // Set of entries included in the merge
  table_t* table;    // Table against which the merge is defined

  keymask_t keymask; // Keymask resulting from the merge
  uint32_t route;    // Route taken by entries in the merge
  uint32_t source;   // Collective source of entries in the route
} merge_t;


// Clear a merge
static inline void merge_clear(merge_t* m)
{
  // Clear the bitset
  bitset_clear(&(m->entries));

  // Initialise the keymask and route
  m->keymask.key  = 0xffffffff;  // !!!...
  m->keymask.mask = 0x00000000;  // Matches nothing
  m->route = 0x0;
  m->source = 0x0;
}


// Initialise a merge
static inline bool merge_init(merge_t* m, table_t* table)
{
  // Store the table pointer, initialise the keymask and route
  m->table = table;

  // Initialise the bitset
  if (!bitset_init(&(m->entries), table->size))
  {
    return false;
  }
  else
  {
    merge_clear(m);
    return true;
  }
}


// Destruct a merge
static inline void merge_delete(merge_t* m)
{
  // Free the bitset
  bitset_delete(&m->entries);
}


// Add an entry to the merge
static inline void merge_add(merge_t* m, unsigned int i)
{
  // Add the entry to the bitset contained in the merge
  if (bitset_add(&m->entries, i))
  {
    entry_t e = m->table->entries[i];

    // Get the keymask
    if (m->keymask.key == 0xffffffff && m->keymask.mask == 0x00000000)
    {
      // If this is the first entry in the merge then the merge keymask is a copy
      // of the entry keymask.
      m->keymask = e.keymask;
    }
    else
    {
      // Otherwise update the key and mask associated with the merge
      m->keymask = keymask_merge(m->keymask, e.keymask);
    }

    // Add the route
    m->route |= e.route;
    m->source |= e.source;
  }
}


// See if an entry is contained within a merge
static inline bool merge_contains(merge_t* m, unsigned int i)
{
  return bitset_contains(&(m->entries), i);
}


// Remove an entry from the merge
static inline void merge_remove(merge_t* m, unsigned int i)
{
  // Remove the entry from the bitset contained in the merge
  if (bitset_remove(&(m->entries), i))
  {
    // Rebuild the key and mask from scratch
    m->route = 0x0;
    m->source = 0x0;
    m->keymask.key  = 0xffffffff;
    m->keymask.mask = 0x000000000;
    for (unsigned int j = 0; j < m->table->size; j++)
    {
      entry_t e = m->table->entries[j];

      if (bitset_contains(&(m->entries), j))
      {
        m->route |= e.route;
        m->source |= e.source;
        if (m->keymask.key  == 0xffffffff && m->keymask.mask == 0x00000000)
        {
          // Initialise the keymask
          m->keymask.key  = e.keymask.key;
          m->keymask.mask = e.keymask.mask;
        }
        else
        {
          // Merge the keymask
          m->keymask = keymask_merge(m->keymask, e.keymask);
        }
      }
    }
  }
}


#define __MERGE_H__
#endif  // __MERGE_H__

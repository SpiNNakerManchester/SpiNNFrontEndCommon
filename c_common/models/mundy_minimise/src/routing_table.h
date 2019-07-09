#include <stdbool.h>
#include <stdint.h>

#ifndef __ROUTING_TABLE_H__

typedef struct _keymask_t
{
  uint32_t key;   // Key for the keymask
  uint32_t mask;  // Mask for the keymask
} keymask_t;


// Get a mask of the Xs in a keymask
static inline uint32_t keymask_get_xs(keymask_t km)
{
  return ~km.key & ~km.mask;
}


// Get a count of the Xs in a keymask
static inline unsigned int keymask_count_xs(keymask_t km)
{
  return __builtin_popcount(keymask_get_xs(km));
}


// Determine if two keymasks would match any of the same keys
static inline bool keymask_intersect(keymask_t a, keymask_t b)
{
  return (a.key & b.mask) == (b.key & a.mask);
}


// Generate a new key-mask which is a combination of two other keymasks
//     c := a | b
static inline keymask_t keymask_merge(keymask_t a, keymask_t b)
{
  keymask_t c;
  uint32_t new_xs = ~(a.key ^ b.key);
  c.mask = a.mask & b.mask & new_xs;
  c.key = (a.key | b.key) & c.mask;

  return c;
}


typedef struct _entry_t
{
  keymask_t keymask;  // Key and mask
  uint32_t route;     // Routing direction
  uint32_t source;    // Source of packets arriving at this entry
} entry_t;


typedef struct _table_t
{
  unsigned int size;  // Number of entries in the table
  entry_t *entries;   // Entries in the table
} table_t;


#define __ROUTING_TABLE_H__
#endif  // __ROUTING_TABLE_H__

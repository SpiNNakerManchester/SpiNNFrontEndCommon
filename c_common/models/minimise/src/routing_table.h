#include <stdbool.h>
#include <stdint.h>
#include "spin1_api.h"
#include <debug.h>

#ifndef __ROUTING_TABLE_H__
#define __ROUTING_TABLE_H__

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
  uint32_t size;  // Number of entries in the table
  entry_t *entries;   // Entries in the table
} table_t;

typedef struct header_t{

    // Application ID to use to load the routing table. This can be left as `0'
    // to load routing entries with the same application ID that was used to
    // load this application.
    uint32_t app_id;

    //flag for compressing when only needed
    uint32_t compress_only_when_needed;

    // flag that uses the available entries of the router table instead of
    //compressing as much as possible.
    uint32_t compress_as_much_as_possible;

    // Initial size of the routing table.
    uint32_t table_size;

    // Routing table entries
    entry_t entries[];
} header_t;

//static void entry_copy(table_t *table, uint32_t old_index, uint32_t new_index){
//    table->entries[new_index].keymask = table->entries[old_index].keymask;
//    table->entries[new_index].route = table->entries[old_index].route;
//    table->entries[new_index].source = table->entries[old_index].source;
//}


//! \brief prints the header object for debug purposes
//! \param[in] header: the header to print
void print_header(header_t *header) {
    log_info("app_id = %d", header->app_id);
    log_info(
        "compress_only_when_needed = %d",
        header->compress_only_when_needed);
    log_info(
        "compress_as_much_as_possible = %d",
        header->compress_as_much_as_possible);
    log_info("table_size = %d", header->table_size);
}

//! \brief Read a new copy of the routing table from SDRAM.
//! \param[in] table : the table containing router table entries
//! \param[in] header: the header object
void read_table(table_t *table, header_t *header) {
    // Copy the size of the table
    table->size = header->table_size;

    // Allocate space for the routing table entries
    table->entries = MALLOC(table->size * sizeof(entry_t));

    // Copy in the routing table entries
    spin1_memcpy((void *) table->entries, (void *) header->entries,
            sizeof(entry_t) * table->size);
}

//! \brief Load a routing table to the router.
//! \param[in] table: the table containing router table entries
//! \param[in] app_id: the app id for the routing table entries to be loaded
//! under
//! \return bool saying if the table was loaded into the router or not
bool load_routing_table(table_t *table, uint32_t app_id) {

    // Try to allocate sufficient room for the routing table.
    uint32_t entry_id = rtr_alloc_id(table->size, app_id);
    if (entry_id == 0) {
        log_info("Unable to allocate routing table of size %u\n", table->size);
        return FALSE;
    }

    // Load entries into the table (provided the allocation succeeded).
    // Note that although the allocation included the specified
    // application ID we also need to include it as the most significant
    // byte in the route (see `sark_hw.c`).
    for (uint32_t i = 0; i < table->size; i++) {
        entry_t entry = table->entries[i];
        uint32_t route = entry.route | (app_id << 24);
        rtr_mc_set(entry_id + i, entry.keymask.key, entry.keymask.mask,
                route);
    }

    // Indicate we were able to allocate routing table entries.
    return TRUE;
}

//! \brief frees memory allocated and calls spin1 exit and sets the user0
//! error code correctly.
//! \param[in] header the header object
//! \param[in] table the data object holding the routing table entries
void cleanup_and_exit(header_t *header, table_t table) {
    // Free the memory used by the routing table.
    log_debug("free sdram blocks which held router tables");
    FREE(table.entries);
    // Free the block of SDRAM used to load the routing table.
    sark_xfree(sv->sdram_heap, (void *) header, ALLOC_LOCK);

    log_info("completed router compressor");
    sark.vcpu->user0 = 0;
    spin1_exit(0);
}

#endif  // __ROUTING_TABLE_H__

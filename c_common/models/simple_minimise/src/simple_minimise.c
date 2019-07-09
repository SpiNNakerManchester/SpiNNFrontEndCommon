#include <stdbool.h>
#include <stdlib.h>
#include "spin1_api.h"
#include "ordered_covering.h"
#include "remove_default_routes.h"
#include <debug.h>
/*****************************************************************************/
/* SpiNNaker routing table minimisation.
 *
 * Minimise a routing table loaded into SDRAM and load the minimised table into
 * the router using the specified application ID.
 *
 * the exit code is stored in the user0 register
 *
 * The memory address with tag "1" is expected contain the following struct
 * (entry_t is defined in `routing_table.h` but is described below).
 */

typedef struct {

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

/* entry_t is defined as:
 *
 *     typedef struct
 *     {
 *       uint32_t key;
 *       uint32_t mask;
 *       uint32_t route;   // Routing direction
 *       uint32_t source;  // Source of packets arriving at this entry
 *     } entry_t;
 *
 * The `source` field is used to determine if the entry could be replaced by
 * default routing, it can be left blank if removing default entries is not to
 * be used. Otherwise indicate which links will be used by packets expected to
 * match the specified entry.
 *
 * NOTE: The routing table provided to this application MUST include all of the
 * entries which are expected to arrive at this router (i.e., entries which
 * could be replaced by default routing MUST be included in the table provided
 * to this application).
 *
 * NOTE: The block of memory containing the header and initial routing table
 * will be freed on exit by this application.
 */

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
;

//! \brief Method used to sort routing table entries.
//! \param[in] va: ?????
//! \param[in] vb: ??????
//! \return ???????
int compare_rte(const void *va, const void *vb) {
    // Grab the keys and masks
    keymask_t a = ((entry_t *) va)->keymask;
    keymask_t b = ((entry_t *) vb)->keymask;

    // Perform the comparison
    return ((int) keymask_count_xs(a)) - ((int) keymask_count_xs(b));
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

//! \brief the callback for setting off the router compressor
void compress_start() {
    log_info("Starting on chip router compressor");

    // Prepare to minimise the routing tables
    log_debug("looking for header using tag %u app_id %u", 1, sark_app_id());
    header_t *header = (header_t *) sark_tag_ptr(1, sark_app_id());
    log_debug("reading data from 0x%08x", (uint32_t) header);
    print_header(header);

    // set the flag to something none useful
    sark.vcpu->user0 = 20;

    // Load the routing table
    table_t table;
    log_debug("start reading table");
    read_table(&table, header);
    log_debug("finished reading table");

    // Store intermediate sizes for later reporting (if we fail to minimise)
    uint32_t size_original, size_rde, size_oc;
    size_original = table.size;

    // Try to load the table
    log_debug("check if compression is needed and compress if needed");
    if ((header->compress_only_when_needed == 1
            && !load_routing_table(&table, header->app_id))
            || header->compress_only_when_needed == 0) {

        // Otherwise remove default routes.
        log_debug("remove default routes from minimiser");
        remove_default_routes_minimise(&table);
        size_rde = table.size;

        // Try to load the table
        log_debug("check if compression is needed and try with no defaults");
        if ((header->compress_only_when_needed == 1
                && !load_routing_table(&table, header->app_id))
                || header->compress_only_when_needed == 0) {

            // Try to use Ordered Covering the minimise the table. This
            // requires that the table be reloaded from memory and that it
            // be sorted in ascending order of generality.

            log_debug("free the tables entries");
            FREE(table.entries);
            read_table(&table, header);

            log_debug("do qsort");
            qsort(table.entries, table.size, sizeof(entry_t), compare_rte);

            // Get the target length of the routing table
            log_debug("acquire target length");
            uint32_t target_length = 0;
            if (header->compress_as_much_as_possible == 0) {
                target_length = rtr_alloc_max();
            }
            log_info("target length of %d", target_length);

            // Perform the minimisation
            aliases_t aliases = aliases_init();
            log_debug("minimise");
            oc_minimise(&table, target_length, &aliases);
            log_debug("done minimise");
            size_oc = table.size;

            // report size to the host for provenance aspects
            log_info("has compressed the router table to %d entries", size_oc);

            // Clean up the memory used by the aliases table
            log_debug("clear up aliases");
            aliases_clear(&aliases);

            // Try to load the routing table
            log_debug("try loading tables");
            if (!load_routing_table(&table, header->app_id)) {

                // Otherwise give up and exit with an error
                log_error(
                    "Failed to minimise routing table to fit %u entries. "
                    "(Original table: %u after removing default entries: %u "
                    "after Ordered Covering: %u).",
                    rtr_alloc_max(), size_original, size_rde, size_oc);

                // Free the block of SDRAM used to load the routing table.
                log_debug("free sdram blocks which held router tables");
                FREE((void *) header);

                // set the failed flag and exit
                sark.vcpu->user0 = 1;
                spin1_exit(0);
            } else {
                cleanup_and_exit(header, table);
            }
        }
    } else {
        cleanup_and_exit(header, table);
    }
}

//! \brief the main entrance.
void c_main(void) {
    log_info("%u bytes of free DTCM", sark_heap_max(sark.heap, 0));

    // kick-start the process
    spin1_schedule_callback(compress_start, 0, 0, 3);

    // go
    spin1_start(SYNC_NOWAIT);	//##
}

#include <stdbool.h>
#include "spin1_api.h"
#include <debug.h>
#include "remove_default_routes.h"

#ifndef __MINIMISE_H__
#define __MINIMISE_H__

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


void minimise(table_t *table, uint32_t target_length);

//! \brief the callback for setting off the router compressor
void compress_start() {
    uint32_t size_original;

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
    size_original = table.size;

    // Try to load the table
    log_debug("check if compression is needed and compress if needed");
    if (header->compress_only_when_needed == 1){
        if (load_routing_table(&table, header->app_id)){
            cleanup_and_exit(header, table);
        } else {
            // Otherwise remove default routes.
            log_debug("remove default routes from minimiser");
            remove_default_routes_minimise(&table);
            if (load_routing_table(&table, header->app_id)){
                cleanup_and_exit(header, table);
            } else {
                //Opps we need the defaults back before trying compression
                log_debug("free the tables entries");
                FREE(table.entries);
                read_table(&table, header);
            }
        }
    }

    // Get the target length of the routing table
    log_debug("acquire target length");
    uint32_t target_length = 0;
    if (header->compress_as_much_as_possible == 0) {
        target_length = rtr_alloc_max();
    }
    log_info("target length of %d", target_length);

    // Perform the minimisation
    log_debug("minimise");
    minimise(&table, target_length);
    log_debug("done minimise");

    // report size to the host for provenance aspects
    log_info("has compressed the router table to %d entries", table.size);

    // Try to load the routing table
    log_debug("try loading tables");
    if (load_routing_table(&table, header->app_id)) {
        cleanup_and_exit(header, table);
    } else {

        // Otherwise give up and exit with an error
        log_error(
            "Failed to minimise routing table to fit %u entries. "
            "(Original table: %u after removing default entries: %u "
            "after Ordered Covering: %u).",
            rtr_alloc_max(), size_original, table.size, table.size);

        // Free the block of SDRAM used to load the routing table.
        log_debug("free sdram blocks which held router tables");
        FREE((void *) header);

        // set the failed flag and exit
        sark.vcpu->user0 = 1;
        spin1_exit(0);
    }
}

#endif //__MINIMISE_H__
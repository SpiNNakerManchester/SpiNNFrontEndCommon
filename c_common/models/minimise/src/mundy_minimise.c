#include "spin1_api.h"
#include "ordered_covering.h"
#include "remove_default_routes.h"
#include "minimise.h"
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

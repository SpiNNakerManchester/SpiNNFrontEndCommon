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
 * \dir
 * \brief Simple routing table compressor
 * \file
 * \brief SpiNNaker routing table minimisation.
 *
 * Minimises a routing table loaded into SDRAM and load the minimised table into
 * the router using the specified application ID.
 *
 * the exit code is stored in the user0 register
 *
 * The memory address with tag "1" is expected contain the following struct
 * (entry_t is defined in `routing_table.h` but is described below).
 */
#include <spin1_api.h>
#include <debug.h>
#include <malloc_extras.h>
#include "compressor_includes/compressor.h"
#include "rt_single.h"
#include "common-typedefs.h"

//! \brief The callback for setting off the router compressor
//! \param[in] unused0: unused
//! \param[in] unused1: unused
void compress_start(UNUSED uint unused0, UNUSED uint unused1) {
    log_info("Starting on chip router compressor");

    // Prepare to minimise the routing tables
    log_debug("looking for header using tag %u app_id %u", 1, sark_app_id());
    header_t *header = (header_t *) sark_tag_ptr(1, sark_app_id());
    log_debug("reading data from 0x%08x", (uint32_t) header);
    print_header(header);

    // set the flag to something non-useful
    sark.vcpu->user0 = 20;

    // Load the routing table
    log_debug("start reading table");
    read_table(header);
    log_debug("finished reading table");

     // Store intermediate sizes for later reporting (if we fail to minimise)
    uint32_t size_original = routing_table_get_n_entries();

    // Currently not used here but used by the bitfeild stuff
    bool failed_by_malloc = false;
    // Currently not used here but used by the bitfeild stuff
    bool stop_compressing = false;
    if (run_compressor(header->compress_as_much_as_possible,
        &failed_by_malloc, &stop_compressing)) {
        // report size to the host for provenance aspects
        log_info("Compressed the router table from %d to %d entries",
                size_original, routing_table_get_n_entries());
    } else {
        log_info("Exiting as compressor reported failure");
        // set the failed flag and exit
        malloc_extras_terminate(EXIT_FAIL);
    }
    // Try to load the routing table
    log_debug("try loading tables");
    if (load_routing_table(header->app_id)) {
        cleanup_and_exit(header);
    } else {
        // Otherwise give up and exit with an error
        log_error("Failed to minimise routing table to fit %u entries. "
                "(Original table: %u after compression: %u).",
                rtr_alloc_max(), size_original,
                routing_table_get_n_entries());

        // Free the block of SDRAM used to load the routing table.
        log_debug("free sdram blocks which held router tables");
        FREE((void *) header);

        // set the failed flag and exit
        malloc_extras_terminate(EXIT_FAIL);
    }
}

//! \brief the main entrance.
void c_main(void) {
    log_info("%u bytes of free DTCM", sark_heap_max(sark.heap, 0));
    malloc_extras_turn_off_safety();

    // kick-start the process
    spin1_schedule_callback(compress_start, 0, 0, 3);

    // go
    spin1_start(SYNC_NOWAIT);	//##
}

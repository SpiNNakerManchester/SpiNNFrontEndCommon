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
 *
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
#include <debug.h>
#ifdef USE_PAIR
    #include "pair_minimize.h"
#else
    #include <junk.h>
#endif
#include "unordered_remove_default_routes.h"
#include "routing_table.h"

//! \brief The callback for setting off the router compressor
//! \param[in] unused0: unused
//! \param[in] unused1: unused
bool run_compressor(int compress_as_much_as_possible) {
    // Get the target length of the routing table
    log_debug("acquire target length");
    int target_length = 0;
    if (compress_as_much_as_possible == 0) {
        target_length = rtr_alloc_max();
    }
    log_info("target length of %d", target_length);

    if (remove_default_routes_minimise(target_length)) {
        return true;
    }

   // Perform the minimisation
    log_debug("minimise");
    minimise_run(target_length);
    log_debug("done minimise");

    return routing_table_get_n_entries() <= target_length;
}

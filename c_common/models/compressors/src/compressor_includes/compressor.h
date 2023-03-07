/*
 * Copyright (c) 2017 The University of Manchester
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
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
    #include "ordered_covering_includes/ordered_covering.h"
#endif
#include "remove_default_routes.h"
#include "../common/routing_table.h"

//! \brief The callback for setting off the router compressor
//! \param[in] compress_as_much_as_possible: Only compress to normal routing
//!       table length
//! \param[out] failed_by_malloc: Flag stating that it failed due to malloc
//! \param[in] stop_compressing: Variable saying if the compressor should stop
//!    and return false; _set by interrupt_ DURING the run of this method!
//! \return Whether compression succeeded
bool run_compressor(int compress_as_much_as_possible, bool *failed_by_malloc,
        volatile bool *stop_compressing) {
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

    if (*stop_compressing) {
        log_info("Not compressing as asked to stop");
        return false;
    }
    // Perform the minimisation
    log_debug("minimise");
    if (minimise_run(target_length, failed_by_malloc, stop_compressing)) {
        return routing_table_get_n_entries() <= (int) rtr_alloc_max();
    } else {
        return false;
    }

}

/*
 * Copyright (c) 2019-2020 The University of Manchester
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

#include <spin1_api.h>
#include <debug.h>
#include <bit_field.h>
#include <sdp_no_scp.h>
#include <malloc_extras.h>
#include "common/routing_table.h"
#include "common/constants.h"

#include "common-typedefs.h"
#include "compressor_includes/aliases.h"
#include "compressor_includes/ordered_covering.h"
/*****************************************************************************/
/* SpiNNaker routing table minimisation with bitfield integration.
 *
 * Minimise a routing table loaded into SDRAM and load the minimised table into
 * the router using the specified application ID.
 *
 * the exit code is stored in the user1 register
 *
 * The memory address with tag "1" is expected contain the following struct
 * (entry_t is defined in `routing_table.h` but is described below).
*/

//! interrupt priorities
typedef enum interrupt_priority{
    TIMER_TICK_PRIORITY = -1,
    COMPRESSION_START_PRIORITY = 2
} interrupt_priority;

//! \timer controls, as it seems timer in massive waits doesnt engage properly
int counter = 0;
int max_counter = 0;

//! \brief pointer to enum?
instructions_to_compressor* sorter_instruction;

//! \brief bool saying if the timer has fired, resulting in attempt to compress
//! shutting down
volatile bool timer_for_compression_attempt = false;

//! \brief bool flag to say if i was forced to stop by the compressor control
volatile bool finished_by_compressor_force = false;

//! bool flag pointer to allow minimise to report if it failed due to malloc
//! issues
bool failed_by_malloc = false;

//! control flag for running compression only when needed
bool compress_only_when_needed = false;

//! control flag for compressing as much as possible
bool compress_as_much_as_possible = false;

//! \brief the sdram location to write the compressed router table into
table_t *sdram_loc_for_compressed_entries;

//! \brief aliases thingy for compression
aliases_t aliases;

//! \brief get pointer to this processor user registers
vcpu_t *this_processor = NULL;

//! \brief n bitfields testing
int n_bit_fields = -1;

// ---------------------------------------------------------------------

//! \brief stores the compressed routing tables into the compressed sdram
//! location
//! \returns bool if was successful or now
bool store_into_compressed_address(void) {
    if (routing_table_sdram_get_n_entries() > TARGET_LENGTH) {
        log_debug("not enough space in routing table");
        return false;
    }

    log_debug(
        "starting store of %d tables with %d entries",
        n_tables, routing_table_sdram_get_n_entries());

    malloc_extras_check_all_marked(50003);

    bool success = routing_table_sdram_store(
        sdram_loc_for_compressed_entries);
    malloc_extras_check_all_marked(50004);

    log_debug("finished store");
    if (!success) {
        log_error("failed to store entries into sdram.");
        return false;
    }
    return true;
}

//! \brief handles the compression process
void start_compression_process(void) {

    log_debug("in compression phase");

    // restart timer (also puts us in running state)
    spin1_resume(SYNC_NOWAIT);

    malloc_extras_check_all_marked(50001);

    // run compression
    bool success = oc_minimise(
        TARGET_LENGTH, &aliases, &failed_by_malloc,
        sorter_instruction,
        &timer_for_compression_attempt, compress_only_when_needed,
        compress_as_much_as_possible);

    // print out result for debugging purposes
    if (success) {
        log_info("Passed oc minimise with success %d", success);
    } else {
        log_info("Failed oc minimise with success %d", success);
    }
    malloc_extras_check_all_marked(50005);

    // turn off timer and set us into pause state
    spin1_pause();

    // check state
    log_debug("success was %d", success);
    if (success) {
        log_debug("store into compressed");
        success = store_into_compressed_address();
        if (success) {
            log_debug("success response");
            this_processor->user3 = SUCCESSFUL_COMPRESSION;
        } else {
            log_debug("failed by space response");
            this_processor->user3 = FAILED_TO_COMPRESS;
        }
    } else {  // if not a success, could be one of 4 states
        if (failed_by_malloc) {  // malloc failed somewhere
            log_debug("failed malloc response");
            this_processor->user3 = FAILED_MALLOC;
        } else if (*sorter_instruction != RUN) {  // control killed it
            log_debug("force fail response");
            this_processor->user3 = FORCED_BY_COMPRESSOR_CONTROL;
            log_debug("send ack");
        } else if (timer_for_compression_attempt) {  // ran out of time
            log_debug("time fail response");
            this_processor->user3 = RAN_OUT_OF_TIME;
        } else { // after finishing compression, still could not fit into table.
            log_debug("failed by space response");
            this_processor->user3 = FAILED_TO_COMPRESS;
        }
    }
}

//! \brief attempts to run the compressor algorithm and get results.
void run_compression_process(void) {
    vcpu_t *sark_virtual_processor_info = (vcpu_t*) SV_VCPU;
    this_processor = &sark_virtual_processor_info[spin1_get_core_id()];
    comp_instruction_t* instructions = (comp_instruction_t*)this_processor->user1;

    // set up fake heap
    log_debug("setting up fake heap for sdram usage");
    malloc_extras_initialise_with_fake_heap(instructions->fake_heap_data);
    log_debug("finished setting up fake heap for sdram usage");

    failed_by_malloc = false;
    timer_for_compression_attempt = false;

    // reset timer counter
    counter = 0;
    aliases_clear(&aliases);
    routing_table_reset();

    // create aliases
    aliases = aliases_init();

    // location where to store the compressed table
    sdram_loc_for_compressed_entries = instructions->compressed_table;

    malloc_extras_check_all_marked(50002);

    log_info("table init for %d tables", instructions->n_elements);
    bool success = routing_tables_init(
        instructions->n_elements, instructions->elements);
    log_debug("table init finish");

    if (!success) {
        log_error("failed to allocate memory for routing table.h state");
        this_processor->user3 = FAILED_MALLOC;
        return;
    }

    log_info("starting compression attempt");

    log_debug("my processor id at start comp is %d", spin1_get_core_id());
    // start compression process
    start_compression_process();
}

//! \brief the sdp control entrance.
//! \param[in] unused0: param 1 forced on us from api
//! \param[in] unused1: param 2 forced on us from api
void wait_for_instructions(uint unused0, uint unused1) {
    //api requirements
    use(unused0);
    use(unused1);

// values for debug logging
    int ignore_counter = 0;
    int ignore_cutoff = 1;

    // busy loop.
    while (true) {
        // set if combination of user2 and user3 is unexpected
        bool user_mismatch = false;

        // values for debug logging
        bool ignore = false;
        ignore_counter++;

        // cache the states so they dont change inside one loop
        instructions_to_compressor sorter_state =
            (instructions_to_compressor)this_processor->user2;
        compressor_states compressor_state =
            (compressor_states)this_processor->user3;

        // Documents all expected combinations of user2 and user3
        // Handle new instruction from sorter,
        // Ignore while waiting for sorter to pick up result
        // Or error if unexpected state reached
        switch(sorter_state) {

            // sorter is preparing
            case PREPARE:
                switch(compressor_state) {
                    case UNUSED:
                        // First prepare
                    case FAILED_MALLOC:
                    case FORCED_BY_COMPRESSOR_CONTROL:
                    case SUCCESSFUL_COMPRESSION:
                    case FAILED_TO_COMPRESS:
                    case RAN_OUT_OF_TIME:
                        // clear previous result
                        log_info("prepared");
                        this_processor->user3 = PREPARED;
                        break;
                    case PREPARED:
                        // waiting for sorter to pick up result
                        ignore = true;
                        break;

                    default:
                        user_mismatch = true;
                }
                break;

            case RUN:
                switch(compressor_state) {
                    case PREPARED:
                        log_info("run detected");
                        this_processor->user3 = COMPRESSING;
                        run_compression_process();
                        break;
                    case COMPRESSING:
                        // Should not be back in this loop before result set
                        user_mismatch = true;
                        break;
                    case FAILED_MALLOC:
                    case FORCED_BY_COMPRESSOR_CONTROL:
                    case SUCCESSFUL_COMPRESSION:
                    case FAILED_TO_COMPRESS:
                    case RAN_OUT_OF_TIME:
                        // waiting for sorter to pick up result
                        ignore = true;
                        break;
                    default:
                        user_mismatch = true;
                }
                break;

            case FORCE_TO_STOP:
               switch(compressor_state) {
                    case COMPRESSING:
                        // passed to compressor as *sorter_instruction
                        // Do nothing until compressor notices changed
                        ignore = true;
                        break;
                    case FAILED_MALLOC:
                        // Keep force malloc as more important message
                        ignore = true;
                        break;
                    case FORCED_BY_COMPRESSOR_CONTROL:
                        // Waiting for sorter to pick up
                        ignore = true;
                        break;
                    case SUCCESSFUL_COMPRESSION:
                    case FAILED_TO_COMPRESS:
                    case RAN_OUT_OF_TIME:
                        log_info("Force detected");
                        // The results other than MALLOC no longer matters
                        this_processor->user3 = FORCED_BY_COMPRESSOR_CONTROL;
                        break;
                    default:
                        user_mismatch = true;
                }
                break;

            case NOTHING:
               switch(compressor_state) {
                    case UNUSED:
                        // waiting for sorter to malloc user1 and send prepare
                        ignore = true;
                        break;
                    default:
                        user_mismatch = true;
                }
                break;
            default:
                user_mismatch = true;
        }

        if (user_mismatch) {
            log_error(
                "Unexpected combination of sorter_state %d and "
                "compressor_state %d", sorter_state, compressor_state);
            malloc_extras_terminate(RTE_SWERR);
        }

        // TODO consider removing as only needed for debuging
        if (ignore) {
            if (ignore_counter == ignore_cutoff){
                //log_info("No new instruction counter: %d sorter_state: %d,"
                //    "user3: %d",
                //    ignore_counter, sorter_state, this_processor->user3);
                ignore_cutoff+= ignore_cutoff;
            }
        } else {
            ignore_counter = 0;
            ignore_cutoff = 1;
        }
    }
}

//! \brief timer interrupt for controlling time taken to try to compress table
//! \param[in] unused0: not used
//! \param[in] unused1: not used
void timer_callback(uint unused0, uint unused1) {
    use(unused0);
    use(unused1);
    counter ++;

    if (counter >= max_counter){
        timer_for_compression_attempt = true;
        log_debug("passed timer point");
        spin1_pause();
    }
}

//! \brief the callback for setting off the router compressor
void initialise(void) {
    log_info("Setting up stuff to allow bitfield compressor to occur.");

    log_info("reading time_for_compression_attempt");
    vcpu_t *sark_virtual_processor_info = (vcpu_t*) SV_VCPU;
    this_processor = &sark_virtual_processor_info[spin1_get_core_id()];

    uint32_t time_for_compression_attempt = this_processor->user1;
    log_info("user 1 = %d", time_for_compression_attempt);

    // bool from int conversion happening here
    uint32_t int_value = this_processor->user2;
    log_info("user 2 = %d", int_value);
    if (int_value == 1) {
        compress_only_when_needed = true;
    }

    int_value = this_processor->user3;
    log_info("user 3 = %d", int_value);
    if (int_value == 1) {
        compress_as_much_as_possible = true;
    }

    // set user 1,2,3 registers to state before setup by sorter
    this_processor->user1 = NULL;
    this_processor->user2 = NOTHING;
    sorter_instruction = (instructions_to_compressor*) &this_processor->user2;
    this_processor->user3 = UNUSED;

    // sort out timer (this is done in a indirect way due to lack of trust to
    // have timer only fire after full time after pause and resume.
    max_counter = time_for_compression_attempt / 1000;
    spin1_set_timer_tick(1000);
    spin1_callback_on(TIMER_TICK, timer_callback, TIMER_TICK_PRIORITY);

    log_info(
       "finished initialise %d %d",
        *sorter_instruction, this_processor->user2);
    log_info("my processor id is %d", spin1_get_core_id());
}

//! \brief the main entrance.
void c_main(void) {
    log_info("%u bytes of free DTCM", sark_heap_max(sark.heap, 0));

    // set up params
    initialise();

    // kick-start the process
    spin1_schedule_callback(
        wait_for_instructions, 0, 0, COMPRESSION_START_PRIORITY);

    // go
    spin1_start(SYNC_WAIT);
}

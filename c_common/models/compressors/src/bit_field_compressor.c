/*
 * Copyright (c) 2019 The University of Manchester
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

//! \file
//! \brief The bitfield compressor
#include <spin1_api.h>
#include <debug.h>
#include <sdp_no_scp.h>
#include <malloc_extras.h>
#include "common-typedefs.h"
#include "common/constants.h"
#include "bit_field_common/compressor_sorter_structs.h"
#include "bit_field_common/bit_field_table_generator.h"
#include "common/minimise.h"
#include "compressor_includes/compressor.h"
#include "bit_field_common/routing_tables.h"
#include "bit_field_common/bit_field_table_generator.h"

/*****************************************************************************/

//! interrupt priorities
enum compressor_interrupt_priorities {
    TIMER_TICK_PRIORITY = -1,           //!< Timer uses FIQ!
    COMPRESSION_START_PRIORITY = 3      //!< Compression start is low priority
};

//! \brief Number of timer iterations to ensure close to matching tracker
#define TIMER_ITERATIONS 1000

//! \brief Timer controls, as it seems timer in massive waits doesn't
//!     necessarily engage properly. Ticks once per millisecond.
int counter = 0;
//! \brief Maximum value of ::counter, at which point the compressor should
//!     shut itself down. Number of milliseconds to allow for a compressor run.
int max_counter = 0;

//! Whether the compressor should shut down
volatile bool stop_compressing = false;

//! Allows minimise to report if it failed due to malloc issues
bool failed_by_malloc = false;

//! Whether to compress as much as possible
bool compress_as_much_as_possible = false;

//! Debugging for wait_for_instructions(): old state of sorter
instructions_to_compressor previous_sorter_state = NOT_COMPRESSOR;
//! Debugging for wait_for_instructions(): old state of compressor
compressor_states previous_compressor_state = UNUSED_CORE;

//! SDRAM are used for communication between sorter and THIS compressor
comms_sdram_t *restrict comms_sdram;

// DEBUG stuff please leave
#ifdef DEBUG_COMPRESSOR
bool hack_malloc_failed = false;
#endif
// ---------------------------------------------------------------------

//! \brief Handle the compression process
void start_compression_process(void) {
    log_debug("in compression phase");

    // restart timer (also puts us in running state)
    spin1_resume(SYNC_NOWAIT);

#ifdef DEBUG_COMPRESSOR
    if (comms_sdram->mid_point >= 100) {
        log_warning("HACK fail at 100 plus bitfeilds!");
        comms_sdram->compressor_state = FAILED_TO_COMPRESS;
        return;
    }
#endif

#ifdef DEBUG_COMPRESSOR
    if ((comms_sdram->mid_point > 0) || (!hack_malloc_failed)) {
        log_warning("HACK malloc fail!");
        hack_malloc_failed = true;
        comms_sdram->compressor_state = FAILED_MALLOC;
        return;
    }
#endif

    // run compression
    bool success = run_compressor(
            compress_as_much_as_possible, &failed_by_malloc, &stop_compressing);

    // turn off timer and set us into pause state
    spin1_pause();

    // Decode whether we succeeded or failed.
    int max_length = rtr_alloc_max();
    if (success && (routing_table_get_n_entries() <= max_length)) {
        log_info("Passed minimise_run() with success code: %d", success);
        routing_tables_save(comms_sdram->routing_tables);
        comms_sdram->compressor_state = SUCCESSFUL_COMPRESSION;
        return;
    }

    // Not a success, could be one of 4 failure states
    log_info("Failed minimise_run() with success code: %d", success);
    if (failed_by_malloc) {  // malloc failed somewhere
        log_debug("failed malloc response");
        comms_sdram->compressor_state = FAILED_MALLOC;
    } else if (comms_sdram->sorter_instruction != RUN) {  // control killed it
        log_debug("force fail response");
        comms_sdram->compressor_state = FORCED_BY_COMPRESSOR_CONTROL;
        log_debug("send ack");
    } else if (stop_compressing) {  // ran out of time
        log_debug("time fail response");
        comms_sdram->compressor_state = RAN_OUT_OF_TIME;
    } else { // after finishing compression, still could not fit into table.
        log_debug("failed by space response");
        comms_sdram->compressor_state = FAILED_TO_COMPRESS;
    }
}

//! \brief Initialise the abstraction layer of many routing tables as single
//!     big table.
void setup_routing_tables(void) {
    routing_tables_init(comms_sdram->routing_tables);

    if (comms_sdram->mid_point == 0) {
        routing_tables_clone_table(comms_sdram->uncompressed_router_table);
    } else {
        bit_field_table_generator_create_bit_field_router_tables(
                comms_sdram->mid_point, comms_sdram->uncompressed_router_table,
                comms_sdram->sorted_bit_fields);
    }
}

//! \brief Run the compressor process as requested
void run_compression_process(void) {
    if (comms_sdram->mid_point > 0) {
        log_info("Run with %d tables and %d mid_point out of %d bitfields",
                comms_sdram->routing_tables->n_sub_tables,
                comms_sdram->mid_point,
                comms_sdram->sorted_bit_fields->n_bit_fields);
    } else {
        log_info("Run with %d tables and no bitfields",
                comms_sdram->routing_tables->n_sub_tables);
    }
    log_debug("setting up fake heap for sdram usage");
    malloc_extras_initialise_with_fake_heap(comms_sdram->fake_heap_data);
    log_debug("set up fake heap for sdram usage");

    // Set all status flags
    failed_by_malloc = false;
    stop_compressing = false;
    counter = 0;

    setup_routing_tables();

    log_debug("starting compression attempt with %d entries",
            routing_table_get_n_entries());

    // start compression process
    start_compression_process();
}

//! \brief Check what to do if anything as sorter has asked to ::RUN
//! \details May do nothing if the previous run has already finished
//! \param[in] compressor_state: The current state of the compressor
//! \returns Whether the ::RUN made sense with the current compressor state
static inline bool process_run(compressor_states compressor_state) {
    switch (compressor_state) {
    case PREPARED:
        comms_sdram->compressor_state = COMPRESSING;
        run_compression_process();
        return true;
    case COMPRESSING:
        // Should not be back in this loop before result set
        return false;
    case FAILED_MALLOC:
    case FORCED_BY_COMPRESSOR_CONTROL:
    case SUCCESSFUL_COMPRESSION:
    case FAILED_TO_COMPRESS:
    case RAN_OUT_OF_TIME:
        // waiting for sorter to pick up result
        return true;
    case UNUSED_CORE:
        // Should never happen
        return false;
    }
    return false;
}

//! \brief Check what to do if anything as sorter has asked to ::PREPARE
//! \details Mainly used to clear result of previous run
//! \param[in] compressor_state: The current state of the compressor
//! \returns Whether the ::PREPARE made sense with the current compressor state
static inline bool process_prepare(compressor_states compressor_state) {
    switch (compressor_state) {
    case UNUSED_CORE:
        // First prepare
        log_info("Prepared for the first time");
        comms_sdram->compressor_state = PREPARED;
        return true;
    case FAILED_MALLOC:
    case FORCED_BY_COMPRESSOR_CONTROL:
    case SUCCESSFUL_COMPRESSION:
    case FAILED_TO_COMPRESS:
    case RAN_OUT_OF_TIME:
        // clear previous result
        log_info("prepared");
        comms_sdram->compressor_state = PREPARED;
        return true;
    case PREPARED:
        // waiting for sorter to pick up result
        return true;
    case COMPRESSING:
        // Should never happen
        return false;
    }
    return false;
}

//! \brief Check what to do if anything as sorter has asked to ::FORCE_TO_STOP
//! \details Mainly used to clear result of previous run
//!     The wait loop that calls this does not run during compressing;
//!     timer_callback() picks up the sorter change during compression
//! \param[in] compressor_state: The current state of the compressor
//! \returns Whether the ::FORCE_TO_STOP made sense with the current compressor
//!     state
static inline bool process_force(compressor_states compressor_state) {
   switch (compressor_state) {
   case COMPRESSING:
       // passed to compressor as *sorter_instruction
       // Do nothing until compressor notices changed
       return true;
   case FORCED_BY_COMPRESSOR_CONTROL:
       // Waiting for sorter to pick up
       return true;
   case FAILED_MALLOC:
   case SUCCESSFUL_COMPRESSION:
   case FAILED_TO_COMPRESS:
   case RAN_OUT_OF_TIME:
       log_info("Force detected so changing result to ack");
       // The results other than MALLOC no longer matters
       comms_sdram->compressor_state = FORCED_BY_COMPRESSOR_CONTROL;
       return true;
   case PREPARED:
   case UNUSED_CORE:
       // Should never happen
       return false;
   }
   return false;
}

//! \brief Busy-wait until there is a new instruction from the sorter.
//! \details Note that this is done at very low priority so that interrupts
//!     (including to deliver instructions to us to work) will breeze past.
//! \param[in] unused0: unused
//! \param[in] unused1: unused
static void wait_for_instructions(UNUSED uint unused0, UNUSED uint unused1) {
    // set if combination of user2 and user3 is expected
    bool users_match = true;

    // cache the states so they dont change inside one loop
    compressor_states compressor_state = comms_sdram->compressor_state;
    instructions_to_compressor sorter_state = comms_sdram->sorter_instruction;
    // When debugging Log if changed
    if (sorter_state != previous_sorter_state) {
         previous_sorter_state = sorter_state;
         log_debug("Sorter state changed  sorter: %d compressor %d",
                 sorter_state, compressor_state);
    }
    if (compressor_state != previous_compressor_state) {
        previous_compressor_state = compressor_state;
        log_debug("Compressor state changed  sorter: %d compressor %d",
                sorter_state, compressor_state);
    }

    switch (sorter_state) {
    case PREPARE:
        users_match = process_prepare(compressor_state);
        break;
    case RUN:
        users_match = process_run(compressor_state);
        break;
    case FORCE_TO_STOP:
        users_match = process_force(compressor_state);
        break;
    case NOT_COMPRESSOR:
        // For some reason compressor sees this state too
    case TO_BE_PREPARED:
        users_match = (compressor_state == UNUSED_CORE);
        break;
    case DO_NOT_USE:
        log_warning("DO_NOT_USE detected exiting wait");
        spin1_pause();
        return;
    }
    if (users_match) {
        spin1_schedule_callback(
                wait_for_instructions, 0, 0, COMPRESSION_START_PRIORITY);
    } else {
        log_error("Unexpected combination of sorter_state %d and "
                "compressor_state %d", sorter_state, compressor_state);
        malloc_extras_terminate(RTE_SWERR);
    }
}

//! \brief Timer interrupt for controlling stopping compression.
//! \details Could be due to time taken to try to compress table.
//!     Could be because sorter has cancelled run request.
//! \param[in] unused0: not used
//! \param[in] unused1: not used
static void timer_callback(UNUSED uint unused0, UNUSED uint unused1) {
    counter++;

    if (counter >= max_counter) {
        stop_compressing = true;
        log_info("passed timer point");
        spin1_pause();
    }

    // check that the sorter has told the compressor to finish for any reason
    if (comms_sdram->sorter_instruction != RUN) {
        stop_compressing = true;
        if (comms_sdram->compressor_state == COMPRESSING) {
            log_info("Sorter cancelled run request");
        } else if (comms_sdram->sorter_instruction == DO_NOT_USE) {
            log_info("Compressor no longer to be used");
        } else {
            log_warning("timer weirdness %d %d",
                    comms_sdram->sorter_instruction,
                    comms_sdram->compressor_state);
        }
        spin1_pause();
    }
}

//! \brief Set up the callback for setting off the router compressor.
static void initialise(void) {
    log_info("Setting up stuff to allow bitfield compressor to occur.");

    log_debug("reading time_for_compression_attempt");
    vcpu_t *restrict sark_virtual_processor_info = (vcpu_t *) SV_VCPU;
    vcpu_t *restrict this_vcpu_info =
            &sark_virtual_processor_info[spin1_get_core_id()];

    uint32_t time_for_compression_attempt = this_vcpu_info->user1;
    log_info("time_for_compression_attempt = %d",
            time_for_compression_attempt);

    // 0 = compress_only_when_needed, 1 = compress_as_much_as_possible
    uint32_t int_value = this_vcpu_info->user2;
    if (int_value & 1) {
        compress_as_much_as_possible = true;
    }
    log_info("int %d, compress_as_much_as_possible = %d",
            int_value, compress_as_much_as_possible);

    // Get the pointer for all cores
    comms_sdram = (comms_sdram_t *) this_vcpu_info->user3;

    // Now move the pointer to the comms for this core
    comms_sdram += spin1_get_core_id();

    // sort out timer (this is shrank to be called 1000 times, so that we can
    // check for sorter controls. e.g. is the sorter forces the compressor
    // to stop early).
    max_counter = time_for_compression_attempt / TIMER_ITERATIONS;
    spin1_set_timer_tick(TIMER_ITERATIONS);
    spin1_callback_on(TIMER_TICK, timer_callback, TIMER_TICK_PRIORITY);
    log_info("my processor id is %d", spin1_get_core_id());
}

//! \brief says this is NOT a standalone compressor.
//! \return Always false
bool standalone(void) {
    return false;
}


//! \brief the main entrance.
void c_main(void) {
    log_debug("%u bytes of free DTCM", sark_heap_max(sark.heap, 0));

    // set up params
    initialise();

    // kick-start the process
    spin1_schedule_callback(
            wait_for_instructions, 0, 0, COMPRESSION_START_PRIORITY);

    // go
    log_info("waiting for synchronisation %d %d",
            comms_sdram->sorter_instruction, comms_sdram->compressor_state);
    spin1_start(SYNC_WAIT);
}

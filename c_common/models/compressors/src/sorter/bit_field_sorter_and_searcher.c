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

//! \file
//! \brief SpiNNaker routing table minimisation with bitfield integration
//!     control processor.
//! \details Controls the attempt to minimise the router entries with bitfield
//!     components.

#include <spin1_api.h>
#include <debug.h>
#include <bit_field.h>
#include <circular_buffer.h>
#include <data_specification.h>
#include <malloc_extras.h>
#include <common-typedefs.h>
#include <common/constants.h>
#include <common/routing_table.h>
#include "bit_field_common/routing_tables_utils.h"
#include "bit_field_common/compressor_sorter_structs.h"
#include "bit_field_common/bit_field_table_generator.h"
#include "bit_field_reader.h"

//============================================================================
// #defines and enums

//! Time step for safety timer tick interrupt
#define TIME_STEP 1000

//! After how many time steps to kill the process
#define KILL_TIME 20000

//! Delay between checks of SDRAM polling
#define SDRAM_POLL_DELAY 50

//! Number of attempts for SDRAM poll
#define SDRAM_POLL_ATTEMPTS 20

//! The magic +1 for inclusive coverage that 0 index is no bitfields
#define ADD_INCLUSIVE_BIT 1

//! Flag for if a rtr_mc failure.
#define RTR_MC_FAILED 0

//! Bit shift for the app id for the route
#define ROUTE_APP_ID_BIT_SHIFT 24

//! Callback priorities
typedef enum priorities {
    COMPRESSION_START_PRIORITY = 3, //!< General processing is low priority
    TIMER_TICK_PRIORITY = 0     //!< Timer tick is high priority
} priorities;

//============================================================================
// global params

//! DEBUG variable: counter of how many time steps have passed
uint32_t time_steps = 0;

//! Whether we found a stopping position
volatile bool terminated = false;

//! \brief The uncompressed router table
//! \details Address comes from `vcpu->user1`
uncompressed_table_region_data_t *restrict uncompressed_router_table;

//! \brief The locations of bitfields from application processors
//! \details Address comes from `vcpu->user2`
region_addresses_t *restrict region_addresses;

//! \brief SDRAM blocks that the fake heap can use
//! \details Address comes from `vcpu->user3`
available_sdram_blocks *restrict usable_sdram_regions;

//! Best midpoint that record a success
int best_success = FAILED_TO_FIND;

//! Lowest midpoint that record failure
uint32_t lowest_failure;

//! The minimum number of bitfields to be merged in
uint32_t threshold_in_bitfields;

//! The store for the last routing table that was compressed
table_t *restrict last_compressed_table = NULL;

//! The compressor's SARK application id
uint32_t app_id = 0;

//! \brief the list of bitfields in sorted order based off best effect, and
//!     processor ids.
sorted_bit_fields_t *restrict sorted_bit_fields;

//! Stores which values have been tested
bit_field_t tested_mid_points;

//! SDRAM used to communicate with the compressors
comms_sdram_t *restrict comms_sdram;

//! Record if the last action was to reduce cores due to malloc
bool just_reduced_cores_due_to_malloc = false;

//============================================================================

//! \brief Load the best routing table to the router.
//! \return Whether the table was loaded into the router or not
static inline bool load_routing_table_into_router(void) {
    // Try to allocate sufficient room for the routing table.
    uint32_t start_entry = rtr_alloc_id(last_compressed_table->size, app_id);
    if (start_entry == RTR_MC_FAILED) {
        log_error("Unable to allocate routing table of size %u\n",
                last_compressed_table->size);
        return false;
    }

    // Load entries into the table (provided the allocation succeeded).
    // Note that although the allocation included the specified
    // application ID we also need to include it as the most significant
    // byte in the route (see `sark_hw.c`).
    log_debug("loading %u entries into router", last_compressed_table->size);
    for (uint32_t i = 0; i < last_compressed_table->size; i++) {
        entry_t entry = last_compressed_table->entries[i];
        uint32_t route = entry.route | (app_id << ROUTE_APP_ID_BIT_SHIFT);
        uint32_t success = rtr_mc_set(
                start_entry + i,
                entry.key_mask.key, entry.key_mask.mask, route);

        // Check that the entry was set
        if (success == RTR_MC_FAILED) {
            log_error("failed to set a router table entry at index %u",
                    start_entry + i);
            return false;
        }
    }

    // Indicate we were able to allocate routing table entries.
    return true;
}

//! \brief Send a message forcing the processor to stop its compression
//!     attempt
//! \param[in] processor_id: the processor ID to send a ::FORCE_TO_STOP to
static inline void send_force_stop_message(uint32_t processor_id) {
    // Get reference to communications block
    comms_sdram_t *comms = &comms_sdram[processor_id];
    if (comms->sorter_instruction == RUN) {
        log_debug("sending stop to processor %d", processor_id);
        comms->sorter_instruction = FORCE_TO_STOP;
    }
}

//! \brief Send a message telling the processor to prepare for the next run
//! \details This is critical as it tells the processor to clear the result
//!     field
//! \param[in] processor_id: the processor ID to send a ::PREPARE to
static inline void send_prepare_message(uint32_t processor_id) {
    // Get reference to communications block
    comms_sdram_t *comms = &comms_sdram[processor_id];
    // set message params
    log_debug("sending prepare to processor %d", processor_id);
    comms->sorter_instruction = PREPARE;
    comms->mid_point = FAILED_TO_FIND;
}

//! \brief Set up the search bitfields.
//! \return Whether the setup succeeded
static inline bool set_up_tested_mid_points(void) {
    log_info("set_up_tested_mid_point n bf addresses is %u",
            sorted_bit_fields->n_bit_fields);

    uint32_t words = get_bit_field_size(
            sorted_bit_fields->n_bit_fields + ADD_INCLUSIVE_BIT);
    tested_mid_points = MALLOC(words * sizeof(bit_field_t));

    // check the malloc worked
    if (tested_mid_points == NULL) {
        return false;
    }

    // clear the bitfields
    clear_bit_field(tested_mid_points, words);

    // return if successful
    return true;
}

//! \brief Store the addresses for freeing when response code is sent.
//! \param[in] processor_id: The compressor processor ID
//! \param[in] mid_point: The point in the bitfields to work from.
//! \param[in] table_size: Number of entries that the uncompressed routing
//!    tables need to hold.
//! \return Whether the addresses were stored
static inline bool pass_instructions_to_compressor(
        uint32_t processor_id, uint32_t mid_point, uint32_t table_size) {
    // Get reference to communications block
    comms_sdram_t *comms = &comms_sdram[processor_id];

    bool success = routing_tables_utils_malloc(
            comms->routing_tables, table_size);
    if (!success) {
        log_info("failed to create bitfield tables for midpoint %d",
                mid_point);
        return false;
    }

    // set the midpoint for the given compressor processor.
    comms->mid_point = mid_point;

    if (comms->mid_point == 0) {
        // Info stuff but local sorted_bit_fields as compressor not set yet
        log_info("using processor %d with %d entries for %d bitfields out of %u",
                processor_id, table_size, comms->mid_point,
                sorted_bit_fields->n_bit_fields);
    } else {
        // Info stuff using compressor data
        log_info("using processor %d with %d entries for %d bitfields out of %u",
                processor_id, table_size, comms->mid_point,
                comms->sorted_bit_fields->n_bit_fields);
    }

    comms->sorter_instruction = RUN;
    return true;
}

//! \brief Build tables and tries to set off a compressor processor based off
//!     a mid-point.
//! \details If there is a problem will set reset the mid_point as untested and
//!     set this and all unused compressors to ::DO_NOT_USE state.
//! \param[in] mid_point: The mid-point to start at
//! \param[in] processor_id: The processor to run the compression on
static inline void malloc_tables_and_set_off_bit_compressor(
        uint32_t mid_point, uint32_t processor_id) {
    // Get reference to communications block
    comms_sdram_t *comms = &comms_sdram[processor_id];
    // free any previous routing tables
    routing_tables_utils_free_all(comms->routing_tables);

    // malloc space for the routing tables
    uint32_t table_size = bit_field_table_generator_max_size(
            (int) mid_point, &uncompressed_router_table->uncompressed_table,
            sorted_bit_fields);

    // if successful, try setting off the bitfield compression
    comms->sorted_bit_fields = sorted_bit_fields;
    bool success = pass_instructions_to_compressor(
            processor_id, mid_point, table_size);

    if (!success) {
        // OK, lets turn this and all ready processors off to save space.
        // At least default no bitfield handled elsewhere so of to reduce.
        comms->sorter_instruction = DO_NOT_USE;

        for (int p_id = 0; p_id < MAX_PROCESSORS; p_id++) {
            instructions_to_compressor inst = comms_sdram[p_id].sorter_instruction;
            if ((inst == PREPARE) || (inst == TO_BE_PREPARED)) {
                comms_sdram[p_id].sorter_instruction = DO_NOT_USE;
            }
        }

        // Ok that midpoint did not work so need to try it again
        bit_field_clear(tested_mid_points, mid_point);
    }
}

#if 0
//! \brief Find the region ID in the region addresses for this processor ID
//! \param[in] processor_id: The processor ID to find the region ID in the
//!     addresses
//! \return The address in the addresses region for the processor ID, or
//!     `NULL` if none found.
static inline filter_region_t *find_processor_bit_field_region(
        uint32_t processor_id) {
    // find the right bitfield region
    uint32_t np = region_addresses->n_processors;
    for (uint32_t i = 0; i < np; i++) {
        bitfield_proc_t *proc = &region_addresses->processors[i];
        uint32_t region_proc_id = proc->processor;
        log_debug("is looking for %u and found %u",
                processor_id, region_proc_id);
        if (region_proc_id == processor_id) {
            return proc->filter;
        }
    }

    // if not found
    log_error("failed to find the right region. WTF");
    malloc_extras_terminate(EXIT_SWERR);
    return NULL;
}
#endif

//! \brief Set the flag for the merged filters
static inline void set_merged_filters(void) {
    log_info("best_success %d", best_success);
    for (int i = 0; i < best_success; i++) {
        // Find the actual index of this bitfield
        int j = sorted_bit_fields->sort_order[i];
        // Update the flag
        sorted_bit_fields->bit_fields[j]->merged = 1;
    }
}

//! \brief Locate the next valid midpoint to test
//! \param[out[ midpoint: The midpoint
//! \return True if a midpoint is found
static inline bool locate_next_mid_point(uint32_t *midpoint) {
    if (sorted_bit_fields->n_bit_fields == 0) {
        return false;
    }

    // if not tested yet / reset test all
    if (!bit_field_test(tested_mid_points, sorted_bit_fields->n_bit_fields)) {
        log_info("Retrying all which is mid_point %d",
                sorted_bit_fields->n_bit_fields);
        *midpoint = sorted_bit_fields->n_bit_fields;
        return true;
    }

    // need to find a midpoint
    log_debug("n_bf_addresses %d tested_mid_points %d",
            sorted_bit_fields->n_bit_fields,
            bit_field_test(tested_mid_points, sorted_bit_fields->n_bit_fields));

    // the last point of the longest space
    int best_end = FAILED_TO_FIND;

    // the length of the longest space to test
    int best_length = 0;

    // the current length of the currently detected space
    int current_length = 0;

    log_debug("best_success %d lowest_failure %u",
            best_success, lowest_failure);

    // iterate over the range to binary search, looking for biggest block to
    // explore, then take the middle of that block

    // NOTE: if there are no available bitfields, this will result in best end
    // being still set to -1, as every bit is set, so there is no blocks with
    // any best length, and so best end is never set and lengths will still be
    // 0 at the end of the for loop. -1 is a special midpoint which higher
    // code knows to recognise as no more exploration needed.
    for (uint32_t i = (uint32_t)(best_success + 1); i <= lowest_failure; i++) {
        log_debug("index: %u, value: %u current_length: %d",
                i, bit_field_test(tested_mid_points, i), current_length);

        // verify that the index has been used before
        if (bit_field_test(tested_mid_points, i)) {
           // if used before and is the end of the biggest block seen so far.
           // Record and repeat.
           if (current_length > best_length) {
                best_length = current_length;
                best_end = i - 1;
                log_debug("found best_length: %d best_end %d",
                        best_length, best_end);
           // if not the end of the biggest block, ignore (log for debugging)
           } else {
                log_debug("not best: %d best_end %d", best_length, best_end);
           }
           // if its seen a set we're at the end of a block. so reset the
           // current block len, as we're about to start another block.
           current_length = 0;
        // not set, so still within a block, increase len.
        } else {
           current_length++;
        }
    }

    if (best_length == 0) {
        // Never found anything
        return false;
    }

    // use the best less half (shifted) of the best length
    uint32_t new_mid_point = best_end - (best_length >> 1);
    log_debug("returning mid point %d", new_mid_point);

    // just a safety check, as this has caught us before.
    if (bit_field_test(tested_mid_points, new_mid_point)) {
        log_info("HOW THE HELL DID YOU GET HERE!");
        malloc_extras_terminate(EXIT_SWERR);
    }

    *midpoint = new_mid_point;
    return true;
}

//! \brief Clean up when we've found a good compression
//! \details Handles the freeing of memory from compressor processors, waiting
//!     for compressor processors to finish and removing merged bitfields from
//!     the bitfield regions.
static inline void handle_best_cleanup(void) {
    // load routing table into router
    load_routing_table_into_router();
    log_debug("finished loading table");

    log_info("setting set_n_merged_filters");
    set_merged_filters();

    // This is to allow the host report to know how many bitfields on the chip
    // merged without reading every cores bit-field region.
    vcpu_t *sark_virtual_processor_info = (vcpu_t *) SV_VCPU;
    uint processor_id = spin1_get_core_id();
    sark_virtual_processor_info[processor_id].user2 = best_success;

    // Safety to break out of loop in check_buffer_queue as terminate wont
    // stop this interrupt
    terminated = true;

    // set up user registers etc to finish cleanly
    malloc_extras_terminate(EXITED_CLEANLY);
}

//! \brief Prepare a processor for the first time.
//! \details This includes mallocing the comp_instruction_t user
//! \param[in] processor_id: The ID of the processor to prepare
//! \return Whether the preparation succeeded.
bool prepare_processor_first_time(uint32_t processor_id) {
    // Get reference to communications block
    comms_sdram_t *comms = &comms_sdram[processor_id];
    comms->sorter_instruction = PREPARE;

    // Create the space for the routing table meta data
    comms->routing_tables = MALLOC_SDRAM(sizeof(multi_table_t));
    if (comms->routing_tables == NULL) {
        comms->sorter_instruction = DO_NOT_USE;
        log_error("Error mallocing routing bake pointer on %u", processor_id);
        return false;
    }

    comms->routing_tables->sub_tables = NULL;
    comms->routing_tables->n_sub_tables = 0;
    comms->routing_tables->n_entries = 0;

    // Pass the fake heap stuff
    comms->fake_heap_data = malloc_extras_get_stolen_heap();
    log_debug("fake_heap_data %u", comms->fake_heap_data);

    // Check the processor is live
    int count = 0;
    while (comms->compressor_state != PREPARED) {
        // give chance for compressor to read
        spin1_delay_us(SDRAM_POLL_DELAY);
        if (++count > SDRAM_POLL_ATTEMPTS) {
            comms->sorter_instruction = DO_NOT_USE;
            log_error("compressor failed to reply %u", processor_id);
            return false;
        }
    }
    return true;
}

//! \brief Get the next processor id which is ready to run a compression.
//! \details May result in preparing a processor in the process.
//! \param[out] processor_id: The processor ID of the next available processor
//! \return True if a processor was found, false if not
static inline bool find_prepared_processor(uint32_t *processor_id) {
    // Look for a prepared one
    for (uint32_t p = 0; p < MAX_PROCESSORS; p++) {
        if (comms_sdram[p].sorter_instruction == PREPARE &&
                comms_sdram[p].compressor_state == PREPARED) {
            log_debug("found prepared %u", p);
            *processor_id = p;
            return true;
        }
    }

    // NOTE: This initialization component exists here due to a race condition
    // with the compressors, where we dont know if they are reacting to
    // "messages" before sync signal has been sent. We also have this here to
    // save the 16 bytes per compressor core we dont end up using.

    // Look for a processor never used and  prepare it
    for (uint32_t p = 0; p < MAX_PROCESSORS; p++) {
        log_debug("processor_id %u status %d",
                p, comms_sdram[p].sorter_instruction);
        if (comms_sdram[p].sorter_instruction == TO_BE_PREPARED) {
            if (prepare_processor_first_time(p)) {
                log_debug("found to be prepared %u", p);
                *processor_id = p;
                return true;
            }
            log_debug("first failed %u", p);
        }
    }
    log_debug("FAILED %d", FAILED_TO_FIND);
    return false;
}

//! \brief Get the next processor ID which is ready to run a compression.
//! \param[in] midpoint: The mid-point this processor will use
//! \param[out] processor_id: The processor ID of the next available processor
//! \return True if there is an available processor, false if not
static bool find_compressor_processor_and_set_tracker(
        uint32_t midpoint, uint32_t *processor_id) {
    uint32_t p;
    if (!find_prepared_processor(&p)) {
        return false;
    }
    // allocate this core to do this midpoint.
    comms_sdram[p].mid_point = midpoint;
    // set the tracker to use this midpoint
    bit_field_set(tested_mid_points, midpoint);
    // return processor id
    *processor_id = p;
    return true;
}

//! \brief Set up the compression attempt for the no-bitfield version.
//! \return Whether setting off the compression attempt was successful.
bool setup_no_bitfields_attempt(void) {
    if (threshold_in_bitfields > 0) {
        log_info("No bitfields attempt skipped due to threshold of %d percent",
                region_addresses->threshold);
        return true;
    }

    uint32_t p;
    if (!find_compressor_processor_and_set_tracker(NO_BIT_FIELDS, &p)) {
        log_error("No processor available for no bitfield attempt");
        malloc_extras_terminate(RTE_SWERR);
    }
    // set off a none bitfield compression attempt, to pipe line work
    log_info("sets off the no bitfield version of the search on %u", p);

    pass_instructions_to_compressor(p, NO_BIT_FIELDS,
            uncompressed_router_table->uncompressed_table.size);
    return true;
}

//! \brief Check if a compressor processor is available.
//! \return Whether at least one processor is ready to compress
static bool all_compressor_processors_busy(void) {
    for (uint32_t p = 0; p < MAX_PROCESSORS; p++) {
        log_debug("processor_id %d status %d",
                p, comms_sdram[p].sorter_instruction);
        switch (comms_sdram[p].sorter_instruction) {
        case TO_BE_PREPARED:
            return false;
        case PREPARE:
            if (comms_sdram[p].compressor_state == PREPARED) {
                return false;
            }
            break;
        default:
            // This processor is busy; continue to next one
            break;
        }
    }
    return true;
}

//! \brief Check to see if all compressor processor are done and not ready
//! \return Whether all processors are done and not set ready
bool all_compressor_processors_done(void) {
    for (uint32_t p = 0; p < MAX_PROCESSORS; p++) {
        if (comms_sdram[p].sorter_instruction >= PREPARE) {
            return false;
        }
    }
    return true;
}

//! \brief Check if all processors are done; if yes, run best and exit
//! \return False if at least one compressors is not done.
//!     True if termination fails (which shouldn't happen, as the application
//!     should terminate on success...)
bool exit_carry_on_if_all_compressor_processors_done(void) {
    for (uint32_t p = 0; p < MAX_PROCESSORS; p++) {
        if (comms_sdram[p].sorter_instruction >= PREPARE) {
            return false;
        }
    }

    // Check there is nothing left to do
    uint32_t mid_point;
    if (locate_next_mid_point(&mid_point)) {
        log_error("Ran out of processors while still having mid_point %u to do",
                mid_point);
        malloc_extras_terminate(RTE_SWERR);
        // Should never get here but break out of the loop
        terminated = true;
        return true;
    }

    // Should never get here if above check worked but just in case
    if (just_reduced_cores_due_to_malloc) {
        log_error("Last result was a malloc fail! Use host");
        malloc_extras_terminate(RTE_SWERR);
        // Should never get here but break out of the loop
        terminated = true;
        return true;
    }

    // Check there was actually a result
    if (best_success == FAILED_TO_FIND) {
        log_error("No usable result found! Use host");
        malloc_extras_terminate(RTE_SWERR);
        // Should never get here but break out of the loop
        terminated = true;
        return true;
    }

    // Should never get here if above check failed but just in case
    if (best_success < (int) threshold_in_bitfields) {
        log_error("The threshold is %d bitfields. "
                "Which is %d percent of the total of %u",
                threshold_in_bitfields, region_addresses->threshold,
                sorted_bit_fields->n_bit_fields);
        log_error("Best result found was %d Which is below the threshold! "
                "Use host", best_success);
        malloc_extras_terminate(RTE_SWERR);
        // Should never get here but break out of the loop
        terminated = true;
        return true;
    }

    handle_best_cleanup();

    // Should never get here but break out of the loop
    terminated = true;
    return true;
}

//! \brief Start the binary search on another compressor if one available
void carry_on_binary_search(void) {
    if (exit_carry_on_if_all_compressor_processors_done()) {
        return; // Should never get here but just in case
    }
    if (all_compressor_processors_busy()) {
        log_debug("all_compressor_processors_busy");
        return;  //Pass back to check_buffer_queue
    }
    log_debug("start carry_on_binary_search");

    uint32_t mid_point;
    if (!locate_next_mid_point(&mid_point)) {
        // OK, lets turn all ready processors off as done.
        for (uint32_t p = 0; p < MAX_PROCESSORS; p++) {
            // Get reference to communications block
            comms_sdram_t *comms = &comms_sdram[p];
            if (comms->sorter_instruction == PREPARE) {
                comms->sorter_instruction = DO_NOT_USE;
            } else if (comms->sorter_instruction > PREPARE) {
                log_debug("waiting for processor %d status %d doing midpoint %u",
                        p, comms->sorter_instruction, comms->mid_point);
            }
        }
        return;
    }

    log_debug("available with midpoint %u", mid_point);
    uint32_t processor_id;
    (void) find_compressor_processor_and_set_tracker(mid_point, &processor_id);
    log_debug("start create at time step: %u", time_steps);
    malloc_tables_and_set_off_bit_compressor(mid_point, processor_id);
    log_debug("end create at time step: %u", time_steps);
}

//! \brief Timer interrupt for controlling time taken to try to compress table
//! \param[in] unused0: unused
//! \param[in] unused1: unused
void timer_callback(UNUSED uint unused0, UNUSED uint unused1) {
    time_steps++;
    // Debug stuff please keep
#if 0
    if ((time_steps & 1023) == 0) {
        log_info("time_steps: %u", time_steps);
    }
    if (time_steps > KILL_TIME) {
        log_error("timer overran %u", time_steps);
        malloc_extras_terminate(RTE_SWERR);
    }
#endif
}

//! \brief Handle the fact that a midpoint was successful.
//! \param[in] mid_point: The mid-point that succeeded.
//! \param[in] processor_id: The compressor processor ID
void process_success(int mid_point, uint32_t processor_id) {
    // if the mid point is better than seen before, store results for final.
    if (best_success <= mid_point) {
        best_success = mid_point;

        // If we have a previous table free it as no longer needed
        if (last_compressed_table != NULL) {
            FREE(last_compressed_table);
        }

        // Get last table and free the rest
        last_compressed_table = routing_tables_utils_convert(
            comms_sdram[processor_id].routing_tables);
        log_debug("n entries is %d", last_compressed_table->size);
    } else {
        routing_tables_utils_free_all(comms_sdram[processor_id].routing_tables);
    }

    // kill any search below this point, as they all redundant as
    // this is a better search.
    for (uint32_t p = 0; p < MAX_PROCESSORS; p++) {
        if (comms_sdram[p].mid_point < mid_point) {
            send_force_stop_message(p);
        }
    }

    just_reduced_cores_due_to_malloc = false;
    log_debug("finished process of successful compression");
}

//! \brief Handle the fact that a midpoint failed due to insufficient memory
//! \param[in] mid_point: The mid-point that failed
//! \param[in] processor_id: The compressor processor ID
void process_failed_malloc(int mid_point, uint32_t processor_id) {
    routing_tables_utils_free_all(comms_sdram[processor_id].routing_tables);
    // Remove the flag that say this midpoint has been checked
    bit_field_clear(tested_mid_points, mid_point);

    if (just_reduced_cores_due_to_malloc) {
        log_info("Multiple malloc detected on %d keeping processor %d",
                mid_point, processor_id);
        // Not thresholding as just did a threshold
        just_reduced_cores_due_to_malloc = false;
    } else {
        comms_sdram[processor_id].sorter_instruction = DO_NOT_USE;
        log_info("Malloc detected on %d removing processor %d",
                mid_point, processor_id);
        just_reduced_cores_due_to_malloc = true;
    }
}

//! \brief Handle the fact that a midpoint failed for reasons other than
//!     memory allocation.
//! \param[in] mid_point: The mid-point that failed
//! \param[in] processor_id: The compressor processor ID
void process_failed(int mid_point, uint32_t processor_id) {
    // safety check to ensure we don't go on if the uncompressed failed
    if (mid_point <= (int) threshold_in_bitfields) {
        if (threshold_in_bitfields == NO_BIT_FIELDS) {
            log_error("The no bitfields attempted failed! Giving up");
        } else {
            log_error("The threshold is %d, "
                    "which is %d percent of the total of %u",
                    threshold_in_bitfields, region_addresses->threshold,
                    sorted_bit_fields->n_bit_fields);
            log_error("The attempt with %d bitfields failed. Giving up",
                    mid_point);
        }
        malloc_extras_terminate(EXIT_FAIL);
    }
    if (lowest_failure > (uint32_t) mid_point) {
        log_info("Changing lowest_failure from: %u to mid_point:%d",
                lowest_failure, mid_point);
        lowest_failure = (uint32_t) mid_point;
    } else {
        log_info("lowest_failure: %u already lower than mid_point:%d",
                lowest_failure, mid_point);
    }
    routing_tables_utils_free_all(comms_sdram[processor_id].routing_tables);

    // tell all compression processors trying midpoints above this one
    // to stop, as its highly likely a waste of time.
    for (uint32_t p = 0; p < MAX_PROCESSORS; p++) {
        if (comms_sdram[p].mid_point > mid_point) {
            send_force_stop_message(p);
        }
    }

    // handler to say this message has changed the last to not be a malloc fail
    just_reduced_cores_due_to_malloc = false;
}

//! \brief Process the response from a compressor's attempt to compress.
//! \param[in] processor_id: The compressor processor ID
//! \param[in] finished_state: The response code
void process_compressor_response(
        uint32_t processor_id, compressor_states finished_state) {
    // locate this responses midpoint
    int mid_point = comms_sdram[processor_id].mid_point;
    log_debug("received response %d from processor %d doing %d midpoint",
            finished_state, processor_id, mid_point);

    // free the processor for future processing
    send_prepare_message(processor_id);

    // process compressor response based off state.
    switch (finished_state) {
    case SUCCESSFUL_COMPRESSION:
        // compressor was successful at compressing the tables.
        log_info("successful from processor %d doing mid point %d "
                "best so far was %d",
                processor_id, mid_point, best_success);
        process_success(mid_point, processor_id);
        break;

    case FAILED_MALLOC:
        // compressor failed as a malloc request failed.
        log_info("failed by malloc from processor %d doing mid point %d",
                processor_id, mid_point);
        process_failed_malloc(mid_point, processor_id);
        break;

    case FAILED_TO_COMPRESS:
        // compressor failed to compress the tables as no more merge options.
        log_info("failed to compress from processor %d doing mid point %d",
                processor_id, mid_point);
        process_failed(mid_point, processor_id);
        break;

    case RAN_OUT_OF_TIME:
        // compressor failed to compress as it ran out of time.
        log_info("failed by time from processor %d doing mid point %d",
                processor_id, mid_point);
        process_failed(mid_point, processor_id);
        break;

    case FORCED_BY_COMPRESSOR_CONTROL:
        // compressor stopped at the request of the sorter.
        log_debug("ack from forced from processor %d doing mid point %d",
                processor_id, mid_point);
        routing_tables_utils_free_all(comms_sdram[processor_id].routing_tables);
        break;

    case UNUSED_CORE:
    case PREPARED:
    case COMPRESSING:
        // states that shouldn't occur
        log_error("no idea what to do with finished state %d, "
                "from processor %d", finished_state, processor_id);
        malloc_extras_terminate(RTE_SWERR);
    }
}

//! \brief Check compressors' state till they're finished.
//! \param[in] unused0: unused
//! \param[in] unused1: unused
void check_compressors(UNUSED uint unused0, UNUSED uint unused1) {
    log_info("Entering the check_compressors loop");
    // iterate over the compressors buffer until we have the finished state
    while (!terminated) {
        bool no_new_result = true;

        // iterate over processors looking for a new result
        for (uint32_t p = 0; p < MAX_PROCESSORS; p++) {
            // Check each compressor asked to run or forced
            compressor_states finished_state = comms_sdram[p].compressor_state;
            if (finished_state > COMPRESSING) {
                no_new_result = false;
                process_compressor_response(p, finished_state);
            }
        }
        if (no_new_result) {
            log_debug("no_new_result");
            // Check if another processor could be started or even done
            carry_on_binary_search();
        } else {
            log_debug("result");
        }
    }
    // Safety code in case exit after setting best_found fails
    log_info("exiting the interrupt, to allow the binary to finish");
}

//! \brief Start binary search on all compressors, dividing the bitfields as
//!     evenly as possible.
void start_binary_search(void) {
    // Find the number of available processors
    uint32_t available = 0;
    for (uint32_t p = 0; p < MAX_PROCESSORS; p++) {
        if (comms_sdram[p].sorter_instruction == TO_BE_PREPARED) {
            available++;
        }
    }

    // Set off the worse acceptable (note no bitfield would have been set off
    // earlier)
    if (threshold_in_bitfields > 0) {
        uint32_t p;
        (void) find_compressor_processor_and_set_tracker(
                threshold_in_bitfields, &p);
        malloc_tables_and_set_off_bit_compressor(threshold_in_bitfields, p);
    }

    // create slices and set off each slice.
    uint32_t mid_point = sorted_bit_fields->n_bit_fields;
    while ((available > 0) && (mid_point > threshold_in_bitfields)) {
        uint32_t p;
        // Check the processor replied and has not been turned of by previous
        if (!find_compressor_processor_and_set_tracker(mid_point, &p)) {
            log_error("No processor available in start_binary_search");
            return;
        }
        malloc_tables_and_set_off_bit_compressor(mid_point, p);

        // Find the next step which may change due to rounding
        int step = (mid_point - threshold_in_bitfields) / available;
        if (step < 1) {
            step = 1;
        }
        mid_point -= step;
        available--;
    }
}

//! \brief Ensure that for each router table entry there is at most 1 bitfield
//!        per processor
//! \param[in] sorted_bit_fields The bit fields ordered by key
static inline void check_bitfield_to_routes(
        sorted_bit_fields_t *restrict sorted_bit_fields) {
    filter_info_t **bit_fields = sorted_bit_fields->bit_fields;
    int *processor_ids = sorted_bit_fields->processor_ids;
    entry_t *entries = uncompressed_router_table->uncompressed_table.entries;
    uint32_t n_bf = sorted_bit_fields->n_bit_fields;
    uint32_t bf_i = 0;

    for (uint32_t i = 0; i < uncompressed_router_table->uncompressed_table.size; i++) {
        // Bit field of seen processors (assumes less than 33 processors)
        uint32_t seen_processors = 0;
        // Go through all bitfields that match the key
        while (bf_i < n_bf && (entries[i].key_mask.mask & bit_fields[bf_i]->key) ==
                entries[i].key_mask.key) {

            if (seen_processors & (1 << processor_ids[bf_i])) {
                log_error("Routing key 0x%08x matches more than one bitfield key"
                        " on processor %d (last found 0x%08x)",
                        entries[i].key_mask.key, processor_ids[bf_i],
                        bit_fields[bf_i]->key);
                malloc_extras_terminate(EXIT_SWERR);
            }
            seen_processors |= (1 << processor_ids[bf_i]);
            bf_i++;
        }
    }
}

//! \brief Start the work for the compression search
//! \param[in] unused0: unused
//! \param[in] unused1: unused
void start_compression_process(UNUSED uint unused0, UNUSED uint unused1) {
    // malloc the struct and populate n bit-fields. DOES NOT populate the rest.
    sorted_bit_fields = bit_field_reader_initialise(region_addresses);
    // check state to fail if not read in
    if (sorted_bit_fields == NULL) {
        log_error("failed to read in bitfields, quitting");
        malloc_extras_terminate(EXIT_MALLOC);
    }

    // Set the threshold
    if (region_addresses->threshold == 0) {
        threshold_in_bitfields = 0;
    } else {
        threshold_in_bitfields = (sorted_bit_fields->n_bit_fields *
                region_addresses->threshold) / 100;
        best_success = threshold_in_bitfields;
    }
    log_info("threshold_in_bitfields %d which is %d percent of %d",
            threshold_in_bitfields, region_addresses->threshold,
            sorted_bit_fields->n_bit_fields);

    // set up mid point trackers. NEEDED here as setup no bitfields attempt
    // will use it during processor allocation.
    set_up_tested_mid_points();

    // set off the first compression attempt (aka no bitfields).
    if (!setup_no_bitfields_attempt()) {
        log_error("failed to set up uncompressed attempt");
        malloc_extras_terminate(EXIT_MALLOC);
    }

    log_debug("populating sorted bitfields at time step: %d", time_steps);
    bit_field_reader_read_in_bit_fields(region_addresses, sorted_bit_fields);
    check_bitfield_to_routes(sorted_bit_fields);

    // the first possible failure is all bitfields so set there.
    lowest_failure = sorted_bit_fields->n_bit_fields;
    log_debug("finished reading bitfields at time step: %d", time_steps);

    //TODO: safety code to be removed
    for (uint32_t i = 0; i < sorted_bit_fields->n_bit_fields; i++) {
        // get key
        filter_info_t *bf_pointer = sorted_bit_fields->bit_fields[i];
        if (bf_pointer == NULL) {
            log_info("failed at index %d", i);
            malloc_extras_terminate(RTE_SWERR);
            return;
        }
    }

    // start the binary search by slicing the search space by the compressors.
    start_binary_search();

    // set off checker which in turn sets of the other compressor processors
    spin1_schedule_callback(
            check_compressors, 0, 0, COMPRESSION_START_PRIORITY);
}

//! \brief Get a handle to this CPU's vcpu structure
//! \return the vcpu structure
static inline vcpu_t *get_this_vcpu_info(void) {
    vcpu_t *sark_virtual_processor_info = (vcpu_t *) SV_VCPU;
    vcpu_t *restrict this_vcpu_info =
            &sark_virtual_processor_info[spin1_get_core_id()];
    return this_vcpu_info;
}

//! \brief Set up a tracker for the user registers so that its easier to use
//!     during coding.
static void initialise_user_register_tracker(void) {
    log_debug("set up user register tracker (easier reading)");
    vcpu_t *restrict this_vcpu_info = get_this_vcpu_info();

    // convert user registers to struct pointers
    data_specification_metadata_t *restrict app_ptr_table =
            (data_specification_metadata_t *) this_vcpu_info->user0;
    uncompressed_router_table =
            (uncompressed_table_region_data_t *) this_vcpu_info->user1;
    region_addresses = (region_addresses_t *) this_vcpu_info->user2;

    comms_sdram = region_addresses->comms_sdram;
    for (uint32_t p = 0; p < MAX_PROCESSORS; p++) {
        // Get reference to communications block
        comms_sdram_t *comms = &comms_sdram[p];

        comms->compressor_state = UNUSED_CORE;
        comms->sorter_instruction = NOT_COMPRESSOR;
        comms->mid_point = FAILED_TO_FIND;
        comms->routing_tables = NULL;
        comms->uncompressed_router_table =
                &uncompressed_router_table->uncompressed_table;
        comms->sorted_bit_fields = NULL;
        comms->fake_heap_data = NULL;
    }
    usable_sdram_regions = (available_sdram_blocks *) this_vcpu_info->user3;

    log_debug("finished setting up register tracker:\n\n"
            "user0 = %d\n user1 = %d\n user2 = %d\n user3 = %d\n",
            app_ptr_table, uncompressed_router_table,
            region_addresses, usable_sdram_regions);
}

//! \brief Read in router table setup parameters.
static void initialise_routing_control_flags(void) {
    app_id = uncompressed_router_table->app_id;
    log_debug("app id %u, uncompress total entries %u",
            app_id, uncompressed_router_table->uncompressed_table.size);
}

//! \brief Set things up for the compressor processors so they are ready to be
//!     compressing
//! \return Whether the initialisation of compressors succeeded
bool initialise_compressor_processors(void) {
    // allocate DTCM memory for the processor status trackers
    log_info("allocate and step compressor processor status");
    compressor_processors_top_t *compressor_processors_top = (void *)
            &region_addresses->processors[region_addresses->n_processors];

    // Switch compressor processors to TO_BE_PREPARED
    for (uint32_t i = 0; i < compressor_processors_top->n_processors; i++) {
        uint32_t p = compressor_processors_top->processor_id[i];
        comms_sdram[p].sorter_instruction = TO_BE_PREPARED;
    }
    return true;
}

//! \brief Callback to set off the router compressor.
//! \return Whether the initialisation was successful
static bool initialise(void) {
    log_debug("Setting up stuff to allow bitfield compressor control process"
            " to occur.");

    // Get pointer to 1st virtual processor info struct in SRAM
    initialise_user_register_tracker();

    // ensure the original table is sorted by key
    // (done here instead of by host for performance)
    sort_table_by_key(&uncompressed_router_table->uncompressed_table);

    // get the compressor data flags (app id, compress only when needed,
    //compress as much as possible, x_entries
    initialise_routing_control_flags();

    // build the fake heap for allocating memory
    log_info("setting up fake heap for sdram usage");
    if (!malloc_extras_initialise_and_build_fake_heap(usable_sdram_regions)) {
        log_error("failed to setup stolen heap");
        return false;
    }

    // allows us to not be forced to use the safety code (
    // used in production mode)
    malloc_extras_turn_off_safety();

    log_info("finished setting up fake heap for sdram usage");

    // get the compressor processors stored in an array
    log_debug("start init of compressor processors");
    if (!initialise_compressor_processors()) {
        log_error("failed to init the compressor processors.");
        return false;
    }

    // finished init
    return true;
}

//! \brief The main entrance.
void c_main(void) {
    if (!initialise()) {
        log_error("failed to init");
        malloc_extras_terminate(EXIT_FAIL);
    }

    // set up interrupts
    spin1_set_timer_tick(TIME_STEP);
    spin1_callback_on(TIMER_TICK, timer_callback, TIMER_TICK_PRIORITY);

    // kick-start the process
    spin1_schedule_callback(
            start_compression_process, 0, 0, COMPRESSION_START_PRIORITY);

    // go
    log_debug("waiting for sycn");
    spin1_start(SYNC_WAIT);
}

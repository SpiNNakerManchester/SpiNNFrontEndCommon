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
#include <circular_buffer.h>
#include <data_specification.h>
#include "common-typedefs.h"
#include "common/platform.h"
#include "common/routing_table.h"
#include "common/sdp_formats.h"
#include "common/constants.h"
#include "common/compressor_sorter_structs.h"
#include "sorter_includes/bit_field_table_generator.h"
#include "sorter_includes/helpful_functions.h"
#include "sorter_includes/constants.h"
#include "sorter_includes/bit_field_reader.h"
#include "sorter_includes/bit_field_sorter.h"
#include "sorter_includes/message_sending.h"
/*****************************************************************************/
/* SpiNNaker routing table minimisation with bitfield integration control core.
 *
 * controls the attempt to minimise the router entries with bitfield
 * components.
 */

//============================================================================

//! \brief time step for safety timer tick interrupt
#define TIME_STEP 10000

//! \brief bit shift for the app id for the route
#define ROUTE_APP_ID_BIT_SHIFT 24

//! \brief the maximum amount of messages possible to be received by the sorter
#define N_MSGS_EXPECTED_FROM_COMPRESSOR 2

//! \brief callback priorities
typedef enum priorities{
    COMPRESSION_START_PRIORITY = 3, SDP_PRIORITY = -1, TIMER_TICK_PRIORITY = 2
}priorities;

//============================================================================

//! \brief bool flag saying still reading in bitfields, so that state machine don't
//! go boom when un compressed result comes in
bool reading_bit_fields = true;

//! \brief bool flag for stopping multiple attempts to run carry on binary search
bool still_trying_to_carry_on = false;

//! \brief bool flag for saying found the best stopping position
volatile bool found_best = false;

//! \brief time to take per compression iteration
uint32_t time_per_iteration = 0;

//! \brief flag of how many times the timer has fired during this one
uint32_t finish_compression_flag = 0;

//! \brief easier programming tracking of the user registers
uncompressed_table_region_data_t *uncompressed_router_table; // user1

//! \brief
region_addresses_t *region_addresses; // user2

//! \brief
available_sdram_blocks *usable_sdram_regions; // user3

//! \brief best routing table position in the search
int best_search_point = 0;

//! \brief the last routing table position in the search
int last_search_point = 0;

//! \brief the store for the last routing table that was compressed
table_t* last_compressed_table;

//! \brief the compressor app id
uint32_t app_id = 0;

// \brief how many bitfields there are
int n_bf_addresses = 0;

//! \brief the list of bitfields in sorted order based off best effect, and
//! processor ids.
sorted_bit_fields_t* sorted_bit_fields;

// \brief the list of compressor cores to bitfield routing table sdram addresses
comp_core_store_t* comp_cores_bf_tables;

//! \brief list of processor ids which will be running the compressor binary
int* compressor_cores;

//! \brief how many compression cores there are
int n_compression_cores;

//! \brief how many compression cores are available
int n_available_compression_cores;

//! \brief stores which values have been tested
bit_field_t tested_mid_points;

//! \brief stores which mid points have successes or failed
bit_field_t mid_points_successes;

//! \brief tracker for what each compressor core is doing (in terms of midpoints)
int* comp_core_mid_point;

//! \brief the bitfield by processor global holder
bit_field_by_processor_t* bit_field_by_processor;

//! \brief sdp message to send control messages to compressors cores
sdp_msg_pure_data my_msg;

//! \brief circular queue for storing sdp messages contents
circular_buffer sdp_circular_queue;

//============================================================================

//! \brief Load the best routing table to the router.
//! \return bool saying if the table was loaded into the router or not

bool load_routing_table_into_router(void) {

    // Try to allocate sufficient room for the routing table.
    int start_entry = rtr_alloc_id(last_compressed_table->size, app_id);
    if (start_entry == 0) {
        log_error(
            "Unable to allocate routing table of size %d\n",
            last_compressed_table->size);
        return false;
    }

    // Load entries into the table (provided the allocation succeeded).
    // Note that although the allocation included the specified
    // application ID we also need to include it as the most significant
    // byte in the route (see `sark_hw.c`).
    log_debug("loading %d entries into router", last_compressed_table->size);
    for (uint32_t entry_id = 0; entry_id < last_compressed_table->size;
            entry_id++) {
        entry_t entry = last_compressed_table->entries[entry_id];
        uint32_t route = entry.route | (app_id << ROUTE_APP_ID_BIT_SHIFT);
        rtr_mc_set(
            start_entry + entry_id, entry.key_mask.key, entry.key_mask.mask,
            route);
    }

    // Indicate we were able to allocate routing table entries.
    return true;
}


//! \brief sends a sdp message forcing the processor to stop its compression
//! attempt
//! \param[in] processor_id: the processor to force stop compression attempt
//! \return bool saying successfully sent the message
void send_sdp_force_stop_message(int compressor_core_index){
    // set message params
    log_debug(
        "sending stop to core %d", compressor_cores[compressor_core_index]);
    my_msg.dest_port =
        (RANDOM_PORT << PORT_SHIFT) | compressor_cores[compressor_core_index];
    compressor_payload_t* data = (compressor_payload_t*) &my_msg.data;
    data->command = STOP_COMPRESSION_ATTEMPT;
    my_msg.length = LENGTH_OF_SDP_HEADER + sizeof(command_codes_for_sdp_packet);

    // send sdp packet
    message_sending_send_sdp_message(
        &my_msg, compressor_cores[compressor_core_index]);
}

//! \brief sets up the search bitfields.
//! \return bool saying success or failure of the setup

bool set_up_search_bitfields(void) {
    // if there's no bitfields to read, then just set stuff to NULL. let that
    // be the check in future usages for this path.
    if (n_bf_addresses == 0){
        tested_mid_points = NULL;
        mid_points_successes = NULL;
        return true;
    }

    log_info("n bf addresses is %d", n_bf_addresses);
    uint32_t words = get_bit_field_size(n_bf_addresses);
    if (tested_mid_points == NULL) {
        tested_mid_points = (bit_field_t) MALLOC(words * sizeof(bit_field_t));
    }
    if (mid_points_successes == NULL){
        mid_points_successes = (bit_field_t) MALLOC(words * sizeof(bit_field_t));
    }

    platform_check_all();

    // check the malloc worked
    if (tested_mid_points == NULL) {
        return false;
    }
    if (mid_points_successes == NULL) {
        FREE(tested_mid_points);
        return false;
    }

    // clear the bitfields
    clear_bit_field(tested_mid_points, words);
    clear_bit_field(mid_points_successes, words);

    platform_check_all();

    // return if successful
    return true;
}


//! \brief counts how many cores are actually doing something.
//! \return the number of compressor cores doing something at the moment.

int count_many_on_going_compression_attempts_are_running(void) {
    int count = 0;
    for (int c_core_index = 0; c_core_index < n_compression_cores;
            c_core_index++) {
        if (comp_core_mid_point[c_core_index] != DOING_NOWT) {
            count ++;
        }
    }
    return count;
}

//! \brief locate the core index for this processor id.
//! \param[in] processor_id: the processor id to find index for.
//! \return the index in the compressor cores for this processor id
static inline int get_core_index_from_id(int processor_id) {
    for (int comp_core_index = 0; comp_core_index < n_compression_cores;
            comp_core_index++) {
        if (compressor_cores[comp_core_index] == processor_id) {
            return comp_core_index;
        }
    }
    terminate(EXIT_FAIL);
    return 0;
}

//! builds tables and tries to set off a compressor core based off midpoint
//! \param[in] mid_point: the mid point to start at
//! \return bool fag if it fails for memory issues

bool create_tables_and_set_off_bit_compressor(int mid_point) {
    int n_rt_addresses = 0;
    log_info("started create bit field router tables");
    table_t **bit_field_routing_tables =
        bit_field_table_generator_create_bit_field_router_tables(
            mid_point, &n_rt_addresses, region_addresses,
            uncompressed_router_table, bit_field_by_processor,
            sorted_bit_fields);

    if (bit_field_routing_tables == NULL){
        log_info(
            "failed to create bitfield tables for midpoint %d", mid_point);
        return false;
    }

    log_info("finished creating bit field router tables");

    log_info("bbqqc");
    platform_check_all();
    log_info("bbqqcc");

    // if successful, try setting off the bitfield compression
    bool success = message_sending_set_off_bit_field_compression(
        n_rt_addresses, mid_point, comp_cores_bf_tables,
        bit_field_routing_tables, &my_msg, compressor_cores,
        n_compression_cores, comp_core_mid_point,
        &n_available_compression_cores);

    // if successful, move to next search point.
    if (!success){
        log_debug("failed to set off bitfield compression");
        return false;
    }
    else{
        return true;
    }
}

//! \brief try running compression on just the uncompressed (attempt to check
//!     that without bitfields compression will work).
//! \return bool saying success or failure of the compression
bool start_binary_search(void){

    // if there's only there's no available, but cores still attempting. just
    // return. it'll bounce back when a response is received
    if (n_available_compression_cores == 0 &&
            count_many_on_going_compression_attempts_are_running() > 0) {
        log_debug(
            "not got any extra cores, but cores are running. so waiting "
            "for their responses");
        reading_bit_fields = false;
        return true;
    }

    // deduce how far to space these testers
    int hops_between_compression_cores =
        n_bf_addresses / n_available_compression_cores;
    int multiplier = 1;

    // safety check for floored to 0.
    if (hops_between_compression_cores == 0) {
        hops_between_compression_cores = 1;
    }

    log_info("n_bf_addresses is %d", n_bf_addresses);
    log_info(
        "n available compression cores is %d", n_available_compression_cores);
    log_info("hops between attempts is %d", hops_between_compression_cores);

    bool failed_to_malloc = false;
    int new_mid_point = hops_between_compression_cores * multiplier;
    log_info("n bf addresses = %d", n_bf_addresses);

    for (int index = 0; index < n_bf_addresses; index++) {
        log_debug(
            "sorted bitfields address at index %d is %x",
            index, sorted_bit_fields->bit_fields[index]);
        log_debug(
            "sorted bitfield processor at index %d is %d",
            index, sorted_bit_fields->processor_ids[index]);
    }



    // iterate till either ran out of cores, or failed to malloc sdram during
    // the setup of a core or when gone too far
    while ((n_available_compression_cores != 0) && !failed_to_malloc &&
            (new_mid_point <= n_bf_addresses)) {

        log_info("next mid point to consider = %d", new_mid_point);
        platform_check_all();

        bool success = create_tables_and_set_off_bit_compressor(new_mid_point);
        platform_check_all();
        log_info("success is %d", success);

        if (success) {
            multiplier++;
        }
        else {
            log_info(
                "failed to malloc when setting up compressor with multiplier"
                " %d", multiplier);
            failed_to_malloc = true;
        }

        //update to next new mid point
        new_mid_point = hops_between_compression_cores * multiplier;
    }

    log_debug("finished the start of compression core allocation");

    // if it did not set off 1 compression. fail fully. coz it wont ever get
    // anything done. host will pick up the slack
    if (multiplier == 1) {
        log_info("failed at first bitfield");
        return false;
    }

    // set off at least one compression, but at some point failed to malloc
    // sdram. assume this is the cap on how many cores can be ran at any
    // given time
    if (failed_to_malloc) {
        n_available_compression_cores = 0;
    }

    // return success for reading in and sorting bitfields
    reading_bit_fields = false;

    // say we've started
    return true;
}


//! \brief finds the region id in the region addresses for this processor id
//! \param[in] processor_id: the processor id to find the region id in the
//! addresses
//! \return the address in the addresses region for the processor id
static inline filter_region_t* find_processor_bit_field_region(
        int processor_id){

    // find the right bitfield region
    for (int r_id = 0; r_id < region_addresses->n_pairs; r_id++) {
        int region_proc_id = region_addresses->pairs[r_id].processor;
        log_debug(
            "is looking for %d and found %d", processor_id, region_proc_id);
        if (region_proc_id == processor_id){
            return region_addresses->pairs[r_id].filter;
        }
    }

    // if not found
    log_error("failed to find the right region. WTF");
    terminate(EXIT_SWERR);
    return NULL;
}

//! \brief checks if a key is in the set to be removed.
//! \param[in] sorted_bf_key_proc: the key store
//! \param[in] key: the key to locate a entry for
//! \return true if found, false otherwise

bool has_entry_in_sorted_keys(
        proc_bit_field_keys_t sorted_bf_key_proc, uint32_t key) {
    for (int element_index = 0;
            element_index < sorted_bf_key_proc.key_list->length_of_list;
            element_index++) {
        log_debug(
            "length %d index %d key %d",
            sorted_bf_key_proc.key_list->length_of_list, element_index, key);
        if (sorted_bf_key_proc.key_list->master_pop_keys[element_index] ==
                key) {
            return true;
        }
    }
    return false;
}

//! \brief removes the merged bitfields from the application cores bitfield
//!        regions
//! \return bool if was successful or not

bool remove_merged_bitfields_from_cores(void) {
    // only try if there are bitfields to remove
    if (n_bf_addresses == 0){
        log_info("no bitfields to remove");
        return true;
    }

    // which bitfields are to be removed from which processors
    proc_bit_field_keys_t *sorted_bf_key_proc = sorter_sort_sorted_to_cores(
        region_addresses, best_search_point, sorted_bit_fields);
    if (sorted_bf_key_proc == NULL) {
        log_error("could not sort out bitfields to keys.");
        return false;
    }

    // iterate though the cores sorted, and remove said bitfields from its
    // region
    for (int c_i = 0; c_i < region_addresses->n_pairs; c_i++){
        int proc_id = sorted_bf_key_proc[c_i].processor_id;
        log_debug("proc %d", proc_id);

        filter_region_t *filter_region = find_processor_bit_field_region(
            proc_id);

        // iterate though the bitfield region looking for bitfields with
        // correct keys to remove
        int n_bfs = filter_region->n_filters;
        filter_region->n_filters =
            n_bfs - sorted_bf_key_proc[c_i].key_list->length_of_list;

        // only operate if there is a reduction to do
        if (filter_region->n_filters != n_bfs){
            // pointers for shifting data up by excluding the ones been added to
            // router.
            filter_info_t *write_index = filter_region->filters;
            filter_info_t *read_index = filter_region->filters;

            // iterate though the bitfields only writing ones which are not
            // removed
            for (int bf_index = 0; bf_index < n_bfs; bf_index++) {
                // if entry is to be removed
                if (!has_entry_in_sorted_keys(
                        sorted_bf_key_proc[c_i], read_index->key)) {
                    // write the data in the current write positions, if it
                    // isn't where we're currently reading from
                    if (write_index != read_index) {
                        // copy the key, n_words and bitfield pointer over to
                        // the new location
                        sark_mem_cpy(
                            write_index, read_index, sizeof(filter_info_t));
                    }
                    // update pointers
                    write_index += 1;
                }
                read_index += 1;
            }
        }
    }

    log_info("go freeing");
    // free items
    for (int core_index = 0; core_index < region_addresses->n_pairs;
            core_index++) {
        if (sorted_bf_key_proc[core_index].key_list->length_of_list != 0) {
            FREE(sorted_bf_key_proc[core_index].key_list->master_pop_keys);
            FREE(sorted_bf_key_proc[core_index].key_list);
        }
    }


    FREE(sorted_bf_key_proc);
    // return we successfully removed merged bitfields
    return true;
}

//! \brief tells ya if a compressor is already doing a mid point
//! \param[in] mid_point: the mid point to look for
//! \return bool saying true if there is a compressor running this right now

bool already_being_processed(int mid_point) {

    for (int c_index = 0; c_index < n_compression_cores; c_index++) {
        log_debug(
            "midpoint for c %d is %d. compared to %d",
            c_index, comp_core_mid_point[c_index], mid_point);
        if (comp_core_mid_point[c_index] == mid_point) {
            return true;
        }
    }
    return false;
}

//! \brief returns the best mid point tested to date. NOTE its only safe to call
//! this after the first attempt finished. which is acceptable
//! \return the best bf midpoint tested and success

int best_mid_point_to_date(void) {
    // go backwards to find the first passed value
    for (int n_bf = n_bf_addresses; n_bf >= 0; n_bf --) {
        if (bit_field_test(mid_points_successes, n_bf)) {
            log_debug("returning %d", n_bf);
            return n_bf;
        }
    }
    // not officially correct, but best place to start search from
    //if no other value has worked. and as the 0 fails will force a complete
    //failure. safe
    return 0;
}

//! \brief returns the next midpoint which has been tested
//! \param[in] mid_point: the midpoint to start from.
//! \return the next tested bf midpoint from midpoint

int next_tested_mid_point_from(int mid_point) {
     for (int n_bf = mid_point + 1; n_bf < n_bf_addresses; n_bf++) {
        if (bit_field_test(tested_mid_points, n_bf)) {
            log_debug("returns %d", n_bf);
            return n_bf;
        }
    }
    return n_bf_addresses;
}

//! \brief checks if there's anything higher to find
//! \param[in] point: the point to look from
//! \param[in] next_tested_point: top level to search to.
//! \return bool stating if theres owt to find

bool is_there_higher_points(int point, int next_tested_point){
    // if the diff between the best tested and next tested is 1, then the
    // best is the overall best
    if (next_tested_point - point == 1 && bit_field_test(
            tested_mid_points, next_tested_point)) {
        found_best = true;
        uint32_t words = get_bit_field_size(n_bf_addresses);
        print_bit_field(tested_mid_points, words);
        log_info("found best by no higher point");
        return false;
    }
    return true;
}

//! \brief how many to track
//! \param[in] point: the point to look from
//! \param[in] next_tested_point: top level to search to.
//! \return how many compressors are running between these values.

int how_many_are_executing_between_these_points(
        int next_tested_point, int point) {
    int length = 1;
    log_info("locate already tested");
    int low_end = next_tested_point;
    int high_end = point;

    // switch if in the wrong way around for the loop
    if (point < next_tested_point){
        low_end = point;
        high_end = next_tested_point;
    }

    log_debug("going from %d to %d", low_end, high_end);
    for (int n_bf = low_end; n_bf <= high_end; n_bf++) {
        log_debug("n bf = %d", n_bf);
        if (already_being_processed(n_bf)) {
            log_debug("add to tracker %d", n_bf);
            length += 1;
        }
    }
    log_debug("legnth is going to be %d", length);
    return length;
}


//! \brief return the spaces higher than me which could be tested
//! \param[in] point: the point to look from
//! \param[in] length: the length of the testing cores.
//! \param[in] next_tested_point: top level to search to.
//! \return bool stating if it was successful or not in memory alloc

int *find_spaces_high_than_point(
        int point, int length, int next_tested_point) {
    log_debug("found best is %d", found_best);

    // malloc the spaces
    platform_check_all();
    log_debug("size is %d", length * sizeof(int));
    int* testing_cores = MALLOC((length + 1) * sizeof(int));
    log_debug("malloc-ed");
    if (testing_cores == NULL) {
        log_error(
            "failed to allocate memory for the locate next midpoint searcher");
        return NULL;
    }

    // populate list
    testing_cores[0] = point;
    int testing_core_index = 1;
    log_debug(
        "point is %d and next tested poitn is %d",
        point, next_tested_point);
    for (int n_bf = point; n_bf <= next_tested_point; n_bf++) {
        if (already_being_processed(n_bf)) {
            log_debug("dumped");
            testing_cores[testing_core_index] = n_bf;
            testing_core_index += 1;
        }
    }
    log_debug("cccc");
    platform_check_all();
    log_debug("c");

    // return success
    return testing_cores;

}

//! \brief locates the next valid midpoint which has not been tested or being
//! tested and has a chance of working/ improving the space
//! \param[out] int to next midpoint to search
//! \return bool saying if mallocs failed
bool locate_next_mid_point(int *new_mid_point) {

    // get base line to start searching for new locations to test
    int best_mp_to_date = best_mid_point_to_date();

    int next_tested_point = next_tested_mid_point_from(best_mp_to_date);

    log_debug(
        "next tested point from %d is %d",
        best_mp_to_date, next_tested_point);

    if (best_mp_to_date == next_tested_point) {
        found_best = true;
        best_search_point = best_mp_to_date;
        *new_mid_point = DOING_NOWT;
        log_debug("best search point is %d", best_mp_to_date);
        return true;
    }

    // fill in the locations bigger than best that are being tested
    platform_check_all();
    log_debug("find spaces");
    int * higher_testers = NULL;
    int length = 1;

    bool has_higher_locs = is_there_higher_points(
        best_mp_to_date, next_tested_point);
    log_debug("aftger hihger %d", has_higher_locs);
    platform_check_all();

    // if theres something to find. go find it
    if (has_higher_locs) {
        log_debug(
            "locate stuff between %d and %d",
            best_mp_to_date, next_tested_point);
        int length = how_many_are_executing_between_these_points(
            best_mp_to_date, next_tested_point);
        platform_check_all();
        log_debug("sss");
        higher_testers = find_spaces_high_than_point(
            best_mp_to_date, length, next_tested_point);
        log_debug("sssss");
        platform_check_all();
    }
    log_debug("populated higher testers");
    platform_check_all();

    // exit if best found
    if (found_best) {
        log_debug("found best");
        best_search_point = best_mp_to_date;
        return true;
    }
    log_debug("passed test");


    // failed to find next point due to malloc issues
    if (higher_testers == NULL){
        log_error("failed to find spaces higher than point");
        return false;
    }

    // got spaces, find one with the biggest difference
    log_debug("looking for biggest dif with length %d", length);
    int biggest_dif = 0;
    for (int test_base_index = 0; test_base_index < length - 1;
            test_base_index++) {

        // will be going from low to high, for that's how its been searched
        int diff = higher_testers[test_base_index + 1] -
            higher_testers[test_base_index];
        log_debug("diff is %d", diff);
        if (diff > biggest_dif) {
            biggest_dif = diff;
        }
    }
    log_debug("best dif is %d", biggest_dif);

    // handle case of no split between best and last tested
    // NOTE this only happens with n compression cores of 1.
    if (length == 1) {
        log_debug(
            "next tested point = %d, best_mp_to_date = %d",
            next_tested_point, best_mp_to_date);
        int hop = (next_tested_point - best_mp_to_date) / 2;
        if (hop == 0) {
            hop = 1;
        }
        *new_mid_point = best_mp_to_date + hop;
        log_debug("new midpoint is %d", *new_mid_point);
        return true;
    }

    // locate the first with biggest dif, split in middle and return that as
    // new mid point to test
    for (int test_base_index = 0; test_base_index < length; test_base_index++) {
        log_debug("entered");

        // will be going from high to low, for that's how its been searched
        int diff = higher_testers[test_base_index + 1] -
            higher_testers[test_base_index];
        log_debug("located diff %d, looking for b diff %d", diff, biggest_dif);

        // if the right diff, figure the midpoint of these points.
        if (diff == biggest_dif) {
            // deduce hop
            int hop = biggest_dif / 2;
            log_debug("hop is %d", hop);
            if (hop == 0){
                hop = 1;
            }

            // deduce new mid point
            *new_mid_point = higher_testers[test_base_index] + hop;
            log_debug("next mid point to test is %d", *new_mid_point);

            // check if we're testing this already, coz if we are. do nowt
            if (already_being_processed(*new_mid_point)) {
                log_debug(
                    "already testing mid point %d, so do nothing",
                    *new_mid_point);
                *new_mid_point = DOING_NOWT;
                return true;
            }

            // if hitting the bottom. check that uncompressed worked or not
            if (*new_mid_point == 0) {
                // check that it worked (it might not have finished, in some
                // odd flow
                if (bit_field_test(mid_points_successes, *new_mid_point)) {
                    best_search_point = *new_mid_point;
                    found_best = true;
                    log_debug("found best by hitting bottom");
                    return true;
                }
                // if we got here its odd. but put this here for completeness
                if (bit_field_test(tested_mid_points, *new_mid_point)) {
                    log_error(
                        "got to the point of searching for mid point 0."
                        " And 0 has been tested and failed. therefore complete"
                        " failure has occurred.");
                    return false;
                }
            }
        }
    }
    log_debug("left cycle with new mid point of %d", *new_mid_point);
    FREE(higher_testers);
    return true;
}


//! \brief handles the freeing of memory from compressor cores, waiting for
//! compressor cores to finish and removing merged bitfields from the bitfield
//! regions.

void handle_best_cleanup(void){
    // tell all compression cores trying midpoints to stop, as pointless.
    for (int check_core_id = 0;
            check_core_id < n_compression_cores; check_core_id++) {
        if (comp_core_mid_point[check_core_id] != DOING_NOWT) {
            send_sdp_force_stop_message(check_core_id);
        }
    }

    // load routing table into router
    load_routing_table_into_router();
    log_debug("finished loading table");

    //hang till the compressor cores have all responded saying stopped
    //(thereby freeing as much sdram/ dtcm as possible before trying to
    //allocate memory for remove merged bitfields. (will be interrupted by sdp
    // packet reception, so safe to do

    // IT SEEMS YOU CAN LOSE SDP MESSAGES HERE. SO COMMENTING OUT
    //int n_cores_doing_things = n_compression_cores;
    //while (n_cores_doing_things != 0){
    //    n_cores_doing_things = 0;
    //    for(int c_index = 0; c_index < n_compression_cores; c_index++){
    //        if (comp_core_mid_point[c_index] != DOING_NOWT) {
    //            n_cores_doing_things += 1;
    //            log_debug("waiting on %d", compressor_cores[c_index]);
    //        }
    //    }
    //}

    // clear away bitfields that were merged into the router from
    //their lists.
    log_debug("remove merged bitfields");
    remove_merged_bitfields_from_cores();

    vcpu_t *sark_virtual_processor_info = (vcpu_t *) SV_VCPU;
    uint core = spin1_get_core_id();
    sark_virtual_processor_info[core].user2 = best_search_point;

    terminate(EXITED_CLEANLY);
}


//! \brief compress the bitfields from the best location
//! \param[in] unused0: not used, tied to api
//! \param[in] unused1: not used, tied to api

void carry_on_binary_search() {

    uint cpsr = 0;
    cpsr = spin1_int_disable();

    log_info("started carry on");

    bool failed_to_malloc = false;
    bool nothing_to_do = false;

    log_info("found best is %d", found_best);

    // iterate till either ran out of cores, or failed to malloc sdram during
    // the setup of a core or found best or no other mid points need to be
    // tested
    log_debug("start while");
    while (n_available_compression_cores != 0 && !failed_to_malloc &&
            !found_best && !nothing_to_do) {
        log_info("try a carry on core");

        // locate next midpoint to test
        int mid_point;
        bool success = locate_next_mid_point(&mid_point);
        platform_check_all();
        log_info("using midpoint %d", mid_point);

        // check for not needing to do things but wait
        if (mid_point == DOING_NOWT && !found_best) {
            log_info("no need to cycle, as nowt to do but wait");
            for (int c_core_index = 0;
                    c_core_index < n_compression_cores; c_core_index++) {
                 if (comp_core_mid_point[c_core_index] != DOING_NOWT) {
                    log_debug(
                        "core %d is doing mid point %d",
                        compressor_cores[c_core_index],
                        comp_core_mid_point[c_core_index]);
                 }
            }
            nothing_to_do = true;
        } else if (found_best){
            // if finished search, load best into table
            log_info(
                "finished search successfully best mid point was %d",
                best_search_point);

            // stop compressor cores, load entries and report success
            handle_best_cleanup();

            return;
        } else{
            // not found best, so try to set off compression if memory done
            log_info("trying with midpoint %d", mid_point);
            platform_check_all();
            if (!success) {
                failed_to_malloc = true;
            } else {  // try a compression run
                log_info("dl");
                platform_check_all();
                log_info("dll");
                success = create_tables_and_set_off_bit_compressor(mid_point);
                platform_check_all();
                // failed to set off the run for a memory reason
                if (!success){
                    failed_to_malloc = true;
                    log_debug("failed to send due to malloc");
                }
                else{
                    log_debug("success sending");
                }
            }
        }
    }

    log_info("aaa");
    platform_check_all();
    log_info("checking state");

    // if failed to malloc, limit exploration to the number of cores running.
    if (failed_to_malloc) {
        log_info("in failed to malloc");
        n_available_compression_cores = 0;

        // if the current running number of cores is 0, then we cant generate
        // the next midpoint,
        if (count_many_on_going_compression_attempts_are_running() == 0) {
            int best_mid_point_tested = best_mid_point_to_date();

            // check if current reach is enough to count as a success
            if ((n_bf_addresses / best_mid_point_tested) <
                    region_addresses->threshold){
                log_error(
                    "failed to compress enough bitfields for threshold "
                    "percentage.");
                terminate(EXIT_FAIL);
            }
            // passed QoS threshold
            found_best = true;
            best_search_point = best_mid_point_tested;
            log_info(
                "finished search by end user QoS, best search point is %d",
                best_search_point);

            // stop compressor cores, load entries and report success
            handle_best_cleanup();
        }
    }

    log_info("finished the try.");

    // set flag for handling responses to bounce back in here
    still_trying_to_carry_on = false;

    platform_check_all();

    spin1_mode_restore(cpsr);
}



//! \brief timer interrupt for controlling time taken to try to compress table
//! \param[in] unused0: not used
//! \param[in] unused1: not used
int timer_iteration = 0;
void timer_callback(uint unused0, uint unused1) {
    use(unused0);
    use(unused1);

    // protects against any race conditions where everything has finished but
    // due to interrupt priorities, sdp message mailbox limits etc. Best way
    // will be to periodically assess if we need to do anything
    /*if (count_many_on_going_compression_attempts_are_running() == 0 &&
            !reading_bit_fields && !still_trying_to_carry_on && !found_best){
        log_debug("firing off carry on from timer");
        spin1_schedule_callback(
            carry_on_binary_search, 0, 0, COMPRESSION_START_PRIORITY);
    }*/
}

//! \brief processes the response from the compressor attempt
//! \param[in] comp_core_index: the compressor core id
//! \param[in] the response code / finished state
void process_compressor_response(int comp_core_index, int finished_state) {
    // filter off finished state

    log_info(
        "core index %d, finished_state = %d",
        comp_core_index, finished_state);

    if (finished_state == SUCCESSFUL_COMPRESSION) {
        log_info(
            "successful from core %d doing mid point %d",
            compressor_cores[comp_core_index],
            comp_core_mid_point[comp_core_index]);
        bit_field_set(tested_mid_points, comp_core_mid_point[comp_core_index]);
        bit_field_set(
            mid_points_successes, comp_core_mid_point[comp_core_index]);

        // set tracker if its the best seen so far
        int best_point_seen = best_mid_point_to_date();
        log_info("best seen = %d", best_point_seen);
        if (best_mid_point_to_date() == comp_core_mid_point[comp_core_index]) {
            best_search_point = comp_core_mid_point[comp_core_index];
            log_info(
                "copying to %x from %x for compressed table",
                last_compressed_table,
                comp_cores_bf_tables[comp_core_index].compressed_table);
            routing_table_copy_table(
                comp_cores_bf_tables[comp_core_index].compressed_table,
                last_compressed_table);
            log_info("n entries is %d", last_compressed_table->size);
        }

        // release for next set
        comp_core_mid_point[comp_core_index] = DOING_NOWT;
        n_available_compression_cores++;

        // free the sdram associated with this compressor core.
        bool success = helpful_functions_free_sdram_from_compression_attempt(
            comp_core_index, comp_cores_bf_tables);
        if (!success) {
            log_error("failed to free sdram for compressor core %d. WTF",
                      compressor_cores[comp_core_index]);
        }
        log_debug("finished process of successful compression");
    } else if (finished_state == FAILED_MALLOC) {
        log_info(
            "failed by malloc from core %d doing mid point %d",
            compressor_cores[comp_core_index],
            comp_core_mid_point[comp_core_index]);
        // this will threshold the number of compressor cores that
        // can be ran at any given time.
        comp_core_mid_point[comp_core_index] = DOING_NOWT;

        // free the sdram associated with this compressor core.
        bool success = helpful_functions_free_sdram_from_compression_attempt(
            comp_core_index, comp_cores_bf_tables);
        if (!success) {
            log_error("failed to free sdram for compressor core %d. WTF",
                      compressor_cores[comp_core_index]);
        }
    }
    else if (finished_state == FAILED_TO_COMPRESS){
        log_info(
            "failed to compress from core %d doing mid point %d",
            compressor_cores[comp_core_index],
            comp_core_mid_point[comp_core_index]);

        // it failed to compress, so it was successful in malloc.
        // so mark the midpoint as tested, and free the core for another
        // attempt
        int compression_mid_point = comp_core_mid_point[comp_core_index];
        bit_field_set(tested_mid_points, compression_mid_point);
        comp_core_mid_point[comp_core_index] = DOING_NOWT;
        n_available_compression_cores ++;

        // set all indices above this one to false, as this one failed
        for (int test_index = compression_mid_point;
                test_index < n_bf_addresses; test_index++) {
            bit_field_set(tested_mid_points, test_index);
        }

        // tell all compression cores trying midpoints above this one
        // to stop, as its highly likely a waste of time.
        for (int check_core_id = 0;
                check_core_id < n_compression_cores; check_core_id++) {
            if (comp_core_mid_point[check_core_id] > compression_mid_point) {
                send_sdp_force_stop_message(check_core_id);
            }
        }

        // free the sdram associated with this compressor core.
        bool success = helpful_functions_free_sdram_from_compression_attempt(
            comp_core_index, comp_cores_bf_tables);
        if (!success) {
            log_error("failed to free sdram for compressor core %d. WTF",
                      compressor_cores[comp_core_index]);
        }
    } else if (finished_state == RAN_OUT_OF_TIME) {
        log_info(
            "failed by time from core %d doing mid point %d",
            compressor_cores[comp_core_index],
            comp_core_mid_point[comp_core_index]);

        // if failed to compress by the end user considered QoS. So it
        // was successful in malloc. So mark the midpoint as tested,
        // and free the core for another attempt
        int compression_mid_point = comp_core_mid_point[comp_core_index];
        bit_field_set(tested_mid_points, compression_mid_point);
        comp_core_mid_point[comp_core_index] = DOING_NOWT;
        n_available_compression_cores++;
        log_info("a");

        // tell all compression cores trying midpoints above this one
        // to stop, as its highly likely a waste of time.
        for (int check_core_id = 0;
                check_core_id < n_compression_cores; check_core_id++){
            if (comp_core_mid_point[check_core_id] > compression_mid_point){
                send_sdp_force_stop_message(check_core_id);
            }
        }
        log_info("b");

        // free the sdram associated with this compressor core.
        bool success = helpful_functions_free_sdram_from_compression_attempt(
            comp_core_index, comp_cores_bf_tables);
        if (!success) {
            log_error("failed to free sdram for compressor core %d. WTF",
                      compressor_cores[comp_core_index]);
        }
        log_info("c");
    } else if (finished_state == FORCED_BY_COMPRESSOR_CONTROL){
        log_info(
            "ack from forced from core %d doing mid point %d",
            compressor_cores[comp_core_index],
            comp_core_mid_point[comp_core_index]);

        // free the sdram associated with this compressor core.
        bool success = helpful_functions_free_sdram_from_compression_attempt(
            comp_core_index, comp_cores_bf_tables);
        if (!success) {
            log_error(
                "failed to free sdram for compressor core %d. WTF",
                compressor_cores[comp_core_index]);
        }

        // this gives no context of why the control killed it. just
        // free the core for another attempt
        comp_core_mid_point[comp_core_index] = DOING_NOWT;
        n_available_compression_cores++;

    } else {
        log_error(
            "no idea what to do with finished state %d, from core %d ignoring",
            finished_state, compressor_cores[comp_core_index]);
    }

    // having processed the packet, and there are spare cores for compression
    // attempts, try to set off another search.  (this encapsulates the
    // finish state as well.
    log_info(
        "n av cores = %d, bool of reading is %d trying carry on %d",
        n_available_compression_cores, reading_bit_fields,
        still_trying_to_carry_on);
    if (n_available_compression_cores > 0 && !reading_bit_fields) {
        if (!still_trying_to_carry_on) {
            log_info("setting off carry on");
            still_trying_to_carry_on = true;
            carry_on_binary_search();
        } else {
            log_info("all ready in carry on mode. ignoring");
        }
    } else {
        log_info("not ready to carry on yet");
    }
}

//! \brief the sdp control entrance.
//! \param[in] mailbox: the message
//! \param[in] port: don't care.
void sdp_handler(uint mailbox, uint port) {
    use(port);

    log_info("received response");

    // get data from the sdp message
    sdp_msg_pure_data *msg = (sdp_msg_pure_data *) mailbox;
    compressor_payload_t* msg_payload = (compressor_payload_t*) &msg->data;
    log_debug("command code is %d", msg_payload->command);
    log_debug(
        "response code was %d", msg_payload->response.response_code);

    // filter off the port we've decided to use for this
    if (msg->srce_port >> PORT_SHIFT == RANDOM_PORT) {
        log_debug("correct port");
        // filter based off the command code. Anything thats not a response is
        // a error
        switch (msg_payload->command) {
            case START_DATA_STREAM:
                log_error(
                    "no idea why i'm receiving a start data message. "
                    "Ignoring");
                log_info("message address is %x", msg);
                log_info("length = %x", msg->length);
                log_info("checksum = %x", msg->checksum);
                log_info("flags = %u", msg->flags);
                log_info("tag = %u", msg->tag);
                log_info("dest_port = %u", msg->dest_port);
                log_info("srce_port = %u", msg->srce_port);
                log_info("dest_addr = %u", msg->dest_addr);
                log_info("srce_addr = %u", msg->srce_addr);
                log_info("data 0 = %d", msg->data[0]);
                log_info("data 1 = %d", msg->data[1]);
                log_info("data 2 = %d", msg->data[2]);
                platform_check_all();
                log_info("finished checkall");
                rt_error(RTE_SWERR);
                break;
            case COMPRESSION_RESPONSE:
                platform_check_all();

                // locate the compressor core id that responded
                log_info("response packet");
                int comp_core_index = get_core_index_from_id(
                    (msg->srce_port & CPU_MASK));

                // response code just has one value, so being lazy and not
                // casting
                int finished_state = msg_payload->response.response_code;

                // free message now, nothing left in it and we don't want to
                // hold the memory for very long
                sark_msg_free((sdp_msg_t*) msg);
                msg = NULL;

                // create holder

                uint32_t store = comp_core_index << CORE_MOVE;
                store = store | finished_state;

                // store holder
                log_info(
                    "finished state %d, index %d, store %d",
                    finished_state, comp_core_index, store);
                circular_buffer_add(sdp_circular_queue, store);
                break;
            case STOP_COMPRESSION_ATTEMPT:
                log_error("no idea why i'm receiving a stop message. Ignoring");
                rt_error(RTE_SWERR);
                break;
            default:
                log_error(
                    "no idea what to do with message with command code %d. "
                    "Ignoring", msg_payload->command);
                rt_error(RTE_SWERR);
                break;
            }
        } else {
            log_error(
                "no idea what to do with message. on port %d Ignoring",
                msg->srce_port >> PORT_SHIFT);
            rt_error(RTE_SWERR);
    }

    // free message if not freed
    if (msg) {
        sark_msg_free((sdp_msg_t *) msg);
    }

    log_info("finish sdp process");
}

bool setup_the_uncompressed_attempt() {
    // sort out teh searcher bitfields. as now first time where can do so
    // NOTE: by doing it here, the response from the uncompressed can be
    // handled correctly.
    log_debug("setting up search bitfields");
    bool success = set_up_search_bitfields();
    if (!success) {
        log_error("can not allocate memory for search fields.");
        return false;
    }
    log_debug("finish setting up search bitfields");

    // set off a none bitfield compression attempt, to pipe line work
    log_debug("sets off the uncompressed version of the search");
    message_sending_set_off_no_bit_field_compression(
        comp_cores_bf_tables, compressor_cores, &my_msg,
        uncompressed_router_table, n_compression_cores, comp_core_mid_point,
        &n_available_compression_cores);
    log_info(" n_available_compression_cores is %d", n_available_compression_cores);
    return true;
}

//! \brief check sdp buffer till its finished
//! \param[in] unused0: api
//! \param[in] unused1: api
void check_buffer_queue(uint unused0, uint unused1) {
    use(unused0);
    use(unused1);

    // iterate over the circular buffer until we have the finished state
    while(!found_best) {
        // get the next element if it has one
        uint32_t next_element;
        if(circular_buffer_get_next(sdp_circular_queue, &next_element)) {
            int core_index = next_element >> CORE_MOVE;
            int finished_state = next_element & FINISHED_STATE_MASK;
            log_info("processing packet from circular buffer");
            process_compressor_response(core_index, finished_state);
        }
    }
    // if i get here. something fucked up. blow up spectacularly
    log_info("exiting the interrupt, to allow the binary to finish");
}

//! \brief starts the work for the compression search
void start_compression_process(uint unused0, uint unused1) {
    //api requirements
    use(unused0);
    use(unused1);

    uint cpsr = 0;
    cpsr = spin1_int_disable();

    log_info("read in bitfields");
    bool read_success = false;
    platform_turn_off_print();
    bit_field_by_processor = bit_field_reader_read_in_bit_fields(
            &n_bf_addresses, region_addresses, &read_success);
    log_info("finished reading in bitfields");

    // check state
    if (bit_field_by_processor == NULL && !read_success){
        log_error("failed to read in bitfields, quitting");
        terminate(EXIT_MALLOC);
    }

    // set off the first compression attempt (aka no bitfields).
    bool success = setup_the_uncompressed_attempt();
    if (!success){
        log_error("failed to set up uncompressed attempt");
        terminate(EXIT_MALLOC);
    }


    // check there are bitfields to merge, if not don't start search
    if (n_bf_addresses == 0){
        log_info(
            "no bitfields to compress, just try the uncompressed and "
            "quit based on that's result.");
        reading_bit_fields = false;
        spin1_mode_restore(cpsr);
        // set off checker
        spin1_schedule_callback(
            check_buffer_queue, 0, 0, COMPRESSION_START_PRIORITY);
        return;
    }

    // if there are bitfields to merge
    // sort the bitfields into order of best impact on worst cores.
    log_info("sorting");
    sorted_bit_fields = bit_field_sorter_sort(
        n_bf_addresses, region_addresses, bit_field_by_processor);
    log_info("finished sorting bitfields");
    //platform_turn_on_print();

    if (sorted_bit_fields == NULL) {
        log_error("failed to read in bitfields, failing");
        spin1_mode_restore(cpsr);
        terminate(EXIT_MALLOC);
        return;
    }

    for (int bit_field_index = 0; bit_field_index < n_bf_addresses;
            bit_field_index++) {
        // get key
        filter_info_t* bf_pointer =
            sorted_bit_fields->bit_fields[bit_field_index];
        if (bf_pointer == NULL) {
            log_info("failed at index %d", bit_field_index);
            spin1_mode_restore(cpsr);
            terminate(RTE_SWERR);
            return;
        }

       //log_info("bf pointer address = %x", bf_pointer);
       log_debug("bf pointer %d is = %d",  bit_field_index, bf_pointer->key);
    }

    for (int s_bf_i = 0; s_bf_i < n_bf_addresses; s_bf_i++){
        log_debug(
            "address for index %d is %x",
            s_bf_i, sorted_bit_fields->bit_fields[s_bf_i]->data);
        log_debug(
            "for address in index %d, it targets processor %d with key %d "
            "and the redundant packet count is %d",
            s_bf_i, sorted_bit_fields->processor_ids[s_bf_i],
            sorted_bit_fields->bit_fields[s_bf_i]->key,
            detect_redundant_packet_count(
                *sorted_bit_fields->bit_fields[s_bf_i], region_addresses));
    }

    log_info("starting the binary search");
    bool success_start_binary_search = start_binary_search();
    log_info("finish starting of the binary search");

    if (!success_start_binary_search) {
        log_error("failed to compress the routing table at all. Failing");
        spin1_mode_restore(cpsr);
        terminate(EXIT_FAIL);
    }
    spin1_mode_restore(cpsr);

    // set off checker
    spin1_schedule_callback(
        check_buffer_queue, 0, 0, COMPRESSION_START_PRIORITY);
}

//! \brief sets up a tracker for the user registers so that its easier to use
//!  during coding.
static void initialise_user_register_tracker(void) {
    log_debug("set up user register tracker (easier reading)");
    vcpu_t *sark_virtual_processor_info = (vcpu_t *) SV_VCPU;
    vcpu_t *this_vcpu_info = &sark_virtual_processor_info[spin1_get_core_id()];

    data_specification_metadata_t * app_ptr_table =
        (data_specification_metadata_t *) this_vcpu_info->user0;
    uncompressed_router_table =
        (uncompressed_table_region_data_t *) this_vcpu_info->user1;
    region_addresses = (region_addresses_t *) this_vcpu_info->user2;
    usable_sdram_regions = (available_sdram_blocks *) this_vcpu_info->user3;

    log_debug(
        "finished setting up register tracker: \n\n"
        "user0 = %d\n user1 = %d\n user2 = %d\n user3 = %d\n",
        app_ptr_table, uncompressed_router_table,
        region_addresses, usable_sdram_regions);
}

//! \brief reads in router table setup params

static void initialise_routing_control_flags(void) {
    app_id = uncompressed_router_table->app_id;
    log_debug(
        "app id %d, uncompress total entries %d",
        app_id, uncompressed_router_table->uncompressed_table.size);
}

//! \brief get compressor cores
bool initialise_compressor_cores(void) {
    // locate the data point for compressor cores, straight after pair data
    int n_region_pairs = region_addresses->n_pairs;
    log_debug("n region pairs = %d", n_region_pairs);

    // get n compression cores and update trackers
    compressor_cores_top_t *compressor_cores_top =
        (compressor_cores_top_t*) &region_addresses->pairs[n_region_pairs];
    n_compression_cores = compressor_cores_top->n_cores;
    //n_compression_cores = 1;

    n_available_compression_cores = n_compression_cores;
    log_info("%d comps cores available", n_available_compression_cores);

    // malloc dtcm for this
    log_info("allocate for compressor core trackers");
    compressor_cores = MALLOC(n_compression_cores * sizeof(int));
    // verify malloc worked
    if (compressor_cores == NULL) {
        log_error("failed to allocate memory for the compressor cores");
        return false;
    }

    // populate with compressor cores
    log_info("start populate compression cores");
    for (int core=0; core < n_compression_cores; core++) {
        compressor_cores[core] = compressor_cores_top->core_id[core];
    }
    log_info("finished populate compression cores");

    // allocate memory for the trackers
    log_info("allocate for compressor core midpoints");
    comp_core_mid_point = MALLOC(n_compression_cores * sizeof(int));
    if (comp_core_mid_point == NULL) {
        log_error(
            "failed to allocate memory for tracking what the "
            "compression cores are doing");
        return false;
    }

    log_info("setting midpoints to DOING_NOWT");
    // set the trackers all to -1 as starting point. to ensure completeness
    for (int core = 0; core < n_compression_cores; core++) {
        comp_core_mid_point[core] = DOING_NOWT;
    }

    // set up addresses tracker (use sdram so that this can be handed to the
    // compressor to solve transmission faffs)
    log_info("malloc for table trackers");
    comp_cores_bf_tables =
        MALLOC(n_compression_cores * sizeof(comp_core_store_t));
    if (comp_cores_bf_tables == NULL) {
        log_error(
            "failed to allocate memory for the holding of bitfield "
            "addresses per compressor core");
        return false;
    }

    // ensure all bits set properly as init
    log_info("setting up table trackers.");
    for (int c_core = 0; c_core < n_compression_cores; c_core++) {
        comp_cores_bf_tables[c_core].n_elements = 0;
        comp_cores_bf_tables[c_core].n_bit_fields = 0;
        comp_cores_bf_tables[c_core].compressed_table = NULL;
        comp_cores_bf_tables[c_core].elements = NULL;
    }

    return true;
}

//! \brief the callback for setting off the router compressor
static bool initialise(void) {
    log_debug(
        "Setting up stuff to allow bitfield comp control class to occur.");

    // Get pointer to 1st virtual processor info struct in SRAM
    initialise_user_register_tracker();

    // get the compressor data flags (app id, compress only when needed,
    //compress as much as possible, x_entries
    initialise_routing_control_flags();

    // build the fake heap for allocating memory
    log_info("setting up fake heap for sdram usage");
    bool heap_creation = platform_new_heap_creation(usable_sdram_regions);
    if (!heap_creation){
        log_error("failed to setup stolen heap");
        return false;
    }
    log_info("finished setting up fake heap for sdram usage");

    // get the compressor cores stored in a array
    log_debug("start init of compressor cores");
    bool success_compressor_cores = initialise_compressor_cores();
    if (!success_compressor_cores) {
        log_error("failed to init the compressor cores.");
        return false;
    }

    // init the circular queue to handle the size of sdp messages expected
    // at any given point
    sdp_circular_queue = circular_buffer_initialize(
        n_compression_cores * N_MSGS_EXPECTED_FROM_COMPRESSOR);

    // set up the best compressed table
    log_info(
        "size asked for is %d",
        routing_table_sdram_size_of_table(TARGET_LENGTH));
    last_compressed_table =
        MALLOC(routing_table_sdram_size_of_table(TARGET_LENGTH));
    if (last_compressed_table == NULL) {
        log_error("failed to allocate best space");
        return false;
    }

    return true;
}

//! \brief the main entrance.
void c_main(void) {
    bool success_init = initialise();
    if (!success_init){
        log_error("failed to init");
        terminate(EXIT_FAIL);
    }

    spin1_callback_on(SDP_PACKET_RX, sdp_handler, SDP_PRIORITY);
    spin1_set_timer_tick(TIME_STEP);
    spin1_callback_on(TIMER_TICK, timer_callback, TIMER_TICK_PRIORITY);

    // kick-start the process
    spin1_schedule_callback(
        start_compression_process, 0, 0, COMPRESSION_START_PRIORITY);

    // go
    log_debug("waiting for sycn");
    spin1_start(SYNC_WAIT);
}

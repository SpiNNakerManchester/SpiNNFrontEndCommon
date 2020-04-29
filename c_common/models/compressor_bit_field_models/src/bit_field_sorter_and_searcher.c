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
#include <malloc_extras.h>
#include "common-typedefs.h"
#include "common/routing_table.h"
#include "common/constants.h"
#include "common/compressor_sorter_structs.h"
#include "sorter_includes/bit_field_table_generator.h"
#include "sorter_includes/helpful_functions.h"
#include "sorter_includes/bit_field_creator.h"
#include "sorter_includes/message_sending.h"
/*****************************************************************************/
/* SpiNNaker routing table minimisation with bitfield integration control
 * processor.
 *
 * controls the attempt to minimise the router entries with bitfield
 * components.
 */

//============================================================================
//! #defines and enums

//! \brief time step for safety timer tick interrupt
#define TIME_STEP 10

//! \brief After how many timesteps to kill the process
#define KILL_TIME 200000

//! \brief the magic +1 for inclusive coverage that 0 index is no bitfields
#define ADD_INCLUSIVE_BIT 1

//! \brief bit shift for the app id for the route
#define ROUTE_APP_ID_BIT_SHIFT 24

//! \brief the maximum amount of messages possible to be received by the sorter
#define N_MSGS_EXPECTED_FROM_COMPRESSOR 2

//! \brief callback priorities
typedef enum priorities{
    COMPRESSION_START_PRIORITY = 3, SDP_PRIORITY = -1, TIMER_TICK_PRIORITY = 0
}priorities;

//============================================================================
//! global params

//! \brief counter of how many timesteps have passed
uint32_t timesteps = 0;

//! \brief bool flag for saying found the best stopping position
volatile bool found_best = false;

//! \brief time to take per compression iteration
uint32_t time_per_iteration = 0;

//! \brief flag of how many times the timer has fired during this one
uint32_t finish_compression_flag = 0;

//! \brief easier programming tracking of the user registers
uncompressed_table_region_data_t *uncompressed_router_table; // user1

//! \brief stores the locations of bitfields from app processors
region_addresses_t *region_addresses; // user2

//! \brief stores of sdram blocks the fake heap can use
available_sdram_blocks *usable_sdram_regions; // user3

// Best midpoint that record a success
int best_success = -1;

// Lowest midpoint that record failure
int lowest_failure;

//! \brief best routing table position in the search
int best_search_point = 0;

//! \brief the last routing table position in the search
int last_search_point = 0;

//! \brief the store for the last routing table that was compressed
table_t* last_compressed_table;

//! \brief the compressor app id
uint32_t app_id = 0;

//! \brief the list of bitfields in sorted order based off best effect, and
//! processor ids.
sorted_bit_fields_t* sorted_bit_fields;

//! \brief the list of compressor processors to bitfield routing table
//! SDRAM addresses
comp_processor_store_t* processor_bf_tables;

//! \brief stores which values have been tested
bit_field_t tested_mid_points;

//! tracker for what each processor is doing (in terms of midpoints)
int* processor_status;

//! \brief the bitfield by processor global holder
bit_field_by_processor_t* bit_field_by_processor;

//! \brief sdp message to send control messages to compressors processors
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
//! \param[in] processor_id: the processor id to send a force stop
//! compression attempt
//! \return bool saying successfully sent the message
void send_sdp_force_stop_message(int processor_id){
    // set message params
    log_debug(
        "sending stop to processor %d", processor_id);
    my_msg.dest_port = (RANDOM_PORT << PORT_SHIFT) | processor_id;
    compressor_payload_t* data = (compressor_payload_t*) &my_msg.data;
    data->command = STOP_COMPRESSION_ATTEMPT;
    my_msg.length = LENGTH_OF_SDP_HEADER + sizeof(command_codes_for_sdp_packet);

    // send sdp packet
    message_sending_send_sdp_message(&my_msg, processor_id);
}

//! \brief sets up the search bitfields.
//! \return bool saying success or failure of the setup
bool set_up_tested_mid_points(void) {
    log_info("set_up_tested_mid_point n bf addresses is %d", n_bf_addresses);
    uint32_t words = get_bit_field_size(n_bf_addresses + ADD_INCLUSIVE_BIT);
    if (tested_mid_points == NULL) {
        tested_mid_points = (bit_field_t) MALLOC(words * sizeof(bit_field_t));
    }
    // check the malloc worked
    if (tested_mid_points == NULL) {
        return false;
    }

    // clear the bitfields
    clear_bit_field(tested_mid_points, words);

    // return if successful
    return true;
}

//! builds tables and tries to set off a compressor processor based off
//! midpoint
//! \param[in] mid_point: the mid point to start at
//! \param[in] processor_id: the processor to run the compression on
//! \return bool fag if it fails for memory issues
bool create_tables_and_set_off_bit_compressor(
        int mid_point, int processor_id) {
    int n_rt_addresses = 0;
    //log_info("started create bit field router tables");
    table_t **bit_field_routing_tables =
        bit_field_table_generator_create_bit_field_router_tables(
            mid_point, &n_rt_addresses,
            uncompressed_router_table,
            sorted_bit_fields);
    if (bit_field_routing_tables == NULL){
        log_info(
            "failed to create bitfield tables for midpoint %d", mid_point);
        return false;
    }

    log_debug("finished creating bit field router tables");

    malloc_extras_check_all_marked(1001);
    // if successful, try setting off the bitfield compression
    bool success = message_sending_set_off_bit_field_compression(
        n_rt_addresses, mid_point, processor_bf_tables,
        bit_field_routing_tables, &my_msg, processor_id);

    // if successful, move to next search point.
    if (!success){
        log_debug("failed to set off bitfield compression");
        return false;
    }
    else{
        return true;
    }
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
    malloc_extras_terminate(EXIT_SWERR);
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

//! \brief removes the merged bitfields from the application processors
//! bitfield regions
//! \return bool if was successful or not
bool remove_merged_bitfields_from_processors(void) {
    // only try if there are bitfields to remove
    if (n_bf_addresses == 0){
        log_info("no bitfields to remove");
        return true;
    }

    // which bitfields are to be removed from which processors
    proc_bit_field_keys_t *sorted_bf_key_proc = sorter_by_processors(
        region_addresses, best_search_point, sorted_bit_fields);
    if (sorted_bf_key_proc == NULL) {
        log_error("could not sort out bitfields to keys.");
        return false;
    }

    // iterate though the processors sorted, and remove said bitfields from its
    // region
    for (int r_id = 0; r_id < region_addresses->n_pairs; r_id++){
        int processor_id = sorted_bf_key_proc[r_id].processor_id;
        log_debug("processor id %d", processor_id);

        filter_region_t *filter_region = find_processor_bit_field_region(
            processor_id);

        // iterate though the bitfield region looking for bitfields with
        // correct keys to remove
        int n_bfs = filter_region->n_filters;
        filter_region->n_filters =
            n_bfs - sorted_bf_key_proc[r_id].key_list->length_of_list;

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
                        sorted_bf_key_proc[r_id], read_index->key)) {
                    // write the data in the current write positions, if it
                    // isn't where we're currently reading from
                    if (write_index != read_index) {
                        // copy the key, n_atoms and bitfield pointer over to
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
    for (int r_id = 0; r_id < region_addresses->n_pairs; r_id++) {
        if (sorted_bf_key_proc[r_id].key_list->length_of_list != 0) {
            FREE(sorted_bf_key_proc[r_id].key_list->master_pop_keys);
            FREE(sorted_bf_key_proc[r_id].key_list);
        }
    }

    FREE(sorted_bf_key_proc);
    // return we successfully removed merged bitfields
    return true;
}

//! \brief locates the next valid midpoint to test
//! \return int which is the midpoint or -1 if no midpoints left
int locate_next_mid_point(void) {
    int new_mid_point;
    if (n_bf_addresses == 0) {
        return -1;
    }

    // if not tested yet, test all
    if (!bit_field_test(tested_mid_points, n_bf_addresses)){
        new_mid_point = n_bf_addresses;
        bit_field_set(tested_mid_points, new_mid_point);
        return new_mid_point;
    }

    // need to find a midpoint
    log_debug(
        "n_bf_addresses %d tested_mid_points %d",
        n_bf_addresses, bit_field_test(tested_mid_points, n_bf_addresses));

    // the last point of the longest space
    int best_end = -1;

    // the length of the longest space to test
    int best_length = 0;

    // the current length of the currently detected space
    int current_length = 0;

    log_debug(
        "best_success %d lowest_failure %d", best_success, lowest_failure);

    // iterate over the range to binary search, looking for biggest block to
    // explore, then take the middle of that block

    // NOTE: if there are no available bitfields, this will result in best end
    // being still set to -1, as every bit is set, so there is no blocks with
    // any best length, and so best end is never set and lengths will still be
    // 0 at the end of the for loop. -1 is a special midpoint which higher
    // code knows to recognise as no more exploration needed.
    for (int index = best_success + 1; index <= lowest_failure; index++) {
        log_debug(
            "index: %d, value: %u current_length: %d",
            index, bit_field_test(tested_mid_points, index),
            current_length);

        // verify that the index has been used before
        if (bit_field_test(tested_mid_points, index)) {

           // if used before and is the end of the biggest block seen so far.
           // Record and repeat.
           if (current_length > best_length) {
                best_length = current_length;
                best_end = index - 1;
                log_debug(
                    "found best_length: %d best_end %d",
                    best_length, best_end);
           // if not the end of the biggest block, ignore (log for debugging)
           } else {
                log_debug(
                    "not best: %d best_end %d", best_length, best_end);
           }
           // if its seen a set we're at the end of a block. so reset the
           // current block len, as we're about to start another block.
           current_length = 0;
        // not set, so still within a block, increase len.
        } else {
           current_length += 1;
        }
    }

    // use the best less half (shifted) of the best length
    new_mid_point = best_end - (best_length >> 1);
    log_debug("returning mid point %d", new_mid_point);

    // set the mid point to be tested. (safe as we de-set if we fail later on)
    if (new_mid_point >= 0) {
        log_debug("setting new mid point %d", new_mid_point);

        // just a safety check, as this has caught us before.
        if (bit_field_test(tested_mid_points, new_mid_point)){
            log_info("HOW THE HELL DID YOU GET HERE!");
            malloc_extras_terminate(EXIT_SWERR);
        }
        // set the tracker.
        bit_field_set(tested_mid_points, new_mid_point);
    }

    return new_mid_point;
}

//! \brief handles the freeing of memory from compressor processors, waiting
//! for compressor processors to finish and removing merged bitfields from
//! the bitfield regions.
void handle_best_cleanup(void){
    // load routing table into router
    load_routing_table_into_router();
    log_debug("finished loading table");

    // clear away bitfields that were merged into the router from
    //their lists.
    log_info("remove merged bitfields");
    remove_merged_bitfields_from_processors();

    vcpu_t *sark_virtual_processor_info = (vcpu_t *) SV_VCPU;
    uint processor_id = spin1_get_core_id();
    sark_virtual_processor_info[processor_id].user2 = best_search_point;

    // Safety to break out of loop in check_buffer_queue
    found_best = true;

    malloc_extras_terminate(EXITED_CLEANLY);
}

//! \brief prints out the status of the processors.
void log_processor_status(){
    for (int i = 0; i < 18; i++){
        if (processor_status[i] < -3 || processor_status[i] > n_bf_addresses){
            log_error("Weird status %d: %d", i, processor_status[i]);
            return;
        }
        //log_info("processor: %d, status: %d", i, processor_status[i]);
    }
    log_info("0:%d 1:%d 2:%d 3:%d 4:%d 5:%d 6:%d 7:%d 8:%d 9:%d 10:%d 11:%d "
        "12:%d 13:%d 14:%d 15:%d 16:%d 17:%d", processor_status[0],
        processor_status[1], processor_status[2], processor_status[3],
        processor_status[4], processor_status[5], processor_status[6],
        processor_status[7], processor_status[8], processor_status[9],
        processor_status[10], processor_status[11], processor_status[12],
        processor_status[13], processor_status[14], processor_status[15],
        processor_status[16], processor_status[17]);
}

//! \brief Returns the next processor id which is ready to run a compression
//! \param[in] mid_point: the mid point this processor will use
//! \return the processor id of the next available processor or -1 if none
int find_compressor_processor(int midpoint){
    for (int processor_id = 0; processor_id < MAX_PROCESSORS; processor_id++) {
        if (processor_status[processor_id] == DOING_NOWT){
            processor_status[processor_id] = midpoint ;
            return processor_id;
        }
    }
    return -1;
}

//! \brief Check if a compressor processor is available
//! \return true if at least one processor is ready to compress
bool all_compressor_processors_busy(void){
    for (int processor_id = 0; processor_id < MAX_PROCESSORS; processor_id++) {
        if (processor_status[processor_id] == DOING_NOWT){
            return false;
        }
    }
    return true;
}

//! \brief Check to see if all compressor processor are done and not ready
//! \return true if all processors are done and not set ready
bool all_compressor_processors_done(void){
    for (int processor_id = 0; processor_id < MAX_PROCESSORS; processor_id++) {
        if (processor_status[processor_id] >= DOING_NOWT){
            return false;
        }
    }
    return true;
}

//! \brief Start the binary search on another compressor if one available

void carry_on_binary_search() {
     if (all_compressor_processors_done()){
        log_info("carry_on_binary_search detected done");
        handle_best_cleanup();
        // Above method has a terminate so no worry about carry on here
    }
    if (all_compressor_processors_busy()){
        return;  //Pass back to check_buffer_queue
    }
    log_debug("start carry_on_binary_search");
    //log_processor_status();

    int mid_point = locate_next_mid_point();
    log_info("available with midpoint %d", mid_point);
    if (mid_point < 0) {
        // Ok lets turn all ready processors off as done.
        // At least default no bitfield handled elsewhere so safe here.
        for (int processor_id = 0; processor_id < MAX_PROCESSORS;
                processor_id++) {
            if (processor_status[processor_id] == DOING_NOWT) {
                processor_status[processor_id] = DO_NOT_USE;
            } else if (processor_status[processor_id] > DOING_NOWT) {
                log_info("waiting for processor %d doing midpoint %u",
                    processor_id, processor_status[processor_id]);
            }
        }
        return;
    }
    int processor_id = find_compressor_processor(mid_point);
    log_debug("start create at timestep: %u", timesteps);
    bool success =
        create_tables_and_set_off_bit_compressor(mid_point, processor_id);
    log_debug("end create at timestep: %u", timesteps);
    if (!success) {
        // Ok lets turn this and all ready processors off to save space.
        // At least default no bitfield handled elsewhere so of to reduce.
        processor_status[processor_id] = DO_NOT_USE;
        for (int processor_id = 0; processor_id < MAX_PROCESSORS;
                processor_id++) {
            if (processor_status[processor_id] == DOING_NOWT) {
                processor_status[processor_id] = DO_NOT_USE;
            }
        }
        // Ok that midpoint did not work so need to try it again
        bit_field_clear(tested_mid_points, mid_point);
        return;
    }
    log_debug("done carry_on_binary_search");
    malloc_extras_check_all_marked(1002);
}

//! \brief timer interrupt for controlling time taken to try to compress table
//! \param[in] unused0: not used
//! \param[in] unused1: not used
void timer_callback(uint unused0, uint unused1) {
    use(unused0);
    use(unused1);
    timesteps+=1;
}

void process_failed(int midpoint){
    log_info("lowest_failure: %d midpoint:%d", lowest_failure, midpoint);
    if (lowest_failure > midpoint){
        lowest_failure = midpoint;
        log_info(
            "Now lowest_failure: %d midpoint:%d", lowest_failure, midpoint);
    }
    // tell all compression processors trying midpoints above this one
    // to stop, as its highly likely a waste of time.
    for (int processor_id = 0; processor_id < MAX_PROCESSORS; processor_id++) {
        if (processor_status[processor_id] > midpoint) {
            send_sdp_force_stop_message(processor_id);
        }
    }
}


//! \brief processes the response from the compressor attempt
//! \param[in] processor_id: the compressor processor id
//! \param[in] the response code / finished state
void process_compressor_response(int processor_id, int finished_state) {
    int mid_point = processor_status[processor_id];
    log_debug("received response %d from processor %d doing %d midpoint",
        finished_state, processor_id, mid_point);

    // safety check to ensure we dont go on if the uncompressed failed
    if (mid_point == 0  && finished_state != SUCCESSFUL_COMPRESSION){
        log_error("The no bitfields attempted failed! Giving up");
        malloc_extras_terminate(EXIT_FAIL);
    }

    // free the processor for future processing
    processor_status[processor_id] = DOING_NOWT;

    if (finished_state == SUCCESSFUL_COMPRESSION) {
        log_info(
            "successful from processor %d doing mid point %d",
            processor_id, mid_point);

        if (best_success <= mid_point){
            best_success = mid_point;
            log_info(
                "copying to %x from %x for compressed table",
                last_compressed_table,
                processor_bf_tables[processor_id].compressed_table);
            sark_mem_cpy(
                last_compressed_table,
                processor_bf_tables[processor_id].compressed_table,
                routing_table_sdram_size_of_table(TARGET_LENGTH));
            log_debug("n entries is %d", last_compressed_table->size);
        }

        // kill any search below this point, as they all redundant as
        // this is a better search.
        for (int processor_id = 0; processor_id < MAX_PROCESSORS;
                processor_id++) {
            if (processor_status[processor_id] >= 0 &&
                    processor_status[processor_id] < mid_point) {
                send_sdp_force_stop_message(processor_id);
            }
        }

        log_debug("finished process of successful compression");
    } else if (finished_state == FAILED_MALLOC) {
        log_info(
            "failed by malloc from processor %d doing mid point %d",
            processor_id, mid_point);
        // this will threshold the number of compressor processors that
        // can be ran at any given time.
        processor_status[processor_id] = DO_NOT_USE;
        // Remove the flag that say this midpoint has been checked
        bit_field_clear(tested_mid_points, mid_point);
    }
    else if (finished_state == FAILED_TO_COMPRESS) {
        log_info(
            "failed to compress from processor %d doing mid point %d",
            processor_id, mid_point);
        process_failed(mid_point);
    } else if (finished_state == RAN_OUT_OF_TIME) {
        log_info(
            "failed by time from processor %d doing mid point %d",
            processor_id, mid_point);
        process_failed(mid_point);
    } else if (finished_state == FORCED_BY_COMPRESSOR_CONTROL) {
        log_info(
            "ack from forced from processor %d doing mid point %d",
            processor_id, mid_point);
    } else {
        log_error(
            "no idea what to do with finished state %d, from processor %d "
            "ignoring", finished_state, processor_id);
    }

    // free the sdram associated with this compressor processor.
    bool success = helpful_functions_free_sdram_from_compression_attempt(
        processor_id, processor_bf_tables);
    if (!success) {
        log_error(
            "failed to free sdram for compressor processor %d. WTF",
             processor_id);
    }
}


//! \brief the sdp control entrance.
//! \param[in] mailbox: the message
//! \param[in] port: don't care.
void sdp_handler(uint mailbox, uint port) {
    use(port);

    log_debug("received response");

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
                malloc_extras_check_all();
                log_info("finished checkall");
                rt_error(RTE_SWERR);
                break;
            case COMPRESSION_RESPONSE:
                malloc_extras_check_all();

                // locate the compressor processor id that responded
                log_debug("response packet");
                int processor_id = msg->srce_port & CPU_MASK;

                // response code just has one value, so being lazy and not
                // casting
                int finished_state = msg_payload->response.response_code;

                // free message now, nothing left in it and we don't want to
                // hold the memory for very long
                sark_msg_free((sdp_msg_t*) msg);
                msg = NULL;

                // create holder
                uint32_t store = processor_id << CORE_MOVE;
                store = store | finished_state;

                // store holder
                log_debug(
                    "finished state %d, index %d, store %d",
                    finished_state, processor_id, store);
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

bool setup_no_bitfeilds_attempt(){
    int processor_id = find_compressor_processor(0);
    if (processor_id < 0){
        log_error("No processor available for no bitfield attempt");
        rt_error(RTE_SWERR);
    }
    bit_field_set(tested_mid_points, 0);
    // set off a none bitfield compression attempt, to pipe line work
    log_info(
        "sets off the no bitfeild version of the search on %u", processor_id);
    return message_sending_set_off_no_bit_field_compression(
        processor_bf_tables, &my_msg, uncompressed_router_table, processor_id);
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
            int processor_id = next_element >> CORE_MOVE;
            int finished_state = next_element & FINISHED_STATE_MASK;
            log_debug("processing packet from circular buffer");
            process_compressor_response(processor_id, finished_state);
        } else {
            // Check if another processor could be started or even done
            carry_on_binary_search();
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

    malloc_extras_turn_off_print();

    // set off the first compression attempt (aka no bitfields).
    bool success = setup_no_bitfeilds_attempt();
    if (!success){
        log_error("failed to set up uncompressed attempt");
        malloc_extras_terminate(EXIT_MALLOC);
    }

    log_info("reading bitfields at timestep: %d", timesteps);
    sorted_bit_fields = bit_field_creator_read_in_bit_fields(region_addresses);

    // check state
    if (sorted_bit_fields == NULL){
        log_error("failed to read in bitfields, quitting");
        malloc_extras_terminate(EXIT_MALLOC);
    }
    lowest_failure = n_bf_addresses;
    log_info("finished reading bitfields at timestep: %d", timesteps);

    set_up_tested_mid_points();

    //TODO: safety code to be removed
    for (int bit_field_index = 0; bit_field_index < n_bf_addresses;
            bit_field_index++) {
        // get key
        filter_info_t* bf_pointer =
            sorted_bit_fields->bit_fields[bit_field_index];
        if (bf_pointer == NULL) {
            log_info("failed at index %d", bit_field_index);
            malloc_extras_terminate(RTE_SWERR);
            return;
        }
    }

    // set off checker which in turn sets of the other compressor cores
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


    sort_table_by_key(&uncompressed_router_table->uncompressed_table);

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

//! \brief get compressor processors
bool initialise_compressor_processors(void) {
    // locate the data point for compressor processors, straight after pair
    // data
    int n_region_pairs = region_addresses->n_pairs;
    log_debug("n region pairs = %d", n_region_pairs);

    // allocate DTCM memory for the processor status trackers
    log_info("allocate and step compressor processor status");
    processor_status = MALLOC(MAX_PROCESSORS * sizeof(int));
    if (processor_status == NULL) {
        log_error(
            "failed to allocate memory for tracking what the "
            "compression processors are doing");
        return false;
    }
    // Unless a processor is found mark as not a compressor
    for (int processor_id = 0; processor_id < MAX_PROCESSORS; processor_id++) {
        processor_status[processor_id] = NOT_COMPRESSOR;
    }
    // Switch compressor processors to DOING_NOWT
    compressor_processors_top_t *compressor_processors_top =
        (void *) &region_addresses->pairs[n_region_pairs];
    for (uint32_t processor_index=0;
            processor_index < compressor_processors_top->n_processors;
            processor_index++) {
        processor_status[compressor_processors_top->processor_id[
            processor_index]] = DOING_NOWT;
    }

    log_processor_status();

    // set up addresses tracker (use sdram so that this can be handed to the
    // compressor to solve transmission faffs)
    log_info("malloc for table trackers");
    // set up addresses tracker (use sdram so that this can be handed to the
    // compressor to solve transmission faffs)
    log_info("malloc for table trackers");
    processor_bf_tables =
        MALLOC_SDRAM(MAX_PROCESSORS * sizeof(comp_processor_store_t));
    if (processor_bf_tables == NULL) {
        log_error(
            "failed to allocate memory for the holding of bitfield "
            "addresses per compressor processor");
        return false;
    }

    // ensure all bits set properly as init
    log_info("setting up table trackers.");
    for (int processor_id = 0; processor_id < MAX_PROCESSORS; processor_id++) {
        processor_bf_tables[processor_id].n_elements = 0;
        processor_bf_tables[processor_id].n_bit_fields = 0;
        processor_bf_tables[processor_id].compressed_table = NULL;
        processor_bf_tables[processor_id].elements = NULL;
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
    bool heap_creation = malloc_extras_initialise_and_build_fake_heap(
            usable_sdram_regions);
    if (!heap_creation){
        log_error("failed to setup stolen heap");
        return false;
    }
    log_info("finished setting up fake heap for sdram usage");

    // get the compressor processors stored in an array
    log_debug("start init of compressor processors");
    bool success_compressor_processors = initialise_compressor_processors();
    if (!success_compressor_processors) {
        log_error("failed to init the compressor processors.");
        return false;
    }

    // init the circular queue to handle the size of sdp messages expected
    // at any given point
    sdp_circular_queue = circular_buffer_initialize(
        MAX_PROCESSORS * N_MSGS_EXPECTED_FROM_COMPRESSOR);

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

    malloc_extras_check_all_marked(1005);
    return true;
}

//! \brief the main entrance.
void c_main(void) {
    bool success_init = initialise();
    if (!success_init){
        log_error("failed to init");
        malloc_extras_terminate(EXIT_FAIL);
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

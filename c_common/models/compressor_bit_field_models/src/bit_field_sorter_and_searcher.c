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
#include "common/constants.h"
#include "common/compressor_sorter_structs.h"
#include "sorter_includes/bit_field_table_generator.h"
#include "sorter_includes/helpful_functions.h"
#include "sorter_includes/bit_field_reader.h"
#include "sorter_includes/bit_field_creator.h"
#include "sorter_includes/message_sending.h"
/*****************************************************************************/
/* SpiNNaker routing table minimisation with bitfield integration control core.
 *
 * controls the attempt to minimise the router entries with bitfield
 * components.
 */

//============================================================================

//! \brief time step for safety timer tick interrupt
#define TIME_STEP 10
//! \brief counter of how many timesteps have passed
uint32_t timesteps = 0;
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

// \brief how many bitfields there are
int n_bf_addresses = 0;

//! \brief the list of bitfields in sorted order based off best effect, and
//! processor ids.
sorted_bit_fields_t* sorted_bit_fields;

// \brief the list of compressor cores to bitfield routing table sdram addresses
comp_core_store_t* cores_bf_tables;

//! \brief stores which values have been tested
bit_field_t tested_mid_points;

//! tracker for what each compressor core is doing (in terms of midpoints)
int* core_status;

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
void send_sdp_force_stop_message(int core_index){
    // set message params
    log_debug(
        "sending stop to core %d", core_index);
    my_msg.dest_port = (RANDOM_PORT << PORT_SHIFT) | core_index;
    compressor_payload_t* data = (compressor_payload_t*) &my_msg.data;
    data->command = STOP_COMPRESSION_ATTEMPT;
    my_msg.length = LENGTH_OF_SDP_HEADER + sizeof(command_codes_for_sdp_packet);

    // send sdp packet
    message_sending_send_sdp_message(&my_msg, core_index);
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

//! builds tables and tries to set off a compressor core based off midpoint
//! \param[in] mid_point: the mid point to start at
//! \param[in] core_index: the core/processor to run the compression on
//! \return bool fag if it fails for memory issues
bool create_tables_and_set_off_bit_compressor(int mid_point, int core_index) {
    int n_rt_addresses = 0;
    //log_info("started create bit field router tables");
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

    log_debug("finished creating bit field router tables");

    platform_check_all_marked(1001);
    // if successful, try setting off the bitfield compression
    bool success = message_sending_set_off_bit_field_compression(
        n_rt_addresses, mid_point, cores_bf_tables, bit_field_routing_tables,
        &my_msg, core_index);

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

//! \brief locates the next valid midpoint to test
//! \return int which is the midpoint or -1 if no midpoints left
int locate_next_mid_point() {
    int new_mid_point;
    if (n_bf_addresses == 0){
        return -1;
    }
    if (!bit_field_test(tested_mid_points, n_bf_addresses)){
        new_mid_point = n_bf_addresses;
    } else {
        log_info("n_bf_addresses %d tested_mid_points %d", n_bf_addresses, bit_field_test(tested_mid_points, n_bf_addresses));
        int best_end = -1;
        int best_length = 0;
        int current_length = 0;
        // check lowest_failure (false) to triggers a final else block
        log_info("best_success %d lowest_failure %d", best_success, lowest_failure);
        for (int index = best_success + 1; index <= lowest_failure; index++) {
            log_debug("index: %d, value: %u current_length: %d", index, bit_field_test(tested_mid_points, index), current_length);
            if (bit_field_test(tested_mid_points, index)){
               if (current_length > best_length){
                    best_length = current_length;
                    best_end = index - 1;
                    log_debug("found best_length: %d best_end %d", best_length, best_end);
                    current_length = 0;
               } else {
                    log_debug("not best: %d best_end %d", best_length, best_end);
               }
            } else {
               current_length+= 1;
            }
        }
        // use the best less half (shifted) of the best length
        new_mid_point = best_end - (best_length >> 1);
    }
    if (new_mid_point >= 0){
        bit_field_set(tested_mid_points, new_mid_point);
    }
    return new_mid_point;
}

//! \brief handles the freeing of memory from compressor cores, waiting for
//! compressor cores to finish and removing merged bitfields from the bitfield
//! regions.
void handle_best_cleanup(void){
    // load routing table into router
    load_routing_table_into_router();
    log_debug("finished loading table");

    // clear away bitfields that were merged into the router from
    //their lists.
    log_debug("remove merged bitfields");
    remove_merged_bitfields_from_cores();

    vcpu_t *sark_virtual_processor_info = (vcpu_t *) SV_VCPU;
    uint core = spin1_get_core_id();
    sark_virtual_processor_info[core].user2 = best_search_point;

    // Safety to break out of loop in check_buffer_queue
    found_best = true;

    terminate(EXITED_CLEANLY);
}

void log_core_status(){
    for (int i = 0; i < 18; i++){
        if (core_status[i] < -3 || core_status[i] > n_bf_addresses){
            log_error("Weird status %d: %d", i, core_status[i]);
            return;
        }
        //log_info("core: %d, status: %d", i, core_status[i]);
    }
    log_info("0:%d 1:%d 2:%d 3:%d 4:%d 5:%d 6:%d 7:%d 8:%d 9:%d 10:%d 11:%d "
        "12:%d 13:%d 14:%d 15:%d 16:%d 17:%d", core_status[0],
        core_status[1], core_status[2], core_status[3], core_status[4],
        core_status[5], core_status[6], core_status[7], core_status[8],
        core_status[9], core_status[10], core_status[11], core_status[12],
        core_status[13], core_status[14], core_status[15], core_status[16],
        core_status[17]);
}

//! \brief Returns the next core which is ready to run a compression
//! \param[in] mid_point: the mid point this core will use
//! \return the core_index/processor id of the next available core or -1 if none
int find_compressor_core(int midpoint){
    for (int core_index = 0; core_index < N_CORES; core_index++) {
        if (core_status[core_index] == DOING_NOWT){
            core_status[core_index] = midpoint ;
            return core_index;
        }
    }
    return -1;
}

//! \brief Check if a compressor core is available
//! \return true if at least one core is ready to compress
bool all_compressor_cores_busy(){
    for (int core_index = 0; core_index < N_CORES; core_index++) {
        if (core_status[core_index] == DOING_NOWT){
            return false;
        }
    }
    return true;
}

//! \brief Check to see if all compressor cores are done and not ready
//! \return true if all cores are done and not set ready
bool all_compressor_cores_done(){
    for (int core_index = 0; core_index < N_CORES; core_index++) {
        if (core_status[core_index] >= DOING_NOWT){
            return false;
        }
    }
    return true;
}

//! \brief Start the binary search on another compressor if one available

void carry_on_binary_search() {
     if (all_compressor_cores_done()){
        log_info("carry_on_binary_search detected done");
        handle_best_cleanup();
        // Above method has a terminate so no worry about carry on here
    }
    if (all_compressor_cores_busy()){
        return;  //Pass back to check_buffer_queue
    }
    log_info("start carry_on_binary_search");
    log_core_status();

    int mid_point = locate_next_mid_point();
    log_info("available with midpoint %d", mid_point);
    if (mid_point < 0) {
        // Ok lets turn all ready cores off as done.
        // At least defualt no bitfeild handled elsewhere so safe here.
        for (int core_index = 0; core_index < N_CORES; core_index++) {
            if (core_status[core_index] == DOING_NOWT) {
                core_status[core_index] = DO_NOT_USE;
            } else if (core_status[core_index] > DOING_NOWT) {
                log_info("waitig for core %d doing midpoint %u",
                    core_index, core_status[core_index]);
            }
        }
        return;
    }
    int core_index = find_compressor_core(mid_point);
    log_info("start create at timestep: %u", timesteps);
    bool success = create_tables_and_set_off_bit_compressor(
        mid_point, core_index);
    log_info("end create at timestep: %u", timesteps);
    if (!success) {
        // Ok lets turn this and all ready cores off to save space.
        // At least defualt no birfeild handled elsewhere so of to reduce.
        core_status[core_index] = DO_NOT_USE;
        for (int core_index = 0; core_index < N_CORES; core_index++) {
            if (core_status[core_index] == DOING_NOWT) {
                core_status[core_index] = DO_NOT_USE;
            }
        }
        // Ok that midpoint did not work so need to try it again
        bit_field_clear(tested_mid_points, mid_point);
        return;
    }
    log_info("done carry_on_binary_search");
    //log_core_status();    //spin1_mode_restore(cpsr);
    platform_check_all_marked(1002);
}

//! \brief timer interrupt for controlling time taken to try to compress table
//! \param[in] unused0: not used
//! \param[in] unused1: not used
void timer_callback(uint unused0, uint unused1) {
    use(unused0);
    use(unused1);
    timesteps+=1;
    //TODO remove this debug line
    if ((timesteps & 1023) == 0){
        log_info("timesteps: %u", timesteps);
    }
    if (timesteps > KILL_TIME){
        log_error("timer overran %u", timesteps);
        rt_error(RTE_SWERR);
    }
}

void process_failed(int midpoint){
    log_info("lowest_failure: %d midpoint:%d", lowest_failure, midpoint);
    if (lowest_failure > midpoint){
        lowest_failure = midpoint;
        log_info("Now lowest_failure: %d midpoint:%d", lowest_failure, midpoint);
    }
    // tell all compression cores trying midpoints above this one
    // to stop, as its highly likely a waste of time.
    for (int check_core_id = 0; check_core_id < N_CORES; check_core_id++) {
        if (core_status[check_core_id] > midpoint) {
            send_sdp_force_stop_message(check_core_id);
        }
    }
}


//! \brief processes the response from the compressor attempt
//! \param[in] comp_core_index: the compressor core id
//! \param[in] the response code / finished state
void process_compressor_response(int core_index, int finished_state) {
    int mid_point = core_status[core_index];
    log_debug("received response %d from core %d doing %d midpoint",
        finished_state, core_index, mid_point);
    if (mid_point == 0  && finished_state != SUCCESSFUL_COMPRESSION){
        log_error("The no bitfeilds attempted failed! Giving up");
        terminate(EXIT_FAIL);
    }
    core_status[core_index] = DOING_NOWT;

    if (finished_state == SUCCESSFUL_COMPRESSION) {
        log_info(
            "successful from core %d doing mid point %d",
            core_index, mid_point);

        if (best_success <= mid_point){
            best_success = mid_point;
            log_debug(
                "copying to %x from %x for compressed table",
                last_compressed_table,
                cores_bf_tables[core_index].compressed_table);
            sark_mem_cpy(
                last_compressed_table,
                cores_bf_tables[core_index].compressed_table,
                routing_table_sdram_size_of_table(TARGET_LENGTH));
            log_debug("n entries is %d", last_compressed_table->size);
        }

        // kill any search below this point, as they all redundant as
        // this is a better search.
        for (int check_core_id = 0; check_core_id < N_CORES; check_core_id++) {
            if (core_status[check_core_id] >= 0 &&
                    core_status[check_core_id] < mid_point) {
                send_sdp_force_stop_message(check_core_id);
            }
        }

        log_debug("finished process of successful compression");
    } else if (finished_state == FAILED_MALLOC) {
        log_info(
            "failed by malloc from core %d doing mid point %d",
            core_index, mid_point);
        // this will threshold the number of compressor cores that
        // can be ran at any given time.
        core_status[core_index] = DO_NOT_USE;
        // Remove the flag that say this midpoint has been checked
        bit_field_clear(tested_mid_points, mid_point);
    }
    else if (finished_state == FAILED_TO_COMPRESS){
        log_info(
            "failed to compress from core %d doing mid point %d",
            core_index, mid_point);
        process_failed(mid_point);
    } else if (finished_state == RAN_OUT_OF_TIME) {
        log_info(
            "failed by time from core %d doing mid point %d",
            core_index, mid_point);
        process_failed(mid_point);
    } else if (finished_state == FORCED_BY_COMPRESSOR_CONTROL){
        log_info(
            "ack from forced from core %d doing mid point %d",
            core_index, mid_point);
    } else {
        log_error(
            "no idea what to do with finished state %d, from core %d ignoring",
            finished_state, core_index);
    }

    // free the sdram associated with this compressor core.
    bool success = helpful_functions_free_sdram_from_compression_attempt(
        core_index, cores_bf_tables);
    if (!success) {
        log_error("failed to free sdram for compressor core %d. WTF",
                  core_index);
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
                platform_check_all_marked(1003);
                log_info("finished checkall");
                rt_error(RTE_SWERR);
                break;
            case COMPRESSION_RESPONSE:
                platform_check_all_marked(1004);

                // locate the compressor core id that responded
                log_debug("response packet");
                int core_index = msg->srce_port & CPU_MASK;

                // response code just has one value, so being lazy and not
                // casting
                int finished_state = msg_payload->response.response_code;

                // free message now, nothing left in it and we don't want to
                // hold the memory for very long
                sark_msg_free((sdp_msg_t*) msg);
                msg = NULL;

                // create holder

                uint32_t store = core_index << CORE_MOVE;
                store = store | finished_state;

                // store holder
                log_info(
                    "finished state %d, index %d, store %d",
                    finished_state, core_index, store);
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
    int core_index = find_compressor_core(0);
    if (core_index < 0){
        log_error("No core available for no bitfeild attempt");
        rt_error(RTE_SWERR);
    }
    bit_field_set(tested_mid_points, 0);
    // set off a none bitfield compression attempt, to pipe line work
    log_info("sets off the no bitfeild version of the search on %u", core_index);
    return message_sending_set_off_no_bit_field_compression(
        cores_bf_tables, &my_msg, uncompressed_router_table, core_index);
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
            log_debug("processing packet from circular buffer");
            process_compressor_response(core_index, finished_state);
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

    platform_turn_off_print();

    //TODO REMOVE
    log_info("OLD read in bitfields");
    bool read_success = false;
    bit_field_by_processor = bit_field_reader_read_in_bit_fields(
            region_addresses);
    if (bit_field_by_processor == NULL){
        log_error("failed to read in bitfields, quitting");
        terminate(EXIT_MALLOC);
    }

    // set off the first compression attempt (aka no bitfields).
    bool success = setup_no_bitfeilds_attempt();
    if (!success){
        log_error("failed to set up uncompressed attempt");
        terminate(EXIT_MALLOC);
    }

    log_info("reading bitfields at timestep: %d", timesteps);
    sorted_bit_fields = bit_field_creator_read_in_bit_fields(&n_bf_addresses,
        region_addresses);
    // check state
    if (sorted_bit_fields == NULL){
        log_error("failed to read in bitfields, quitting");
        terminate(EXIT_MALLOC);
    }
    lowest_failure = n_bf_addresses;
    log_info("finished reading bitfields at timestep: %d", timesteps);

    set_up_tested_mid_points();
    //platform_turn_on_print();

    //TODO: safety code to be removed
    for (int bit_field_index = 0; bit_field_index < n_bf_addresses;
            bit_field_index++) {
        // get key
        filter_info_t* bf_pointer =
            sorted_bit_fields->bit_fields[bit_field_index];
        if (bf_pointer == NULL) {
            log_info("failed at index %d", bit_field_index);
            terminate(RTE_SWERR);
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

    // allocate DTCM memory for the core status trackers
    log_info("allocate and step compressor core status");
    core_status = MALLOC(N_CORES * sizeof(int));
    if (core_status == NULL) {
        log_error(
            "failed to allocate memory for tracking what the "
            "compression cores are doing");
        return false;
    }
    // Unless a core is found mark as not a compressor
    for (int core = 0; core < N_CORES; core++) {
        core_status[core] = NOT_COMPRESSOR;
    }
    // Switch compressor cores to DOING_NOWT
    compressor_cores_top_t *compressor_cores_top =
        (void *) &region_addresses->pairs[n_region_pairs];
    for (uint32_t core=0; core < compressor_cores_top->n_cores; core++) {
        core_status[compressor_cores_top->core_id[core]] = DOING_NOWT;
    }
    //core_status[4] = DOING_NOWT;
    log_core_status();

    // set up addresses tracker (use sdram so that this can be handed to the
    // compressor to solve transmission faffs)
    log_info("malloc for table trackers");
    // set up addresses tracker (use sdram so that this can be handed to the
    // compressor to solve transmission faffs)
    log_info("malloc for table trackers");
    cores_bf_tables =
        MALLOC_SDRAM(N_CORES * sizeof(comp_core_store_t));
    if (cores_bf_tables == NULL) {
        log_error(
            "failed to allocate memory for the holding of bitfield "
            "addresses per compressor core");
        return false;
    }

    // ensure all bits set properly as init
    log_info("setting up table trackers.");
    for (int c_core = 0; c_core < N_CORES; c_core++) {
        cores_bf_tables[c_core].n_elements = 0;
        cores_bf_tables[c_core].n_bit_fields = 0;
        cores_bf_tables[c_core].compressed_table = NULL;
        cores_bf_tables[c_core].elements = NULL;
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
        N_CORES * N_MSGS_EXPECTED_FROM_COMPRESSOR);

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

    platform_check_all_marked(1005);
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

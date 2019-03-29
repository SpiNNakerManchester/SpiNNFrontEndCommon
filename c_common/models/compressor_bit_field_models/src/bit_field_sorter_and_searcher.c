#include <spin1_api.h>
#include <debug.h>
#include <bit_field.h>
#include <sdp_no_scp.h>
#include "common-typedefs.h"
#include "common/platform.h"
#include "common/routing_table.h"
#include "common/sdp_formats.h"
#include "common/constants.h"
#include "sorter_includes/compressor_sorter_structs.h"
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

//! time step for safety timer tick interrupt
#define TIME_STEP 10000

//! bits in a word
#define BITS_IN_A_WORD 32

//! bit shift for the app id for the route
#define ROUTE_APP_ID_BIT_SHIFT 24

//============================================================================

//! bool flag saying still reading in bitfields, so that state machine dont 
//! go boom when un compressed result comes in
bool reading_bit_fields = true;

//! bool flag for stopping multiple attempts to run carry on binary search
bool still_trying_to_carry_on = false;

//! time to take per compression iteration
uint32_t time_per_iteration = 0;

//! flag of how many times the timer has fired during this one
uint32_t finish_compression_flag = 0;

//! easier programming tracking of the user registers
address_t user_register_content[USER_REGISTER_LENGTH];

//! best routing table position in the search
int best_search_point = 0;

//! the last routing table position in the search
int last_search_point = 0;

//! the store for the last routing table that was compressed
table_t* last_compressed_table;

//! the compressor app id
uint32_t app_id = 0;

// how many bitfields there are
int n_bf_addresses = 0;

//! the list of bitfields in sorted order based off best effect, and
//! processor ids.
sorted_bit_fields_t* sorted_bit_fields;

// the list of compressor cores to bitfield routing table sdram addresses
comp_core_store_t* comp_cores_bf_tables;

//! list of processor ids which will be running the compressor binary
int* compressor_cores;

//! how many compression cores there are
int n_compression_cores;

//! how many compression cores are available
int n_available_compression_cores;

//! stores which values have been tested
bit_field_t tested_mid_points;

//! stores which mid points have successes or failed
bit_field_t mid_points_successes;

//! tracker for what each compressor core is doing (in terms of midpoints)
int* comp_core_mid_point;

//! the bitfield by processor global holder
_bit_field_by_processor_t* bit_field_by_processor;

//! \brief sdp message to send control messages to compressors cores
sdp_msg_pure_data my_msg;

//============================================================================

//! \brief Load the best routing table to the router.
//! \return bool saying if the table was loaded into the router or not
bool load_routing_table_into_router() {

    // Try to allocate sufficient room for the routing table.
    int start_entry = rtr_alloc_id(last_compressed_table->size, app_id);
    if (start_entry == 0) {
        log_error(
            "Unable to allocate routing table of size %u\n",
            last_compressed_table->size);
        return false;
    }

    // Load entries into the table (provided the allocation succeeded).
    // Note that although the allocation included the specified
    // application ID we also need to include it as the most significant
    // byte in the route (see `sark_hw.c`).
    log_info("loading %d entries into router", last_compressed_table->size);
    for (int entry_id = 0; entry_id < last_compressed_table->size; entry_id++) {
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
void send_sdp_force_stop_message(int processor_id){
    // set message params
    my_msg.dest_port = (RANDOM_PORT << PORT_SHIFT) | processor_id;
    my_msg.data[COMMAND_CODE] = STOP_COMPRESSION_ATTEMPT;
    my_msg.length = LENGTH_OF_SDP_HEADER + COMMAND_CODE_SIZE_IN_BYTES;
    
    // send sdp packet
    message_sending_send_sdp_message(&my_msg);
}

//! \brief sets up the search bitfields.
//! \return bool saying success or failure of the setup
bool set_up_search_bitfields(){
    tested_mid_points = bit_field_alloc(n_bf_addresses);
    mid_points_successes = bit_field_alloc(n_bf_addresses);

    // check the malloc worked
    if (tested_mid_points == NULL){
        return false;
    }
    if (mid_points_successes == NULL){
        FREE(tested_mid_points);
        return false;
    }

    // clear the bitfields
    clear_bit_field(tested_mid_points, get_bit_field_size(n_bf_addresses));
    clear_bit_field(mid_points_successes, get_bit_field_size(n_bf_addresses));

    // return if successful
    return true;
}

//! \brief counts how many cores are actually doing something.
//! \return the number of compressor cores doing something at the moment.
int count_many_on_going_compression_attempts_are_running(){
    int count = 0;
    for(int c_core_index = 0; c_core_index < n_compression_cores;
            c_core_index++){
        if (comp_core_mid_point[c_core_index] != DOING_NOWT){
            count ++;
        }
    }
    return count;
}

//! \brief locate the core index for this processor id.
//! \param[in] processor_id: the processor id to find index for.
//! \return the index in the compressor cores for this processor id
int get_core_index_from_id(int processor_id){
    for(int comp_core_index = 0; comp_core_index < n_compression_cores;
            comp_core_index++){
        if(compressor_cores[comp_core_index] == processor_id){
            return comp_core_index;
        }
    }
    log_error(
        "failed to find the core id for this core index %d", processor_id);
    vcpu_t *sark_virtual_processor_info = (vcpu_t*) SV_VCPU;
    sark_virtual_processor_info[spin1_get_core_id()].user1 = EXIT_FAIL;
    rt_error(RTE_SWERR);
    return 0;
}

//! builds tables and tries to set off a compressor core based off midpoint
//! \param[in] mid_point: the mid point to start at
//! \return bool fag if it fails for memory issues
bool create_tables_and_set_off_bit_compressor(int mid_point){
    int n_rt_addresses = 0;
    log_debug("started create bit field router tables");
    address_t* bit_field_routing_tables =
        bit_field_table_generator_create_bit_field_router_tables(
            mid_point, &n_rt_addresses, user_register_content,
            bit_field_by_processor, sorted_bit_fields);
    if (bit_field_routing_tables == NULL){
        log_debug(
            "failed to create bitfield tables for midpoint %d", mid_point);
        return false;
    }

    log_debug("finished creating bit field router tables");

    // if successful, try setting off the bitfield compression
    bool success = set_off_bit_field_compression(
        n_rt_addresses, mid_point, comp_cores_bf_tables,
        bit_field_routing_tables, &my_msg, compressor_cores,
        user_register_content, n_compression_cores, comp_core_mid_point,
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
bool start_binary_search(){

    // if there's only there's no available, but cores still attempting. just
    // return. it'll bounce back when a response is received
    if (n_available_compression_cores == 0 &&
            count_many_on_going_compression_attempts_are_running() > 0){
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
    if (hops_between_compression_cores == 0){
        hops_between_compression_cores = 1;
    }

    log_debug("n_bf_addresses is %d", n_bf_addresses);
    log_debug("n available compression cores is %d",
    n_available_compression_cores);
    log_debug("hops between attempts is %d", hops_between_compression_cores);

    bool failed_to_malloc = false;
    int new_mid_point = hops_between_compression_cores * multiplier;
    log_debug("n bf addresses = %d", n_bf_addresses);

    for (int index = 0; index < n_bf_addresses; index++){
        log_debug(
            "sorted bitfields address at index %d is %x",
            index, sorted_bit_fields->bit_fields[index]);
    }

    // iterate till either ran out of cores, or failed to malloc sdram during
    // the setup of a core or when gone too far
    while (n_available_compression_cores != 0 && !failed_to_malloc &&
            new_mid_point <= n_bf_addresses){

        log_info("next mid point to consider = %d", new_mid_point);
        bool success = create_tables_and_set_off_bit_compressor(new_mid_point);
        log_info("success is %d", success);

        if(success){
            multiplier ++;
        }
        else{
            log_debug(
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
    if (multiplier == 1){
        log_debug("failed at first bitfield");
        return false;
    }
    
    // set off at least one compression, but at some point failed to malloc 
    // sdram. assume this is the cap on how many cores can be ran at any 
    // given time
    if (failed_to_malloc){
        n_available_compression_cores = 0;
    }

    // return success for reading in and sorting bitfields
    reading_bit_fields = false;
    
    // say we've started
    return true;
}

//! sort out bitfields into processors and the keys of the bitfields to remove
//! \param[out] sorted_bf_by_processor: the sorted stuff
bool sort_sorted_to_cores(
        proc_bit_field_keys_t* sorted_bf_by_processor){

    int n_regions = user_register_content[REGION_ADDRESSES][N_PAIRS];
    sorted_bf_by_processor = MALLOC(n_regions * sizeof(proc_bit_field_keys_t));
    if (sorted_bf_by_processor == NULL){
        log_error(
            "failed to allocate memory for the sorting of bitfield to keys");
        return false;
    }

    //locate how many bitfields in the search space accepted that are of a
    // given core.
    uint position_in_region_data = START_OF_ADDRESSES_DATA;
    for (int r_id = 0; r_id < n_regions; r_id++){

        // locate processor id for this region
        int region_proc_id = user_register_content[
            REGION_ADDRESSES][position_in_region_data + PROCESSOR_ID];
        sorted_bf_by_processor[r_id].processor_id = region_proc_id;
        position_in_region_data += ADDRESS_PAIR_LENGTH;

        // count entries
        int n_entries = 0;
        for(int bf_index = 0; bf_index < best_search_point; bf_index++){
            if (sorted_bit_fields->processor_ids[bf_index] == region_proc_id){
                n_entries ++;
            }
        }

        // update length
        sorted_bf_by_processor[r_id].length_of_list = n_entries;

        // alloc for keys
        sorted_bf_by_processor[r_id].master_pop_keys = MALLOC(
            n_entries * sizeof(int));
        if (sorted_bf_by_processor[r_id].master_pop_keys == NULL){
            log_error(
                "failed to allocate memory for the master pop keys for "
                "processor %d in the sorting of successful bitfields to "
                "remove.", region_proc_id);
            for (int free_id =0; free_id < r_id; free_id++){
                FREE(sorted_bf_by_processor->master_pop_keys);
            }
            FREE(sorted_bf_by_processor);
            return false;
        }

        // put keys in the array
        int array_index = 0;
        for(int bf_index = 0; bf_index < best_search_point; bf_index++){
            if (sorted_bit_fields->processor_ids[bf_index] == region_proc_id){
                sorted_bf_by_processor->master_pop_keys[array_index] =
                    sorted_bit_fields->bit_fields[bf_index][
                        BIT_FIELD_BASE_KEY];
                array_index ++;
            }
        }
    }

    return true;
}

//! \brief finds the region id in the region addresses for this processor id
//! \param[in] processor_id: the processor id to find the region id in the
//! addresses
//! \return the address in the addresses region for the processor id
address_t find_processor_bit_field_region(int processor_id){

    // find the right bitfield region
    uint position_in_region_data = START_OF_ADDRESSES_DATA;
    for (uint32_t r_id = 0;
            r_id < user_register_content[REGION_ADDRESSES][N_PAIRS]; r_id ++){
        int region_proc_id = user_register_content[
            REGION_ADDRESSES][position_in_region_data + PROCESSOR_ID];
        if (region_proc_id == processor_id){
            return (address_t) user_register_content[REGION_ADDRESSES][
                position_in_region_data + BITFIELD_REGION];
        }
        position_in_region_data += ADDRESS_PAIR_LENGTH;
    }

    // if not found
    log_error("failed to find the right region. WTF");
    vcpu_t *sark_virtual_processor_info = (vcpu_t*) SV_VCPU;
    sark_virtual_processor_info[spin1_get_core_id()].user1 = EXIT_SWERR;
    rt_error(RTE_SWERR);
    return NULL;
}

//! \brief checks if a key is in the set to be removed.
//! \param[in] sorted_bf_key_proc: the key store
//! \param[in] key: the key to locate a entry for
//! \return true if found, false otherwise
bool has_entry_in_sorted_keys(
        proc_bit_field_keys_t sorted_bf_key_proc, uint32_t key){
    for (int element_index = 0;
            element_index < sorted_bf_key_proc.length_of_list;
            element_index++){
        if(sorted_bf_key_proc.master_pop_keys[element_index] == key){
            return true;
        }
    }
    return false;
}

//! \brief removes the merged bitfields from the application cores bitfield
//!        regions
//! \return bool if was successful or not
bool remove_merged_bitfields_from_cores(){

    proc_bit_field_keys_t* sorted_bf_key_proc = NULL;

    // sort out the bitfields
    bool success = sort_sorted_to_cores(sorted_bf_key_proc);
    if (!success){
        log_error("could not sort out bitfields to keys.");
        return false;
    }

    // iterate though the cores sorted, and remove said bitfields from its
    // region
    for (uint32_t core_index = 0;
            core_index < user_register_content[REGION_ADDRESSES][N_PAIRS];
            core_index++){
        int proc_id = sorted_bf_key_proc[core_index].processor_id;
        address_t bit_field_region = find_processor_bit_field_region(proc_id);

        // iterate though the bitfield region looking for bitfields with
        // correct keys to remove
        int n_bit_fields = bit_field_region[N_BIT_FIELDS];
        bit_field_region[N_BIT_FIELDS] =
            n_bit_fields -  sorted_bf_key_proc[core_index].length_of_list;

        // pointers for shifting data up by excluding the ones been added to
        // router.
        int write_index = START_OF_BIT_FIELD_TOP_DATA;
        int read_index = START_OF_BIT_FIELD_TOP_DATA;

        // iterate though the bitfields only writing ones which are not removed
        for (int bf_index = 0; bf_index < n_bit_fields; bf_index++){
            uint32_t sdram_key =
                bit_field_region[read_index + BIT_FIELD_BASE_KEY];

            // if entry is to be removed
            if(has_entry_in_sorted_keys(
                    sorted_bf_key_proc[core_index], sdram_key)){
                // hop over in reading, do no writing
                read_index += (
                    bit_field_region[read_index + BIT_FIELD_N_WORDS] +
                    START_OF_BIT_FIELD_DATA);
            }
            else{  // write the data in the current write positions
                int words_written_read = START_OF_BIT_FIELD_DATA;
                if (write_index != read_index){
                    // key and n words
                    bit_field_region[write_index + BIT_FIELD_BASE_KEY] =
                        bit_field_region[read_index + BIT_FIELD_BASE_KEY];
                    bit_field_region[write_index + BIT_FIELD_N_WORDS] =
                        bit_field_region[read_index + BIT_FIELD_N_WORDS];

                    // copy the bitfield over to the new location
                    sark_mem_cpy(
                        &bit_field_region[
                            read_index + START_OF_BIT_FIELD_DATA],
                        &bit_field_region[
                            write_index + START_OF_BIT_FIELD_DATA],
                        bit_field_region[read_index + BIT_FIELD_N_WORDS]);

                    words_written_read +=
                        bit_field_region[write_index + BIT_FIELD_N_WORDS];
                }

                // update pointers
                write_index += words_written_read;
                read_index += words_written_read;
            }
        }
    }

    // free items
    for (uint32_t core_index = 0;
            core_index < user_register_content[REGION_ADDRESSES][N_PAIRS];
            core_index++){
        if(sorted_bf_key_proc[core_index].length_of_list != 0){
            FREE(sorted_bf_key_proc[core_index].master_pop_keys);
        }
    }
    FREE(sorted_bf_key_proc);

    // return we successfully removed merged bitfields
    return true;
}

//! \brief tells ya if a compressor is already doing a mid point
//! \param[in] mid_point: the mid point to look for
//! \return bool saying true if there is a compressor running this right now
bool already_being_processed(int mid_point){
    for(int c_index = 0; c_index < n_compression_cores; c_index++){
        if (comp_core_mid_point[c_index] == mid_point){
            return true;
        }
    }
    return false;
}

//! \brief returns the best mid point tested to date. NOTE its only safe to call
//! this after the first attempt finished. which is acceptable
//! \return the best bf midpoint tested and success
int best_mid_point_to_date(){

    // go backwards to find the first passed value
    for (int n_bf = n_bf_addresses; n_bf >= 0; n_bf --){
        if (bit_field_test(mid_points_successes, n_bf)){
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
//! \return the next tested bf midpoint from midpoint
int next_tested_mid_point_from(int mid_point){
     for (int n_bf = mid_point + 1; n_bf < n_bf_addresses ; n_bf ++){
        if (bit_field_test(tested_mid_points, n_bf)){
            log_debug("returns %d", n_bf);
            return n_bf;
        }
    }
    return n_bf_addresses;
}

//! \brief return the spaces higher than me which could be tested
//! \param[in] point: the point to look from
//! \param[out] length: the length of the testing cores.
//! \param[out] found_best: bool flag saying if found the best point overall
//! \return bool stating if it was successful or not in memory alloc
int* find_spaces_high_than_point(
        int point, int* length, int next_tested_point, bool* found_best){

    log_debug("found best is %d", *found_best);

    // if the diff between the best tested and next tested is 1, then the
    // best is the overall best
    if (next_tested_point - point == 1 && bit_field_test(
            tested_mid_points, next_tested_point)){
        *found_best = true;
        return NULL;
    }

    // find how many values are being tested between best tested and next
    // tested
    *length = 1;

    log_debug("locate already tested");
    for (int n_bf = next_tested_point; n_bf >= point; n_bf--){
        if (already_being_processed(n_bf)){
            *length += 1;
        }
    }
    log_info("length is %d", *length);

    // malloc the spaces
    log_debug("size is %d", *length * sizeof(int));
    int* testing_cores = MALLOC(*length * sizeof(int));
    log_debug("malloc-ed");
    if (testing_cores == NULL){
        log_error(
            "failed to allocate memory for the locate next midpoint searcher");
        return NULL;
    }

    // populate list
    log_info("populate list");
    testing_cores[0] = point;
    log_info("testing cores index %d is %d", 0, point);
    int testing_core_index = 1;
    for (int n_bf = point; n_bf <= next_tested_point; n_bf ++){

        if (already_being_processed(n_bf)){
            testing_cores[testing_core_index] = n_bf;
            log_info("testing cores index %d is %d", testing_core_index, n_bf);
            testing_core_index += 1;
        }
    }

    // return success
    return testing_cores;

}

//! \brief locates the next valid midpoint which has not been tested or being
//! tested and has a chance of working/ improving the space
//! \param[out] bool flag to say found best
//! \return midpoint to search
bool locate_next_mid_point(bool* found_best, int* new_mid_point){
    // get base line to start searching for new locations to test
    int best_mp_to_date = best_mid_point_to_date();
    int next_tested_point = next_tested_mid_point_from(best_mp_to_date);
    int length = 0;

    log_debug(
        "next tested point from %d is %d",
        best_mp_to_date, next_tested_point);

    if (best_mp_to_date == next_tested_point){
        *found_best = true;
        best_search_point = best_mp_to_date;
        *new_mid_point = DOING_NOWT;
        log_debug("best search point is %d", best_mp_to_date);
        return true;
    }

    // fill in the locations bigger than best that are being tested
    log_debug("find spaces");
    int* higher_testers = find_spaces_high_than_point(
        best_mp_to_date, &length, next_tested_point, found_best);
    log_debug("populated higher testers");

    // exit if best found
    if (*found_best){
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
            test_base_index++){

        // will be going from low to high, for that's how its been searched
        int diff = higher_testers[test_base_index + 1] -
            higher_testers[test_base_index];
        log_debug("diff is %d", diff);
        if (diff > biggest_dif){
            biggest_dif = diff;
        }
    }
    log_debug("best dif is %d", biggest_dif);

    // handle case of no split between best and last tested
    // NOTE this only happens with n compression cores of 1.
    if (length == 1){
        log_info(
            "next tested point = %d, best_mp_to_date = %d",
            next_tested_point, best_mp_to_date);
        int hop = (next_tested_point - best_mp_to_date) / 2;
        if (hop == 0){
            hop = 1;
        }
        *new_mid_point = best_mp_to_date + hop;
        log_info("new midpoint is %d", *new_mid_point);
        return true;
    }

    // locate the first with biggest dif, split in middle and return that as
    // new mid point to test
    log_info("cycling");
    for (int test_base_index = 0; test_base_index < length; test_base_index++){
        log_debug("entered");

        // will be going from high to low, for that's how its been searched
        int diff = higher_testers[test_base_index + 1] -
            higher_testers[test_base_index];
        log_debug("located diff %d, looking for b diff %d", diff, biggest_dif);

        // if the right diff, figure the midpoint of these points.
        if (diff == biggest_dif){
            // deduce hop
            int hop = (biggest_dif / 2);
            log_debug("hop is %d", hop);
            if (hop == 0){
                hop = 1;
            }

            // deduce new mid point
            *new_mid_point = higher_testers[test_base_index] + hop;
            log_debug("next mid point to test is %d", *new_mid_point);

            // check if we're testing this already, coz if we are. do nowt
            if (already_being_processed(*new_mid_point)){
                log_info(
                    "already testing mid point %d, so do nothing",
                    *new_mid_point);
                *new_mid_point = DOING_NOWT;
                return true;
            }

            // if hitting the bottom. check that uncompressed worked or not
            if (*new_mid_point == 0){
                // check that it worked (it might not have finished, in some
                // odd flow
                if (bit_field_test(mid_points_successes, *new_mid_point)){
                    best_search_point = *new_mid_point;
                    *found_best = true;
                    return true;
                }
                // if we got here its odd. but put this here for completeness
                if(bit_field_test(tested_mid_points, *new_mid_point)){
                    log_error(
                        "got to the point of searching for mid point 0."
                        " And 0 has been tested and failed. therefore complete"
                        " failure has occurred.");
                    return false;
                }
            }
        }
    }
    log_info("left cycle with new mid point of %d", *new_mid_point);
    FREE(higher_testers);
    return true;
}

//! \brief compress the bitfields from the best location
void carry_on_binary_search(uint unused0, uint unused1){
    // api requirement
    use(unused0);
    use(unused1);
    log_info("started carry on");

    bool failed_to_malloc = false;
    bool found_best = false;
    bool nothing_to_do = false;

    log_debug("found best is %d", found_best);

    // iterate till either ran out of cores, or failed to malloc sdram during
    // the setup of a core or found best or no other mid points need to be
    // tested
    log_debug("start while");
    while (n_available_compression_cores != 0 && !failed_to_malloc &&
            !found_best && !nothing_to_do){

        log_info("try a carry on core");

        // locate next midpoint to test
        int mid_point;
        bool success = locate_next_mid_point(&found_best, &mid_point);

        // check for not needing to do things but wait
        if (mid_point == DOING_NOWT && !found_best){
            log_info("no need to cycle, as nowt to do but wait");
            nothing_to_do = true;
        }
        else{
            // if finished search, load best into table
            if (found_best){
                log_info(
                    "finished search successfully best mid point was %d",
                    best_search_point);
                load_routing_table_into_router();
                log_info("finished loading table");
                vcpu_t *sark_virtual_processor_info = (vcpu_t*) SV_VCPU;
                sark_virtual_processor_info[spin1_get_core_id()].user1 =
                    EXITED_CLEANLY;
                spin1_exit(0);
                return;
            }
            else{
                // not found best, so try to set off compression if memory done

                log_info("trying with midpoint %d", mid_point);
                if (!success){
                    failed_to_malloc = true;
                }
                else{  // try a compression run
                    success = create_tables_and_set_off_bit_compressor(
                        mid_point);
                    if (success){
                        log_info("success sending");
                    }

                    // failed to set off the run for a memory reason
                    if (!success){
                        failed_to_malloc = true;
                        log_info("failed to send due to malloc");
                    }
                }
            }
        }
    }

    log_info("checking state");

    // if failed to malloc, limit exploration to the number of cores running.
    if (failed_to_malloc){
        log_info("in failed to malloc");
        n_available_compression_cores = 0;

        // if the current running number of cores is 0, then we cant generate
        // the next midpoint,
        if(count_many_on_going_compression_attempts_are_running() == 0){
            int best_mid_point_tested = best_mid_point_to_date();

            // check if current reach is enough to count as a success
            if ((n_bf_addresses / best_mid_point_tested) >=
                    (int) user_register_content[REGION_ADDRESSES][THRESHOLD]){
                found_best = true;
                best_search_point = best_mid_point_tested;
                log_debug("finished search by end user QoS");
                load_routing_table_into_router();
            }
            else{
                log_error(
                    "failed to compress enough bitfields for threshold.");
                vcpu_t *sark_virtual_processor_info = (vcpu_t*) SV_VCPU;
                sark_virtual_processor_info[spin1_get_core_id()].user1 =
                    EXIT_FAIL;
                spin1_exit(0);
            }
        }
    }

    // set flag for handling responses to bounce back in here
    still_trying_to_carry_on = false;
}


//! \brief timer interrupt for controlling time taken to try to compress table
//! \param[in] unused0: not used
//! \param[in] unused1: not used
void timer_callback(uint unused0, uint unused1) {
    use(unused0);
    use(unused1);

    // protects against any race conditions where everything has finished but
    // due to interrupt priorities, sdp message mailbox limits etc. Best way
    // will be to periodically assess if we need to do anything
    if (count_many_on_going_compression_attempts_are_running() == 0 &&
            !reading_bit_fields && !still_trying_to_carry_on){
        log_info("firing off carry on from timer");
        spin1_schedule_callback(
            carry_on_binary_search, 0, 0, COMPRESSION_START_PRIORITY);
    }
}

//! \brief processes the response from the compressor attempt
//! \param[in] comp_core_index: the compressor core id
//! \param[in] the response code / finished state
void process_compressor_response(int comp_core_index, int finished_state){
    
    // filter off finished state
    if (finished_state == SUCCESSFUL_COMPRESSION){
        log_info(
            "successful from core %d doing mid point %d",
            compressor_cores[comp_core_index],
            comp_core_mid_point[comp_core_index]);
        bit_field_set(tested_mid_points, comp_core_mid_point[comp_core_index]);
        bit_field_set(
            mid_points_successes, comp_core_mid_point[comp_core_index]);

        // set tracker if its the best seen so far
        if (best_mid_point_to_date() == comp_core_mid_point[comp_core_index]){
            best_search_point = comp_core_mid_point[comp_core_index];
            sark_mem_cpy(
                last_compressed_table,
                comp_cores_bf_tables[comp_core_index].compressed_table,
                routing_table_sdram_size_of_table(TARGET_LENGTH));
        }

        // release for next set
        comp_core_mid_point[comp_core_index] = DOING_NOWT;
        n_available_compression_cores ++;

        // kill any search below this point, as they all successful if this one
        // was / redundant as this is a better search.

        // free the sdram associated with this compressor core.
        bool success = helpful_functions_free_sdram_from_compression_attempt(
            comp_core_index, comp_cores_bf_tables);
        if (!success){
            log_error("failed to free sdram for compressor core %d. WTF",
                      comp_core_index);
        }
        log_debug("finished process of successful compression");
    }
    else if (finished_state == FAILED_MALLOC){
        log_info(
            "failed to malloc from core %d doing mid point %d",
            comp_core_index, comp_core_mid_point[comp_core_index]);
        // this will threshold the number of compressor cores that
        // can be ran at any given time.
        comp_core_mid_point[comp_core_index] = DOING_NOWT;
        // free the sdram associated with this compressor core.
        bool success = helpful_functions_free_sdram_from_compression_attempt(
            comp_core_index, comp_cores_bf_tables);
        if (!success){
            log_error("failed to free sdram for compressor core %d. WTF",
                      comp_core_index);
        }
    }
    else if (finished_state == FAILED_TO_COMPRESS){
        log_info(
            "failed to compress from core %d doing mid point %d",
            comp_core_index, comp_core_mid_point[comp_core_index]);

        // it failed to compress, so it was successful in malloc.
        // so mark the midpoint as tested, and free the core for another
        // attempt
        int compression_mid_point = comp_core_mid_point[comp_core_index];
        bit_field_set(tested_mid_points, compression_mid_point);
        comp_core_mid_point[comp_core_index] = DOING_NOWT;
        n_available_compression_cores ++;
    
        // set all indices above this one to false, as this one failed
        for(int test_index = compression_mid_point;
                test_index < n_bf_addresses; test_index++){
            bit_field_set(tested_mid_points, test_index);
        }
    
        // tell all compression cores trying midpoints above this one
        // to stop, as its highly likely a waste of time.
        for (int check_core_id = 0;
                check_core_id < n_compression_cores; check_core_id++){
            if (comp_core_mid_point[check_core_id] > compression_mid_point){
                send_sdp_force_stop_message(check_core_id);
            }
        }

        // free the sdram associated with this compressor core.
        bool success = helpful_functions_free_sdram_from_compression_attempt(
            comp_core_index, comp_cores_bf_tables);
        if (!success){
            log_error("failed to free sdram for compressor core %d. WTF",
                      comp_core_index);
        }
    }
    else if (finished_state == RAN_OUT_OF_TIME){
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
        n_available_compression_cores ++;

        // tell all compression cores trying midpoints above this one
        // to stop, as its highly likely a waste of time.
        for (int check_core_id = 0;
                check_core_id < n_compression_cores; check_core_id++){
            if (comp_core_mid_point[check_core_id] > compression_mid_point){
                send_sdp_force_stop_message(check_core_id);
            }
        }

        // free the sdram associated with this compressor core.
        bool success = helpful_functions_free_sdram_from_compression_attempt(
            comp_core_index, comp_cores_bf_tables);
        if (!success){
            log_error("failed to free sdram for compressor core %d. WTF",
                      comp_core_index);
        }
    }
    else if (finished_state == FORCED_BY_COMPRESSOR_CONTROL){
        log_info(
            "ack from forced from core %d doing mid point %d",
            comp_core_index, comp_core_mid_point[comp_core_index]);
        // this gives no context of why the control killed it. just
        // free the core for another attempt
        comp_core_mid_point[comp_core_index] = DOING_NOWT;
        n_available_compression_cores ++;

        // free the sdram associated with this compressor core.
        bool success = helpful_functions_free_sdram_from_compression_attempt(
            comp_core_index, comp_cores_bf_tables);
        if (!success){
            log_error("failed to free sdram for compressor core %d. WTF",
                      comp_core_index);
        }
    }
    else{
        log_error("no idea what to do with finished state %d, from "
                  "core %d ignoring", finished_state, comp_core_index);
    }

    // having processed the packet, and there are spare cores for compression
    // attempts, try to set off another search.  (this encapsulates the
    // finish state as well.
    log_debug(
        "n av cores = %d, bool of reading is %d",
        n_available_compression_cores, reading_bit_fields);
    if (n_available_compression_cores > 0 && !reading_bit_fields){
        if (!still_trying_to_carry_on){
            log_info("setting off carry on");
            still_trying_to_carry_on = true;
            spin1_schedule_callback(
                carry_on_binary_search, 0, 0, COMPRESSION_START_PRIORITY);
        }else{
            log_info("all ready in carry on mode. ignoring");
        }
    }
    else{
        log_info("not ready to carry on yet");
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
    log_debug("command code is %d", msg->data[COMMAND_CODE]);
    log_debug(
        "response code was %d", msg->data[START_OF_SPECIFIC_MESSAGE_DATA]);

    // filter off the port we've decided to use for this
    if (msg->srce_port >> PORT_SHIFT == RANDOM_PORT){
        log_debug("correct port");
        // filter based off the command code. Anything thats not a response is
        // a error
        if (msg->data[COMMAND_CODE] == START_DATA_STREAM){
            log_error(
                "no idea why im receiving a start data message. Ignoring");
            sark_msg_free((sdp_msg_t*) msg);
        }
        else if (msg->data[COMMAND_CODE] == EXTRA_DATA_STREAM){
            log_error(
                "no idea why im receiving a extra data message. Ignoring");
            sark_msg_free((sdp_msg_t*) msg);
        }
        else if(msg->data[COMMAND_CODE] == COMPRESSION_RESPONSE){
            // locate the compressor core id that responded
            log_debug("response packet");
            int comp_core_index = get_core_index_from_id(
                (msg->srce_port & CPU_MASK));

            // response code just has one value, so being lazy and not casting
            int finished_state = msg->data[START_OF_SPECIFIC_MESSAGE_DATA];

            // free message now, nothing left in it
            sark_msg_free((sdp_msg_t*) msg);
            
            process_compressor_response(comp_core_index, finished_state);
        }
        else if (msg->data[COMMAND_CODE] == STOP_COMPRESSION_ATTEMPT){
            log_error(
                "no idea why im receiving a stop message from core %d. "
                "Ignoring", (msg->srce_port & CPU_MASK));
            sark_msg_free((sdp_msg_t*) msg);
        }
        else{
            log_error(
                "no idea what to do with message with command code %d Ignoring",
                msg->data[COMMAND_CODE]);
            sark_msg_free((sdp_msg_t*) msg);
        }
    }
    else{
        log_error(
            "no idea what to do with message. on port %d Ignoring",
            msg->srce_port >> PORT_SHIFT);
        sark_msg_free((sdp_msg_t*) msg);
    }

    log_debug("finish sdp process");
}

void setup_the_uncompressed_attempt(){
    // sort out teh searcher bitfields. as now first time where can do so
    // NOTE: by doing it here, the response from the uncompressed can be
    // handled correctly.
    log_debug("setting up search bitfields");
    bool success = set_up_search_bitfields();
    if (!success){
        log_error("can not allocate memory for search fields of uncompressed.");
        vcpu_t *sark_virtual_processor_info = (vcpu_t*) SV_VCPU;
        sark_virtual_processor_info[spin1_get_core_id()].user1 = EXIT_MALLOC;
        rt_error(RTE_SWERR);
    }
    log_debug("finish setting up search bitfields");

    // set off a none bitfield compression attempt, to pipe line work
    log_info("sets off the uncompressed version of the search");
    message_sending_set_off_no_bit_field_compression(
        comp_cores_bf_tables, compressor_cores, &my_msg,
        user_register_content, n_compression_cores, comp_core_mid_point,
        &n_available_compression_cores);
}

//! \brief starts the work for the compression search
void start_compression_process(uint unused0, uint unused1){
    //api requirements
    use(unused0);
    use(unused1);

    // will use this many palces. so exrtact at top
    vcpu_t *sark_virtual_processor_info = (vcpu_t*) SV_VCPU;

    log_info("read in bitfields");
    bit_field_by_processor = bit_field_reader_read_in_and_sort_bit_fields(
            &n_bf_addresses, user_register_content);
    log_info("finished reading in bitfields");

    // set off the first compression attempt (aka no bitfields).
    setup_the_uncompressed_attempt();

    // sort the bitfields into order of best impact on worst cores.
    sorted_bit_fields = bit_field_sorter_sort(
        n_bf_addresses, user_register_content, bit_field_by_processor);

    log_info("finished sorting bitfields");

    if (sorted_bit_fields == NULL){
        log_error("failed to read in bitfields, failing");
        sark_virtual_processor_info[spin1_get_core_id()].user1 = EXIT_MALLOC;
        rt_error(RTE_SWERR);
    }

    log_info("starting the binary search");
    bool success_start_binary_search = start_binary_search();
    log_info("finish starting of the binary search");

    if (!success_start_binary_search){
        log_error("failed to compress the routing table at all. Failing");
        sark_virtual_processor_info[spin1_get_core_id()].user1 = EXIT_FAIL;
        rt_error(RTE_SWERR);
    }
}

//! \brief sets up a tracker for the user registers so that its easier to use
//!  during coding.
void initialise_user_register_tracker(){
    log_info("set up user register tracker (easier reading)");
    vcpu_t *sark_virtual_processor_info = (vcpu_t*) SV_VCPU;
    user_register_content[APPLICATION_POINTER_TABLE] =
        (address_t) sark_virtual_processor_info[spin1_get_core_id()].user0;
    user_register_content[UNCOMP_ROUTER_TABLE] =
        (address_t) sark_virtual_processor_info[spin1_get_core_id()].user1;
    user_register_content[REGION_ADDRESSES] =
        (address_t) sark_virtual_processor_info[spin1_get_core_id()].user2;
    user_register_content[USABLE_SDRAM_REGIONS] =
        (address_t) sark_virtual_processor_info[spin1_get_core_id()].user3;
    log_info("finished setting up register tracker: \n\n"
             "user0 = %d\n user1 = %d\n user2 = %d\n user3 = %d\n",
             user_register_content[APPLICATION_POINTER_TABLE],
             user_register_content[UNCOMP_ROUTER_TABLE],
             user_register_content[REGION_ADDRESSES],
             user_register_content[USABLE_SDRAM_REGIONS]);
}

//! \brief reads in router table setup params
void initialise_routing_control_flags(){
    uncompressed_table_region_data_t* uncompressed =
        (uncompressed_table_region_data_t*) user_register_content[
            UNCOMP_ROUTER_TABLE];

    app_id = uncompressed->app_id;
    log_info(
        "app id %d, uncompress total entries %d",
        app_id, uncompressed->uncompressed_table.size);
}

//! \brief get compressor cores
bool initialise_compressor_cores(){
    // locate the data point for compressor cores
    int n_region_pairs = user_register_content[REGION_ADDRESSES][N_PAIRS];
    int hop = START_OF_ADDRESSES_DATA + (
        n_region_pairs * ADDRESS_PAIR_LENGTH);

    log_debug(" n region pairs = %d, hop = %d", n_region_pairs, hop);

    // get n compression cores and update trackers
    n_compression_cores =
        user_register_content[REGION_ADDRESSES][hop + N_COMPRESSOR_CORES];

    n_available_compression_cores = n_compression_cores;
    log_debug("%d comps cores available", n_available_compression_cores);

    // malloc dtcm for this
    compressor_cores = MALLOC(n_compression_cores * sizeof(int));
    // verify malloc worked
    if (compressor_cores == NULL){
        log_error("failed to allocate memory for the compressor cores");
        return false;
    }

    for (int core=0; core < n_compression_cores; core++){
        log_debug(
            "compressor core id at index %d is %d",
            core,
            user_register_content[REGION_ADDRESSES][
                hop + N_COMPRESSOR_CORES + START_OF_COMP_CORE_IDS + core]);
    }

    // populate with compressor cores
    log_debug("start populate compression cores");
    for (int core=0; core < n_compression_cores; core++){
        compressor_cores[core] = user_register_content[REGION_ADDRESSES][
            hop + N_COMPRESSOR_CORES + START_OF_COMP_CORE_IDS + core];
    }
    log_debug("finished populate compression cores");

    // allocate memory for the trackers
    comp_core_mid_point = MALLOC(n_compression_cores * sizeof(int));
    if (comp_core_mid_point == NULL){
        log_error(
            "failed to allocate memory for tracking what the "
            "compression cores are doing");
        return false;
    }

    // set the trackers all to -1 as starting point. to ensure completeness
    for (int core = 0; core < n_compression_cores; core++){
        comp_core_mid_point[core] = DOING_NOWT;
    }

    // set up addresses tracker
    comp_cores_bf_tables =
        MALLOC(n_compression_cores * sizeof(comp_core_store_t));
    if(comp_cores_bf_tables == NULL){
        log_error(
            "failed to allocate memory for the holding of bitfield "
            "addresses per compressor core");
        return false;
    }

    // ensure all bits set properly as init
    for(int c_core = 0; c_core < n_compression_cores; c_core++){
        comp_cores_bf_tables[c_core].n_elements = 0;
        comp_cores_bf_tables[c_core].n_bit_fields = 0;
        comp_cores_bf_tables[c_core].compressed_table = NULL;
        comp_cores_bf_tables[c_core].elements = NULL;
    }

    return true;
}

//! \brief the callback for setting off the router compressor
bool initialise() {
    log_info("Setting up stuff to allow bitfield comp control class to occur.");

    // Get pointer to 1st virtual processor info struct in SRAM
    initialise_user_register_tracker();

    // get the compressor data flags (app id, compress only when needed,
    //compress as much as possible, x_entries
    initialise_routing_control_flags();

    // get the compressor cores stored in a array
    log_debug("start init of compressor cores");
    bool success_compressor_cores = initialise_compressor_cores();
    if(!success_compressor_cores){
        log_error("failed to init the compressor cores.");
        return false;
    }

    // set up the best compressed table
    last_compressed_table = MALLOC(
        routing_table_sdram_size_of_table(TARGET_LENGTH));
    if (last_compressed_table == NULL){
        log_error("failed to allocate best space");
        return false;
    }

    // build the fake heap for allocating memory
    log_info("setting up fake heap for sdram usage");
    platform_new_heap_creation(user_register_content[USABLE_SDRAM_REGIONS]);
    log_info("finished setting up fake heap for sdram usage");
    return true;
}

//! \brief the main entrance.
void c_main(void) {

    bool success_init = initialise();
    if (!success_init){
        log_error("failed to init");
        vcpu_t *sark_virtual_processor_info = (vcpu_t*) SV_VCPU;
        sark_virtual_processor_info[spin1_get_core_id()].user1 = EXIT_FAIL;
        rt_error(RTE_SWERR);
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
    //spin1_pause
    //spin1_resume
}

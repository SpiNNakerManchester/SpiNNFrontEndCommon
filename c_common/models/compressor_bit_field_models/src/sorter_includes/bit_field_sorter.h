#ifndef __BIT_FIELD_SORTER_H__

#include "sorters.h"

//! \brief do some location and addition stuff
//! \param[in] coverage:the set of bitfields and corresponding processors
//!                      for bitfields with a given redundant packet count.
//! \param[in] coverage_index: where in the coverage array we are
//! \param[in] cores_to_add_for: the cores who's bitfields we want to find
//! \param[in] cores_to_add_length: length of array of core ids
//! \param[in] diff: the amount of bitfields to add for these cores
//! \param[out] covered: the new set of bitfields
//! \return the new covered level
static inline int locate_and_add_bit_fields(
        _coverage_t** coverage, int coverage_index,
        int *cores_to_add_for, int cores_to_add_length, int diff,
        int covered, sorted_bit_fields_t* sorted_bit_fields,
        int sorted_bit_field_current_fill_loc){

    log_debug(
        "going to look for %d cores with a diff of %d",
        cores_to_add_length, diff);
    for(int index = 0; index < cores_to_add_length; index++){
        log_debug("am allowed to add from core %d", cores_to_add_for[index]);
    }

    _coverage_t* coverage_e = coverage[coverage_index];
    log_debug(
        "taking from coverage %d which has r packets of %d",
        coverage_index, coverage_e->n_redundant_packets);

    for (int p_index = 0; p_index < coverage_e->length_of_list; p_index++){
        // check for the processor id's in the cores to add from, and add the
        // bitfield with that redundant packet rate and processor to the sorted
        // bitfields
        int proc = coverage_e->processor_ids[p_index];

        // look to see if the core is one of those allowed to merge
        for (int allow_p_index = 0; allow_p_index < cores_to_add_length;
                allow_p_index++){

            int allowed_p = cores_to_add_for[allow_p_index];
            if(proc == allowed_p && covered < diff &&
                    coverage_e->bit_field_addresses[proc] != NULL){

                // add to sorted bitfield
                sorted_bit_fields->bit_fields[
                    sorted_bit_field_current_fill_loc] =
                        coverage_e->bit_field_addresses[p_index];
                sorted_bit_field_current_fill_loc += 1;

                log_debug(
                    "dumping into sorted at index %d address %x and is %x"
                    " from coverage entry %d, ",
                    sorted_bit_field_current_fill_loc - 1,
                    coverage_e->bit_field_addresses[p_index],
                    sorted_bit_fields->bit_fields[
                        sorted_bit_field_current_fill_loc - 1]);

                // delete (aka set to null, to bypass lots of data moves)
                coverage_e->bit_field_addresses[p_index] = NULL;
                coverage_e->processor_ids[p_index] = NULL;

                // update coverage so that it can reflect merger
                covered += 1;

                log_debug(
                    "removing from index's %d, %d", coverage_index, p_index);
            }
        }
    }
    return covered;
}


//! \brief orders the bitfields for the binary search based off the impact
//! made in reducing the redundant packet processing on cores.
//! \param[in] coverage: the set of bitfields and corresponding processors
//!                      for bitfields with a given redundant packet count.
//! \param[in] proc_cov_by_bit_field: the processors bitfield redundant
//! packet counts.
//! \param[in] n_pairs: the number of processors/elements to search
//! \param[in] n_unique_redundant_packet_counts: the count of how many unique
//!      redundant packet counts there are.
//! \return None
void order_bit_fields_based_on_impact(
        _coverage_t** coverage, _proc_cov_by_bitfield_t** proc_cov_by_bit_field,
        int n_pairs, int n_unique_redundant_packet_counts,
        sorted_bit_fields_t* sorted_bit_fields){

    // sort processor coverage by bitfield so that ones with longest length are
    // at the front of the list
    int sorted_bit_field_current_fill_loc = 0;

    // print all coverage for sanity purposes
    for (int coverage_index = 0;
            coverage_index < n_unique_redundant_packet_counts;
            coverage_index++){
        for(int bit_field_index = 0;
                bit_field_index < coverage[coverage_index]->length_of_list;
                bit_field_index ++){
            log_debug(
                "before sort by n bitfields bitfield address in coverage at "
                "index %d in array index %d is %x",
                coverage_index, bit_field_index,
                 coverage[coverage_index]->bit_field_addresses[
                    bit_field_index]);
        }
    }
    sorter_sort_by_n_bit_fields(proc_cov_by_bit_field, n_pairs);

    // print all coverage for sanity purposes
    for (int coverage_index = 0;
            coverage_index < n_unique_redundant_packet_counts;
            coverage_index++){
        for(int bit_field_index = 0;
                bit_field_index < coverage[coverage_index]->length_of_list;
                bit_field_index ++){
            log_debug(
                "after sort by n bitfields bitfield address in coverage at "
                "index %d in array index %d is %x",
                coverage_index, bit_field_index,
                 coverage[coverage_index]->bit_field_addresses[
                    bit_field_index]);
        }
    }

    // move bit_fields over from the worst affected cores. The list of worst
    // affected cores will grow in time as the worst cores are balanced out
    // by the redundant packets being filtered by each added bitfield.
    int cores_to_add_for[n_pairs];
    int cores_to_add_length = 0;

    // go through all cores but last 1
    for (int worst_core_id = 0; worst_core_id < n_pairs - 1;
            worst_core_id++){

        // add worst core to set to look for bitfields in
        cores_to_add_for[cores_to_add_length] =
            proc_cov_by_bit_field[worst_core_id]->processor_id;
        cores_to_add_length += 1;
        log_debug(
            "adding core %d into the search",
            proc_cov_by_bit_field[worst_core_id]->processor_id);

        // determine difference between the worst and next worst
        int diff = proc_cov_by_bit_field[worst_core_id]->length_of_list -
             proc_cov_by_bit_field[worst_core_id + 1]->length_of_list;
        log_debug("diff is %d", diff);

        // sort by bubble sort so that the most redundant packet count
        // addresses are at the front

        // print all coverage for sanity purposes
        for (int coverage_index = 0;
                coverage_index < n_unique_redundant_packet_counts;
                coverage_index++){
            for(int bit_field_index = 0;
                    bit_field_index < coverage[coverage_index]->length_of_list;
                    bit_field_index ++){
                log_debug(
                    "before sort by redudant in coverage at "
                    "index %d in array index %d is %x",
                    coverage_index, bit_field_index,
                     coverage[coverage_index]->bit_field_addresses[
                        bit_field_index]);
            }
        }

        sorter_sort_by_redundant_packet_count(
            proc_cov_by_bit_field, n_pairs, worst_core_id);

        // print all coverage for sanity purposes
        for (int coverage_index = 0;
                coverage_index < n_unique_redundant_packet_counts;
                coverage_index++){
            for(int bit_field_index = 0;
                    bit_field_index < coverage[coverage_index]->length_of_list;
                    bit_field_index ++){
                log_debug(
                    "after sort by redudant in coverage at "
                    "index %d in array index %d is %x",
                    coverage_index, bit_field_index,
                     coverage[coverage_index]->bit_field_addresses[
                        bit_field_index]);
            }
        }

        // print for sanity
        for(int r_packet_index = 0;
                r_packet_index < proc_cov_by_bit_field[
                    worst_core_id]->length_of_list;
                r_packet_index ++){
            log_debug(
                "order of redundant packet count at index %d is %d",
                proc_cov_by_bit_field[worst_core_id]->redundant_packets[
                    r_packet_index]);
        }

        for (int coverage_index = 0;
                coverage_index < n_unique_redundant_packet_counts;
                coverage_index++){
            for(int bit_field_index = 0;
                    bit_field_index < coverage[coverage_index]->length_of_list;
                    bit_field_index ++){
                log_debug(
                    "bitfield proc in coverage at index %d in array index"
                     " %d is %d", coverage_index, bit_field_index,
                     coverage[coverage_index]->processor_ids[bit_field_index]);
            }
        }

        // cycle through the list of a cores redundant packet counts and locate
        // the bitfields which match up
        int covered = 0;
        for (int redundant_packet_count_index = 0;
                redundant_packet_count_index <
                proc_cov_by_bit_field[worst_core_id]->length_of_list;
                redundant_packet_count_index ++){

            // the coverage packet count to try this time
            int x_redundant_packets = proc_cov_by_bit_field[
                worst_core_id]->redundant_packets[redundant_packet_count_index];

            // locate the bitfield with coverage that matches the x redundant
            // packets
            for (int coverage_index = 0;
                    coverage_index < n_unique_redundant_packet_counts;
                    coverage_index++){
                if (coverage[coverage_index]->n_redundant_packets ==
                        x_redundant_packets){
                    covered = locate_and_add_bit_fields(
                        coverage, coverage_index, cores_to_add_for,
                        cores_to_add_length, diff, covered, sorted_bit_fields,
                        sorted_bit_field_current_fill_loc);
                }
            }

            // print all coverage for sanity purposes
            for (int coverage_index = 0;
                    coverage_index < n_unique_redundant_packet_counts;
                    coverage_index++){
                for(int bit_field_index = 0;
                        bit_field_index < coverage[
                            coverage_index]->length_of_list;
                        bit_field_index ++){
                    log_debug(
                        "bitfield address in coverage at index %d in array "
                        "index %d is %x", coverage_index, bit_field_index,
                         coverage[coverage_index]->bit_field_addresses[
                            bit_field_index]);
                }
            }

            for (int coverage_index = 0;
                    coverage_index < n_unique_redundant_packet_counts;
                    coverage_index++){
                for(int bit_field_index = 0;
                        bit_field_index < coverage[
                            coverage_index]->length_of_list;
                        bit_field_index ++){
                    log_debug(
                        "bitfield proc in coverage after a move to sorted at "
                        "index %d in array index %d is %x", coverage_index,
                        bit_field_index,
                        coverage[coverage_index]->processor_ids[
                            bit_field_index]);
                }
            }
            log_debug("next cycle of moving to sorted");
        }
    }
}

void add_left_overs(
        sorted_bit_fields_t* sorted_bit_fields,
        int n_unique_redundant_packet_counts, _coverage_t** coverage)
    // iterate through the coverage and add any that are left over.
    for (int index = 0; index < n_unique_redundant_packet_counts;
            index ++){
        for (int bit_field_index = 0;
                bit_field_index < coverage[index]->length_of_list;
                bit_field_index++){
            if (coverage[index]->bit_field_addresses[bit_field_index] != NULL){

                sorted_bit_fields->bit_fields[
                    sorted_bit_field_current_fill_loc] =
                        coverage[index]->bit_field_addresses[bit_field_index];

                log_debug(
                    "dumping into sorted at index %d address %x and is %x",
                    sorted_bit_field_current_fill_loc,
                    coverage[index]->bit_field_addresses[bit_field_index],
                    sorted_bit_fields->bit_fields[
                        sorted_bit_field_current_fill_loc]);

                sorted_bit_fields->processor_ids[
                    sorted_bit_field_current_fill_loc] = coverage[
                        index]->processor_ids[bit_field_index];

                sorted_bit_field_current_fill_loc += 1;
            }
        }
    }
}

static inline _proc_cov_by_bitfield_t** create_coverage_by_bit_field(
        address_t* user_register_content, int n_pairs_of_addresses){

    // build processor coverage by bitfield
    _proc_cov_by_bitfield_t** proc_cov_by_bf = MALLOC(
        n_pairs_of_addresses * sizeof(_proc_cov_by_bitfield_t*));
    if (proc_cov_by_bf == NULL){
        log_error("failed to allocate memory for processor coverage by "
                  "bitfield, if it fails here. might as well give up");
        return NULL;
    }
    log_debug("finished malloc proc_cov_by_bf");

    // iterate through a processors bitfield region and get n bitfields
    int position_in_region_data = START_OF_ADDRESSES_DATA;
    for (int r_id = 0; r_id < n_pairs_of_addresses; r_id++){

        // malloc for n redundant packets
        proc_cov_by_bf[r_id] = MALLOC(sizeof(
            _proc_cov_by_bitfield_t));
        if (proc_cov_by_bf[r_id] == NULL){
            log_error("failed to allocate memory for processor coverage for "
                      "region %d. might as well give up", r_id);
            return NULL;
        }

        // track processor id
        proc_cov_by_bf[r_id]->processor_id =
            user_register_content[REGION_ADDRESSES][
                position_in_region_data + PROCESSOR_ID];

        // track lengths
        address_t bit_field_address = (address_t) user_register_content[
            REGION_ADDRESSES][position_in_region_data + BITFIELD_REGION];
        uint32_t core_n_bit_fields = bit_field_address[N_BIT_FIELDS];
        proc_cov_by_bf[r_id]->length_of_list = core_n_bit_fields;

        // malloc for n redundant packets
        proc_cov_by_bf[r_id]->redundant_packets = MALLOC(
            core_n_bit_fields * sizeof(uint));
        if (proc_cov_by_bf[r_id]->redundant_packets == NULL){
            log_error("failed to allocate memory for processor coverage for "
                      "region %d, might as well fail", r_id);
            return NULL;
        }

        for (uint32_t bit_field_id = 0; bit_field_id < core_n_bit_fields;
                bit_field_id++){
            uint32_t n_redundant_packets =
                detect_redundant_packet_count(
                    (address_t) &bit_field_address[N_BIT_FIELDS],
                    user_register_content);
            log_debug(
                "prov cov by bitfield for region %d, redundant packets "
                "at index %d, has n redundant packets of %d",
                r_id, bit_field_id, n_redundant_packets);

            proc_cov_by_bf[r_id]->redundant_packets[bit_field_id] =
                n_redundant_packets;
        }
    }
    return proc_cov_by_bf;
}

static inline int determine_unique_redundant_packets(
        int n_bf_addresses, address_t* user_register_content,
        _proc_cov_by_bitfield_t** proc_cov_by_bf, int ** redundant_packets,
        int n_pairs_of_addresses){
// set up redundant packet tracker
    int n_unique_redundant_packets = 0;
    *redundant_packets = MALLOC(n_bf_addresses * sizeof(int));
    if (*redundant_packets == NULL){
        log_error("cannot allocate memory for the redundant packet counts");
        return NULL;
    }

    // filter out duplicates in the n redundant packets
    int position_in_region_data = START_OF_ADDRESSES_DATA;
    for (int r_id = 0; r_id < n_pairs_of_addresses; r_id++){
        // cycle through the bitfield registers again to get n bitfields per
        // core
        address_t bit_field_address =
            (address_t) user_register_content[REGION_ADDRESSES][
                position_in_region_data + BITFIELD_REGION];
        position_in_region_data += ADDRESS_PAIR_LENGTH;
        int core_n_bit_fields = bit_field_address[N_BIT_FIELDS];

        // check that each bitfield redundant packets are unqiue and add to set
        for (int bit_field_id = 0; bit_field_id < core_n_bit_fields;
                bit_field_id++){
            int x_packets =
                proc_cov_by_bf[r_id]->redundant_packets[bit_field_id];

            // check if seen this before
            bool found = false;
            for (int index = 0; index < n_unique_redundant_packets; index++){
                if(*redundant_packets[index] == x_packets){
                    found = true;
                }
            }
            // if not a duplicate, add to list and update size
            if (!found){
                *redundant_packets[n_unique_redundant_packets] = x_packets;
                n_unique_redundant_packets += 1;
            }
        }
    }
    log_debug("length of n redundant packets = %d", n_unique_redundant_packets);
    return n_unique_redundant_packets;
}

static _coverage_t** create_coverage_by_redundant_packet(
        int n_unique_redundant_packets, int* redundant_packets,
        int n_pairs_of_addresses, _proc_cov_by_bitfield_t** proc_cov_by_bf,
        _bit_field_by_processor_t* bit_field_by_processor){

    // malloc space for the bitfield by coverage map
    _coverage_t** coverage = MALLOC(
        n_unique_redundant_packets * sizeof(_coverage_t*));
    if (coverage == NULL){
        log_error("failed to malloc memory for the bitfields by coverage. "
                  "might as well fail");
        return NULL;
    }

    // go through the unique x redundant packets and build the list of
    // bitfields for it
    for (int r_packet_index = 0; r_packet_index < n_unique_redundant_packets;
            r_packet_index++){
        // malloc a redundant packet entry
        log_debug(
            "try to allocate memory of size %d for coverage at index %d",
             sizeof(_coverage_t), r_packet_index);
        coverage[r_packet_index] = MALLOC(sizeof(_coverage_t));
        if (coverage[r_packet_index] == NULL){
            log_error(
                "failed to malloc memory for the bitfields by coverage "
                "for index %d. might as well fail", r_packet_index);
            return NULL;
        }

        // update the redundant packet pointer
        coverage[r_packet_index]->n_redundant_packets =
            redundant_packets[r_packet_index];

        // search to see how long the list is going to be.
        int n_bf_with_same_r_packets = 0;
        for (int r_id = 0; r_id < n_pairs_of_addresses; r_id++){
            int length = proc_cov_by_bf[r_id]->length_of_list;
            for(int red_packet_index = 0; red_packet_index < length;
                    red_packet_index ++){
                if(proc_cov_by_bf[r_id]->redundant_packets[
                        red_packet_index] == redundant_packets[r_packet_index]){
                    n_bf_with_same_r_packets += 1;
                }
            }
        }
        log_debug("size going to be %d", n_bf_with_same_r_packets);

        // update length of list
        coverage[r_packet_index]->length_of_list = n_bf_with_same_r_packets;

        // malloc list size for these addresses of bitfields with same
        // redundant packet counts.
        coverage[r_packet_index]->bit_field_addresses = MALLOC(
            n_bf_with_same_r_packets * sizeof(address_t));
        if(coverage[r_packet_index]->bit_field_addresses == NULL){
            log_error(
                "failed to allocate memory for the coverage on index %d"
                " for addresses. might as well fail.", r_packet_index);
            return NULL;
        }

        // malloc list size for the corresponding processors ids for the
        // bitfields
        log_debug(
            "trying to allocate %d bytes, for x bitfields same xr packets %d",
            n_bf_with_same_r_packets * sizeof(uint32_t),
            n_bf_with_same_r_packets);
        coverage[r_packet_index]->processor_ids = MALLOC(
            n_bf_with_same_r_packets * sizeof(uint32_t));
        if(coverage[r_packet_index]->processor_ids == NULL){
            log_error(
                "failed to allocate memory for the coverage on index %d"
                " for processors. might as well fail.", r_packet_index);
            return NULL;
        }

        // populate list of bitfields addresses which have same redundant
        //packet count.
        log_debug(
            "populating list of bitfield addresses with same packet count");
        int processor_id_index = 0;
        for (int r_id = 0; r_id < n_pairs_of_addresses; r_id++){
            for(int red_packet_index = 0;
                    red_packet_index < proc_cov_by_bf[r_id]->length_of_list;
                    red_packet_index ++){
                if(proc_cov_by_bf[r_id]->redundant_packets[red_packet_index] ==
                        redundant_packets[r_packet_index]){
                    log_debug(
                        "found! at %x",
                        bit_field_by_processor[ r_id].bit_field_addresses[
                            red_packet_index]);

                    coverage[r_packet_index]->bit_field_addresses[
                        processor_id_index] = bit_field_by_processor[
                            r_id].bit_field_addresses[red_packet_index];

                    coverage[r_packet_index]->processor_ids[processor_id_index]
                        = bit_field_by_processor[r_id].processor_id;

                    processor_id_index += 1;
                }
            }
        }
        log_debug(
            "processor id index = %d and need to fill in %d elements",
            processor_id_index, n_bf_with_same_r_packets);
        if (processor_id_index != n_bf_with_same_r_packets){
            log_error("WTF!");
            rt_error(RTE_SWERR);
        }
    }

    // free the redundant packet tracker, as now tailored ones are in the dict
    FREE(redundant_packets);

    return coverage;
}


//! \brief reads in bitfields, makes a few maps, sorts into most priority.
//! \return bool that states if it succeeded or not.
sorted_bit_fields_t* bit_field_sorter_sort(
        int n_bf_addresses, address_t* user_register_content,
        _bit_field_by_processor_t* bit_field_by_processor){

    sorted_bit_fields_t* sorted_bit_fields =
       MALLOC(sizeof(sorted_bit_fields_t));

    if (sorted_bit_fields == NULL){
        log_error("failed to allocate dtcm for sorted bitfields.");
        return NULL;
    }

    // malloc the separate bits of the sorted bitfield struct
    log_info("n bitfield addresses = %d", n_bf_addresses);
    sorted_bit_fields->bit_fields = MALLOC(n_bf_addresses * sizeof(address_t));
    if(sorted_bit_fields->bit_fields == NULL){
        log_error("cannot allocate memory for the sorted bitfield addresses");
        return NULL;
    }

    sorted_bit_fields->processor_ids =
        MALLOC(n_bf_addresses * sizeof(uint32_t));
    if (sorted_bit_fields->processor_ids == NULL){
        log_error("cannot allocate memory for the sorted bitfields with "
                  "processors ids");
        return NULL;
    }

    // populate the bitfield by coverage
    int n_pairs_of_addresses = user_register_content[REGION_ADDRESSES][N_PAIRS];
    _proc_cov_by_bitfield_t** proc_cov_by_bf = create_coverage_by_bit_field(
        user_register_content, n_pairs_of_addresses);

    // determine how many unique redundant packets there are
    int * redundant_packets;
    int n_unique_redundant_packets = determine_unique_redundant_packets(
        n_bf_addresses, user_register_content, proc_cov_by_bf,
        &redundant_packets, n_pairs_of_addresses);

    // create coverage by redundant packets
    _coverage_t** coverage = create_coverage_by_redundant_packet(
        n_unique_redundant_packets, redundant_packets, n_pairs_of_addresses,
        proc_cov_by_bf, bit_field_by_processor);

    // order the bitfields based off the impact to cores redundant packet
    // processing
    order_bit_fields_based_on_impact(
        coverage, proc_cov_by_bf, n_pairs_of_addresses,
        n_unique_redundant_packets, sorted_bit_fields);
    add_left_overs(sorted_bit_fields, n_unique_redundant_packets, coverage);


    // free the data holders we don't care about now that we've got our
    // sorted bitfields list
    for(int r_id = 0; r_id < n_pairs_of_addresses; r_id++){
        _coverage_t* cov_element = coverage[r_id];
        FREE(cov_element->bit_field_addresses);
        FREE(cov_element->processor_ids);
        FREE(cov_element);
        _proc_cov_by_bitfield_t* proc_cov_element =
            proc_cov_by_bf[r_id];
        FREE(proc_cov_element->redundant_packets);
        FREE(proc_cov_element);
    }
    FREE(coverage);
    FREE(proc_cov_by_bf);

    // print out the sorted bitfields.
    for(int bf_index = 0; bf_index < n_bf_addresses; bf_index++){
        log_debug(
            "bitfield address for sorted in index %d is %x",
            bf_index, sorted_bit_fields->bit_fields[bf_index]);
    }
    return sorted_bit_fields;
}

#define __BIT_FIELD_SORTER_H__
#endif  // __BIT_FIELD_SORTER_H__
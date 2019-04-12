#ifndef __SORTERS_H__
#define __SORTERS_H__

//! \brief struct for processor coverage by bitfield
typedef struct _proc_cov_by_bitfield_t{
    // processor id
    int processor_id;
    // length of the list
    int length_of_list;
    // list of the number of redundant packets from a bitfield
    int* redundant_packets;
} _proc_cov_by_bitfield_t;

//! \brief struct for n redundant packets and the bitfield addresses of it
typedef struct _coverage_t{
    // n redundant packets
    int n_redundant_packets;
    // length of list
    int length_of_list;
    // list of corresponding processor id to the bitfield addresses list
    int* processor_ids;
    // list of addresses of bitfields with this x redundant packets
    address_t* bit_field_addresses;
} _coverage_t;

//! \brief sorter for redundant packet counts
//! \param[in/out] proc_cov_by_bit_field: the array of struct to be sorted
//! \param[in] length_of_internal_array: length of internal array
//! \param[in] worst_core_id: the core id to sort
void sorter_sort_by_redundant_packet_count(
        _proc_cov_by_bitfield_t **proc_cov_by_bit_field,
        int length_of_internal_array, uint32_t worst_core_id) {

    // sort by bubble sort so that the most redundant packet count
    // addresses are at the front
    bool moved;
    do {
        moved = false;
        uint32_t element =
            proc_cov_by_bit_field[worst_core_id]->redundant_packets[0];
        for (int index = 1; index < length_of_internal_array; index ++) {
            uint32_t compare_element = proc_cov_by_bit_field[
                    worst_core_id]->redundant_packets[index];

            if (element < compare_element) {
                uint32_t temp_value = 0;

                // move to temp
                temp_value = element;

                // move compare over to element
                proc_cov_by_bit_field[worst_core_id]->redundant_packets[
                    index - 1] = compare_element;

                // move element over to compare location
                proc_cov_by_bit_field[worst_core_id]->redundant_packets[
                    index] = temp_value;

                // update flag
                moved = true;
            } else {  // jump to next element
                element = proc_cov_by_bit_field[
                    worst_core_id]->redundant_packets[index];
            }
        }
    } while (moved);
}

//! \brief sort processor coverage by bitfield so that ones with longest length
//!  are at the front of the list
//! \param[in/out] proc_cov_by_bit_field: the array of structs to sort
//! \param[in] length_of_array: length of the array of structs
void sorter_sort_by_n_bit_fields(
        _proc_cov_by_bitfield_t **proc_cov_by_bit_field,
        uint32_t length_of_array) {
    bool moved;
    do {
        moved = false;
        _proc_cov_by_bitfield_t* element = proc_cov_by_bit_field[0];
        for (uint index = 1; index < length_of_array; index ++) {
            _proc_cov_by_bitfield_t* compare_element =
                proc_cov_by_bit_field[index];
            if (element->length_of_list < compare_element->length_of_list) {

                // create temp holder for moving objects
                _proc_cov_by_bitfield_t* temp_pointer;

                // move to temp
                temp_pointer = element;

                // move compare over to element
                proc_cov_by_bit_field[index - 1] = compare_element;

                // move element over to compare location
                proc_cov_by_bit_field[index] = temp_pointer;

                // update flag
                moved = true;
            } else {  // move to next element
                element = proc_cov_by_bit_field[index];
            }
        }
    } while (moved);
}


// \brief sort bitfields by coverage by n_redundant_packets so biggest at front
//! \param[in/out] coverage: the array of structs to sort
//! \param[in] length_of_array: length of array of structs
void sorter_sort_bitfields_so_most_impact_at_front(
        _coverage_t **coverage, int length_of_array) {
    // print for sanity
    for (int index = 0; index < length_of_array; index ++){
        _coverage_t* element = coverage[index];
        for (int in_index = 1; in_index < element->length_of_list;
                in_index ++){
            log_debug(
                "before address of element %d, in list %d is %x",
                index, in_index, element->bit_field_addresses[in_index]);
        }
    }

    bool moved;
    do {
        moved = false;
        _coverage_t *element = coverage[0];
        for (int index = 1; index < length_of_array; index++) {

            _coverage_t *compare_element = coverage[index];

            if (element->n_redundant_packets <
                    compare_element->n_redundant_packets) {

                _coverage_t* temp_pointer;
                // move to temp
                temp_pointer = element;
                // move compare over to element
                coverage[index - 1] = compare_element;
                // move element over to compare location
                coverage[index] = temp_pointer;
                // update flag
                moved = true;
            } else {  // move to next element
                element = coverage[index];
            }
        }
    } while (moved);

    // print for sanity
    for (int index = 0; index < length_of_array; index ++){
        _coverage_t* element = coverage[index];
        for (int in_index = 1; in_index < element->length_of_list;
                in_index ++){
            log_debug(
                "after address of element %d, in list %d is %x",
                index, in_index, element->bit_field_addresses[in_index]);
        }
    }
}


//! sort out bitfields into processors and the keys of the bitfields to remove
//! \param[out] sorted_bf_by_processor: the sorted stuff
//! \param[in] region_addresses: addresses of the regions
//! \param[in] best_search_point: best search point
//! \param[in] sorted_bit_fields: the bitfields in sort order
proc_bit_field_keys_t* sorter_sort_sorted_to_cores(
        region_addresses_t *region_addresses, int best_search_point,
        sorted_bit_fields_t* sorted_bit_fields) {
    proc_bit_field_keys_t *sorted_bf_by_processor =
            MALLOC(region_addresses->n_pairs * sizeof(proc_bit_field_keys_t));
    if (sorted_bf_by_processor == NULL) {
        log_error(
            "failed to allocate memory for the sorting of bitfield to keys");
        return NULL;
    }

    //locate how many bitfields in the search space accepted that are of a
    // given core.
    for (int r_id = 0; r_id < region_addresses->n_pairs; r_id++){

        // locate processor id for this region
        int region_proc_id = region_addresses->pairs[r_id].processor;
        log_info("region proc id is %d", region_proc_id);
        sorted_bf_by_processor[r_id].processor_id = region_proc_id;

        // count entries
        int n_entries = 0;
        for(int bf_index = 0; bf_index < best_search_point; bf_index++) {
            if (sorted_bit_fields->processor_ids[bf_index] == region_proc_id) {
                n_entries ++;
            }
        }

        // update length
        sorted_bf_by_processor[r_id].length_of_list = n_entries;

        // alloc for keys
        sorted_bf_by_processor[r_id].master_pop_keys =
            MALLOC(n_entries * sizeof(int));
        if (sorted_bf_by_processor[r_id].master_pop_keys == NULL) {
            log_error(
                "failed to allocate memory for the master pop keys for "
                "processor %d in the sorting of successful bitfields to "
                "remove.", region_proc_id);
            for (int free_id =0; free_id < r_id; free_id++) {
                FREE(sorted_bf_by_processor->master_pop_keys);
            }
            FREE(sorted_bf_by_processor);
            return NULL;
        }

        // put keys in the array
        int array_index = 0;
        for(int bf_index = 0; bf_index < best_search_point; bf_index++) {
            if (sorted_bit_fields->processor_ids[bf_index] == region_proc_id) {
                filter_info_t *bf_pointer =
                    (filter_info_t*) sorted_bit_fields->bit_fields[bf_index];
                sorted_bf_by_processor->master_pop_keys[array_index] =
                    bf_pointer->key;
                array_index ++;
            }
        }
    }

    return sorted_bf_by_processor;
}

#endif  // __SORTERS_H__
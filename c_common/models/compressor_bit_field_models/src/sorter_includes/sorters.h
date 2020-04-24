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

#ifndef __SORTERS_H__
#define __SORTERS_H__

#include <malloc_extras.h>

//! \brief sorter for redundant packet counts
//! \param[in/out] proc_cov_by_bit_field: the array of struct to be sorted
//! \param[in] length_of_internal_array: length of internal array
//! \param[in] worst_core_id: the core id to sort
void sorter_sort_by_redundant_packet_count(
        _proc_cov_by_bitfield_t **proc_cov_by_bit_field,
        int length_of_internal_array, uint32_t worst_core_id) {

    // sort by bubble sort so that the most redundant packet count
    // addresses are at the front
    if (length_of_internal_array == 0) {
        return;
    }

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
}


//! sort out bitfields into processors and the keys of the bitfields to remove
//! \param[out] sorted_bf_by_processor: the sorted stuff
//! \param[in] region_addresses: addresses of the regions
//! \param[in] best_search_point: best search point
//! \param[in] sorted_bit_fields: the bitfields in sort order
//! \return list of master pop keys for a given processor
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

    // malloc the lists
    for (int r_id = 0; r_id < region_addresses->n_pairs; r_id++){
        sorted_bf_by_processor[r_id].key_list =
            MALLOC(sizeof(master_pop_key_list_t));
        if (sorted_bf_by_processor[r_id].key_list == NULL){
            log_error("failed to alloc memory for master pop key list.");
            return NULL;
        }
    }

    //locate how many bitfields in the search space accepted that are of a
    // given core.
    for (int r_id = 0; r_id < region_addresses->n_pairs; r_id++){

        // locate processor id for this region
        int region_proc_id = region_addresses->pairs[r_id].processor;
        sorted_bf_by_processor[r_id].processor_id = region_proc_id;

        // count entries
        int n_entries = 0;
        for (int bf_index = 0; bf_index < best_search_point; bf_index++) {
            if (sorted_bit_fields->processor_ids[bf_index] == region_proc_id) {
                n_entries ++;
            }
        }

        // update length
        sorted_bf_by_processor[r_id].key_list->length_of_list = n_entries;

        // alloc for keys
        if (n_entries != 0){
            sorted_bf_by_processor[r_id].key_list->master_pop_keys =
                MALLOC(n_entries * sizeof(int));
            if (sorted_bf_by_processor[r_id].key_list->master_pop_keys ==
                    NULL) {
                log_error(
                    "failed to allocate memory for the master pop keys for "
                    "processor %d in the sorting of successful bitfields to "
                    "remove.", region_proc_id);
                for (int free_id =0; free_id < r_id; free_id++) {
                    FREE(sorted_bf_by_processor[free_id].key_list->master_pop_keys);
                }
                for (int free_id = 0; free_id < region_addresses->n_pairs;
                        free_id++){
                    FREE(sorted_bf_by_processor[free_id].key_list);
                }
                FREE(sorted_bf_by_processor);
                return NULL;
            }

            // put keys in the array
            int a_index = 0;
            for (int bf_index = 0; bf_index < best_search_point; bf_index++) {
                if (sorted_bit_fields->processor_ids[bf_index] ==
                        region_proc_id) {
                    filter_info_t* bf_pointer =
                        sorted_bit_fields->bit_fields[bf_index];
                    sorted_bf_by_processor[r_id].key_list->master_pop_keys[
                        a_index] = bf_pointer->key;
                    a_index ++;
                }
            }
         }
    }

    return sorted_bf_by_processor;
}

#endif  // __SORTERS_H__

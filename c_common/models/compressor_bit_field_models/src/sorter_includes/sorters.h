#ifndef __SORTERS_H__

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
        _proc_cov_by_bitfield_t** proc_cov_by_bit_field, 
        int length_of_internal_array, uint32_t worst_core_id){

    // sort by bubble sort so that the most redundant packet count
    // addresses are at the front
    bool moved = true;
    while (moved){
        moved = false;
        uint32_t element =
            proc_cov_by_bit_field[worst_core_id]->redundant_packets[0];
        for (int index = 1; index < length_of_internal_array; index ++){
            uint32_t compare_element = proc_cov_by_bit_field[
                    worst_core_id]->redundant_packets[index];
                    
            if (element < compare_element){
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
            }
            else{  // jump to next element
                element = proc_cov_by_bit_field[
                    worst_core_id]->redundant_packets[index];
            }
        }
    }
}

//! \brief sort processor coverage by bitfield so that ones with longest length
//!  are at the front of the list
//! \param[in/out] proc_cov_by_bit_field: the array of structs to sort
//! \param[in] length_of_array: length of the array of structs
void sorter_sort_by_n_bit_fields(
        _proc_cov_by_bitfield_t** proc_cov_by_bit_field,
        uint32_t length_of_array){
    bool moved = true;
    while (moved){
        moved = false;
        _proc_cov_by_bitfield_t* element = proc_cov_by_bit_field[0];
        for (uint index = 1; index < length_of_array; index ++){
            _proc_cov_by_bitfield_t* compare_element =
                proc_cov_by_bit_field[index];
            if (element->length_of_list < compare_element->length_of_list){

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
            }
            else{  // move to next element
                element = proc_cov_by_bit_field[index];
            }
        }
    }
}


// \brief sort bitfields by coverage by n_redundant_packets so biggest at front
//! \param[in/out] coverage: the array of structs to sort
//! \param[in] length_of_array: length of array of structs
void sorter_sort_bitfields_so_most_impact_at_front(
        _coverage_t** coverage, int length_of_array){
    // print for sanity
    for (int index = 0; index < length_of_array; index ++){
        coverage_t* element = coverage[index];
        for (int in_index = 1; in_index < element->length_of_list;
                in_index ++){
            log_debug(
                "before address of element %d, in list %d is %x",
                index, in_index, element->bit_field_addresses[in_index]);
        }
    }

    bool moved = true;
    while (moved){
        moved = false;
        coverage_t* element = coverage[0];
        for (int index = 1; index < length_of_array; index ++){

            coverage_t* compare_element = coverage[index];

            if (element->n_redundant_packets <
                    compare_element->n_redundant_packets){

                coverage_t* temp_pointer;
                // move to temp
                temp_pointer = element;
                // move compare over to element
                coverage[index - 1] = compare_element;
                // move element over to compare location
                coverage[index] = temp_pointer;
                // update flag
                moved = true;
            }
            else{  // move to next element
                element = coverage[index];
            }
        }
    }

    // print for sanity
    for (int index = 0; index < length_of_array; index ++){
        coverage_t* element = coverage[index];
        for (int in_index = 1; in_index < element->length_of_list;
                in_index ++){
            log_debug(
                "after address of element %d, in list %d is %x",
                index, in_index, element->bit_field_addresses[in_index]);
        }
    }
}

#define __SORTERS_H__
#endif  // __SORTERS_H__
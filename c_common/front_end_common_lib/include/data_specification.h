/*! \file
 *
 *  \brief Data Specification Header File
 *
 *  DESCRIPTION
 *    Specifies functions that can be used to read an executed Data
 *    Specification, including checking the header and extracting the
 *    regions.
 *
 */

#ifndef _DATA_SPECIFICATION_H_
#define _DATA_SPECIFICATION_H_

#include "common-typedefs.h"

//! \brief Gets the location of the data for this core using the user0 entry
//!        of the SARK VCPU structure
//! \return The address of the generated data
address_t data_specification_get_data_address();

//! \brief Reads the header from the address given and returns the version
//!        and flags
//! \param[in] data_address The address of the start of the data generated
//! \param[out] version A pointer to an int to be filled with the version
//! \return true if the header was found, or false if was not
bool data_specification_read_header(address_t data_address, uint32_t* version);

//! \brief Gets the address of a region
//! \param[in] region the id of the region, starting at 0
//! \param[in] data_address The address of the start of the data generated
//! \return The address of the specified region
address_t data_specification_get_region(
        uint32_t region, address_t data_address);

void data_specification_copy_word_vector(
        uint32_t* target, uint32_t size, uint32_t* data_source);

void data_specification_copy_half_word_vector(
        uint16_t* target, uint32_t size, uint32_t* data_source);

void data_specification_copy_byte_vector(
        uint8_t* target, uint32_t size, uint32_t* data_source);

bool data_specification_is_vector_single_valued(
        uint32_t size, uint32_t* vector);

#endif

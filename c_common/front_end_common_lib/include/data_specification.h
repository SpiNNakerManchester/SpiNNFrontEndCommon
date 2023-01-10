/*
 * Copyright (c) 2017-2019 The University of Manchester
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

/*! \file
 *
 * \brief Data Specification region access API.
 *
 * Specifies functions that can be used to read an executed Data
 * Specification, including checking the header and extracting the regions.
 */

#ifndef _DATA_SPECIFICATION_H_
#define _DATA_SPECIFICATION_H_

#include <stdbool.h>
#include "common-typedefs.h"

typedef struct region_desc_t {
    void *pointer;
    //! Simple checksum which is rounded 32-bit unsigned sum of words
    uint32_t checksum;
    //! The number of valid words in the region
    uint32_t n_words;
} region_desc_t;

//! \brief The central structure that the DSE writes.
//!
//! A pointer to this will be placed in user0 before the application launches.
//! The number of entries in the table is application-specific, and is not
//! checked.
typedef struct data_specification_metadata_t {
    //! A magic number, used to verify that the pointer is sane.
    uint32_t magic_number;
    //! The version of the DSE data layout specification being followed.
    uint32_t version;
    //! The regions; as many as required.
    region_desc_t regions[];
} data_specification_metadata_t;

//! \brief Gets the location of the data for this core using the user0 entry
//!        of the SARK VCPU structure
//!
//! Locates the start address for a core in SDRAM. This value is loaded into
//! the user0 register of the core during the tool chain loading.
//!
//! Does not validate the value! That's data_specification_read_header()
//! \return The address of the generated data
data_specification_metadata_t *data_specification_get_data_address(void);

//! \brief Reads the header from the address given and checks if the parameters
//! are of the correct values
//!
//! Reads the header written by a DSE and checks that the magic number which is
//! written by every DSE is consistent. Inconsistent DSE magic numbers would
//! reflect a model being used with an different DSE interface than the DSE
//! used by the host machine.
//!
//! \param[in] ds_regions: The address of the start of the data generated
//! \return true if a valid header was found, or false if was not
bool data_specification_read_header(data_specification_metadata_t *ds_regions);

//! \brief Gets the address of a region
//! \param[in] region: the ID of the region, starting at 0
//! \param[in] ds_regions: The address of the start of the data generated; it
//!                        is the caller's job to validate this first.
//! \return The address of the specified region. This function does not know
//! the actual type of the region.
static inline void *data_specification_get_region(
        uint32_t region, data_specification_metadata_t *ds_regions) {
    return ds_regions->regions[region].pointer;
}

//! \brief Check the binary checksum still gives the right value
bool data_specification_validate_binary(void);

#endif

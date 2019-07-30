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

typedef struct data_specification_metadata_t {
    uint32_t magic_number;
    uint32_t version;
    void *regions[];
} data_specification_metadata_t;

//! \brief Gets the location of the data for this core using the user0 entry
//!        of the SARK VCPU structure
//! \return The address of the generated data
data_specification_metadata_t *data_specification_get_data_address();

//! \brief Reads the header from the address given and checks if the parameters
//! are of the correct values
//! \param[in] ds_regions The address of the start of the data generated
//! \return true if the header was found, or false if was not
bool data_specification_read_header(data_specification_metadata_t *ds_regions);

//! \brief Gets the address of a region
//! \param[in] region the ID of the region, starting at 0
//! \param[in] ds_regions The address of the start of the data generated
//! \return The address of the specified region
static inline void *data_specification_get_region(
        uint32_t region, data_specification_metadata_t *ds_regions) {
    return ds_regions->regions[region];
}

#endif

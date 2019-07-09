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
data_specification_metadata_t *data_specification_get_data_address(void);

//! \brief Reads the header from the address given and checks if the parameters
//! are of the correct values
//! \param[in] ds_regions The address of the start of the data generated
//! \return true if the header was found, or false if was not
bool data_specification_read_header(data_specification_metadata_t *ds_regions);

//! \brief Returns the absolute SDRAM memory address for a given region value.
//!
//! \param[in] region The region ID (between 0 and 15) to which the absolute
//!            memory address in SDRAM is to be located
//! \param[in] ds_regions The app_pointer table as created by the host DSE.
//! \return a void* which represents the absolute SDRAM address for the
//!         start of the requested region.
static inline void *data_specification_get_region(
        uint32_t region, data_specification_metadata_t *ds_regions) {
    return ds_regions->regions[region];
}

#endif

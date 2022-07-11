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
 * \brief implementation of data_specification.h
 */

#include "data_specification.h"

#include <sark.h>
#include <debug.h>

//! Misc constants
enum {
    //! A magic number that identifies the start of an executed data
    //! specification
    DATA_SPECIFICATION_MAGIC_NUMBER = 0xAD130AD6,
    //! The version of the spec we support; only one was ever supported
    DATA_SPECIFICATION_VERSION = 0x00010000,
    //! The mask to apply to the version number to get the minor version
    VERSION_MASK = 0xFFFF,
    //! The amount of shift to apply to the version number to get the major
    //! version
    VERSION_SHIFT = 16
};

#define N_REGIONS 32

//! \brief Gets the location of the data for this core using the user0 entry
//!        of the SARK VCPU structure
//!
//! Locates the start address for a core in SDRAM. This value is loaded into
//! the user0 register of the core during the tool chain loading.
//!
//! Does not validate the value! That's data_specification_read_header()
//! \return The address of the generated data
data_specification_metadata_t *data_specification_get_data_address(void) {
    // Get pointer to 1st virtual processor info struct in SRAM
    vcpu_t *virtual_processor_table = (vcpu_t*) SV_VCPU;

    // Get the address this core's DTCM data starts at from the user data
    // member of the structure associated with this virtual processor
    uint user0 = virtual_processor_table[spin1_get_core_id()].user0;

    log_debug("SDRAM data begins at address: %08x", user0);

    // Cast to the correct type
    return (data_specification_metadata_t *) user0;
}

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
bool data_specification_read_header(
        data_specification_metadata_t *ds_regions) {
    // Check for the magic number
    if (ds_regions->magic_number != DATA_SPECIFICATION_MAGIC_NUMBER) {
        log_error("Magic number is incorrect: %08x", ds_regions->magic_number);
        return false;
    }

    if (ds_regions->version != DATA_SPECIFICATION_VERSION) {
        log_error("Version number is incorrect: %08x", ds_regions->version);
        return false;
    }

    // Log what we have found
    log_info("magic = %08x, version = %d.%d", ds_regions->magic_number,
            ds_regions->version >> VERSION_SHIFT,
            ds_regions->version & VERSION_MASK);

    // Check the data in the regions checksums
    for (uint32_t region = 0; region < N_REGIONS; region++) {
        uint32_t *data = ds_regions->regions[region].pointer;
        uint32_t checksum = ds_regions->regions[region].checksum;
        uint32_t n_words = ds_regions->regions[region].n_words;

        // If the region is not in use, skip
        if (data == NULL) {
            continue;
        }

        // Do simple unsigned 32-bit checksum
        uint32_t sum = 0;
        for (uint32_t i = 0; i < n_words; i++) {
            sum += data[i];
        }
        if (sum != checksum) {
            log_error("Region %u with %u words starting at 0x%08x: "
                    "checksum %u does not match computed sum %u",
                    region, n_words, data, checksum, sum);
            return false;
        }
    }

    return true;
}

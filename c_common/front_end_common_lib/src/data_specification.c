/*
 * Copyright (c) 2014 The University of Manchester
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
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

// ITCM is 32K
#define ITCM_LENGTH 0x7FFF

// ITCM starts at 0
#define ITCM_START 0

static uint32_t binary_checksum;

uint32_t get_binary_checksum(void) {
    uint32_t *ro_data = (uint32_t *) ITCM_START;
    uint32_t sum = 0;
    for (uint32_t i = ITCM_LENGTH; i > 0; i--) {
        sum += ro_data[i - 1];
    }
    return sum;
}

bool data_specification_validate_binary(void) {
    // Skip if we don't have a checksum stored (unlikely to be 0 though possible)
    if (binary_checksum == 0) {
        return true;
    }
    uint32_t sum = get_binary_checksum();
    return sum == binary_checksum;
}


/**
 * \brief Verify the checksum of a region; on failure, RTE
 * \param[in] ds_regions The array of region metadata
 * \param[in] region The region to verify
 */
static inline void verify_checksum(data_specification_metadata_t *ds_regions,
        uint32_t region) {
    uint32_t *data = ds_regions->regions[region].pointer;
    uint32_t checksum = ds_regions->regions[region].checksum;
    uint32_t n_words = ds_regions->regions[region].n_words;

    // If the region is not in use or marked as having no size, skip
    if (data == NULL || n_words == 0) {
        return;
    }

    // Do simple unsigned 32-bit checksum
    uint32_t sum = 0;
    for (uint32_t i = n_words; i > 0; i--) {
        sum += data[i - 1];
    }
    if (sum != checksum) {
        log_error("[ERROR] Region %u with %u words starting at 0x%08x: "
                "checksum %u does not match computed sum %u",
                region, n_words, data, checksum, sum);
        rt_error(RTE_SWERR);
    }

    // Avoid checking this again (unless it is changed)
    ds_regions->regions[region].checksum = 0;
    ds_regions->regions[region].n_words = 0;
}

data_specification_metadata_t *data_specification_get_data_address(void) {
    // Get pointer to 1st virtual processor info struct in SRAM
    vcpu_t *virtual_processor_table = (vcpu_t*) SV_VCPU;

    // Get the address this core's DTCM data starts at from the user data
    // member of the structure associated with this virtual processor
    uint user0 = virtual_processor_table[spin1_get_core_id()].user0;

    log_debug("SDRAM data begins at address: %08x", user0);
    binary_checksum = get_binary_checksum();

    // Cast to the correct type
    data_specification_metadata_t *ds_regions = (data_specification_metadata_t *) user0;
    for (uint32_t region = N_REGIONS; region > 0; region--) {
        verify_checksum(ds_regions, region - 1);
    }

    return ds_regions;
}

bool data_specification_read_header(
        data_specification_metadata_t *ds_regions) {
    // Check for the magic number
    if (ds_regions->magic_number != DATA_SPECIFICATION_MAGIC_NUMBER) {
        log_error("[ERROR] Magic number is incorrect: %08x", ds_regions->magic_number);
        return false;
    }

    if (ds_regions->version != DATA_SPECIFICATION_VERSION) {
        log_error("[ERROR] Version number is incorrect: %08x", ds_regions->version);
        return false;
    }

    // Log what we have found
    log_debug("magic = %08x, version = %d.%d", ds_regions->magic_number,
            ds_regions->version >> VERSION_SHIFT,
            ds_regions->version & VERSION_MASK);

    return true;
}

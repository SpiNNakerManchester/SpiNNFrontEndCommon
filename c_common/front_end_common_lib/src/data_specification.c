#include "data_specification.h"

#include <sark.h>
#include <debug.h>

// A magic number that identifies the start of an executed data specification
#define DATA_SPECIFICATION_MAGIC_NUMBER 0xAD130AD6

#define DATA_SPECIFICATION_VERSION 0x00010000

// The mask to apply to the version number to get the minor version
#define VERSION_MASK 0xFFFF

typedef enum region_elements{
    dse_magic_number, dse_version,
} region_elements;

// The index of the start of the region table within the data
#define REGION_START_INDEX 2

// The amount of shift to apply to the version number to get the major version
#define VERSION_SHIFT 16

//! \brief Locates the start address for a core in SDRAM. This value is
//!        loaded into the user0 register of the core during the tool chain
//!        loading.
//! \return the SDRAM start address for this core.
address_t data_specification_get_data_address() {

    // Get pointer to 1st virtual processor info struct in SRAM
    vcpu_t *sark_virtual_processor_info = (vcpu_t*) SV_VCPU;

    // Get the address this core's DTCM data starts at from the user data member
    // of the structure associated with this virtual processor
    address_t address =
        (address_t) sark_virtual_processor_info[spin1_get_core_id()].user0;

    log_info("SDRAM data begins at address: %08x", address);

    return address;
}

//! \brief Reads the header written by a DSE and checks that the magic number
//!        which is written by every DSE is consistent. Inconsistent DSE magic
//!        numbers would reflect a model being used with an different DSE
//!        interface than the DSE used by the host machine.
//! \param[in] address the absolute memory address in SDRAM to read the
//!            header from.
//! \return boolean where True is when the header is correct and False if there
//!         is a conflict with the DSE magic number
bool data_specification_read_header(uint32_t* address) {

    // Check for the magic number
    if (address[dse_magic_number] != DATA_SPECIFICATION_MAGIC_NUMBER) {
        log_error("Magic number is incorrect: %08x", address[dse_magic_number]);
        return (false);
    }

    if (address[dse_version] != DATA_SPECIFICATION_VERSION) {
        log_error("Version number is incorrect: %08x", address[dse_version]);
        return (false);
    }

    // Log what we have found
    log_info("magic = %08x, version = %d.%d", address[dse_magic_number],
             address[dse_version] >> VERSION_SHIFT,
             address[dse_version] & VERSION_MASK);
    return (true);
}

//! \brief Returns the absolute SDRAM memory address for a given region value.
//!
//! \param[in] region The region id (between 0 and 15) to which the absolute
//!            memory address in SDRAM is to be located
//! \param[in] data_address The absolute SDRAM address for the start of the
//!            app_pointer table as created by the host DSE.
//! \return a address_t which represents the absolute SDRAM address for the
//!         start of the requested region.
address_t data_specification_get_region(
        uint32_t region, address_t data_address) {
    return (address_t) (data_address[REGION_START_INDEX + region]);
}

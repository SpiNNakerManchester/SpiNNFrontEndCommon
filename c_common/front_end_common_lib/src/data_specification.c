#include "data_specification.h"

#include <sark.h>
#include <debug.h>

// A magic number that identifies the start of an executed data specification
#define DATA_SPECIFICATION_MAGIC_NUMBER  0xAD130AD6
// The version of the spec we support; only one was ever supported
#define DATA_SPECIFICATION_VERSION       0x00010000

// The mask to apply to the version number to get the minor version
#define VERSION_MASK    0xFFFF

// The amount of shift to apply to the version number to get the major version
#define VERSION_SHIFT   16

//! \brief Locates the start address for a core in SDRAM. This value is
//!        loaded into the user0 register of the core during the tool chain
//!        loading.
//! \return the SDRAM start address for this core.
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

//! \brief Reads the header written by a DSE and checks that the magic number
//!        which is written by every DSE is consistent. Inconsistent DSE magic
//!        numbers would reflect a model being used with an different DSE
//!        interface than the DSE used by the host machine.
//! \param[in] ds_regions the absolute memory address in SDRAM to read the
//!            header from.
//! \return boolean where True is when the header is correct and False if there
//!         is a conflict with the DSE magic number
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
    return true;
}

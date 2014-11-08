#include "data_specification.h"

#include <sark.h>
#include <debug.h>

// A magic number that identifies the start of an executed data specification
#define DATA_SPECIFICATION_MAGIC_NUMBER 0xAD130AD6

// The index of the magic number within the executed data specification
#define MAGIC_NUMBER_INDEX 0

// The index of the version of the data specification within the data
#define VERSION_INDEX 1

// The index of the start of the region table within the data
#define REGION_START_INDEX 2

// The amount of shift to apply to the version number to get the major version
#define VERSION_SHIFT 16

// The mask to apply to the version number to get the minor version
#define VERSION_MASK 0xFFFF

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

bool data_specification_read_header(uint32_t* address, uint32_t* version) {

    // Check for the magic number
    if (address[MAGIC_NUMBER_INDEX] != DATA_SPECIFICATION_MAGIC_NUMBER) {
        log_error("Magic number is incorrect: %08x",
                address[MAGIC_NUMBER_INDEX]);
        return (false);
    }

    // Get the version
    *version = address[VERSION_INDEX];

    // Log what we have found
    log_info("magic = %08x, version = %d.%d", address[MAGIC_NUMBER_INDEX],
            address[VERSION_INDEX] >> VERSION_SHIFT,
            address[VERSION_INDEX] & VERSION_MASK);
    return (true);
}

address_t data_specification_get_region(
        uint32_t region, address_t data_address) {

    // As the address is a uint32_t array, we need to divide the byte address
    // in the region table by 4 (hence down-shift by 2) to get the position in
    // the "address array"
    return (&data_address[data_address[REGION_START_INDEX + region] >> 2]);
}

void data_specification_copy_word_vector(
        uint32_t* target, uint32_t size, uint32_t* data_source) {
    log_debug("v32[%u] = {%08x, ...}", 0, data_source[0]);

    for (uint32_t i = 0; i < size; i++) {
        target[i] = data_source[i];
    }
}

void data_specification_copy_half_word_vector(
        uint16_t* target, uint32_t size, uint32_t* data_source) {

    log_info("v16[%u] = {%04x, ...}", size, data_source[0] & 0xFFFF);

    for (uint32_t i = 0; i < (size >> 1); i++) {
        ((uint32_t*) target)[i] = data_source[i];
    }
}

void data_specification_copy_byte_vector(
        uint8_t* target, uint32_t size, uint32_t* data_source) {

    log_info("v8 [%u] = {%02x, ...}", size, data_source[0] & 0xFF);

    for (uint32_t i = 0; i < size; i++) {
        target[i] = data_source[i] & 0xFF;
    }
}

bool data_specification_is_vector_single_valued(
        uint32_t size, uint32_t* vector) {

    assert(size > 0);

    uint32_t first_value = vector[0];

    for (uint32_t i = 1; i < size; i++) {
        if (first_value != vector[i]) {
            return false;
        }
    }

    return true;
}

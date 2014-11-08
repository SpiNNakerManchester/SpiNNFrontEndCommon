#include "simulation.h"

#include <debug.h>
#include <spin1_api.h>

bool simulation_read_timing_details(
        address_t address, uint32_t expected_application_magic_number,
        uint32_t* timer_period, uint32_t* n_simulation_ticks) {

    if (address[0] != expected_application_magic_number) {
        log_info("Unexpected magic number 0x%.8x instead of 0x%.8x", address[0],
                expected_application_magic_number);
        return false;
    }

    *timer_period = address[1];
    *n_simulation_ticks = address[2];

    return true;
}

void simulation_run() {
    spin1_start(SYNC_WAIT);
}

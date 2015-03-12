#include "simulation.h"

#include <debug.h>
#include <spin1_api.h>

// the position and human readable terms for each element from the region
// containing the timing details.
typedef enum region_elements{
	application_magic_number, simulation_timer_period, n_simulation_tics,
}region_elements;

//! \method that checks that the data in this region has the correct identifier
//! for the model calling this method and also interprets the timer period and
//! runtime for the model.
//! \param[in] address The memory address to start reading the parameters from
//! \param[in] expected_app_magic_number The application's magic number thats
//! requesting timing details from this memory address.
//! \param[in] timer_period A pointer for storing the timer period once read
//! from the memory region
//! \param[in] n_simulation_ticks A pointer for storing the number of timer
//! tics this executable should run for, which is read from this region
//! \return True if the method was able to read the parameters and the
//! application magic number corresponded to the magic number in memory.
//! Otherwise the method will return False.
bool simulation_read_timing_details(
        address_t address, uint32_t expected_app_magic_number,
        uint32_t* timer_period, uint32_t* n_simulation_ticks) {

    if (address[application_magic_number] != expected_app_magic_number) {
        log_info("Unexpected magic number 0x%.8x instead of 0x%.8x",
        		 address[application_magic_number],
				 expected_app_magic_number);
        return false;
    }

    *timer_period = address[simulation_timer_period];
    *n_simulation_ticks = address[n_simulation_tics];

    return true;
}

//! \general method to encapsulate the setting off of any executable.
//! Just calls the spin1api start command.
//! \return does not return anything
void simulation_run() {
    spin1_start(SYNC_WAIT);
}

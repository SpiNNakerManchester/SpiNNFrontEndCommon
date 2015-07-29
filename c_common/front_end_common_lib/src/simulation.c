/*!
 * \file
 * \brief implementation of simulation.h
 */

#include "simulation.h"

#include <debug.h>
#include <spin1_api.h>

// the position and human readable terms for each element from the region
// containing the timing details.
typedef enum region_elements{
	APPLICATION_MAGIC_NUMBER, SIMULATION_TIMER_PERIOD, INFINITE_RUN, 
	N_SIMULATION_TICS
}region_elements;

//! \method that checks that the data in this region has the correct identifier
//! for the model calling this method and also interprets the timer period and
//! runtime for the model.
//! \param[in] address The memory address to start reading the parameters from
//! \param[in] expected_app_magic_number The application's magic number thats
//! requesting timing details from this memory address.
//! \param[out] timer_period A pointer for storing the timer period once read
//! from the memory region
//! \param[out] n_simulation_ticks A pointer for storing the number of timer
//! tics this executable should run for, which is read from this region
//! \param INFINITE_RUN[out] a pointer to an int which represents if the model 
//!                          should run for infinite time
//! \return True if the method was able to read the parameters and the
//! application magic number corresponded to the magic number in memory.
//! Otherwise the method will return False.
bool simulation_read_timing_details(
        address_t address, uint32_t expected_app_magic_number,
        uint32_t* timer_period, uint32_t* n_simulation_ticks,
        uint32_t* infinite_run) {

    if (address[APPLICATION_MAGIC_NUMBER] != expected_app_magic_number) {
        log_error("Unexpected magic number 0x%.8x instead of 0x%.8x",
        		 address[APPLICATION_MAGIC_NUMBER],
				 expected_app_magic_number);
        return false;
    }

    *timer_period = address[SIMULATION_TIMER_PERIOD];
    *infinite_run = address[INFINITE_RUN];
    *n_simulation_ticks = address[N_SIMULATION_TICS];
    

    return true;
}

//! \general method to encapsulate the setting off of any executable.
//! Just calls the spin1api start command.
//! \return does not return anything
void simulation_run() {
    spin1_start(SYNC_WAIT);
}

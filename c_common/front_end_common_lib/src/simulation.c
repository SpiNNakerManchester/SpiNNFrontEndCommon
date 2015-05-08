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
	simulation_timer_period, n_simulation_tics
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
        address_t address, uint32_t* timer_period,
        uint32_t* n_simulation_ticks) {

    *timer_period = address[simulation_timer_period];
    *n_simulation_ticks = address[n_simulation_tics];
    log_info("timer tic is %d, n_simulation_ticks is %d",
             *timer_period, *n_simulation_ticks);
    return true;
}

//! \brief Reads a piece of memory to extract a collection of component
//! magic numbers for parts of models to read and deduce if they are reading
//!the correct data in memory.
//!
//!
//! \param[in]  region_start A pointer to the start of the region (or to the
//!                          first 32-bit word if included as part of another
//!                          region
//! \param[in] num_components the number of components to read from memory
//! \param[out] component_magic_numbers A pointer to the array of components
bool simulation_read_components(
        address_t address, uint32_t num_components,
        uint32_t component_magic_numbers[]){

   // get each number of components, bypassing the first two elements
   for (uint32_t index = 0; index < num_components; index++){
       component_magic_numbers[index] = address[index];
   }
   log_info("read in components magic numebrs of :[");
   for (uint32_t index = 0; index < num_components; index++){
       log_info("%d", component_magic_numbers[index]);
   }
   log_info("]");
   return true;
}

//! \general method to encapsulate the setting off of any executable.
//! Just calls the spin1api start command.
//! \return does not return anything
void simulation_run() {
    spin1_start(SYNC_WAIT);
}

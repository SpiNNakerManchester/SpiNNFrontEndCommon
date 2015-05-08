/*! \file
 *
 *  \brief Simulation Functions Header File
 *
 *  DESCRIPTION
 *    Specifies functions that are used to get simulation information and start
 *    simulations.
 *
 */

#ifndef _SIMULATION_H_
#define _SIMULATION_H_

#include "common-typedefs.h"

//! \brief The number of words that will be read by
//         simulation_read_timing_details
#define SIMULATION_N_TIMING_DETAIL_WORDS 3

//! \brief Reads the timing details for the simulation out of a region,
//!        which is formatted as:
//!            uint32_t magic_number;
//!            uint32_t timer_period;
//!            uint32_t n_simulation_ticks;
//! \param[in] address The address of the region
//! \param[out] timer_period a pointer to an int to receive the timer period,
//!                          in microseconds
//! \param[out] n_simulation_ticks a pointer to an int to receive the number
//!                                of simulation time steps to be performed
//! \return True if the data was found, false otherwise
bool simulation_read_timing_details(
        address_t address, uint32_t* timer_period,
        uint32_t* n_simulation_ticks);

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
        uint32_t component_magic_numbers[]);

//! \brief Starts the simulation running, returning when it is complete
void simulation_run();

#endif // _SIMULATION_H_

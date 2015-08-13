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

// the position and human readable terms for each element from the region
// containing the timing details.
typedef enum region_elements {
    APPLICATION_MD5_HASH, SIMULATION_TIMER_PERIOD, INFINITE_RUN,
	N_SIMULATION_TICS, SIMULATION_N_TIMING_DETAIL_WORDS
} region_elements;

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
//! \param infinite_run[out] a pointer to an int which represents if the model
//!                          should run for infinite time
//! \return True if the data was found, false otherwise
bool simulation_timing_details(
        address_t address, uint32_t* timer_period,
        uint32_t* n_simulation_ticks, uint32_t* infinite_run);

//! \brief Starts the simulation running, returning when it is complete
void simulation_run();

#endif // _SIMULATION_H_

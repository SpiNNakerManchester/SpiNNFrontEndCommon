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
//! \param[in] expected_application_magic_number The expected value of the magic
//!                                          number that checks if the data was
//!                                          meant for this code
//! \param timer_period[out] a pointer to an int to receive the timer period,
//!                          in microseconds
//! \param n_simulation_ticks[out] a pointer to an int to receive the number
//!                                of simulation time steps to be performed
//! \param infinite_run[out] a pointer to an int which represents if the model
//!                          should run for infinite time
//! \return True if the data was found, false otherwise
bool simulation_read_timing_details(
        address_t address, uint32_t expected_application_magic_number,
        uint32_t* timer_period, uint32_t* n_simulation_ticks,
        uint32_t* infinite_run);

//! \brief Starts the simulation running, returning when it is complete
void simulation_run();

#endif // _SIMULATION_H_

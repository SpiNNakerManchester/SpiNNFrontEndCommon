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
        uint32_t* infinite_run);

//! \brief Starts the simulation running, returning when it is complete
void simulation_run();

#endif // _SIMULATION_H_

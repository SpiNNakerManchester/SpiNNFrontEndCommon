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
#include <debug.h>
#include <spin1_api.h>

// the position and human readable terms for each element from the region
// containing the timing details.
typedef enum region_elements{
	APPLICATION_MD5_HASH, SIMULATION_TIMER_PERIOD, N_SIMULATION_TICS
}region_elements;

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
static inline bool simulation_read_header(
        address_t address, uint32_t* timer_period,
        uint32_t* n_simulation_ticks){

    if (address[APPLICATION_MD5_HASH] != APPLICATION_NAME_HASH){
        log_error("The application hash 0x%.8x does not match the expected hash 0x%.8x",
                  address[APPLICATION_MD5_HASH], APPLICATION_NAME_HASH);
        return false;
    }
    *timer_period = address[SIMULATION_TIMER_PERIOD];
    *n_simulation_ticks = address[N_SIMULATION_TICS];
    log_info("timer tic is %d, n_simulation_ticks is %d",
             *timer_period, *n_simulation_ticks);
    return true;
}

//! \brief Starts the simulation running, returning when it is complete
static inline void simulation_run() {
    spin1_start(SYNC_WAIT);
}

#endif // _SIMULATION_H_

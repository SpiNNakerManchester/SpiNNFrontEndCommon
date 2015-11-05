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
#include <spin1_api.h>

// the position and human readable terms for each element from the region
// containing the timing details.
typedef enum region_elements{
	APPLICATION_MAGIC_NUMBER, SIMULATION_TIMER_PERIOD, INFINITE_RUN,
	N_SIMULATION_TICS, SIMULATION_N_TIMING_DETAIL_WORDS
}region_elements;

// the different types of sdp packet callbacks and their functionality.
typedef enum simulation_sdp_packet_callback_ports{
    PAUSE_RESUME = 1, BUFFERING_IN_SDP_PORT = 2
}simulation_sdp_packet_callback_ports;

typedef enum simulation_commands{
    CMD_STOP = 6, CMD_RUNTIME = 7
}simulation_commands;

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

//! \brief cleans up the house keeping, falls into a sync state and handles
//!        the resetting up of states as required to resume.
//! \param[in] timer_function: The callback function used for the
//!            timer_callback inturrpt registeration
//! \param[in] timer_function_priority: the priotiy level wanted for the
//! timer callback used by the application model.
void simulation_handle_pause_resume(
         callback_t timer_function, int timer_function_priority);

//! \brief handles the new commands needed to resume the binary with a new
//! runtime counter, as well as switching off the binary when it truely needs
//! to be stopped.
//! \param[in] mailbox ????????????
//! \param[in] port ??????????????
//! \return does not return anything
void simulation_sdp_packet_callback(uint mailbox, uint port);

//! \brief handles the registeration of the sdp callback for handleing the
//! new runtimes and exit modes for application models
//! \param[in] simulation_ticks: pointer to the variable the model uses for
//! recording the simulation time
//! \param[in] sdp_packet_callback_priority: the priotiy level wanted for the
//! sdp callback for runtime and exit states.
//! \return does not return anything
void simulation_register_simulation_sdp_callback(
        uint32_t *simulation_ticks, int sdp_packet_callback_priority);

#endif // _SIMULATION_H_

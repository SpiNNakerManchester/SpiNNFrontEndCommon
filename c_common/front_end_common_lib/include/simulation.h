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
    APPLICATION_MAGIC_NUMBER, SIMULATION_TIMER_PERIOD,
    SDP_EXIT_RUNTIME_COMMAND_PORT, SIMULATION_N_TIMING_DETAIL_WORDS
} region_elements;

//! elements that are always grabbed for provenance if possible when requested
typedef enum provenance_data_elements{
    TRANSMISSION_EVENT_OVERFLOW, CALLBACK_QUEUE_OVERLOADED,
    DMA_QUEUE_OVERLOADED, TIMER_TIC_HAS_OVERRUN,
    MAX_NUMBER_OF_TIMER_TIC_OVERRUN, PROVENANCE_DATA_ELEMENTS
}provenance_data_elements;

typedef enum simulation_commands{
    CMD_STOP = 6, CMD_RUNTIME = 7, SDP_SWITCH_STATE = 8,
    PROVENANCE_DATA_GATHERING = 9,
}simulation_commands;

//! the definition of the callback used by provenance data functions
typedef void (*prov_callback_t)(address_t);

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
//! \return True if the data was found, false otherwise
bool simulation_read_timing_details(
        address_t address, uint32_t expected_application_magic_number,
        uint32_t* timer_period);

//! \brief cleans up the house keeping, falls into a sync state and handles
//!        the resetting up of states as required to resume.
void simulation_handle_pause_resume();

//! \brief Starts the simulation running, returning when it is complete,
//! \param[in] timer_function: The callback function used for the
//!            timer_callback interrupt registration
//! \param[in] timer_function_priority: the priority level wanted for the
//! timer callback used by the application model.
void simulation_run(callback_t timer_function, int timer_function_priority);

//! \brief handles the new commands needed to resume the binary with a new
//! runtime counter, as well as switching off the binary when it truly needs
//! to be stopped.
//! \param[in] mailbox The mailbox containing the SDP packet received
//! \param[in] port The port on which the packet was received
//! \return does not return anything
void simulation_sdp_packet_callback(uint mailbox, uint port);

//! \brief handles the registration of the SDP callback
//! \param[in] simulation_ticks_pointer Pointer to the number of simulation
//!            ticks, to allow this to be updated when requested via SDP
//! \param[in] infinite_run_pointer Pointer to the infinite run flag, to allow
//!            this to be updated when requested via SDP
//! \param[in] sdp_packet_callback_priority The priority to use for the
//!            SDP packet reception
void simulation_register_simulation_sdp_callback(
        uint32_t *simulation_ticks_pointer, uint32_t *infinite_run_pointer,
        int sdp_packet_callback_priority);

//! \brief timer callback to support updating runtime via SDP message during
//! first run
//! \param[in] timer_function: The callback function used for the
//!            timer_callback interrupt registration
//! \param[in] timer_function_priority: the priority level wanted for the
//! timer callback used by the application model.
void simulation_timer_tic_callback(uint timer_count, uint unused);

//! \brief handles the storing of basic provenance data
//! \param[in] provenance_data_region_id The region id to which the provenance
//!                                      data should be stored
//! \return the address place to carry on storing prov data from
address_t simulation_store_provenance_data();

//! \brief handles the registration for storing provenance data (needs to be
//! done at least with the provenance region id)
//! \param[in] provenance_function: function to call for extra provenance data
//!     can be NULL as well.
//! \param[in] provenance_data_region_id: the region id in dsg for where
//!  provenance is to be stored
//! \return does not return anything
void simulation_register_provenance_function_call(
        prov_callback_t provenance_function,
        uint32_t provenance_data_region_id);

#endif // _SIMULATION_H_

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
    SIMULATION_CONTROL_SDP_PORT, SIMULATION_N_TIMING_DETAIL_WORDS
} region_elements;

//! elements that are always grabbed for provenance if possible when requested
typedef enum provenance_data_elements{
    TRANSMISSION_EVENT_OVERFLOW, CALLBACK_QUEUE_OVERLOADED,
    DMA_QUEUE_OVERLOADED, TIMER_TIC_HAS_OVERRUN,
    MAX_NUMBER_OF_TIMER_TIC_OVERRUN, PROVENANCE_DATA_ELEMENTS
} provenance_data_elements;

typedef enum simulation_commands{
    CMD_STOP = 6, CMD_RUNTIME = 7, SDP_SWITCH_STATE = 8,
    PROVENANCE_DATA_GATHERING = 9, IOBUF_CLEAR = 10
} simulation_commands;

//! the definition of the callback used by provenance data functions
typedef void (*prov_callback_t)(address_t);

//! the definition of the callback used by pause and resume
typedef void (*resume_callback_t)();

//! \brief initialises the simulation interface which involves:
//! 1. Reading the timing details for the simulation out of a region,
//!        which is formatted as:
//!            uint32_t magic_number;
//!            uint32_t timer_period;
//!            uint32_t n_simulation_ticks;
//! 2. setting the simulation SDP port code that supports multiple runs of the
//! executing code through front end calls.
//! 3. setting up the registration for storing provenance data
//! \param[in] address The address of the region
//! \param[in] expected_application_magic_number The expected value of the magic
//!            number that checks if the data was meant for this code
//! \param[in] simulation_ticks_pointer Pointer to the number of simulation
//!            ticks, to allow this to be updated when requested via SDP
//! \param[in] infinite_run_pointer Pointer to the infinite run flag, to allow
//!            this to be updated when requested via SDP
//! \param[in] sdp_packet_callback_priority The priority to use for the
//!            SDP packet reception
//! \param[in] provenance_function: function to call for extra provenance data
//!            (can be NULL if no additional provenance data is to be stored)
//! \param[in] provenance_data_region_id: the id of the region where
//!            provenance is to be stored
//! \param[out] timer_period a pointer to an int to receive the timer period,
//!             in microseconds
//! \param[out] simulation_control_sdp_port The SDP port requested for
//!             simulation control
//! \return True if the data was found, false otherwise
bool simulation_initialise(
        address_t address, uint32_t expected_application_magic_number,
        uint32_t* timer_period, uint32_t *simulation_ticks_pointer,
        uint32_t *infinite_run_pointer, int sdp_packet_callback_priority,
        prov_callback_t provenance_function,
        address_t provenance_data_address);

//! \brief cleans up the house keeping, falls into a sync state and handles
//!        the resetting up of states as required to resume.
//! \param[in] resume_function The function to call just before the simulation
//!            is resumed (to allow the resetting of the simulation)
void simulation_handle_pause_resume(resume_callback_t resume_function);

//! \brief a helper method for people not using the auto pause and
//! resume functionality
void simulation_exit();

//! \brief Starts the simulation running, returning when it is complete,
void simulation_run();

//! \brief Registers an additional SDP callback on a given SDP port.  This is
//!        required when using simulation_register_sdp_callback, as this will
//!        register its own SDP handler.
//! \param[in] port The SDP port to use
//! \param[in] sdp_callback The callback to call when a packet is received
void simulation_sdp_callback_on(
    uint sdp_port, callback_t sdp_callback);

//! \brief disables SDP callbacks on the given port
//| \param[in] sdp_port The SDP port to disable callbacks for
void simulation_sdp_callback_off(uint sdp_port);

#endif // _SIMULATION_H_

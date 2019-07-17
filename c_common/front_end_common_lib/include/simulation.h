/*
 * Copyright (c) 2017-2019 The University of Manchester
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

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

// constant for how many DMA IDs you can use (caps the values of the tags as
// well)
#define MAX_DMA_CALLBACK_TAG 16

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
    CMD_STOP = 6, CMD_RUNTIME = 7, PROVENANCE_DATA_GATHERING = 8,
    IOBUF_CLEAR = 9
} simulation_commands;

//! the definition of the callback used by provenance data functions
typedef void (*prov_callback_t)(address_t);

//! the definition of the callback used by pause and resume
typedef void (*resume_callback_t)();

//! the definition of the callback used by pause and resume when exit command
//! is sent and models want to do cleaning up
typedef void (*exit_callback_t)();

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
//! \param[out] timer_period a pointer to an int to receive the timer period,
//!             in microseconds
//! \param[in] simulation_ticks_pointer Pointer to the number of simulation
//!            ticks, to allow this to be updated when requested via SDP
//! \param[in] infinite_run_pointer Pointer to the infinite run flag, to allow
//!            this to be updated when requested via SDP
//! \param[in] time_pointer Pointer to the current time, to allow this to be
//!            updated when requested via SDP
//! \param[in] sdp_packet_callback_priority The priority to use for the
//!            SDP packet reception
//! \param[in] dma_transfer_complete_priority The priority to use for the
//!            DMA transfer complete callbacks
//! \return True if the data was found, false otherwise
bool simulation_initialise(
        address_t address, uint32_t expected_application_magic_number,
        uint32_t* timer_period, uint32_t *simulation_ticks_pointer,
        uint32_t *infinite_run_pointer, uint32_t *time_pointer,
        int sdp_packet_callback_priority, int dma_transfer_complete_priority);

//! \brief Set the address of the data region where provenance data is to be
//!        stored
//! \param[in] provenance_data_address: the address where provenance data should
//!            be stored
void simulation_set_provenance_data_address(address_t provenance_data_address);

//! \brief Set an additional callback function to store extra provenance data
//! \param[in] provenance_function: function to call for extra provenance data
//! \param[in] provenance_data_address: the address where provenance data should
//!            be stored
void simulation_set_provenance_function(
        prov_callback_t provenance_function, address_t provenance_data_address);

//! \brief Set an additional function to call before exiting the binary when
//!        running without a fixed duration of execution
//! \param[in] exit_function: function to call when the host tells the
//!            simulation to exit. Executed before API exit.
void simulation_set_exit_function(exit_callback_t exit_function);

//! \brief cleans up the house keeping, falls into a sync state and handles
//!        the resetting up of states as required to resume.  Note that
//!        following this function, the code should call
//!        simulation_ready_to_read (see later).
//! \param[in] resume_function The function to call just before the simulation
//!            is resumed (to allow the resetting of the simulation)
void simulation_handle_pause_resume(resume_callback_t resume_function);

//! \brief a helper method for people not using the auto pause and
//! resume functionality
void simulation_exit();

//! \brief Starts the simulation running, returning when it is complete,
void simulation_run();

//! \brief Indicates that all data has been written and the core is going
//!        idle, so any data can now be read
void simulation_ready_to_read();

//! \brief Registers an additional SDP callback on a given SDP port.  This is
//!        required when using simulation_register_sdp_callback, as this will
//!        register its own SDP handler.
//! \param[in] port The SDP port to use
//! \param[in] sdp_callback The callback to call when a packet is received
//! \return true if successful, false otherwise
bool simulation_sdp_callback_on(
    uint sdp_port, callback_t sdp_callback);

//! \brief disables SDP callbacks on the given port
//| \param[in] sdp_port The SDP port to disable callbacks for
void simulation_sdp_callback_off(uint sdp_port);

//! \brief registers a DMA transfer callback to the simulation system
//! \param[in] tag: the DMA transfer tag to register against
//! \param[in] callback: the callback to register for the given tag
//! \return true if successful, false otherwise
bool simulation_dma_transfer_done_callback_on(uint tag, callback_t callback);

//! \brief turns off a registered callback for a given DMA transfer done tag
//! \param[in] tag: the DMA transfer tag to de-register
void simulation_dma_transfer_done_callback_off(uint tag);

#endif // _SIMULATION_H_

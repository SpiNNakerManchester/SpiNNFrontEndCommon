/*
 * Copyright (c) 2014 The University of Manchester
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/*! \file
 *
 *  \brief Simulation Functions Header File
 *
 *    Specifies functions that are used to get simulation information and start
 *    simulations.
 *
 */

#ifndef _SIMULATION_H_
#define _SIMULATION_H_

#include <stdbool.h>
#include "common-typedefs.h"
#include <spin1_api.h>

//! constant for how many DMA IDs you can use (caps the values of the tags as
//! well)
#define MAX_DMA_CALLBACK_TAG 16

//! \brief the position and human readable terms for each element from the
//! region containing the timing details.
struct simulation_config {
    uint32_t application_magic_number;
    uint32_t timer_period;
    uint32_t control_sdp_port;
    uint32_t num_timing_detail_words;
};

//! elements that are always grabbed for provenance if possible when requested
struct simulation_provenance {
    uint32_t transmission_event_overflow;
    uint32_t callback_queue_overloads;
    uint32_t dma_queue_overloads;
    uint32_t user_queue_overloads;
    uint32_t timer_tic_has_overrun;
    uint32_t max_num_timer_tic_overrun;
    uint32_t provenance_data_elements[];
};

//! the commands that the simulation control protocol may send
typedef enum simulation_commands {
    //! Asks the simulation loop to stop as soon as possible
    CMD_STOP = 6,
    //! Tells the simulation loop how long to run for
    CMD_RUNTIME = 7,
    //! Asks the application to gather provenance data
    PROVENANCE_DATA_GATHERING = 8,
    //! Clears the IOBUF
    IOBUF_CLEAR = 9,
    //! Asks the application to pause.  This relies on the application using
    //! simulation_is_finished which can then handle the pause status better.
    CMD_PAUSE = 10,
    //! Get the current simulation time
    CMD_GET_TIME = 11,
} simulation_commands;

//! the definition of the callback used by provenance data functions
typedef void (*prov_callback_t)(address_t);

//! the definition of the callback used by pause and resume
typedef void (*resume_callback_t)(void);

//! the definition of the callback used by pause and resume when exit command
//! is sent and models want to do cleaning up
typedef void (*exit_callback_t)(void);

//! the definition of the callback used to call a function once at start
typedef resume_callback_t start_callback_t;

//! \brief initialises the simulation interface which involves:
//! 1. Reading the timing details for the simulation out of a region,
//!        which is formatted as:
//!            uint32_t magic_number;
//!            uint32_t timer_period;
//!            uint32_t n_simulation_ticks;
//! 2. setting the simulation SDP port code that supports multiple runs of the
//! executing code through front end calls.
//! 3. setting up the registration for storing provenance data
//! \param[in] address: The address of the region
//! \param[in] expected_application_magic_number: The expected value of the magic
//!            number that checks if the data was meant for this code
//! \param[out] timer_period: Pointer to an int to receive the timer period,
//!             in microseconds
//! \param[in] simulation_ticks_pointer: Pointer to the number of simulation
//!            ticks, to allow this to be updated when requested via SDP
//! \param[in] infinite_run_pointer: Pointer to the infinite run flag, to allow
//!            this to be updated when requested via SDP
//! \param[in] time_pointer: Pointer to the current time, to allow this to be
//!            updated when requested via SDP
//! \param[in] sdp_packet_callback_priority: The priority to use for the
//!            SDP packet reception
//! \param[in] dma_transfer_complete_priority: The priority to use for the
//!            DMA transfer complete callbacks
//! \return True if the data was found, false otherwise
bool simulation_initialise(
        address_t address, uint32_t expected_application_magic_number,
        uint32_t* timer_period, uint32_t *simulation_ticks_pointer,
        uint32_t *infinite_run_pointer, uint32_t *time_pointer,
        int sdp_packet_callback_priority, int dma_transfer_complete_priority);

//! \brief initialises the simulation interface for step-based simulation,
//! which involves:
//! 1. Reading the timing details for the simulation out of a region,
//!        which is formatted as:
//!            uint32_t magic_number;
//!            uint32_t timer_period; (ignored in this case)
//!            uint32_t n_simulation_steps;
//! 2. setting the simulation SDP port code that supports multiple runs of the
//! executing code through front end calls.
//! 3. setting up the registration for storing provenance data
//! \param[in] address The address of the region
//! \param[in] expected_application_magic_number The expected value of the magic
//!            number that checks if the data was meant for this code
//! \param[in] simulation_steps_pointer Pointer to the number of simulation
//!            steps, to allow this to be updated when requested via SDP
//! \param[in] infinite_steps_pointer Pointer to the infinite steps flag, to
//!            allow this to be updated when requested via SDP
//! \param[in] step_pointer Pointer to the current step, to allow this to be
//!            updated when requested via SDP
//! \param[in] sdp_packet_callback_priority The priority to use for the
//!            SDP packet reception
//! \param[in] dma_transfer_complete_priority The priority to use for the
//!            DMA transfer complete callbacks or <= -2 to disable
//! \return True if the data was found, false otherwise
static inline bool simulation_steps_initialise(
        address_t address, uint32_t expected_application_magic_number,
        uint32_t *simulation_steps_pointer, uint32_t *infinite_steps_pointer,
        uint32_t *step_pointer, int sdp_packet_callback_priority,
        int dma_transfer_complete_priority) {
    // Use the normal simulation initialise, passing in matching parameters
    uint32_t unused_timer_period;
    return simulation_initialise(address, expected_application_magic_number,
        &unused_timer_period, simulation_steps_pointer, infinite_steps_pointer,
        step_pointer, sdp_packet_callback_priority,
        dma_transfer_complete_priority);
}

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

//! \brief Set an additional function to call before starting the binary
//! \param[in] start_function: function to call when the host tells the
//!            simulation to start.  Executed before "synchronisation".
void simulation_set_start_function(start_callback_t start_function);

//! \brief cleans up the house keeping, falls into a sync state and handles
//!        the resetting up of states as required to resume.  Note that
//!        following this function, the code should call
//!        simulation_ready_to_read (see later).
//! \param[in] callback: The function to call just before the simulation
//!            is resumed (to allow the resetting of the simulation)
void simulation_handle_pause_resume(resume_callback_t callback);

//! \brief a helper method for people not using the auto pause and
//! resume functionality
void simulation_exit(void);

//! \brief Starts the simulation running, returning when it is complete,
void simulation_run(void);

//! \brief Indicates that all data has been written and the core is going
//!        idle, so any data can now be read
void simulation_ready_to_read(void);

//! \brief Registers an additional SDP callback on a given SDP port.  This is
//!        required when using simulation_register_sdp_callback, as this will
//!        register its own SDP handler.
//! \param[in] sdp_port: The SDP port to use
//! \param[in] sdp_callback: The callback to call when a packet is received
//! \return true if successful, false otherwise
bool simulation_sdp_callback_on(
        uint sdp_port, callback_t sdp_callback);

//! \brief disables SDP callbacks on the given port
//! \param[in] sdp_port: The SDP port to disable callbacks for
void simulation_sdp_callback_off(uint sdp_port);

//! \brief registers a DMA transfer callback to the simulation system
//! \param[in] tag: the DMA transfer tag to register against
//! \param[in] callback: the callback to register for the given tag
//! \return true if successful, false otherwise
bool simulation_dma_transfer_done_callback_on(uint tag, callback_t callback);

//! \brief turns off a registered callback for a given DMA transfer done tag
//! \param[in] tag: the DMA transfer tag to de-register
void simulation_dma_transfer_done_callback_off(uint tag);

//! \brief set whether the simulation uses the timer.  By default it will
//!        be assumed that simulations use the timer unless this function is
//!        called.
//! \param[in] sim_uses_timer: Whether the simulation uses the timer (true)
//!                            or not (false)
void simulation_set_uses_timer(bool sim_uses_timer);

//! \brief sets the simulation to enter a synchronisation barrier repeatedly
//!        during the simulation.  The synchronisation message must be sent
//!        from the host.  Note simulation_is_finished() must be used each
//!        timestep to cause the pause to happen.
//! \param[in] n_steps: The number of steps of simulation between synchronisations
void simulation_set_sync_steps(uint32_t n_steps);

//! \brief determine if the simulation is finished.  Will also pause the simulation
//!        for resynchronisation if requested (see simulation_set_sync_steps).
//! \return true if the simulation is finished, false if not.
bool simulation_is_finished(void);

#endif // _SIMULATION_H_

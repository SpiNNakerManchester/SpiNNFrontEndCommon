/*
 * Copyright (c) 2015 The University of Manchester
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

//! \file
//!
//! \brief The implementation of the Command Sender Multicast Source.
//!
//! The purpose of this application is to inject SpiNNaker packets into the
//! on-chip network at specified times. It is used (among other things) to
//! implement the SpikeSourceArray model in sPyNNaker.

#include <common-typedefs.h>
#include <data_specification.h>
#include <debug.h>
#include <simulation.h>
#include <stdbool.h>

//! \brief Command structure, describing a SpiNNaker multicast packet to be
//! sent at some point.
//!
//! Note that the delay actually comes after sending each mandated packet when
//! repeats are requested rather than just between packets.
typedef struct command {
    //! The key of the packet.
    uint32_t key;
    //! Whether to send a payload with the packet.
    bool has_payload;
    //! The payload for the packet.
    uint32_t payload;
    //! \brief The number of times to repeat the packet.
    //! \details If zero, the packet is only sent once.
    uint32_t repeats;
    //! The time (in microseconds) to delay between sending each repeat.
    uint32_t delay;
} command;

//! A command that happens at a particular simulation time.
typedef struct timed_command {
    uint32_t time;   //!< The simulation time to send a packet.
    command command; //!< What to send.
} timed_command;

//! \brief A collection of commands to be sent in response to an event.
//!
//! This is used for SDRAM only.
typedef struct command_list {
    uint32_t size;      //!< The number of commands to send.
    command commands[]; //!< The commands to send.
} command_list;

//! \brief A collection of commands to be sent at particular simulation times.
//!
//! This is used for SDRAM only.
typedef struct timed_command_list {
    uint32_t size;            //!< The number of commands to send.
    timed_command commands[]; //!< The commands to send, sorted in time order.
} timed_command_list;

// Globals
//! The simulation timer.
static uint32_t time;
//! The number of ticks to run for.
static uint32_t simulation_ticks;
//! Whether the simulation is running "forever" (robotics mode).
static uint32_t infinite_run;
//! The commands to send at particular times.
static timed_command *timed_commands;
//! The commands to run when a simulation starts or resumes after pause.
static command *start_resume_commands;
//! The commands to run when a simulation stops or pauses.
static command *pause_stop_commands;
//! The number of timed commands.
static uint32_t n_timed_commands;
//! The number of commands to send on start/resume.
static uint32_t n_start_resume_commands;
//! The number of commands to send on stop/pause.
static uint32_t n_pause_stop_commands;
//! The index of the next timed command to run.
static uint32_t next_timed_command;
//! Whether we are in the state where the next run will be a start/resume.
static bool resume = true;
//! The number of commands sent
static uint32_t n_commands_sent;

//! values for the priority for each callback
typedef enum callback_priorities {
    SDP = 0,   //!< Responding to network traffic is highest priority
    DMA = 1,   //!< Handling memory transfers is next highest
    TIMER = 2  //!< Responding to timers is lowest priority, and most common
} callback_priorities;

//! region identifiers
typedef enum region_identifiers {
    //! Where simulation system information is stored.
    SYSTEM_REGION = 0,
    //! Where to read timed commands from. The region is formatted as a
    //! timed_command_list.
    COMMANDS_WITH_ARBITRARY_TIMES,
    //! Where to read start/resume commands from. The region is formatted as a
    //! command_list.
    COMMANDS_AT_START_RESUME,
    //! Where to read stop/pause commands from. The region is formatted as a
    //! command_list.
    COMMANDS_AT_STOP_PAUSE,
    //! Where to record provenance data. (Format: ::cs_provenance_t)
    PROVENANCE_REGION
} region_identifiers;

//! custom provenance data
typedef struct cs_provenance_t {
    //! The number of commands sent
    uint32_t n_commands_sent;
} cs_provenance_t;

//! time ID
enum {
    FIRST_TIME = 0
};

//! \brief Immediately sends SpiNNaker multicast packets in response to a
//! command.
//! \param[in] command_to_send: The command to send.
static void transmit_command(command *command_to_send) {
    // check for repeats
    if (command_to_send->repeats != 0) {
        for (uint32_t repeat_count = 0;
                repeat_count <= command_to_send->repeats;
                repeat_count++) {
            if (command_to_send->has_payload) {
                log_debug("Sending %08x, %08x at time %u with %u repeats and "
                        "%u delay",
                        command_to_send->key, command_to_send->payload, time,
                        command_to_send->repeats, command_to_send->delay);
                spin1_send_mc_packet(
                        command_to_send->key, command_to_send->payload,
                        WITH_PAYLOAD);
            } else {
                log_debug("Sending %08x at time %u with %u repeats and "
                        "%u delay",
                        command_to_send->key, time, command_to_send->repeats,
                        command_to_send->delay);
                spin1_send_mc_packet(command_to_send->key, 0, NO_PAYLOAD);
            }
            n_commands_sent++;

            // if the delay is 0, don't call delay
            if (command_to_send->delay > 0) {
                spin1_delay_us(command_to_send->delay);
            }
        }
    } else {
        if (command_to_send->has_payload) {
            log_debug("Sending %08x, %08x at time %u",
                    command_to_send->key, command_to_send->payload, time);

            //if no repeats, then just send the message
            spin1_send_mc_packet(
                    command_to_send->key, command_to_send->payload,
                    WITH_PAYLOAD);
        } else {
            log_debug("Sending %08x at time %u", command_to_send->key, time);
            spin1_send_mc_packet(command_to_send->key, 0, NO_PAYLOAD);
        }
        n_commands_sent++;
    }
}

//! \brief Sends all the commands registered for sending on simulation stop or
//! pause.
static void run_stop_pause_commands(void) {
    log_info("Transmit pause/stop commands");
    for (uint32_t i = 0; i < n_pause_stop_commands; i++) {
        transmit_command(&pause_stop_commands[i]);
    }
}

//! \brief Sends all the commands registered for sending on simulation start or
//! resume.
static void run_start_resume_commands(void) {
    log_info("Transmit start/resume commands");
    for (uint32_t i = 0; i < n_start_resume_commands; i++) {
        transmit_command(&start_resume_commands[i]);
    }
}

//! \brief Copy the list of commands to run at particular times into DTCM.
//! \param[in] sdram_timed_commands The memory region containing the
//! description of what commands to send and when.
//! \return True if we succeeded, false if we failed (due to memory problems)
static bool read_scheduled_parameters(timed_command_list *sdram_timed_commands) {
    n_timed_commands = sdram_timed_commands->size;
    log_info("%d timed commands", n_timed_commands);

    // if no data, do not read it in
    if (n_timed_commands == 0) {
        return true;
    }

    // Allocate the space for the scheduled_commands
    timed_commands = spin1_malloc(n_timed_commands * sizeof(timed_command));

    if (timed_commands == NULL) {
        log_error("Could not allocate the scheduled commands");
        return false;
    }

    spin1_memcpy(timed_commands, sdram_timed_commands->commands,
            n_timed_commands * sizeof(timed_command));

    log_info("Schedule commands starts at time %u",
            timed_commands[FIRST_TIME].time);
    return true;
}

//! \brief Copy the list of commands to run on start or resume into DTCM.
//! \param[in] sdram_commands The memory region containing the
//! description of what commands to send.
//! \return True if we succeeded, false if we failed (due to memory problems)
static bool read_start_resume_commands(command_list *sdram_commands) {
    n_start_resume_commands = sdram_commands->size;
    log_info("%u start/resume commands", n_start_resume_commands);

    if (n_start_resume_commands == 0) {
        return true;
    }

    // Allocate the space for the start resume
    start_resume_commands =
            spin1_malloc(n_start_resume_commands * sizeof(command));
    if (start_resume_commands == NULL) {
        log_error("Could not allocate the start/resume commands");
        return false;
    }

    spin1_memcpy(start_resume_commands, sdram_commands->commands,
            n_start_resume_commands * sizeof(command));
    return true;
}

//! \brief Copy the list of commands to run on stop or pause into DTCM.
//! \param[in] sdram_commands The memory region containing the
//! description of what commands to send.
//! \return True if we succeeded, false if we failed (due to memory problems)
static bool read_pause_stop_commands(command_list *sdram_commands) {
    n_pause_stop_commands = sdram_commands->size;
    log_info("%u pause/stop commands", n_pause_stop_commands);

    if (n_pause_stop_commands == 0) {
        return true;
    }

    // Allocate the space for the start resume
    pause_stop_commands =
            spin1_malloc(n_pause_stop_commands * sizeof(command));
    if (pause_stop_commands == NULL) {
        log_error("Could not allocate the pause/stop commands");
        return false;
    }

    spin1_memcpy(pause_stop_commands, sdram_commands->commands,
            n_pause_stop_commands * sizeof(command));
    return true;
}

// Callbacks
//! \brief The timer tick callback. Sends those commands that are due in the
//! current simulation state and time.
//!
//! \param unused0 unused
//! \param unused1 unused
static void timer_callback(UNUSED uint unused0, UNUSED uint unused1) {
    time++;

    if (resume) {
        log_info("running first start resume commands");
        run_start_resume_commands();
        resume = false;
    }

    if (simulation_is_finished()) {
        run_stop_pause_commands();

        simulation_handle_pause_resume(NULL);

        log_info("in pause resume mode");
        resume = true;

        // Subtract 1 from the time so this tick gets done again on the next
        // run
        time--;

        simulation_ready_to_read();
        return;
    }

    while ((next_timed_command < n_timed_commands) &&
            (timed_commands[next_timed_command].time == time)) {
        transmit_command(&timed_commands[next_timed_command].command);
        ++next_timed_command;
    }
}

//! \brief Write our provenance data into the provenance region.
//! \param[in] address: Where to write
static void write_provenance(address_t address) {
    cs_provenance_t *sdram_prov = (void *) address;
    sdram_prov->n_commands_sent = n_commands_sent;
}

//! \brief Initialises the core.
//! \param[out] timer_period The timer tick period.
//! \return True if initialisation succeeded.
static bool initialize(uint32_t *timer_period) {
    // Get the address this core's DTCM data starts at from SRAM
    data_specification_metadata_t *ds_regions =
            data_specification_get_data_address();

    // Read the header
    if (!data_specification_read_header(ds_regions)) {
        return false;
    }

    // Get the timing details and set up the simulation interface
    if (!simulation_initialise(
            data_specification_get_region(SYSTEM_REGION, ds_regions),
            APPLICATION_NAME_HASH, timer_period, &simulation_ticks,
            &infinite_run, &time, SDP, DMA)) {
        return false;
    }
    simulation_set_provenance_function(
            write_provenance,
            data_specification_get_region(PROVENANCE_REGION, ds_regions));
    simulation_set_exit_function(run_stop_pause_commands);

    // Read the parameters
    bool success;
    success = read_scheduled_parameters(data_specification_get_region(
            COMMANDS_WITH_ARBITRARY_TIMES, ds_regions));
    success &= read_start_resume_commands(data_specification_get_region(
            COMMANDS_AT_START_RESUME, ds_regions));
    success &= read_pause_stop_commands(data_specification_get_region(
            COMMANDS_AT_STOP_PAUSE, ds_regions));
    return success;
}

//! Entry point
void c_main(void) {
    // Configure system
    uint32_t timer_period = 0;
    if (!initialize(&timer_period)) {
        log_error("Error in initialisation - exiting!");
        rt_error(RTE_SWERR);
    }

    // Set timer_callback
    spin1_set_timer_tick(timer_period);

    // Register callbacks
    spin1_callback_on(TIMER_TICK, timer_callback, TIMER);

    // Start the time at "-1" so that the first tick will be 0
    time = UINT32_MAX;
    simulation_run();
}

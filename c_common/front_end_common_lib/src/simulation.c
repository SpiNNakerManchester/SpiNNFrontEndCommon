/*!
 * \file
 * \brief implementation of simulation.h
 */

#include "simulation.h"

#include <debug.h>
#include <spin1_api.h>

//! the pointer to the simulation time used by application models
static uint32_t *pointer_to_simulation_time;

//! the port used by the host machine for setting up the sdp port for
//! receiving the exit, new runtime etc
static int sdp_exit_run_command_port;

//! flag for checking if we're in exit state
static bool exited = false;


//! \brief method that checks that the data in this region has the correct
//!        identifier for the model calling this method and also interprets the
//!        timer period and runtime for the model.
//! \param[in] address The memory address to start reading the parameters from
//! \param[in] expected_app_magic_number The application's magic number thats
//!            requesting timing details from this memory address.
//! \param[out] timer_period A pointer for storing the timer period once read
//!             from the memory region
//! \param[out] n_simulation_ticks A pointer for storing the number of timer
//!             ticks this executable should run for, which is read from this
//!             region
//! \param INFINITE_RUN[out] a pointer to an int which represents if the model
//!                          should run for infinite time
//! \return True if the method was able to read the parameters and the
//!         application magic number corresponded to the magic number in
//!         memory, otherwise the method will return False.
bool simulation_read_timing_details(
        address_t address, uint32_t expected_app_magic_number,
        uint32_t* timer_period, uint32_t* n_simulation_ticks,
        uint32_t* infinite_run) {

    if (address[APPLICATION_MAGIC_NUMBER] != expected_app_magic_number) {
        log_error("Unexpected magic number 0x%.8x instead of 0x%.8x",
                address[APPLICATION_MAGIC_NUMBER],
                expected_app_magic_number);
        return false;
    }

    *timer_period = address[SIMULATION_TIMER_PERIOD];
    *infinite_run = address[INFINITE_RUN];
    *n_simulation_ticks = address[N_SIMULATION_TICS];
    sdp_exit_run_command_port = address[SDP_EXIT_RUNTIME_COMMAND_PORT];
    return true;
}

//! \brief General method to encapsulate the setting off of any executable.
//!        Just calls the spin1api start command.
void simulation_run() {
    spin1_start(SYNC_WAIT);
}

//! \brief cleans up the house keeping, falls into a sync state and handles
//!        the resetting up of states as required to resume.
void simulation_handle_pause_resume(
        callback_t timer_function, int timer_function_priority){

    // Wait for the next run of the simulation
    spin1_callback_off(TIMER_TICK);

    // Fall into a sync state to await further calls (sark level call)
    event_wait();

    if (exited){
        spin1_exit(0);
        log_info("exited");
    }
    else{
        log_info("resuming");
        spin1_callback_on(TIMER_TICK, timer_function, timer_function_priority);
    }
}

//! \brief handles the new commands needed to resume the binary with a new
//!        runtime counter, as well as switching off the binary when it truly
//!        needs to be stopped.
//! \param[in] mailbox The SDP message mailbox
//! \param[in] port The SDP port on which the message was received
void simulation_sdp_packet_callback(uint mailbox, uint port) {
    use(port);
    sdp_msg_t *msg = (sdp_msg_t *) mailbox;
    uint16_t length = msg->length;

    if (msg->cmd_rc == CMD_STOP) {
        log_info("Received exit signal. Program complete.");

        // free the message to stop overload
        spin1_msg_free(msg);
        exited = true;
        sark_cpu_state(CPU_STATE_13);

    } else if (msg->cmd_rc == CMD_RUNTIME) {
        log_info("Setting the runtime of this model to %d", msg->arg1);

        // resetting the simulation time pointer
        *pointer_to_simulation_time = msg->arg1;

        // free the message to stop overload
        spin1_msg_free(msg);

        // change state to CPU_STATE_12
        sark_cpu_state(CPU_STATE_12);

    } else if (msg->cmd_rc == SDP_SWITCH_STATE){

        // change the state of the cpu into what's requested from the host
        sark_cpu_state(msg->arg1);

        // free the message to stop overload
        spin1_msg_free(msg);
    } else {

        log_error("received packet with unknown command code %d", msg->cmd_rc);
        spin1_msg_free(msg);
    }
}

//! \brief handles the registration of the SDP callback
//! \param[out] simulation_ticks The number of ticks that the simulation is to
//!             run for
//! \param[in] sdp_packet_callback_priority The priority to use for the
//!            SDP packet reception
void simulation_register_simulation_sdp_callback(
        uint32_t *simulation_ticks, int sdp_packet_callback_priority) {
    pointer_to_simulation_time = simulation_ticks;
    log_info("port no is %d", sdp_exit_run_command_port);
    spin1_sdp_callback_on(
        sdp_exit_run_command_port, simulation_sdp_packet_callback,
        sdp_packet_callback_priority);
}

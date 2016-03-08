/*!
 * \file
 * \brief implementation of simulation.h
 */

#include "simulation.h"

#include <debug.h>
#include <spin1_api.h>

//! the pointer to the simulation time used by application models
static uint32_t *pointer_to_simulation_time;

//! the pointer to the flag for if it is a infinite run
static uint32_t *pointer_to_infinite_run;

//! the pointer to the users timer tick callback
static callback_t users_timer_callback;

//! the user timer tick priority
static int user_timer_tick_priority;

//! flag to state that code has received a runtime update.
static bool has_received_runtime_update = false;

//! flag to state that the first runtime update.
static bool is_first_runtime_update = true;

//! the port used by the host machine for setting up the SDP port for
//! receiving the exit, new runtime etc
static int sdp_exit_run_command_port;

//! flag for checking if we're in exit state
static bool exited = false;


//! \brief method that checks that the data in this region has the correct
//!        identifier for the model calling this method and also interprets the
//!        timer period and runtime for the model.
//! \param[in] address The memory address to start reading the parameters from
//! \param[in] expected_app_magic_number The application's magic number that's
//!            requesting timing details from this memory address.
//! \param[out] timer_period A pointer for storing the timer period once read
//!             from the memory region
//! \return True if the method was able to read the parameters and the
//!         application magic number corresponded to the magic number in
//!         memory, otherwise the method will return False.
bool simulation_read_timing_details(
        address_t address, uint32_t expected_app_magic_number,
        uint32_t* timer_period) {

    if (address[APPLICATION_MAGIC_NUMBER] != expected_app_magic_number) {
        log_error(
            "Unexpected magic number 0x%08x instead of 0x%08x at 0x%08x",
            address[APPLICATION_MAGIC_NUMBER],
            expected_app_magic_number,
            (uint32_t) address + APPLICATION_MAGIC_NUMBER);
        return false;
    }

    *timer_period = address[SIMULATION_TIMER_PERIOD];

    sdp_exit_run_command_port = address[SDP_EXIT_RUNTIME_COMMAND_PORT];
    return true;
}


void simulation_run(
        callback_t timer_function, int timer_function_priority){

    // Store end users timer tick callbacks to be used once runtime stuff been
    // set up for the first time.
    users_timer_callback = timer_function;
    user_timer_tick_priority = timer_function_priority;

    // turn off any timer tick callbacks, as we're replacing them for the moment
    spin1_callback_off(TIMER_TICK);

    // Set off simulation runtime callback
    spin1_callback_on(TIMER_TICK, simulation_timer_tic_callback, 1);

    // go into SARK start
    spin1_start(SYNC_NOWAIT);

    // return from running
    return;
}

//! \brief timer callback to support updating runtime via SDP message during
//!        first run
//! \param[in] timer_function: The callback function used for the
//!            timer_callback interrupt registration
//! \param[in] timer_function_priority: the priority level wanted for the
//! timer callback used by the application model.
void simulation_timer_tic_callback(uint timer_count, uint unused){
    log_debug(
        "Setting off the second run for simulation_handle_run_pause_resume");
    simulation_handle_pause_resume();
}

//! \brief cleans up the house keeping, falls into a sync state and handles
//!        the resetting up of states as required to resume.
void simulation_handle_pause_resume(){

    // Wait for the next run of the simulation
    spin1_callback_off(TIMER_TICK);

    // reset the has received runtime flag, for the next run
    has_received_runtime_update = false;

    // Fall into a sync state to await further calls (SARK level call)
    event_wait();
    if (exited){
        spin1_exit(0);
        log_info("Exiting");
    } else {
        if (has_received_runtime_update & is_first_runtime_update) {
            log_info("Starting");
            is_first_runtime_update = false;
        } else if (has_received_runtime_update & !is_first_runtime_update) {
            log_info("Resuming");
        } else if (!has_received_runtime_update){
            log_error("Runtime has not been updated!");
            rt_error(RTE_API);
        }
        spin1_callback_on(
            TIMER_TICK, users_timer_callback, user_timer_tick_priority);
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
        *pointer_to_infinite_run = msg->arg2;

        // free the message to stop overload
        spin1_msg_free(msg);

        // change state to CPU_STATE_12
        sark_cpu_state(CPU_STATE_12);

        // update flag to state received a runtime
        has_received_runtime_update = true;

    } else if (msg->cmd_rc == SDP_SWITCH_STATE) {

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
//! \param[in] simulation_ticks_pointer Pointer to the number of simulation
//!            ticks, to allow this to be updated when requested via SDP
//! \param[in] infinite_run_pointer Pointer to the infinite run flag, to allow
//!            this to be updated when requested via SDP
//! \param[in] sdp_packet_callback_priority The priority to use for the
//!            SDP packet reception
void simulation_register_simulation_sdp_callback(
        uint32_t *simulation_ticks_pointer, uint32_t *infinite_run_pointer,
        int sdp_packet_callback_priority) {
    pointer_to_simulation_time = simulation_ticks_pointer;
    pointer_to_infinite_run = infinite_run_pointer;
    log_info("port no is %d", sdp_exit_run_command_port);
    spin1_sdp_callback_on(
        sdp_exit_run_command_port, simulation_sdp_packet_callback,
        sdp_packet_callback_priority);
}

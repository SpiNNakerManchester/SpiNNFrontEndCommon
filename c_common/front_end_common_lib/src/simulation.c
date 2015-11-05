/*!
 * \file
 * \brief implementation of simulation.h
 */

#include "simulation.h"

#include <debug.h>
#include <spin1_api.h>

//! the pointer to the simulation time used by application models
static uint32_t *pointer_to_simulation_time;

extern event_data_t event;


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
    

    return true;
}

//! \general method to encapsulate the setting off of any executable.
//! Just calls the spin1api start command.
//! \return does not return anything
void simulation_run() {
    spin1_start(SYNC_WAIT);
}

//! \brief cleans up the house keeping, falls into a sync state and handles
//!        the resetting up of states as required to resume.
//! \return does not return anything
void simulation_handle_pause_resume(
        callback_t timer_function, int timer_function_priority){
    // Wait for the next run of the simulation
    spin1_callback_off(TIMER_TICK);

    // Fall into a sync state to await further calls (sark level call)
    event_wait();

    spin1_callback_on(TIMER_TICK, timer_function, timer_function_priority);
}

//! \brief handles the new commands needed to resume the binary with a new
//! runtime counter, as well as switching off the binary when it truely needs
//! to be stopped.
//! \param[in] mailbox ????????????
//! \param[in] port ??????????????
//! \param[in] free_message bool to check if the message should be freed
//! \return does not return anything
void simulation_sdp_packet_callback(uint mailbox, uint port) {
    use(port);
    sdp_msg_t *msg = (sdp_msg_t *) mailbox;
    uint16_t length = msg->length;
    log_info("received packet with command code %d", msg->cmd_rc);

    if (msg->cmd_rc == CMD_STOP) {
        log_info("Received exit signal. Program complete.");

        // free the message to stop overload
        spin1_msg_free(msg);

        // get the virutal cpu for this core
        uint bit = 1 << sark.virt_cpu;

        // knocks the event waits out for the callbacks that have been syncd
        if (event.wait){
            sc[SC_FLAG] = sc[SC_FLAG] | bit;
        }
        else{
            sc[SC_FLAG] = sc[SC_FLAG] & ~bit;
        }

        // sets some stuff for getting to exit
        spin1_exit(0);

    } else if (msg->cmd_rc == CMD_RUNTIME) {
        log_info("setting pointer");
        *pointer_to_simulation_time = msg->arg1;
        // free the message to stop overload
        log_info("freeing mesage");
        spin1_msg_free(msg);
        // Fall into the next Sync state, so that host can deduce that the
        // application has recieved this data
        log_info("going into event wait");
        event_wait();
        log_info("exiting event wait");
    }
}

//! \brief handles the
void simulation_register_simulation_sdp_callback(
        uint32_t *simulation_ticks, int sdp_packet_callback_priority) {
    pointer_to_simulation_time = simulation_ticks;
    spin1_sdp_callback_on(PAUSE_RESUME, simulation_sdp_packet_callback,
                          sdp_packet_callback_priority);
}
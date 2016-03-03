/*!
 * \file
 * \brief implementation of simulation.h
 */

#include "simulation.h"

#include <debug.h>
#include <spin1_api.h>

//! the pointer to the simulation time used by application models
static uint32_t *pointer_to_simulation_time;

//! the pointer to the flag which indicates if this simulation runs forever
static uint32_t *pointer_to_infinite_run;

//! the function call to run when extracting provenance data from the chip
static prov_callback_t stored_provenance_function = NULL;

//! the region id for storing provenance data from the chip
static uint32_t stored_provenance_data_region_id = NULL;

//! the pointer to the users timer tic callback
static callback_t users_timer_callback;
//! the user timer tic priority
static int user_timer_tic_priority;

//! flag to state that code has received a runtime update.
static bool has_received_runtime_update = false;
//! flag to state that the first runtime update.
static bool is_first_runtime_update = true;

//! the port used by the host machine for setting up the sdp port for
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
        log_error(
            "Unexpected magic number 0x%08x instead of 0x%08x at 0x%08x",
            address[APPLICATION_MAGIC_NUMBER],
            expected_app_magic_number,
            (uint32_t) address + APPLICATION_MAGIC_NUMBER);
        return false;
    }

    *timer_period = address[SIMULATION_TIMER_PERIOD];
    *infinite_run = address[INFINITE_RUN];

    sdp_exit_run_command_port = address[SDP_EXIT_RUNTIME_COMMAND_PORT];
    return true;
}


void simulation_run(
        callback_t timer_function, int timer_function_priority){

    // Store end users timer tic callbacks to be used once runtime stuff been
    // set up for the first time.
    users_timer_callback = timer_function;
    user_timer_tic_priority = timer_function_priority;

    // turn off any timer tic callbacks, as we're replacing them for the moment
    spin1_callback_off(TIMER_TICK);
    // Set off simulation runtime callback
    spin1_callback_on(TIMER_TICK, simulation_timer_tic_callback, 1);
    // go into sark start
    spin1_start(SYNC_NOWAIT);
    // return from running
    return;
}

//! \brief timer callback to support updating runtime via sdp message during
//! first run
//! \param[in] timer_count the number of times this call back has been
//!            executed since start of simulation
//! \param[in] unused unused parameter kept for API consistency
//! timer callback used by the application model.
//! \return: none
void simulation_timer_tic_callback(uint timer_count, uint unused){
    log_debug("Setting off the second run for "
              "simulation_handle_run_pause_resume\n");
    simulation_handle_pause_resume();
}

//! \brief helper private method for running provenance data storage
void _execute_provenance_storage(){
    if (stored_provenance_data_region_id == NULL){
        log_warning("No provenance region id was given, so basic "
                    "provenance will not be gathered.\n");
    }
    else{
        log_info("Starting basic provenance gathering\n");
        address_t region_to_start_with = simulation_store_provenance_data();
        if (stored_provenance_function != NULL){
            log_info("running other provenance gathering\n");
            stored_provenance_function(region_to_start_with);
        }
    }
}

//! \brief cleans up the house keeping, falls into a sync state and handles
//!        the resetting up of states as required to resume.
void simulation_handle_pause_resume(){
    // Wait for the next run of the simulation
    spin1_callback_off(TIMER_TICK);
    // reset the has received runtime flag, for the next run
    has_received_runtime_update = false;

    // Store provenance data as required
    if (!is_first_runtime_update){
        _execute_provenance_storage();
    }

    // Fall into a sync state to await further calls (sark level call)
    log_info("Falling into sync state");
    event_wait();

    if (exited){
        spin1_exit(0);
        log_info("exited");
    }
    else{
        if (has_received_runtime_update & is_first_runtime_update){
            log_info("starting");
            is_first_runtime_update = false;
        }else if (has_received_runtime_update & !is_first_runtime_update){
            log_info("resuming");
        }else if (!has_received_runtime_update){
            log_error("Been asked to run again even though I've not had my"
                      " runtime updated. Therefore exiting in error state");
            rt_error(RTE_API);
        }

        spin1_callback_on(
            TIMER_TICK, users_timer_callback, user_timer_tic_priority);
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

    switch (msg->cmd_rc) {
        case CMD_STOP:
            log_info("Received exit signal. Program complete.\n");

            // free the message to stop overload
            spin1_msg_free(msg);
            exited = true;
            sark_cpu_state(CPU_STATE_13);
            break;

        case CMD_RUNTIME:
            log_info("Setting the runtime of this model to %d\n", msg->arg1);

            // resetting the simulation time pointer
            *pointer_to_simulation_time = msg->arg1;
            *pointer_to_infinite_run = msg->arg2;

            // free the message to stop overload
            spin1_msg_free(msg);

            // change state to CPU_STATE_12
            sark_cpu_state(CPU_STATE_12);

            // update flag to state ive received a runtime
            has_received_runtime_update = true;
            break;

        case SDP_SWITCH_STATE:

            log_info("Switching to state %d\n", msg->arg1);
            // change the state of the cpu into what's requested from the host
            sark_cpu_state(msg->arg1);

            // free the message to stop overload
            spin1_msg_free(msg);
            break;

        case PROVENANCE_DATA_GATHERING:
            log_info("Forced provenance gathering\n");
            // force provenance to be executed and then exit
            _execute_provenance_storage();
            rt_error(RTE_API);
            break;

        default:
            // should never get here
            log_error("received packet with unknown command code %d\n",
                      msg->cmd_rc);
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

//! \brief handles the registration for storing provenance data (needs to be
//! done at least with the provenance region id)
//! \param[in] provenance_function: function to call for extra provenance data
//!     can be NULL as well.
//! \param[in] provenance_data_region_id: the region id in dsg for where
//!  provenance is to be stored
//! \return does not return anything
void simulation_register_provenance_function_call(
        prov_callback_t provenance_function,
        uint32_t provenance_data_region_id){
    stored_provenance_function = provenance_function;
    stored_provenance_data_region_id = provenance_data_region_id;
}

//! \brief handles the storing of basic provenance data
//! \param[in] provenance_data_region_id The region id to which the provenance
//!                                      data should be stored
//! \return the address place to carry on storing prov data from
address_t simulation_store_provenance_data(){
    //! gets access to the diagnostics object from sark
    extern diagnostics_t diagnostics;
    // Get the address this core's DTCM data starts at from SRAM
    address_t address = data_specification_get_data_address();
    // get the address of the start of the core's provenance data region
    address_t provenance_region = data_specification_get_region(
        stored_provenance_data_region_id, address);

    // store the data into the provenance data region
    provenance_region[TRANSMISSION_EVENT_OVERFLOW] =
        diagnostics.tx_packet_queue_full;
    provenance_region[CALLBACK_QUEUE_OVERLOADED] =
        diagnostics.task_queue_full;
    provenance_region[DMA_QUEUE_OVERLOADED] =
        diagnostics.dma_queue_full;
    provenance_region[TIMER_TIC_HAS_OVERRUN] =
        diagnostics.total_times_tick_tic_callback_overran;
    provenance_region[MAX_NUMBER_OF_TIMER_TIC_OVERRUN] =
        diagnostics.largest_number_of_concurrent_timer_tic_overruns;
    return &provenance_region[PROVENANCE_DATA_ELEMENTS];
}

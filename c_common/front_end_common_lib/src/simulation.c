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

//! the port used by the host machine for setting up the SDP port for
//! receiving the exit, new runtime etc
static int sdp_exit_run_command_port;

//! the function call to run when extracting provenance data from the chip
static prov_callback_t stored_provenance_function = NULL;

//! the function call to run just before resuming a simulation
static resume_callback_t stored_resume_function = NULL;

//! the region id for storing provenance data from the chip
static uint32_t stored_provenance_data_region_id = NULL;

//! \brief handles the storing of basic provenance data
//! \return the address after which new provenance data can be stored
address_t _simulation_store_provenance_data() {

    //! gets access to the diagnostics object from SARK
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

//! \brief helper private method for running provenance data storage
void _execute_provenance_storage(){
    log_info("Starting basic provenance gathering");
    address_t region_to_start_with = _simulation_store_provenance_data();
    if (stored_provenance_function != NULL){
        log_info("running other provenance gathering");
        stored_provenance_function(region_to_start_with);
    }
}

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


void simulation_run() {

    // check that the top level code has registered a provenance region id
    if (stored_provenance_data_region_id == NULL){
        log_error(
            "The top level code needs to register a provenance region id via"
            " the simulation_register_provenance_function_call() function");
        spin1_rte(RTE_API);
    }

    // go into spin1 API start, but paused (no SYNC)
    spin1_start_paused();

    // return from running
    return;
}

void simulation_handle_pause_resume(resume_callback_t callback){

    stored_resume_function = callback;

    // Store provenance data as required
    _execute_provenance_storage();

    // Pause the simulation
    spin1_pause();
}

void simulation_sdp_packet_callback(uint mailbox, uint port) {
    use(port);
    sdp_msg_t *msg = (sdp_msg_t *) mailbox;
    uint16_t length = msg->length;

    switch (msg->cmd_rc) {
        case CMD_STOP:
            log_info("Received exit signal. Program complete.");

            // free the message to stop overload
            spin1_msg_free(msg);
            spin1_exit(0);
            break;

        case CMD_RUNTIME:
            log_info("Setting the runtime of this model to %d", msg->arg1);

            // resetting the simulation time pointer
            *pointer_to_simulation_time = msg->arg1;
            *pointer_to_infinite_run = msg->arg2;

            // free the message to stop overload
            spin1_msg_free(msg);

            log_info("Resuming");
            if (stored_resume_function != NULL) {
                stored_resume_function();
                stored_resume_function = NULL;
            }
            spin1_resume(SYNC_WAIT);
            break;

        case SDP_SWITCH_STATE:

            log_debug("Switching to state %d", msg->arg1);

            // change the state of the cpu into what's requested from the host
            sark_cpu_state(msg->arg1);

            // free the message to stop overload
            spin1_msg_free(msg);
            break;

        case PROVENANCE_DATA_GATHERING:
            log_info("Forced provenance gathering");

            // force provenance to be executed and then exit
            _execute_provenance_storage();
            spin1_msg_free(msg);
            spin1_rte(RTE_SWERR);
            break;

        default:
            // should never get here
            log_error(
                "received packet with unknown command code %d", msg->cmd_rc);
            spin1_msg_free(msg);
    }
}

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

void simulation_register_provenance_callback(
        prov_callback_t provenance_function,
        uint32_t provenance_data_region_id){
    stored_provenance_function = provenance_function;
    stored_provenance_data_region_id = provenance_data_region_id;
}

/*!
 * \file
 * \brief implementation of simulation.h
 */

#include "simulation.h"

#include <stdbool.h>
#include <debug.h>
#include <spin1_api_params.h>
#include <spin1_api.h>

//! the pointer to the simulation time used by application models
static uint32_t *pointer_to_simulation_time;

//! the pointer to the flag for if it is a infinite run
static uint32_t *pointer_to_infinite_run;

//! the function call to run when extracting provenance data from the chip
static prov_callback_t stored_provenance_function = NULL;

//! the function call to run just before resuming a simulation
static resume_callback_t stored_resume_function = NULL;

//! the region id for storing provenance data from the chip
static address_t stored_provenance_data_address = NULL;

//! the list of SDP callbacks for ports
static callback_t sdp_callback[NUM_SDP_PORTS];


//! \brief handles the storing of basic provenance data
//! \return the address after which new provenance data can be stored
static address_t _simulation_store_provenance_data() {

    //! gets access to the diagnostics object from SARK
    extern diagnostics_t diagnostics;

    // store the data into the provenance data region
    stored_provenance_data_address[TRANSMISSION_EVENT_OVERFLOW] =
        diagnostics.tx_packet_queue_full;
    stored_provenance_data_address[CALLBACK_QUEUE_OVERLOADED] =
        diagnostics.task_queue_full;
    stored_provenance_data_address[DMA_QUEUE_OVERLOADED] =
        diagnostics.dma_queue_full;
    stored_provenance_data_address[TIMER_TIC_HAS_OVERRUN] =
        diagnostics.total_times_tick_tic_callback_overran;
    stored_provenance_data_address[MAX_NUMBER_OF_TIMER_TIC_OVERRUN] =
        diagnostics.largest_number_of_concurrent_timer_tic_overruns;
    return &stored_provenance_data_address[PROVENANCE_DATA_ELEMENTS];
}

//! \brief helper private method for running provenance data storage
static void _execute_provenance_storage() {
    if (stored_provenance_data_address != NULL) {
        log_info("Starting basic provenance gathering");
        address_t address_to_start_with = _simulation_store_provenance_data();
        if (stored_provenance_function != NULL){
            log_info("running other provenance gathering");
            stored_provenance_function(address_to_start_with);
        }
    }
}

void simulation_run() {

    // go into spin1 API start, but paused (no SYNC yet)
    spin1_start_paused();
}

//! \brief cleans up the house keeping, falls into a sync state and handles
//!        the resetting up of states as required to resume.
//! \param[in] resume_function The function to call just before the simulation
//!            is resumed (to allow the resetting of the simulation)
void simulation_handle_pause_resume(resume_callback_t callback){

    stored_resume_function = callback;

    // Store provenance data as required
    _execute_provenance_storage();

    // Pause the simulation
    spin1_pause();
}

//! \brief a helper method for people not using the auto pause and
//! resume functionality
void simulation_exit(){
    simulation_handle_pause_resume(NULL);
}

//! \brief handles the new commands needed to resume the binary with a new
//! runtime counter, as well as switching off the binary when it truly needs
//! to be stopped.
//! \param[in] mailbox The mailbox containing the SDP packet received
//! \param[in] port The port on which the packet was received
//! \return does not return anything
void _simulation_control_scp_callback(uint mailbox, uint port) {
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

            if (stored_resume_function != NULL) {
                log_info("Calling pre-resume function");
                stored_resume_function();
                stored_resume_function = NULL;
            }
            log_info("Resuming");
            spin1_resume(SYNC_WAIT);

            // If we are told to send a response, send it now
            if (msg->arg3 == 1) {
                msg->cmd_rc = RC_OK;
                msg->length = 12;
                uint dest_port = msg->dest_port;
                uint dest_addr = msg->dest_addr;
                msg->dest_port = msg->srce_port;
                msg->srce_port = dest_port;
                msg->dest_addr = msg->srce_addr;
                msg->srce_addr = dest_addr;
                spin1_send_sdp_msg(msg, 10);
            }

            // free the message to stop overload
            spin1_msg_free(msg);
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
            spin1_exit(1);
            break;

        default:
            // should never get here
            log_error(
                "received packet with unknown command code %d", msg->cmd_rc);
            spin1_msg_free(msg);
    }
}

void _simulation_sdp_callback_handler(uint mailbox, uint port) {

    if (sdp_callback[port] != NULL) {

        // if a callback is associated with the port, process it
        sdp_callback[port](mailbox, port);
    } else {

        // if no callback is associated, dump the received packet
        sdp_msg_t *msg = (sdp_msg_t *) mailbox;
        sark_msg_free(msg);
    }
}

void simulation_sdp_callback_on(uint sdp_port, callback_t callback) {
    sdp_callback[sdp_port] = callback;
}

void simulation_sdp_callback_off(uint sdp_port) {
    sdp_callback[sdp_port] = NULL;
}

bool simulation_initialise(
        address_t address, uint32_t expected_app_magic_number,
        uint32_t* timer_period, uint32_t *simulation_ticks_pointer,
        uint32_t *infinite_run_pointer, int sdp_packet_callback_priority,
        prov_callback_t provenance_function,
        address_t provenance_data_address) {

    // handle the timing reading
    if (address[APPLICATION_MAGIC_NUMBER] != expected_app_magic_number) {
        log_error(
            "Unexpected magic number 0x%08x instead of 0x%08x at 0x%08x",
            address[APPLICATION_MAGIC_NUMBER],
            expected_app_magic_number,
            (uint32_t) address + APPLICATION_MAGIC_NUMBER);
        return false;
    }

    if (sdp_packet_callback_priority < -1) {
        log_error(
            "The SDP callback priority should be set to a number greater "
            "than or equal to -1.  "
            "It is currently set to %d", sdp_packet_callback_priority);
        return false;
    }

    // transfer data to pointers for end user usage
    *timer_period = address[SIMULATION_TIMER_PERIOD];

    // handle the SDP callback for the simulation
    pointer_to_simulation_time = simulation_ticks_pointer;
    pointer_to_infinite_run = infinite_run_pointer;

    spin1_callback_on(
        SDP_PACKET_RX, _simulation_sdp_callback_handler,
        sdp_packet_callback_priority);
    simulation_sdp_callback_on(
        address[SIMULATION_CONTROL_SDP_PORT],
        _simulation_control_scp_callback);

    // handle the provenance setting up
    stored_provenance_function = provenance_function;
    stored_provenance_data_address = provenance_data_address;

    // if all simulation initialisation complete return true,
    return true;
}

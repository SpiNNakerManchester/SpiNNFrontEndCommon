/*!
 * \file
 * \brief implementation of simulation.h
 */

#include "simulation.h"

#include <stdbool.h>
#include <debug.h>
#include <spin1_api_params.h>
#include <spin1_api.h>

//! the position and human readable terms for each element from the region
//! containing the timing details.
typedef struct simulation_config_t {
    uint32_t magic_number;
    uint32_t timer_period;
    uint32_t control_port;
} simulation_config_t;

//! elements that are always grabbed for provenance if possible when requested
typedef struct simulation_provenance_t {
    uint32_t transmission_event_overflow;
    uint32_t callback_queue_overload;
    uint32_t dma_queue_overload;
    uint32_t timer_tick_has_overrun;
    uint32_t max_timer_tick_overrun_count;
} simulation_provenance_t;

//! the pointer to the simulation time used by application models
static uint32_t *sim_time_ptr;

//! the pointer to the flag for if it is a infinite run
static uint32_t *inf_run_flag_ptr;

//! the pointer to the current simulation time
static uint32_t *curr_time_ptr;

//! general collection of provenance-related information
static struct {
    //! the function call to run when extracting provenance data from the chip
    prov_callback_t extra_prov_provider;
    //! the function call to run when received a exit command.
    exit_callback_t exit_callback;
    //! the function call to run just before resuming a simulation
    resume_callback_t resume_callback;
    //! the region for storing provenance data from the chip
    simulation_provenance_t *data;
} provenance = {
    NULL, NULL, NULL, NULL
};

//! the list of SDP callbacks for ports
static callback_t sdp_callback[NUM_SDP_PORTS];

//! the list of DMA callbacks for DMA complete callbacks
static callback_t dma_complete_callbacks[MAX_DMA_CALLBACK_TAG];

//! \brief helper function for running provenance data storage
static void execute_provenance_storage(void) {
    extern diagnostics_t diagnostics;

    if (provenance.data != NULL) {
        log_info("Starting basic provenance gathering");

        // store the data into the provenance data region
        provenance.data->transmission_event_overflow =
                diagnostics.tx_packet_queue_full;
        provenance.data->callback_queue_overload = diagnostics.task_queue_full;
        provenance.data->dma_queue_overload = diagnostics.dma_queue_full;
        provenance.data->timer_tick_has_overrun =
                diagnostics.total_times_tick_tic_callback_overran;
        provenance.data->max_timer_tick_overrun_count =
                diagnostics.largest_number_of_concurrent_timer_tic_overruns;

        if (provenance.extra_prov_provider != NULL) {
            log_info("running other provenance gathering");

            void *extra_prov_ptr = &provenance.data[1];
            provenance.extra_prov_provider(extra_prov_ptr);
        }
    }
}

void simulation_run(void) {
    // go into spin1 API start, but paused (no SYNC yet)
    spin1_start_paused();
}

//! \brief cleans up the house keeping, falls into a sync state and handles
//!        the resetting up of states as required to resume.
//! \param[in] resume_function The function to call just before the simulation
//!            is resumed (to allow the resetting of the simulation)
void simulation_handle_pause_resume(resume_callback_t callback) {
    // Pause the simulation
    spin1_pause();

    provenance.resume_callback = callback;

    // Store provenance data as required
    execute_provenance_storage();
}

//! \brief a helper method for people not using the auto pause and
//! resume functionality
void simulation_exit(void) {
    simulation_handle_pause_resume(NULL);
}

void simulation_ready_to_read(void) {
    sark_cpu_state(CPU_STATE_WAIT);
}

//! \brief method for sending OK response to the host when a command message
//! is received.
//! \param[in] msg: the message object to send to the host.
static void send_ok_response(sdp_msg_t *msg) {
    msg->cmd_rc = RC_OK;
    msg->length = 12;

    // reverse the direction of the message by swapping ports and addresses
    uint dest_port = msg->dest_port;
    msg->dest_port = msg->srce_port;
    msg->srce_port = dest_port;

    uint dest_addr = msg->dest_addr;
    msg->dest_addr = msg->srce_addr;
    msg->srce_addr = dest_addr;

    spin1_send_sdp_msg(msg, 10);
}

//! \brief handles the new commands needed to resume the binary with a new
//! runtime counter, as well as switching off the binary when it truly needs
//! to be stopped.
//! \param[in] mailbox The mailbox containing the SDP packet received
//! \param[in] port The port on which the packet was received
//! \return does not return anything
static void control_scp_callback(uint mailbox, uint port) {
    use(port);
    sdp_msg_t *msg = (sdp_msg_t *) mailbox;

    switch (msg->cmd_rc) {
    case CMD_STOP:
        log_info("Received exit signal. Program complete.");

        // free the message to stop overload
        spin1_msg_free(msg);

        // call any stored exit callbacks
        if (provenance.exit_callback != NULL) {
            log_info("Calling pre-exit function");
            provenance.exit_callback();
        }
        log_info("Exiting");
        spin1_exit(0);
        break;

    case CMD_RUNTIME:
        log_info("Setting the runtime of this model to %d starting at %d",
                msg->arg1, msg->arg3);
        log_info("Setting the flag of infinite run for this model to %d",
                msg->arg2);

        // resetting the simulation time pointer
        *sim_time_ptr = msg->arg1;
        *inf_run_flag_ptr = msg->arg2;
        // We start at time - 1 because the first thing models do is
        // increment a time counter
        *curr_time_ptr = msg->arg3 - 1;

        if (provenance.resume_callback != NULL) {
            log_info("Calling pre-resume function");
            provenance.resume_callback();
            provenance.resume_callback = NULL;
        }
        log_info("Resuming");
        spin1_resume(SYNC_WAIT);

        // If we are told to send a response, send it now
        if (msg->data[0] == 1) {
            _send_ok_response(msg);
        }

        // free the message to stop overload
        spin1_msg_free(msg);
        break;

    case PROVENANCE_DATA_GATHERING:
        log_info("Forced provenance gathering");

        // force provenance to be executed and then exit
        execute_provenance_storage();

        // call any stored exit callbacks
        if (provenance.exit_callback != NULL) {
            log_info("Calling pre-exit function");
            provenance.exit_callback();
        }
        spin1_msg_free(msg);
        spin1_exit(1);
        break;

    case IOBUF_CLEAR:
        // run clear iobuf code
        sark_io_buf_reset();

        // If we are told to send a response, send it now
        if (msg->arg3 == 1) {
            send_ok_response(msg);
        }

        // free the message to stop overload
        spin1_msg_free(msg);
        break;

    default:
        // should never get here
        log_error("received packet with unknown command code %d", msg->cmd_rc);
        spin1_msg_free(msg);
    }
}

//! \brief handles the SDP callbacks interface.
static void sdp_callback_handler(uint mailbox, uint port) {
    if (port < NUM_SDP_PORTS && sdp_callback[port] != NULL) {
        // if a callback is associated with the port, process it
        sdp_callback[port](mailbox, port);
    } else {
        // if no callback is associated, dump the received packet
        sdp_msg_t *msg = (sdp_msg_t *) mailbox;
        sark_msg_free(msg);
    }
}

bool simulation_sdp_callback_on(uint sdp_port, callback_t callback) {
    if (sdp_port >= NUM_SDP_PORTS || sdp_callback[sdp_port] != NULL) {
        log_error("Cannot allocate SDP callback on port %d as its already "
                "been allocated.", sdp_port);
        return false;
    }
    sdp_callback[sdp_port] = callback;
    return true;
}

void simulation_sdp_callback_off(uint sdp_port) {
    if (sdp_port < NUM_SDP_PORTS) {
        sdp_callback[sdp_port] = NULL;
    }
}

//! \brief handles the DMA transfer done callbacks interface.
static void dma_transfer_done_callback(uint unused, uint tag) {
    if (tag < MAX_DMA_CALLBACK_TAG && dma_complete_callbacks[tag] != NULL) {
        dma_complete_callbacks[tag](unused, tag);
    }
}

bool simulation_dma_transfer_done_callback_on(uint tag, callback_t callback) {
    // ensure that tag being allocated is less than max tag
    if (tag >= MAX_DMA_CALLBACK_TAG) {
        log_error("Cannot handle tag value above %d, please reduce the tag "
                "value accordingly.", MAX_DMA_CALLBACK_TAG - 1);
        return false;
    }

    // allocate tag callback if not already allocated
    if (dma_complete_callbacks[tag] != NULL) {
        // if allocated already, raise error
        log_error("Cannot allocate DMA transfer callback on tag %d as its "
                "already been allocated.", tag);
        return false;
    }
    dma_complete_callbacks[tag] = callback;
    return true;
}

void simulation_dma_transfer_done_callback_off(uint tag) {
    if (tag < MAX_DMA_CALLBACK_TAG) {
        dma_complete_callbacks[tag] = NULL;
    }
}

bool simulation_initialise(
        address_t address, uint32_t expected_app_magic_number,
        uint32_t* timer_period, uint32_t *simulation_ticks_pointer,
        uint32_t *infinite_run_pointer, uint32_t *time_pointer,
        int sdp_packet_callback_priority,
        int dma_transfer_done_callback_priority) {
    simulation_config_t *config = (simulation_config_t *) address;

    // handle the timing reading
    if (config->magic_number != expected_app_magic_number) {
        log_error("Unexpected magic number 0x%08x instead of 0x%08x at 0x%08x",
                config->magic_number, expected_app_magic_number,
                &config->magic_number);
        return false;
    }

    if (sdp_packet_callback_priority < -1) {
        log_error("The SDP callback priority should be set to a number greater "
                "than or equal to -1.  It is currently set to %d",
                sdp_packet_callback_priority);
        return false;
    }

    // transfer data to pointers for end user usage
    *timer_period = config->timer_period;

    // handle the SDP callback for the simulation
    sim_time_ptr = simulation_ticks_pointer;
    inf_run_flag_ptr = infinite_run_pointer;
    curr_time_ptr = time_pointer;

    spin1_callback_on(SDP_PACKET_RX, sdp_callback_handler,
            sdp_packet_callback_priority);
    simulation_sdp_callback_on(config->control_port, control_scp_callback);
    spin1_callback_on(DMA_TRANSFER_DONE, dma_transfer_done_callback,
            dma_transfer_done_callback_priority);

    // if all simulation initialisation complete return true,
    return true;
}

void simulation_set_provenance_data_address(address_t provenance_data_address) {
    provenance.data = (simulation_provenance_t *) provenance_data_address;
}

void simulation_set_provenance_function(
        prov_callback_t provenance_function,
        address_t provenance_data_address) {
    provenance.extra_prov_provider = provenance_function;
    provenance.data = (simulation_provenance_t *) provenance_data_address;
}

void simulation_set_exit_function(exit_callback_t exit_function) {
    provenance.exit_callback = exit_function;
}

/*
 * Copyright (c) 2019-2020 The University of Manchester
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

#include <spin1_api.h>
#include <debug.h>
#include <bit_field.h>
#include <sdp_no_scp.h>
#include "common/platform.h"
#include "common/routing_table.h"
#include "common/sdp_formats.h"
#include "common/constants.h"

#include "common-typedefs.h"
#include "compressor_includes/aliases.h"
#include "compressor_includes/ordered_covering.h"
/*****************************************************************************/
/* SpiNNaker routing table minimisation with bitfield integration.
 *
 * Minimise a routing table loaded into SDRAM and load the minimised table into
 * the router using the specified application ID.
 *
 * the exit code is stored in the user1 register
 *
 * The memory address with tag "1" is expected contain the following struct
 * (entry_t is defined in `routing_table.h` but is described below).
*/

//! interrupt priorities
typedef enum interrupt_priority{
    TIMER_TICK_PRIORITY = -1,
    SDP_PRIORITY = 0,
    COMPRESSION_START_PRIORITY = 2
} interrupt_priority;

//! \timer controls, as it seems timer in massive waits doesnt engage properly
int counter = 0;
int max_counter = 0;

//! \brief bool saying if the timer has fired, resulting in attempt to compress
//! shutting down
volatile bool timer_for_compression_attempt = false;

//! \brief bool flag to say if i was forced to stop by the compressor control
volatile bool finished_by_compressor_force = false;

//! bool flag pointer to allow minimise to report if it failed due to malloc
//! issues
bool failed_by_malloc = false;

//! control flag for running compression only when needed
bool compress_only_when_needed = false;

//! control flag for compressing as much as possible
bool compress_as_much_as_possible = false;

//! \brief the sdram location to write the compressed router table into
table_t *sdram_loc_for_compressed_entries;

//! \brief the control core id for sending responses to
int control_core_id = -1;

//! \brief sdp message to send acks to the control core with
sdp_msg_pure_data my_msg;

//! \brief sdp message data as a response packet (reducing casts)
response_sdp_packet_t* response = (response_sdp_packet_t*) &my_msg.data;

//! \brief aliases thingy for compression
aliases_t aliases;

// ---------------------------------------------------------------------

//! \brief sends a sdp message back to the control core
void send_sdp_message_response(void) {
    my_msg.dest_port = (RANDOM_PORT << PORT_SHIFT) | control_core_id;
    // send sdp packet
    while (!spin1_send_sdp_msg((sdp_msg_t *) &my_msg, _SDP_TIMEOUT)) {
        log_debug("failed to send. trying again");
        // Empty body
    }
}

//! \brief send a failed response due to a malloc issue
void return_malloc_response_message(void) {
    // set message ack finished state to malloc fail
    response->response_code = FAILED_MALLOC;

    // send message
    send_sdp_message_response();
    log_debug("sent failed to malloc response");
}

//! \brief send a success response message
void return_success_response_message(void) {
    // set message ack finished state to malloc fail
    response->response_code = SUCCESSFUL_COMPRESSION;

    // send message
    send_sdp_message_response();
    log_info("send success ack");
}

//! \brief send a failed response due to the control forcing it to stop
void return_failed_by_force_response_message(void) {
       // set message ack finished state to malloc fail
    response->response_code = FORCED_BY_COMPRESSOR_CONTROL;

    // send message
    send_sdp_message_response();
    log_debug("send forced ack");
}

//! \brief sends a failed response due to running out of time
void return_failed_by_time_response_message(void) {
       // set message ack finished state to malloc fail
    response->response_code = RAN_OUT_OF_TIME;

    // send message
    send_sdp_message_response();
    log_debug("send failed by time");
}

//! \brief send a failed response where finished compression but failed to
//! fit into allocated size.
void return_failed_by_space_response_message(void) {
       // set message ack finished state to malloc fail
    response->response_code = FAILED_TO_COMPRESS;

    // send message
    send_sdp_message_response();
    log_debug("send failed by space");
}

//! \brief stores the compressed routing tables into the compressed sdram
//! location
//! \returns bool if was successful or now
bool store_into_compressed_address(void) {
    if (routing_table_sdram_get_n_entries() > TARGET_LENGTH) {
        log_debug("not enough space in routing table");
        return false;
    }

    log_debug("starting store of %d tables", n_tables);
    bool success = routing_table_sdram_store(
        sdram_loc_for_compressed_entries);
    log_debug("finished store");
    if (!success) {
        log_error("failed to store entries into sdram.");
        return false;
    }
    return true;
}

//! \brief handles the compression process
//! \param[in] unused0: param 1 forced on us from api
//! \param[in] unused1: param 2 forced on us from api
void start_compression_process(uint unused0, uint unused1) {
    // api requirement
    use(unused0);
    use(unused1);

    log_debug("in compression phase");

    // restart timer (also puts us in running state)
    spin1_resume(SYNC_NOWAIT);

    // run compression
    bool success = oc_minimise(
        TARGET_LENGTH, &aliases, &failed_by_malloc,
        &finished_by_compressor_force,
        &timer_for_compression_attempt, compress_only_when_needed,
        compress_as_much_as_possible);

    // turn off timer and set us into pause state
    spin1_pause();
    log_debug("finished oc minimise with success %d", success);

    // check state
    log_debug("success was %d", success);
    if (success) {
        log_debug("store into compressed");
        success = store_into_compressed_address();
        if (success) {
            log_debug("success response");
            return_success_response_message();
        } else {
            log_debug("failed by space response");
            return_failed_by_space_response_message();
        }
    } else {  // if not a success, could be one of 4 states
        if (failed_by_malloc) {  // malloc failed somewhere
            log_debug("failed malloc response");
            return_malloc_response_message();
        } else if (finished_by_compressor_force) {  // control killed it
            log_debug("force fail response");
            return_failed_by_force_response_message();
            log_debug("send ack");
        } else if (timer_for_compression_attempt) {  // ran out of time
            log_debug("time fail response");
            return_failed_by_time_response_message();
        } else { // after finishing compression, still could not fit into table.
            log_debug("failed by space response");
            return_failed_by_space_response_message();
        }
    }
}

//! \brief handle the first message. Will store in the routing table store,
//! and then set off user event if no more  are expected.
//! \param[in] first_cmd: the first packet.
static void handle_start_data_stream(start_sdp_packet_t *start_cmd) {
    // reset states by first turning off timer (puts us in pause state as well)
    spin1_pause();
    return;
    // set up fake heap
    log_info("setting up fake heap for sdram usage");
    platform_new_heap_update(start_cmd->fake_heap_data);
    log_info("finished setting up fake heap for sdram usage");

    failed_by_malloc = false;
    finished_by_compressor_force = false;
    timer_for_compression_attempt = false;
    counter = 0;
    aliases_clear(&aliases);
    routing_table_reset();

    // create aliases
    aliases = aliases_init();

    // location where to store the compressed table
    sdram_loc_for_compressed_entries = start_cmd->table_data->compressed_table;

    log_info("table init");
    bool success = routing_tables_init(
        start_cmd->table_data->n_elements, start_cmd->table_data->elements);
    log_info("table init finish");

    if (!success) {
        log_error("failed to allocate memory for routing table.h state");
        return_malloc_response_message();
        return;
    }

    log_info("starting compression attempt");
    // start compression process
    spin1_schedule_callback(
        start_compression_process, 0, 0, COMPRESSION_START_PRIORITY);
}

//! \brief the sdp control entrance.
//! \param[in] mailbox: the message
//! \param[in] port: don't care.
void _sdp_handler(uint mailbox, uint port) {
    use(port);

    log_debug("received packet");

    // get data from the sdp message
    sdp_msg_pure_data *msg = (sdp_msg_pure_data *) mailbox;
    compressor_payload_t *payload = (compressor_payload_t *) msg->data;

    // record control core.
    if (control_core_id == -1){
        control_core_id = (msg->srce_port & CPU_MASK);
    }

    log_debug("control core is %d", control_core_id);
    log_debug("command code is %d", payload->command);

    // get command code
    if (msg->srce_port >> PORT_SHIFT == RANDOM_PORT) {
        switch (payload->command) {
            case START_DATA_STREAM:
                log_info("start a stream packet");
                handle_start_data_stream(&payload->start);
                sark_msg_free((sdp_msg_t*) msg);
                break;
            case COMPRESSION_RESPONSE:
                log_error("I really should not be receiving this!!! WTF");
                log_error(
                    "came from core %d with code %d",
                    msg->srce_port & CPU_MASK, payload->response.response_code);
                sark_msg_free((sdp_msg_t*) msg);
                break;
            case STOP_COMPRESSION_ATTEMPT:
                log_debug("been forced to stop by control");
                finished_by_compressor_force = true;
                sark_msg_free((sdp_msg_t*) msg);
                break;
            default:
                log_error(
                    "no idea what to do with message with command code %d; "
                    "Ignoring", payload->command);
                sark_msg_free((sdp_msg_t*) msg);
        }
    } else {
        log_error(
            "no idea what to do with message. on port %d; Ignoring",
            msg->srce_port >> PORT_SHIFT);
        sark_msg_free((sdp_msg_t*) msg);
    }
}

//! \brief timer interrupt for controlling time taken to try to compress table
//! \param[in] unused0: not used
//! \param[in] unused1: not used
void timer_callback(uint unused0, uint unused1) {
    use(unused0);
    use(unused1);
    counter ++;

    if (counter >= max_counter){
        timer_for_compression_attempt = true;
        log_info("passed timer point");
        spin1_pause();
    }
}

//! \brief the callback for setting off the router compressor
void initialise(void) {
    log_debug("Setting up stuff to allow bitfield compressor to occur.");

    log_debug("reading time_for_compression_attempt");
    vcpu_t *sark_virtual_processor_info = (vcpu_t*) SV_VCPU;
    vcpu_t *this_processor = &sark_virtual_processor_info[spin1_get_core_id()];

    uint32_t time_for_compression_attempt = this_processor->user1;
    log_debug("user 1 = %d", time_for_compression_attempt);

    // bool from int conversion happening here
    uint32_t int_value = this_processor->user2;
    log_debug("user 2 = %d", int_value);
    if (int_value == 1) {
        compress_only_when_needed = true;
    }

    int_value = this_processor->user3;
    log_debug("user 3 = %d", int_value);
    if (int_value == 1) {
        compress_as_much_as_possible = true;
    }

    // sort out timer (this is done in a indirect way due to lack of trust to
    // have timer only fire after full time after pause and resume.
    max_counter = time_for_compression_attempt / 1000;
    spin1_set_timer_tick(1000);
    spin1_callback_on(TIMER_TICK, timer_callback, TIMER_TICK_PRIORITY);

    // set up sdp callback
    log_debug("set up sdp interrupt");
    spin1_callback_on(SDP_PACKET_RX, _sdp_handler, SDP_PRIORITY);
    log_debug("finished sdp interrupt");

    //set up message static bits
    log_debug("set up sdp message bits");
    response->command_code = COMPRESSION_RESPONSE;
    my_msg.flags = REPLY_NOT_EXPECTED;
    my_msg.srce_addr = spin1_get_chip_id();
    my_msg.dest_addr = spin1_get_chip_id();
    my_msg.srce_port = (RANDOM_PORT << PORT_SHIFT) | spin1_get_core_id();
    my_msg.length = LENGTH_OF_SDP_HEADER + (sizeof(response_sdp_packet_t));

    log_debug("finished sdp message bits");
    log_debug("my core id is %d", spin1_get_core_id());
    log_debug(
        "srce_port = %d the core id is %d",
        my_msg.srce_port, my_msg.srce_port & CPU_MASK);
}

//! \brief the main entrance.
void c_main(void) {
    log_debug("%u bytes of free DTCM", sark_heap_max(sark.heap, 0));


    // set up params
    initialise();

    // go
    spin1_start(SYNC_WAIT);
}

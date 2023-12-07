/*
 * Copyright (c) 2017 The University of Manchester
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
//! \brief The implementation of the Data Speed Up Packet Gatherer.
//!
//! The purpose of this application is to allow data to be streamed in and out
//! of SpiNNaker at very high speed while other applications are not running.
//! It is designed to only run on chips with an active Ethernet port.

// imports
#include <spin1_api.h>
#include <common-typedefs.h>
#include "common.h"
#include <data_specification.h>
#include <simulation.h>
#include <debug.h>
#include <bit_field.h>

//-----------------------------------------------------------------------------
// MAGIC NUMBERS
//-----------------------------------------------------------------------------

//! timeout used in sending SDP messages
#define SDP_TIMEOUT 100

//! \brief the time to wait before trying again to send a message (MC, SDP) in
//! microseconds
#define MESSAGE_DELAY_TIME_WHEN_FAIL 1

//! first sequence number to use and reset to
#define FIRST_SEQ_NUM 0

//! max index needed to cover the chips in either direction on a spinn-5 board
#define MAX_CHIP_INDEX 8

//! values for port numbers this core will respond to
enum functionality_to_port_num_map {
    REINJECTION_PORT = 4,      //!< Reinjection control messages
    DATA_COPY_IN_PORT = 7      //!< Data copy Inbound messages
};

//! Offsets into messages
enum {

    //! \brief location of where the seq num is in the packet
    SEQ_NUM_LOC = 0,

    //! \brief location of the transaction id in the packet
    TRANSACTION_ID = 1,

    //! \brief location of the start of raw data in the packet
    START_OF_DATA = 2
};

//! mask needed by router timeout
#define ROUTER_TIMEOUT_MASK 0xFF

//! Misc constants for Data Out
enum {
    //! absolute maximum size of a SDP message
    ABSOLUTE_MAX_SIZE_OF_SDP_IN_BYTES = 280
};

//-----------------------------------------------------------------------------
// TYPES AND GLOBALS
//-----------------------------------------------------------------------------

//! the key that causes data out sequence number to be processed
static uint32_t new_sequence_key = 0;

//! the key that says this is the first item of data in a data out stream
static uint32_t first_data_key = 0;

//! the key that provides a new data out transaction ID
static uint32_t transaction_id_key = 0;

//! the key that marks the end of a data out stream
static uint32_t end_flag_key = 0;

//! the key that marks an ordinary word within a data out stream
static uint32_t basic_data_key = 0;

//! default seq num
static uint32_t seq_num = FIRST_SEQ_NUM;

//! maximum sequence number
static uint32_t max_seq_num = 0xFFFFFFFF;

//! The Data Out transaction ID. Used to distinguish streams of packets
static uint32_t data_out_transaction_id = 0;

//! data holders for the SDP packet (plus 1 to protect against memory
//! overwrites with command messages)
static uint32_t data[ITEMS_PER_DATA_PACKET];

//! index into ::data
static uint32_t position_in_store = 0;

//! the tag to use to send SDP
static uint32_t tag = 0;

//! human readable definitions of each DSG region in SDRAM
enum {
    //! Index of general configuration region
    CONFIG,
    //! Index of chip-to-key mapping table
    CHIP_TO_KEY,
    //! Index of provenance region
    PROVENANCE_REGION
};

//! The layout of the Data Out configuration region
typedef struct data_out_config_t {
    //! The key used to indicate a new sequence/stream
    const uint new_seq_key;
    //! The key used to indicate the first word of a stream
    const uint first_data_key;
    //! The key used to indicate a transaction ID
    const uint transaction_id_key;
    //! The key used to indicate a stream end
    const uint end_flag_key;
    //! The key used to indicate a general data item in a stream
    const uint basic_data_key;
    //! \brief The ID of the IPtag to send the SDP packets out to host on
    //!
    //! Note that the host is responsible for configuring the tag.
    const uint tag_id;
} data_out_config_t;

//! values for the priority for each callback
enum {
    MC_PACKET = -1, //!< Multicast packet receive uses FIQ
    SDP = 0         //!< SDP receive priority standard (high)
};

//! \brief How to find which key to use to talk to which chip on this board.
//!
//! Note that these addresses are *board-local* chip addresses.
//!
//! The keys here are base keys, and indicate the first key in a group where the
//! LSBs (see ::key_offsets) indicate the meaning of the message.
static uint data_in_mc_key_map[MAX_CHIP_INDEX][MAX_CHIP_INDEX] = {{0}};

//! Human readable definitions of the offsets for data in multicast key
//! elements. These act as commands sent to the target extra monitor core.
typedef enum {
    //! Payload contains a write address
    WRITE_ADDR_KEY_OFFSET = 0,
    //! Payload contains a data word
    DATA_KEY_OFFSET = 1,
    //! Write stream complete. Payload irrelevant
    BOUNDARY_KEY_OFFSET = 2,
} key_offsets;

//! Associates a _board-local_ coordinate with a key for talking to the extra
//! monitor on that chip.
struct chip_key_data_t {
    uint32_t x_coord;  //!< Board local x coordinate of extra monitor
    uint32_t y_coord;  //!< Board local y coordinate of extra monitor
    uint32_t base_key; //!< Base key to use for talking to that chip
};

//! The layout of the Data In configuration region
typedef struct data_in_config_t {
    //! The number of extra monitors that we can talk to
    const uint32_t n_extra_monitors;
    //! The base key for reinjection control messages
    const uint32_t reinjector_base_key;
    //! \brief The configuration data for routing messages to specific extra
    //! monitors.
    //!
    //! Used to populate ::data_in_mc_key_map
    const struct chip_key_data_t chip_to_key[];
} data_in_config_t;

//! The structure of the provenance region FIXME
typedef struct dsupg_provenance_t {
    //! The number of SDP messages sent
    uint32_t n_sdp_sent;
    //! The number of SDP messages received (excluding those for SARK)
    uint32_t n_sdp_recvd;
    //! The number of input streams
    uint32_t n_in_streams;
    //! The number of output streams (technically, output transactions)
    uint32_t n_out_streams;
} dsupg_provenance_t;

//! The DTCM copy of the provenance
static dsupg_provenance_t prov = {0};

//! The SDRAM copy of the provenance
static dsupg_provenance_t *sdram_prov;

//-----------------------------------------------------------------------------
// FUNCTIONS
//-----------------------------------------------------------------------------

//! \brief sends the SDP message built in the ::my_msg global
static inline void send_sdp_message(sdp_msg_pure_data *my_msg, uint n_data_words) {
    my_msg->tag = tag;        // IPTag 1
    my_msg->dest_port = PORT_ETH;        // Ethernet
    my_msg->dest_addr = sv->eth_addr;    // Nearest Ethernet chip

    // fill in SDP source & flag fields
    my_msg->flags = 0x07;
    my_msg->srce_port = 3;
    my_msg->srce_addr = sv->p2p_addr;
    my_msg->length = sizeof(sdp_hdr_t) + sizeof(uint) * n_data_words;
    if (my_msg->length > ABSOLUTE_MAX_SIZE_OF_SDP_IN_BYTES) {
        log_error("bad message length %u", my_msg->length);
    }

    log_debug("sending message of length %u", my_msg->length);
    while (!spin1_send_sdp_msg((sdp_msg_t *) my_msg, SDP_TIMEOUT)) {
        log_debug("failed to send SDP message");
        spin1_delay_us(MESSAGE_DELAY_TIME_WHEN_FAIL);
    }
    prov.n_sdp_sent++;
    sdram_prov->n_sdp_sent = prov.n_sdp_sent;
}

//! \brief sends a multicast (with payload) message to the current target chip
//! \param[in] command: the key offset, which indicates the command being sent
//! \param[in] payload: the argument to the command
//! \param[in] key_x: The key x chip to use
//! \param[in] key_y: The key y chip to use
static inline void send_mc_message(key_offsets command, uint payload,
        uint key_x, uint key_y) {
    uint key = data_in_mc_key_map[key_x][key_y] + command;
    while (spin1_send_mc_packet(key, payload, WITH_PAYLOAD) == 0) {
        spin1_delay_us(MESSAGE_DELAY_TIME_WHEN_FAIL);
    }
}

//! \brief sends multicast messages accordingly for an SDP message
//! \param[in] data: the actual data from the SDP message
//! \param[in] n_elements: the number of data items in the SDP message
//! \param[in] set_write_address: bool flag for if we should send the
//!                               address where our writes will start;
//!                               this is not set every time to reduce
//!                               on-chip network overhead
//! \param[in] write_address: the sdram address where this block of data is
//!                           to be written to
//! \param[in] key_x: The key x chip to use
//! \param[in] key_y: The key y chip to use
static void process_sdp_message_into_mc_messages(
        const uint *data, uint n_elements, uint key_x, uint key_y) {

    // send mc messages containing rest of sdp data
    for (uint data_index = 0; data_index < n_elements; data_index++) {
        log_debug("data is %d", data[data_index]);
        send_mc_message(DATA_KEY_OFFSET, data[data_index], key_x, key_y);
    }
}

//! \brief because spin1_memcpy() is stupid, especially for access to SDRAM
//! \param[out] target: Where to copy to
//! \param[in] source: Where to copy from
//! \param[in] n_words: The number of words to copy
static inline void copy_data(
        void *restrict target, const void *source, uint n_words) {
    uint *to = target;
    const uint *from = source;
    while (n_words-- > 0) {
        *to++ = *from++;
    }
}

//! \brief sends the basic timeout command via multicast to the extra monitors
//! \param[in,out] msg: the request to send the timeout; will be updated with
//!                     result
//! \param[in] key: the multicast key to use here
static void send_timeout(sdp_msg_t* msg, uint32_t key) {
    if (msg->arg1 > ROUTER_TIMEOUT_MASK) {
        msg->cmd_rc = RC_ARG;
        return;
    }
    while (spin1_send_mc_packet(key, msg->arg1, WITH_PAYLOAD) == 0) {
        spin1_delay_us(MESSAGE_DELAY_TIME_WHEN_FAIL);
    }
    msg->cmd_rc = RC_OK;
}

//! \brief sends the clear message to all extra monitors on this board
//! \param[in,out] msg: the request to send the clear; will be updated with
//!                     result
static void send_clear_message(sdp_msg_t* msg) {
    while (spin1_send_mc_packet(
            reinject_clear_mc_key, 0, WITH_PAYLOAD) == 0) {
        spin1_delay_us(MESSAGE_DELAY_TIME_WHEN_FAIL);
    }
    msg->cmd_rc = RC_OK;
}

//! \brief handles the commands for the reinjector code.
//! \param[in,out] msg: the message with the commands; will be updated with
//!                     result
static void reinjection_sdp_command(sdp_msg_t *msg) {
    // handle the key conversion
    switch (msg->cmd_rc) {
    case CMD_DPRI_SET_ROUTER_TIMEOUT:
        send_timeout(msg, reinject_timeout_mc_key);
        log_debug("sent reinjection timeout mc");
        break;
    case CMD_DPRI_SET_ROUTER_EMERGENCY_TIMEOUT:
        send_timeout(msg, reinject_emergency_timeout_mc_key);
        log_debug("sent reinjection emergency timeout mc");
        break;
    case CMD_DPRI_CLEAR:
        send_clear_message(msg);
        log_debug("sent reinjection clear mc");
        break;
    default:
        // If we are here, the command was not recognised, so fail
        // (ARG as the command is an argument)
        log_error(
                "ignoring message as don't know what to do with it when "
                "command id is %d", msg->cmd_rc);
        return;
    }

    // set message to correct format
    msg->length = SDP_REPLY_HEADER_LEN;
    reflect_sdp_message(msg, 0);

    while (!spin1_send_sdp_msg(msg, SDP_TIMEOUT)) {
        log_debug("failed to send SDP message");
        spin1_delay_us(MESSAGE_DELAY_TIME_WHEN_FAIL);
    }
}

static void send_msg(sdp_msg_t *msg) {
    while (!spin1_send_sdp_msg(msg, SDP_TIMEOUT)) {
        log_debug("failed to send SDP message");
        spin1_delay_us(MESSAGE_DELAY_TIME_WHEN_FAIL);
    }
}

static uint last_sequence = 0xFFFFFFF0;

static bool send_in_progress = false;

static void send_data_over_multicast(sdp_msg_t *msg) {
    if (send_in_progress) {
        if (last_sequence != msg->seq) {
            msg->cmd_rc = RC_BUF;
            reflect_sdp_message(msg, 0);
            send_msg(msg);
        }
        return;
    } else if (last_sequence == msg->seq) {
        msg->cmd_rc = RC_OK;
        reflect_sdp_message(msg, 0);
        send_msg(msg);
        return;
    }

    last_sequence = msg->seq;
    send_in_progress = true;

    uint *data = &(msg->arg1);
    uint length = (msg->length - 12) >> 2;

    while (length > 0) {

        // Read a header
        uint address = data[0];
        uint chip_x = (data[1] >> 16) & 0xFFFF;
        uint chip_y = data[1] & 0xFFFF;
        uint n_data_items = data[2];
        data = &(data[3]);
        length -= 3;

        if (chip_x >= 8 || chip_y >= 8) {
            log_error("Chip %u, %u is not valid!", chip_x, chip_y);
            msg->cmd_rc = RC_ARG;
            reflect_sdp_message(msg, 0);
            send_msg(msg);
            return;
        }

        if (n_data_items > length) {
            log_error("Not enough data to read %u words from %u remaining",
                    n_data_items, length);
            msg->cmd_rc = RC_ARG;
            reflect_sdp_message(msg, 0);
            send_msg(msg);
            return;
        }

        log_debug("Writing using %u words to %u, %u: 0x%08x", n_data_items,
                chip_x, chip_y, address);
        send_mc_message(WRITE_ADDR_KEY_OFFSET, address, chip_x, chip_y);
        process_sdp_message_into_mc_messages(data, n_data_items,
                    chip_x, chip_y);

        data = &(data[n_data_items]);
        length -= n_data_items;
    }
    send_in_progress = false;

    // set message to correct format
    msg->cmd_rc = RC_OK;
    reflect_sdp_message(msg, 0);
    send_msg(msg);
}

//! \brief processes SDP messages
//! \param[in,out] mailbox: the SDP message; will be _freed_ by this call!
//! \param[in] port: the port associated with this SDP message
static void receive_sdp_message(uint mailbox, uint port) {
    switch (port) {
    case REINJECTION_PORT:
        reinjection_sdp_command((sdp_msg_t *) mailbox);
        break;
    case DATA_COPY_IN_PORT:
        send_data_over_multicast((sdp_msg_t *) mailbox);
        break;
    default:
        log_info("unexpected port %d\n", port);
    }
    // free the message to stop overload
    spin1_msg_free((sdp_msg_t *) mailbox);
}

//! \brief sends data to the host via SDP (using ::my_msg)
static void send_data(void) {
    sdp_msg_pure_data my_msg;
    copy_data(&my_msg.data, data, position_in_store);

    if (seq_num > max_seq_num) {
        log_error("Got a funky seq num in sending; max is %d, received %d",
                max_seq_num, seq_num);
    }

    send_sdp_message(&my_msg, position_in_store);

    seq_num++;
    data[SEQ_NUM_LOC] = seq_num;
    data[TRANSACTION_ID] = data_out_transaction_id;
    position_in_store = START_OF_DATA;
}

//! \brief Handles receipt of a fixed route packet with payload from the
//!        SpiNNaker network.
//! \param[in] key: The key in the packet
//! \param[in] payload: The payload in the packet
static void receive_data(uint key, uint payload) {
    if (key == new_sequence_key) {
        if (position_in_store != START_OF_DATA) {
            log_info("sending surplus data from new seq setting");
            send_data();
        }

        log_info("new seq num to set is %d", payload);
        data[SEQ_NUM_LOC] = payload;
        data[TRANSACTION_ID] = data_out_transaction_id;
        seq_num = payload;
        position_in_store = START_OF_DATA;

        if (payload > max_seq_num) {
            log_error("Got a funky seq num; max is %d, received %d",
                    max_seq_num, payload);
        }
    } else {
        data[position_in_store] = payload;
        position_in_store++;

        if (key == first_data_key) {
            log_debug("received new stream with max %d", payload);
            seq_num = FIRST_SEQ_NUM;
            data[SEQ_NUM_LOC] = seq_num;
            position_in_store = TRANSACTION_ID;
            max_seq_num = payload;
        }

        if (key == transaction_id_key) {
            data_out_transaction_id = payload;
            data[TRANSACTION_ID] = data_out_transaction_id;
            position_in_store = START_OF_DATA;
            prov.n_out_streams++;
            sdram_prov->n_out_streams = prov.n_out_streams;
        }

        if (key == end_flag_key) {
            // set end flag bit in seq num
            data[SEQ_NUM_LOC] |= 1 << 31;

            // adjust size as last payload not counted
            position_in_store--;

            send_data();
            log_debug("sent all data");
        } else if (position_in_store == ITEMS_PER_DATA_PACKET) {
            send_data();
        }
    }
}

//! Sets up the application
static void initialise(void) {
    // Get the address this core's DTCM data starts at from SRAM
    data_specification_metadata_t *ds_regions =
            data_specification_get_data_address();

    // Read the header
    if (!data_specification_read_header(ds_regions)) {
        log_error("Failed to read the data spec header");
        rt_error(RTE_SWERR);
    }

    log_info("Initialising data out");

    // read keys from sdram
    data_out_config_t *config =
            data_specification_get_region(CONFIG, ds_regions);
    new_sequence_key = config->new_seq_key;
    first_data_key = config->first_data_key;
    transaction_id_key = config->transaction_id_key;
    end_flag_key = config->end_flag_key;
    basic_data_key = config->basic_data_key;
    tag = config->tag_id;

    log_info("new seq key = %d, first data key = %d, transaction id key = %d, "
            "end flag key = %d, basic_data_key = %d",
            new_sequence_key, first_data_key, transaction_id_key,
            end_flag_key, basic_data_key);

    log_info("the tag id being used is %d", config->tag_id);

    // Set up provenance
    sdram_prov = data_specification_get_region(PROVENANCE_REGION, ds_regions);

    spin1_callback_on(FRPL_PACKET_RECEIVED, receive_data, MC_PACKET);

    log_info("Initialising data in");

    // Get the address this core's DTCM data starts at from SRAM
    data_in_config_t *chip_key_map =
            data_specification_get_region(CHIP_TO_KEY, ds_regions);

    // sort out bitfield for reinjection ack tracking
    uint32_t n_extra_monitors = chip_key_map->n_extra_monitors;

    // read in the keys for mc packets for data in
    for (uint i = 0; i < n_extra_monitors; i++) {
        uint x_coord = chip_key_map->chip_to_key[i].x_coord;
        uint y_coord = chip_key_map->chip_to_key[i].y_coord;
        uint base_key = chip_key_map->chip_to_key[i].base_key;
        data_in_mc_key_map[x_coord][y_coord] = base_key;
    }

    // set up the reinjection multicast API
    initialise_reinjection_mc_api(chip_key_map->reinjector_base_key);

    // set sdp callback
    spin1_callback_on(SDP_PACKET_RX, receive_sdp_message, SDP);
}

//! \brief This function is called at application start-up.
//!
//! It is used to register event callbacks (delegated to initialise()) and
//! begin the simulation.
void c_main(void) {
    log_info("Configuring packet gatherer");

    // initialise the code
    initialise();

    // start execution
    log_info("Starting");

    spin1_start(SYNC_NOWAIT);
}

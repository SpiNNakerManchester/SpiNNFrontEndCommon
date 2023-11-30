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
#include <sdp_no_scp.h>

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

//! SDP port commands relating to the Data In protocol
enum sdp_port_commands {
    // received
    //! Data In: Received message describes where to send data
    SDP_SEND_DATA_TO_LOCATION_CMD = 200,
    //! Data In: Received message contains data to write
    SDP_SEND_SEQ_DATA_CMD = 2000,
    //! Data In: Received message asks for missing sequence numbers sent
    SDP_TELL_MISSING_BACK_TO_HOST = 2001,
    //! Data In: Sent message contains missing sequence numbers
    SDP_SEND_MISSING_SEQ_DATA_IN_CMD = 2002,
    //! Data In: Sent message indicates that everything has been received
    SDP_SEND_FINISHED_DATA_IN_CMD = 2003,
    //! Data In: Send from SDRAM address on 0, 0 to target
    SDP_SEND_FROM_SDRAM_CMD = 2004,
    //! Data In: Send from SDRAM, re-trigger response
    SDP_SEND_FROM_SDRAM_CHECK = 2005,
};

//! values for port numbers this core will respond to
enum functionality_to_port_num_map {
    REINJECTION_PORT = 4,     //!< Reinjection control messages
    DATA_SPEED_UP_IN_PORT = 6 //!< Data Speed Up Inbound messages
};

//! threshold for SDRAM vs DTCM when allocating ::received_seq_nums_store
#define SDRAM_VS_DTCM_THRESHOLD 40000

//! Offsets into messages
enum {
    //! \brief location of command IDs in SDP message
    COMMAND_ID = 0,

    //! \brief location of where the seq num is in the packet
    SEQ_NUM_LOC = 0,

    //! \brief location of the transaction id in the packet
    TRANSACTION_ID = 1,

    //! \brief location of the start of raw data in the packet
    START_OF_DATA = 2
};

//! flag when all seq numbers are missing
#define ALL_MISSING_FLAG 0xFFFFFFFE

//! mask needed by router timeout
#define ROUTER_TIMEOUT_MASK 0xFF

//! Misc constants for Data In
enum {
    //! offset with just command transaction id and seq in bytes
    SEND_SEQ_DATA_HEADER_WORDS = 3,
    //! offset with just command, transaction id
    SEND_MISSING_SEQ_HEADER_WORDS = 2,
    //! offset with command, transaction id, address in bytes, [x, y], max seq,
    SEND_DATA_LOCATION_HEADER_WORDS = 5,
    //! absolute maximum size of a SDP message
    ABSOLUTE_MAX_SIZE_OF_SDP_IN_BYTES = 280
};

//! Counts of items in a packet
enum {
    //! \brief size of data stored in packet with command and seq
    //!
    //! defined from calculation
    DATA_IN_NORMAL_PACKET_WORDS =
            ITEMS_PER_DATA_PACKET - SEND_SEQ_DATA_HEADER_WORDS,
    //! \brief size of payload for a packet describing the batch of missing
    //! inbound seqs
    ITEMS_PER_MISSING_PACKET =
            ITEMS_PER_DATA_PACKET - SEND_MISSING_SEQ_HEADER_WORDS,
};

//-----------------------------------------------------------------------------
// TYPES AND GLOBALS
//-----------------------------------------------------------------------------

//! meaning of payload in first data in SDP packet
typedef struct receive_data_to_location_msg_t {
    uint command;        //!< The meaning of the message
    uint transaction_id; //!< The transaction that the message is taking part in
    address_t address;   //!< Where the stream will be writing to in memory
    ushort chip_y;       //!< Board-local y coordinate of chip to do write on
    ushort chip_x;       //!< Board-local x coordinate of chip to do write on
    uint max_seq_num;    //!< Maximum sequence number of data stream
} receive_data_to_location_msg_t;

//! meaning of payload in subsequent data in SDP packets
typedef struct receive_seq_data_msg_t {
    uint command;        //!< The meaning of the message
    uint transaction_id; //!< The transaction that the message is taking part in
    uint seq_num;        //!< The sequence number of this message
    uint data[];         //!< The payload of real data
} receive_seq_data_msg_t;

//! SDP packet payload definition
typedef struct sdp_msg_out_payload_t {
    //! The meaning of the message
    uint command;
    //! The transaction associated with the message
    uint transaction_id;
    //! The payload data of the message
    uint data[ITEMS_PER_MISSING_PACKET];
} sdp_msg_out_payload_t;

//! SDP message to copy from SDRAM
typedef struct sdp_copy_msg_t {
    uint command;              //!< The command of the message
    uint transaction_id;       //!< The transaction that the message is taking part in
    uint base_address_local;   //!< The local base address to copy from
    uint base_address_target;  //!< The target base address to copy to
    ushort target_x;           //!< The x-coordinate of the target chip
    ushort target_y;           //!< The y-coordinate of the target chip
    uint n_values;             //!< The number of values to copy
} sdp_copy_msg_t;

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

//! the SDP tag to use
static uint32_t tag = 0;

//! default seq num
static uint32_t seq_num = FIRST_SEQ_NUM;

//! maximum sequence number
static uint32_t max_seq_num = 0xFFFFFFFF;

//! The Data In transaction ID. Used to distinguish streams of packets
static uint32_t transaction_id = 0;

//! The Data Out transaction ID. Used to distinguish streams of packets
static uint32_t data_out_transaction_id = 0;

//! data holders for the SDP packet (plus 1 to protect against memory
//! overwrites with command messages)
static uint32_t data[ITEMS_PER_DATA_PACKET];

//! index into ::data
static uint32_t position_in_store = 0;

//! If there is a copy in progress (one at a time)
static bool copy_in_progress = false;

static bool copy_msg_valid = false;

//! The copy that is in progress if any (otherwise ignored)
static sdp_copy_msg_t copy_msg;

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

//! Board-relative x-coordinate of current chip being written to
static uint chip_x = 0xFFFFFFF; // Not a legal chip coordinate

//! Board-relative y-coordinate of current chip being written to
static uint chip_y = 0xFFFFFFF; // Not a legal chip coordinate

//! Records what sequence numbers we have received from host during Data In
static bit_field_t received_seq_nums_store = NULL;

//! The size of the bitfield in ::received_seq_nums_store
static uint size_of_bitfield = 0;

//! \brief Whether ::received_seq_nums_store was allocated in SDRAM.
//!
//! If false, the bitfield fitted in DTCM
static bool alloc_in_sdram = false;

//! Count of received sequence numbers.
static uint total_received_seq_nums = 0;

//! The most recently seen sequence number.
static uint last_seen_seq_num = 0;

//! Where the current stream of data started in SDRAM.
static uint start_sdram_address = 0;

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

//! \brief Writes the updated transaction ID to the user1
//! \param[in] transaction_id: The transaction ID to publish
static void publish_transaction_id_to_user_1(int transaction_id) {
// Get pointer to 1st virtual processor info struct in SRAM
    vcpu_t *virtual_processor_table = (vcpu_t*) SV_VCPU;

    // Get the address this core's DTCM data starts at from the user data
    // member of the structure associated with this virtual processor
    virtual_processor_table[spin1_get_core_id()].user1 = transaction_id;
}

//! \brief sends the SDP message built in the ::my_msg global
static inline void send_sdp_message(sdp_msg_pure_data *my_msg, uint n_data_words) {

    my_msg->tag = tag;        // IPTag 1
    my_msg->dest_port = PORT_ETH;        // Ethernet
    my_msg->dest_addr = sv->eth_addr;    // Nearest Ethernet chip

    // fill in SDP source & flag fields
    my_msg->flags = 0x07;
    my_msg->srce_port = 3;
    my_msg->srce_addr = sv->p2p_addr;

    my_msg->length = sizeof(sdp_hdr_t) + n_data_words * sizeof(uint);
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
static inline void send_mc_message(key_offsets command, uint payload) {
    uint key = data_in_mc_key_map[chip_x][chip_y] + command;
    while (spin1_send_mc_packet(key, payload, WITH_PAYLOAD) == 0) {
        spin1_delay_us(MESSAGE_DELAY_TIME_WHEN_FAIL);
    }
}

//! \brief Sanity checking for writes, ensuring that they're to the _buffered_
//! SDRAM range.
//!
//! Note that the RTE here is good as it is better (easier to debug, easier to
//! comprehend) than having corrupt memory actually written.
//!
//! \param[in] write_address: where we are going to write.
//! \param[in] n_elements: the number of words we are going to write.
static inline void sanity_check_write(uint write_address, uint n_elements) {
    // determine size of data to send
    log_debug("Writing %u elements to 0x%08x", n_elements, write_address);

    uint end_ptr = write_address + n_elements * sizeof(uint);
    if (write_address < SDRAM_BASE_BUF || end_ptr >= SDRAM_BASE_UNBUF ||
            end_ptr < write_address) {
        log_error("bad write range 0x%08x-0x%08x", write_address, end_ptr);
        rt_error(RTE_SWERR);
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
static void process_sdp_message_into_mc_messages(
        const uint *data, uint n_elements, bool set_write_address,
        uint write_address) {
    // send mc message with SDRAM location to correct chip
    if (set_write_address) {
        send_mc_message(WRITE_ADDR_KEY_OFFSET, write_address);
    }

    // send mc messages containing rest of sdp data
    for (uint data_index = 0; data_index < n_elements; data_index++) {
        log_debug("data is %d", data[data_index]);
        send_mc_message(DATA_KEY_OFFSET, data[data_index]);
    }
}

//! \brief creates a store for sequence numbers in a memory store.
//!
//! May allocate in either DTCM (preferred) or SDRAM.
//!
//! \param[in] max_seq: the max seq num expected during this stage
static void create_sequence_number_bitfield(uint max_seq) {
    if (received_seq_nums_store != NULL) {
        log_error("Allocating seq num store when already one exists at 0x%08x",
                received_seq_nums_store);
        rt_error(RTE_SWERR);
    }
    size_of_bitfield = get_bit_field_size(max_seq + 1);
    if (max_seq_num != max_seq) {
        max_seq_num = max_seq;
        alloc_in_sdram = false;
        if (max_seq_num >= SDRAM_VS_DTCM_THRESHOLD || (NULL ==
                (received_seq_nums_store = spin1_malloc(
                        size_of_bitfield * sizeof(uint32_t))))) {
            received_seq_nums_store = sark_xalloc(
                    sv->sdram_heap, size_of_bitfield * sizeof(uint32_t), 0,
                    ALLOC_LOCK | ALLOC_ID | (sark_vec->app_id << 8));
            if (received_seq_nums_store == NULL) {
                log_error(
                        "Failed to allocate %u bytes for missing seq num store",
                        size_of_bitfield * sizeof(uint32_t));
                rt_error(RTE_SWERR);
            }
            alloc_in_sdram = true;
        }
    }
    log_debug("clearing bit field");
    clear_bit_field(received_seq_nums_store, size_of_bitfield);
}

//! \brief Frees the allocated sequence number store.
static inline void free_sequence_number_bitfield(void) {
    if (received_seq_nums_store == NULL) {
        log_error("Freeing a non-existent seq num store");
        rt_error(RTE_SWERR);
    }
    if (alloc_in_sdram) {
        sark_xfree(sv->sdram_heap, received_seq_nums_store,
                ALLOC_LOCK | ALLOC_ID | (sark_vec->app_id << 8));
    } else {
        sark_free(received_seq_nums_store);
    }
    received_seq_nums_store = NULL;
    max_seq_num = 0xFFFFFFFF;
}

//! \brief calculates the new sdram location for a given seq num
//! \param[in] seq_num: the seq num to figure offset for
//! \return the new sdram location.
static inline uint calculate_sdram_address_from_seq_num(uint seq_num) {
    return (start_sdram_address
            + (DATA_IN_NORMAL_PACKET_WORDS * seq_num * sizeof(uint)));
}

//! \brief handles reading the address, chips and max packets from a
//! SDP message (command: ::SDP_SEND_DATA_TO_LOCATION_CMD)
//! \param[in] receive_data_cmd: The message to parse
static void process_address_data(
        const receive_data_to_location_msg_t *receive_data_cmd) {
    // if received when doing a stream. ignore as either clone or oddness
    if (received_seq_nums_store != NULL) {
        log_debug(
                "received location message with transaction id %d when "
                "already processing stream with transaction id %d",
                receive_data_cmd->transaction_id, transaction_id);
        return;
    }

    // updater transaction id if it hits the cap
    if (((transaction_id + 1) & TRANSACTION_CAP) == 0) {
        transaction_id = 0;
        publish_transaction_id_to_user_1(transaction_id);
    }

    // if transaction id is not as expected. ignore it as its from the past.
    // and worthless
    if (receive_data_cmd->transaction_id != transaction_id + 1) {
        log_debug(
                "received location message with unexpected "
                "transaction id %d; mine is %d",
                receive_data_cmd->transaction_id, transaction_id + 1);
        return;
    }

    //extract transaction id and update
    transaction_id = receive_data_cmd->transaction_id;
    publish_transaction_id_to_user_1(transaction_id);

    // track changes
    uint prev_x = chip_x, prev_y = chip_y;

    // update sdram and tracker as now have the sdram and size
    chip_x = receive_data_cmd->chip_x;
    chip_y = receive_data_cmd->chip_y;

    if (prev_x != chip_x || prev_y != chip_y) {
        log_debug(
                "Changed stream target chip to %d,%d for transaction id %d",
                chip_x, chip_y, transaction_id);
    }

    log_debug("Writing %u packets to 0x%08x for transaction id %d",
             receive_data_cmd->max_seq_num + 1, receive_data_cmd->address,
             transaction_id);

    // store where the sdram started, for out-of-order UDP packets.
    start_sdram_address = (uint) receive_data_cmd->address;

    // allocate location for holding the seq numbers
    create_sequence_number_bitfield(receive_data_cmd->max_seq_num);
    total_received_seq_nums = 0;
    prov.n_in_streams++;
    sdram_prov->n_in_streams = prov.n_in_streams;

    // set start of last seq number
    last_seen_seq_num = 0;
}

//! \brief sends the finished request
static void send_finished_response(void) {
    // send boundary key, so that monitor knows everything in the previous
    // stream is done
    sdp_msg_pure_data my_msg;
    sdp_msg_out_payload_t *payload = (sdp_msg_out_payload_t *) my_msg.data;
    send_mc_message(BOUNDARY_KEY_OFFSET, 0);
    payload->command = SDP_SEND_FINISHED_DATA_IN_CMD;
    payload->transaction_id = transaction_id;
    send_sdp_message(&my_msg, SEND_MISSING_SEQ_HEADER_WORDS);
    log_debug("Sent end flag");
}

//! \brief searches through received sequence numbers and transmits missing ones
//! back to host for retransmission
//! \param[in] msg: The message asking for the missed seq nums
static void process_missing_seq_nums_and_request_retransmission(
        const sdp_msg_pure_data *msg) {
    // verify in right state
    uint this_message_transaction_id = msg->data[TRANSACTION_ID];
    if (received_seq_nums_store == NULL &&
            this_message_transaction_id != transaction_id) {
        log_debug(
            "received missing seq numbers before a location with a "
            "transaction id which is stale.");
        return;
    }
    if (received_seq_nums_store == NULL &&
            this_message_transaction_id == transaction_id) {
        log_debug("received tell request when already sent finish. resending");
        send_finished_response();
        return;
    }

    // check that missing seq transmission is actually needed, or
    // have we finished
    if (total_received_seq_nums == max_seq_num + 1) {
        free_sequence_number_bitfield();
        total_received_seq_nums = 0;
        send_finished_response();
        return;
    }

    sdp_msg_pure_data my_msg;
    sdp_msg_out_payload_t *payload = (sdp_msg_out_payload_t *) my_msg.data;
    payload->transaction_id = transaction_id;

    // sending missing seq nums
    log_debug("Looking for %d missing packets",
            ((int) max_seq_num + 1) - ((int) total_received_seq_nums));
    payload->command = SDP_SEND_MISSING_SEQ_DATA_IN_CMD;

    // handle case of all missing
    if (total_received_seq_nums == 0) {
        // send response
        payload->data[0] = ALL_MISSING_FLAG;
        send_sdp_message(&my_msg, SEND_MISSING_SEQ_HEADER_WORDS + 1);
        return;
    }

    // handle a random number of missing seqs
    uint data_index = 0;
    for (uint bit = 0; bit <= max_seq_num; bit++) {
        if (bit_field_test(received_seq_nums_store, bit)) {
            continue;
        }

        payload->data[data_index++] = bit;
        if (data_index >= ITEMS_PER_MISSING_PACKET) {
            send_sdp_message(&my_msg, data_index + SEND_MISSING_SEQ_HEADER_WORDS);
            data_index = 0;
        }
    }

    // send final message if required
    if (data_index > 0) {
        send_sdp_message(&my_msg, data_index + SEND_MISSING_SEQ_HEADER_WORDS);
    }
}

//! \brief Calculates the number of words of data in an SDP message.
//! \param[in] msg: the SDP message, as received from SARK
//! \param[in] data_start: where in the message the data actually starts
//! \return the number of data words in the message
static inline uint n_elements_in_msg(
        const sdp_msg_pure_data *msg, const uint *data_start) {
    // Offset in bytes from the start of the SDP message to where the data is
    uint offset = ((uint8_t *) data_start) - &msg->flags;
    return (msg->length - offset) / sizeof(uint);
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

//! \brief Handles receipt and parsing of a message full of sequence numbers
//! that need to be retransmitted (command: ::SDP_SEND_SEQ_DATA_CMD)
//! \param[in] msg: The message to parse (really of type receive_seq_data_msg_t)
static inline void receive_seq_data(const sdp_msg_pure_data *msg) {
    // cast to the receive seq data
    const receive_seq_data_msg_t *receive_data_cmd =
            (receive_seq_data_msg_t *) msg->data;

    // check for bad states
    if (received_seq_nums_store == NULL) {
        log_debug("received data before being given a location");
        return;
    }
    if (receive_data_cmd->transaction_id != transaction_id) {
        log_debug("received data from a different transaction");
        return;
    }

    // all good, process data
    uint seq = receive_data_cmd->seq_num;
    log_debug("Sequence data, seq:%u", seq);
    if (seq > max_seq_num) {
        log_error("Bad sequence number %u when max is %u!", seq, max_seq_num);
        return;
    }

    uint this_sdram_address = calculate_sdram_address_from_seq_num(seq);
    bool send_sdram_address = (last_seen_seq_num != seq - 1);

    if (!bit_field_test(received_seq_nums_store, seq)) {
        bit_field_set(received_seq_nums_store, seq);
        total_received_seq_nums++;
    }
    last_seen_seq_num = seq;

    uint n_elements = n_elements_in_msg(msg, receive_data_cmd->data);
    log_debug("n elements is %d", n_elements);
    sanity_check_write(this_sdram_address, n_elements);
    if (chip_x == 0 && chip_y == 0) {
        // directly write the data to where it belongs
        for (uint data_index = 0; data_index < n_elements; data_index++) {
            log_debug("data is %x", receive_data_cmd->data[data_index]);
        }
        copy_data(
                (address_t) this_sdram_address, receive_data_cmd->data,
                n_elements);
    } else {
        // transmit data to chip; the data lasts to the end of the message
        process_sdp_message_into_mc_messages(
                receive_data_cmd->data, n_elements,
                send_sdram_address, this_sdram_address);
    }
}

static void send_rc_code(uint rc_code, uint transaction_id) {
    sdp_msg_pure_data my_msg;
    my_msg.data[0] = rc_code;
    my_msg.data[1] = transaction_id;
    send_sdp_message(&my_msg, 2);
}

static void send_from_sdram_check(sdp_copy_msg_t *msg) {
    log_debug("Copy progress check for transaction %u, potential in progress %u...",
            msg->transaction_id, copy_msg.transaction_id);
    if (!copy_in_progress && (msg->transaction_id == copy_msg.transaction_id)) {
        log_debug("Sending OK now!");
        send_rc_code(SDP_SEND_FINISHED_DATA_IN_CMD, msg->transaction_id);
    }
}

void do_sdram_sends(UNUSED uint unused0, UNUSED uint unused1) {
    log_debug("Starting copy of %u words from from 0x%08x locally to 0x%08x"
            " on %u, %u for transaction %u",
            copy_msg.n_values, copy_msg.base_address_local, copy_msg.base_address_target,
            copy_msg.target_x, copy_msg.target_y, copy_msg.transaction_id);
    if (copy_msg.target_x == 0 && copy_msg.target_y == 0) {
        copy_data((uint *) copy_msg.base_address_target,
                (uint *) copy_msg.base_address_local, copy_msg.n_values);
    } else {
        chip_x = copy_msg.target_x;
        chip_y = copy_msg.target_y;
        process_sdp_message_into_mc_messages((uint *) copy_msg.base_address_local,
                copy_msg.n_values, true, copy_msg.base_address_target);
    }
    log_debug("Sending OK response for transaction %u", copy_msg.transaction_id);
    copy_in_progress = false;
    send_from_sdram_check(&copy_msg);
}

static void send_from_sdram(const sdp_msg_pure_data *msg) {
    sdp_copy_msg_t *copy_msg_ptr = (sdp_copy_msg_t *) msg->data;

    // Can't to if already copying
    if (copy_in_progress) {
        if (copy_msg_ptr->transaction_id != copy_msg.transaction_id) {
            // Trying to start a new transaction = fail
            log_debug("Copy in progress on transaction %u, rejecting %u",
                    copy_msg.transaction_id, copy_msg_ptr->transaction_id);
            send_rc_code(RC_P2P_BUSY, copy_msg_ptr->transaction_id);
            return;
        } else {
            // Trying to start the same transaction = missed finished message
            log_debug("Resending Done for transaction %u", copy_msg_ptr->transaction_id);
            send_rc_code(RC_OK, copy_msg_ptr->transaction_id);
            return;
        }
    } else if (copy_msg_valid && copy_msg_ptr->transaction_id == copy_msg.transaction_id) {
        // Already done it but not recognised!
        send_from_sdram_check(copy_msg_ptr);
        return;
    }
    copy_in_progress = true;
    copy_msg_valid = true;
    copy_msg = *copy_msg_ptr;
    log_debug("Scheduling copy of %u words from from 0x%08x locally to 0x%08x"
            " on %u, %u for transaction %u",
            copy_msg.n_values, copy_msg.base_address_local, copy_msg.base_address_target,
            copy_msg.target_x, copy_msg.target_y, copy_msg.transaction_id);
    spin1_schedule_callback(do_sdram_sends, 0, 0, 1);
    send_rc_code(RC_OK, copy_msg_ptr->transaction_id);
    return;
}

//! \brief processes SDP messages for the Data In protocol
//! \param[in] msg: the SDP message
static void data_in_receive_sdp_data(const sdp_msg_pure_data *msg) {
    uint command = msg->data[COMMAND_ID];
    prov.n_sdp_recvd++;
    sdram_prov->n_sdp_recvd = prov.n_sdp_recvd;

    // check for separate commands
    switch (command) {
    case SDP_SEND_DATA_TO_LOCATION_CMD:
        // translate elements to variables
        process_address_data((receive_data_to_location_msg_t *) msg->data);
        break;
    case SDP_SEND_SEQ_DATA_CMD:
        receive_seq_data(msg);
        break;
    case SDP_TELL_MISSING_BACK_TO_HOST:
        log_debug("Checking for missing");
        process_missing_seq_nums_and_request_retransmission(msg);
        break;
    case SDP_SEND_FROM_SDRAM_CMD:
        send_from_sdram(msg);
        break;
    case SDP_SEND_FROM_SDRAM_CHECK:
        send_from_sdram_check((sdp_copy_msg_t *) msg->data);
        break;
    default:
        log_error("Failed to recognise command id %u", command);
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

//! \brief processes SDP messages
//! \param[in,out] mailbox: the SDP message; will be _freed_ by this call!
//! \param[in] port: the port associated with this SDP message
static void receive_sdp_message(uint mailbox, uint port) {
    switch (port) {
    case REINJECTION_PORT:
        reinjection_sdp_command((sdp_msg_t *) mailbox);
        break;
    case DATA_SPEED_UP_IN_PORT:
        data_in_receive_sdp_data((sdp_msg_pure_data *) mailbox);
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
            log_debug("sending surplus data from new seq setting");
            send_data();
        }

        log_debug("new seq num to set is %d", payload);
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

    // load user 1 in case this is a consecutive load
    publish_transaction_id_to_user_1(transaction_id);
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

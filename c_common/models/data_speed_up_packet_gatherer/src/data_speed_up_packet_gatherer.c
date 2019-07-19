/*
 * Copyright (c) 2017-2019 The University of Manchester
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

//! imports
#include "spin1_api.h"
#include "common-typedefs.h"
#include <data_specification.h>
#include <simulation.h>
#include <debug.h>
#include <bit_field.h>

//-----------------------------------------------------------------------------
// MAGIC NUMBERS
//-----------------------------------------------------------------------------

//! timeout used in sending SDP messages
#define SDP_TIMEOUT 100

 //! whatever SDP flags do
#define SDP_FLAGS 0x07

 //! the source port for the SDP messages. possibly used by host
#define SDP_SOURCE_PORT 3

 //! the time to wait before trying again to send a message (MC, SDP)
#define MESSAGE_DELAY_TIME_WHEN_FAIL 1

//! How many multicast packets are to be received per SDP packet
#define ITEMS_PER_DATA_PACKET 68

//! first sequence number to use and reset to
#define FIRST_SEQ_NUM 0

// max id needed to cover the chips in either direction on a spinn-5 board
#define MAX_CHIP_ID 8

//! size of total missing seq packets as elements
#define TOTAL_MISSING_SEQ_PACKETS_IN_ELEMENTS 1

// bit shift to find x coord from the chip int in sdp message
#define BIT_SHIFT_CHIP_X_COORD 16

// mask for getting y coord from the chip int in sdp message
#define BIT_MASK_FOR_CHIP_Y_COORD 0x0000FFFF

// sdp port commands received
enum sdp_port_commands {
    // received
    SDP_SEND_DATA_TO_LOCATION_CMD = 200,
    SDP_SEND_SEQ_DATA_CMD = 2000,
    SDP_SEND_MISSING_SEQ_NUMS_BACK_TO_HOST_CMD = 2001,
    SDP_LAST_DATA_IN_CMD = 2002,
    // sent
    SDP_SEND_FIRST_MISSING_SEQ_DATA_IN_CMD = 2003,
    SDP_SEND_MISSING_SEQ_DATA_IN_CMD = 2004,
    SDP_SEND_FINISHED_DATA_IN_CMD = 2005
};

// threshold for sdram vs dtcm missing seq store.
#define SDRAM_VS_DTCM_THRESHOLD 40000

// location of command ids in sdp message
#define COMMAND_ID 0

//! offset with just command and seq in bytes
#define SEND_SEQ_DATA_HEADER_WORDS 2

//! offset with command, x, y, address in bytes
#define SEND_DATA_LOCATION_HEADER_WORDS 4

//! size of data stored in packet with command and address
//! defined from calculation:
#define DATA_IN_ADDRESS_PACKET_WORDS \
    (ITEMS_PER_DATA_PACKET - SEND_DATA_LOCATION_HEADER_WORDS)

//! size of data stored in packet with command and seq
//! defined from calculation:
#define DATA_IN_NORMAL_PACKET_WORDS \
    (ITEMS_PER_DATA_PACKET - SEND_SEQ_DATA_HEADER_WORDS)

//! size of payload for a packet describing the first batch of missing inbound seqs
#define ITEMS_PER_FIRST_MISSING_PACKET \
    (ITEMS_PER_DATA_PACKET - 2)

//! size of payload for a packet describing the further batches of missing inbound seqs
#define ITEMS_PER_MORE_MISSING_PACKET \
    (ITEMS_PER_DATA_PACKET - 1)

//-----------------------------------------------------------------------------
// TYPES AND GLOBALS
//-----------------------------------------------------------------------------

//! struct for a SDP message with pure data, no SCP header
typedef struct sdp_msg_pure_data {	// SDP message (=292 bytes)
    struct sdp_msg *next;	// Next in free list
    uint16_t length;		// length
    uint16_t checksum;		// checksum (if used)

    // sdp_hdr_t
    // The length field measures from HERE...
    uint8_t flags;	    	// SDP flag byte
    uint8_t tag;		    // SDP IPtag
    uint8_t dest_port;		// SDP destination port/CPU
    uint8_t srce_port;		// SDP source port/CPU
    uint16_t dest_addr;		// SDP destination address
    uint16_t srce_addr;		// SDP source address

    // User data (272 bytes when no SCP header)
    uint32_t data[ITEMS_PER_DATA_PACKET];

    uint32_t _PAD;		// Private padding
} sdp_msg_pure_data;

//! meaning of payload in first data in SDP packet
typedef struct receive_data_to_location_msg_t {
    uint command;
    address_t address;
    ushort chip_y;
    ushort chip_x;
    uint max_seq_num;
    uint data[];
} receive_data_to_location_msg_t;

//! meaning of payload in subsequent data in SDP packets
typedef struct receive_seq_data_msg_t {
    uint command;
    uint seq_num;
    uint data[];
} receive_seq_data_msg_t;

typedef union sdp_msg_out_payload_t {
    uint command;
    struct {
        uint command;
        uint n_packets;
        uint data[ITEMS_PER_FIRST_MISSING_PACKET];
    } first;
    struct {
        uint command;
        uint data[ITEMS_PER_MORE_MISSING_PACKET];
    } more;
} sdp_msg_out_payload_t;

//! control value, which says how many timer ticks to run for before exiting
static uint32_t simulation_ticks = 0;
static uint32_t infinite_run = 0;
static uint32_t timer = 0;

//! the key that causes sequence number to be processed
static uint32_t new_sequence_key = 0;
static uint32_t first_data_key = 0;
static uint32_t end_flag_key = 0;

//! default seq num
static uint32_t seq_num = FIRST_SEQ_NUM;
static uint32_t max_seq_num = 0;

//! data holders for the SDP packet
static uint32_t data[ITEMS_PER_DATA_PACKET];
static uint32_t position_in_store = 0;

//! SDP message holder for transmissions
static sdp_msg_pure_data my_msg;

//! human readable definitions of each region in SDRAM
typedef enum regions_e {
    SYSTEM_REGION,
    CONFIG,
    CHIP_TO_KEY
} regions_e;

//! human readable definitions of the data in each region
typedef struct data_out_config_t {
    uint new_seq_key;
    uint first_data_key;
    uint end_flag_key;
    uint tag_id;
} data_out_config_t;

//! values for the priority for each callback
typedef enum callback_priorities {
    MC_PACKET = -1,
    SDP = 0,
    DMA = 0,
    TIMER = 1
} callback_priorities;

// Note that these addresses are *board-local* chip addresses.
static uint data_in_mc_key_map[MAX_CHIP_ID][MAX_CHIP_ID] = {{0}};
static uint chip_x = 0xFFFFFFF; // Not a legal chip coordinate
static uint chip_y = 0xFFFFFFF; // Not a legal chip coordinate

static bit_field_t received_seq_nums_store = NULL;
static uint size_of_bitfield = 0;
static bool alloc_in_sdram = false;

static uint total_received_seq_nums = 0;
static uint last_seen_seq_num = 0;
static uint start_sdram_address = 0;

// Timeout control
static uint time, wait_until;
#define TIMER_INTERVAL 1000
#define TIMEOUT 33

//! Human readable definitions of the offsets for multicast key elements.
//! These act as commands sent to the target extra monitor core.
typedef enum key_offsets {
    WRITE_ADDR_KEY_OFFSET = 0,
    DATA_KEY_OFFSET = 1,
    BOUNDARY_KEY_OFFSET = 2
} key_offsets;

typedef struct data_in_config_t {
    uint32_t n_chips;
    struct chip_key_data_t {
        uint32_t x_coord;
        uint32_t y_coord;
        uint32_t base_key;
    } chip_to_key[];
} data_in_config_t;

//-----------------------------------------------------------------------------
// FUNCTIONS
//-----------------------------------------------------------------------------

//! \brief sends the SDP message built in the my_msg global
static inline void send_sdp_message(void) {
    log_debug("sending message of length %u", my_msg.length);
    while (!spin1_send_sdp_msg((sdp_msg_t *) &my_msg, SDP_TIMEOUT)) {
        log_error("failed to send SDP message");
        spin1_delay_us(MESSAGE_DELAY_TIME_WHEN_FAIL);
    }
}

//! \brief sends a multicast (with payload) message to the current target chip
//! \param[in] command: the key offset, which indicates the command being sent
//! \param[in] payload: the argument to the command
static inline void send_mc_message(uint command, uint payload) {
    uint key = data_in_mc_key_map[chip_x][chip_y] + command;
    while (spin1_send_mc_packet(key, payload, WITH_PAYLOAD) == 0) {
        spin1_delay_us(MESSAGE_DELAY_TIME_WHEN_FAIL);
    }
}

static inline void sanity_check_write(uint write_address, uint n_elements) {
    // determine size of data to send
    log_debug("Writing %u elements to 0x%08x", n_elements, write_address);

    uint end_ptr = write_address + n_elements * sizeof(uint);
    if (write_address < SDRAM_BASE_BUF || end_ptr >= SDRAM_BASE_UNBUF) {
        log_error("bad write range 0x%08x-0x%08x", write_address, end_ptr);
        rt_error(RTE_SWERR);
    }
}

//! \brief sends multicast messages accordingly for an SDP message
//! \param[in] data: the actual data from the SDP message
//! \param[in] n_elements: the number of data items in the SDP message
//! \param[in] set_write_address: bool flag for if we should send the
//                                address where our writes will start;
//                                this is not set every time to reduce
//                                on-chip network overhead
//! \param[in] write_address: the sdram address where this block of data is
//                            to be written to
static void process_sdp_message_into_mc_messages(
        const uint *data, uint n_elements, bool set_write_address,
        uint write_address) {
    // send mc message with SDRAM location to correct chip
    if (set_write_address) {
        send_mc_message(WRITE_ADDR_KEY_OFFSET, write_address);
    }

    // send mc messages containing rest of sdp data
    for (uint data_index = 0; data_index < n_elements; data_index++) {
        send_mc_message(DATA_KEY_OFFSET, data[data_index]);
    }
}

//! \brief creates a store for seq nums in a memory store.
//! \param[in] max_seq: the max seq num expected during this stage
static void create_sequence_number_bitfield(uint max_seq) {
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

static inline void free_sequence_number_bitfield(void) {
    if (alloc_in_sdram) {
        sark_xfree(sv->sdram_heap, received_seq_nums_store,
                ALLOC_LOCK | ALLOC_ID | (sark_vec->app_id << 8));
    } else {
        sark_free(received_seq_nums_store);
    }
    received_seq_nums_store = NULL;
    max_seq_num = 0;
}

//! \brief determines how many packets will be needed to describe missing seqs.
static inline uint data_in_n_missing_seq_packets(void) {
    uint received = count_bit_field(received_seq_nums_store, size_of_bitfield);
    uint missing_seq_count = max_seq_num - received;
    if (missing_seq_count < ITEMS_PER_FIRST_MISSING_PACKET) {
        return 0;
    }
    missing_seq_count -= ITEMS_PER_FIRST_MISSING_PACKET;
    const uint denom = ITEMS_PER_MORE_MISSING_PACKET;
    uint num = missing_seq_count / denom, rem = missing_seq_count % denom;
    return num + (rem > 0 ? 1 : 0);
}

//! \brief calculates the new sdram location for a given seq num
//! \param[in] seq_num: the seq num to figure offset for
//! \return the new sdram location.
static inline uint calculate_sdram_address_from_seq_num(uint seq_num) {
    if (seq_num == 0) {
        return start_sdram_address;
    }

    return start_sdram_address
            + (DATA_IN_ADDRESS_PACKET_WORDS
                    + DATA_IN_NORMAL_PACKET_WORDS * (seq_num - 1))
                    * sizeof(uint);
}

static inline void schedule_timeout(void) {
    wait_until = time + TIMEOUT;
    log_debug("scheduled timeout for %u (now %u)", wait_until, time);
}

static inline void cancel_timeout(void) {
    wait_until = 0;
}

static inline void set_message_length(const void *end) {
    my_msg.length = ((const uint8_t *) end) - &my_msg.flags;
    if (my_msg.length > 272) {
        log_error("bad message length %u", my_msg.length);
    }
}

//! \brief searches through received seq nums and transmits missing ones back
//! to host for retransmission
static void process_missing_seq_nums_and_request_retransmission(void) {
    //! \brief Used to guard access to the received_seq_nums_store from this
    //!   function; it counts the number of running calls to this function.
    //!   Access to this variable is only allowed when you have disabled
    //!   interrupts!
    static uint access_lock = 0;

    uint sr;
    sr = spin1_irq_disable();
    if (++access_lock > 1) {
        access_lock--;
        spin1_mode_restore(sr);
        return;
    } else if (received_seq_nums_store == NULL) {
        access_lock--;
        spin1_mode_restore(sr);
        return;
    }
    spin1_mode_restore(sr);

    sdp_msg_out_payload_t *payload = (sdp_msg_out_payload_t *) my_msg.data;

    // check that missing seq transmission is actually needed, or
    // have we finished
    if (total_received_seq_nums == max_seq_num) {
        free_sequence_number_bitfield();
        sr = spin1_irq_disable();
        access_lock--;
        spin1_mode_restore(sr);

        // send boundary key, so that monitor knows everything in the previous
        // stream is done
        send_mc_message(BOUNDARY_KEY_OFFSET, 0);
        payload->command = SDP_SEND_FINISHED_DATA_IN_CMD;
        my_msg.length = sizeof(sdp_hdr_t) + sizeof(int);
        send_sdp_message();
        log_info("Sent end flag");
        return;
    }

    // sending missing seq nums
    log_info("Looking for %d missing packets",
            ((int) max_seq_num) - ((int) total_received_seq_nums));
    const uint *data_start, *end_of_buffer = (uint *) (payload + 1);
    uint *data_ptr;
    payload->first.command = SDP_SEND_FIRST_MISSING_SEQ_DATA_IN_CMD;
    payload->first.n_packets = data_in_n_missing_seq_packets();
    data_start = data_ptr = payload->first.data;
    for (uint bit = 1; bit <= max_seq_num; bit++) {
        if (bit_field_test(received_seq_nums_store, bit)) {
            continue;
        }

        *(data_ptr++) = bit;
        if (data_ptr >= end_of_buffer) {
            set_message_length(data_ptr);
            send_sdp_message();
            payload->more.command = SDP_SEND_MISSING_SEQ_DATA_IN_CMD;
            data_start = data_ptr = payload->more.data;
        }
    }

    sr = spin1_irq_disable();
    access_lock--;
    spin1_mode_restore(sr);

    // send final message if required
    if (data_ptr > data_start) {
        set_message_length(data_ptr);
        send_sdp_message();
    }
}

//! \brief Calculates the number of words of data in an SDP message.
//! \param[in] msg: the SDP message, as received from SARK
//! \param[in] data_start: where in the message the data actually starts
static inline uint n_elements_in_msg(
        const sdp_msg_pure_data *msg, const uint *data_start) {
    // Offset in bytes from the start of the SDP message to where the data is
    uint offset = ((uint8_t *) data_start) - &msg->flags;
    return (msg->length - offset) / sizeof(uint);
}

//! \brief because spin1_memcpy is stupid, especially for access to SDRAM
static inline void copy_data(void *target, const void *source, uint n_words) {
    uint *to = target;
    const uint *from = source;
    while (n_words-- > 0) {
        *to++ = *from++;
    }
}

static inline void receive_data_to_location(const sdp_msg_pure_data *msg) {
    const receive_data_to_location_msg_t *receive_data_cmd =
            (receive_data_to_location_msg_t *) msg->data;

    // translate elements to variables
    uint prev_x = chip_x, prev_y = chip_y;
    chip_x = receive_data_cmd->chip_x;
    chip_y = receive_data_cmd->chip_y;
    if (prev_x != chip_x || prev_y != chip_y) {
        log_info("Changed stream target chip to %d,%d", chip_x, chip_y);
    }
    log_info("Writing %u packets to 0x%08x",
            receive_data_cmd->max_seq_num, receive_data_cmd->address);

    // allocate location for holding the seq numbers
    create_sequence_number_bitfield(receive_data_cmd->max_seq_num);
    total_received_seq_nums = 0;

    // set start of last seq number
    last_seen_seq_num = 0;
    // store where the sdram started, for out-of-order UDP packets.
    start_sdram_address = (uint) receive_data_cmd->address;

    uint n_elements = n_elements_in_msg(msg, receive_data_cmd->data);
    sanity_check_write((uint) receive_data_cmd->address, n_elements);
    if (chip_x == 0 && chip_y == 0) {
        // directly write the data to where it belongs
        copy_data(receive_data_cmd->address, receive_data_cmd->data, n_elements);
    } else {
        // send start key, so that monitor knows everything in the previous stream is done
        send_mc_message(BOUNDARY_KEY_OFFSET, 0);
        // send mc messages for first packet; the data lasts to the end of the
        // message
        process_sdp_message_into_mc_messages(
                receive_data_cmd->data, n_elements, true, start_sdram_address);
    }
}

static inline void receive_seq_data(const sdp_msg_pure_data *msg) {
    const receive_seq_data_msg_t *receive_data_cmd =
            (receive_seq_data_msg_t *) msg->data;
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
    sanity_check_write(this_sdram_address, n_elements);
    if (chip_x == 0 && chip_y == 0) {
        // directly write the data to where it belongs
        copy_data((address_t) this_sdram_address, receive_data_cmd->data, n_elements);
    } else {
        // transmit data to chip; the data lasts to the end of the message
        process_sdp_message_into_mc_messages(
                receive_data_cmd->data, n_elements,
                send_sdram_address, this_sdram_address);
    }
}

static void check_for_timeout(uint unused0, uint unused1) {
    use(unused0);
    use(unused1);
    if (wait_until != 0 && ++time > wait_until) {
        log_info("Timed out; checking for missing anyway");
        cancel_timeout();
        process_missing_seq_nums_and_request_retransmission();
    }
}

//! \brief processes sdp messages
//! \param[in] mailbox: the sdp message
//! \param[in] port: the port associated with this sdp message
static void data_in_receive_sdp_data(uint mailbox, uint port) {
    // use as not important
    use(port);

    // convert mailbox into correct sdp format
    sdp_msg_pure_data *msg = (sdp_msg_pure_data *) mailbox;
    uint command = msg->data[COMMAND_ID];

    // check for separate commands
    switch (command) {
    case SDP_SEND_DATA_TO_LOCATION_CMD:
        // Stop timeouts while doing synchronous message processing
        cancel_timeout();
        receive_data_to_location(msg);
        // Schedule a timeout for if all subsequent messages go missing
        schedule_timeout();
        break;
    case SDP_SEND_SEQ_DATA_CMD:
        // Stop timeouts while doing synchronous message processing
        cancel_timeout();
        receive_seq_data(msg);
        // Schedule a timeout for if all subsequent messages go missing
        schedule_timeout();
        break;
    case SDP_SEND_MISSING_SEQ_NUMS_BACK_TO_HOST_CMD:
        log_debug("Checking for missing");
        cancel_timeout();
        process_missing_seq_nums_and_request_retransmission();
        break;
    case SDP_LAST_DATA_IN_CMD:
        log_debug("Received final flag");
        cancel_timeout();
        process_missing_seq_nums_and_request_retransmission();
        break;
    default:
        log_error("Failed to recognise command id %u", command);
    }

    // free the message to stop overload
    spin1_msg_free((sdp_msg_t *) msg);
}

static void send_data(void) {
    copy_data(&my_msg.data, data, position_in_store);
    my_msg.length = sizeof(sdp_hdr_t) + position_in_store * sizeof(uint);

    if (seq_num > max_seq_num) {
        log_error("Got a funky seq num in sending; max is %d, received %d",
                max_seq_num, seq_num);
    }

    send_sdp_message();

    position_in_store = 1;
    seq_num++;
    data[0] = seq_num;
}

static void receive_data(uint key, uint payload) {
    if (key == new_sequence_key) {
        if (position_in_store != 1) {
            send_data();
        }
        data[0] = payload;
        seq_num = payload;
        position_in_store = 1;

        if (payload > max_seq_num) {
            log_error("Got a funky seq num; max is %d, received %d",
                    max_seq_num, payload);
        }
    } else {
        data[position_in_store] = payload;
        position_in_store++;

        if (key == first_data_key) {
            seq_num = FIRST_SEQ_NUM;
            data[0] = seq_num;
            position_in_store = 1;
            max_seq_num = payload;
        }

        if (key == end_flag_key) {
            // set end flag bit in seq num
            data[0] |= 1 << 31;

            // adjust size as last payload not counted
            position_in_store--;

            send_data();
        } else if (position_in_store == ITEMS_PER_DATA_PACKET) {
            send_data();
        }
    }
}

static void initialise(void) {
    // Get the address this core's DTCM data starts at from SRAM
    data_specification_metadata_t *ds_regions =
            data_specification_get_data_address();

    // Read the header
    if (!data_specification_read_header(ds_regions)) {
        log_error("Failed to read the data spec header");
        rt_error(RTE_SWERR);
    }

    // Get the timing details and set up the simulation interface
    uint32_t dummy;
    if (!simulation_initialise(
            data_specification_get_region(SYSTEM_REGION, ds_regions),
            APPLICATION_NAME_HASH, &dummy, &simulation_ticks,
            &infinite_run, &timer, SDP, DMA)) {
        rt_error(RTE_SWERR);
    }

    log_info("Initialising data out");

    data_out_config_t *config = (data_out_config_t *)
            data_specification_get_region(CONFIG, ds_regions);
    new_sequence_key = config->new_seq_key;
    first_data_key = config->first_data_key;
    end_flag_key = config->end_flag_key;

    my_msg.tag = config->tag_id;    	// IPTag 1
    my_msg.dest_port = PORT_ETH;		// Ethernet
    my_msg.dest_addr = sv->eth_addr;		// Nearest Ethernet chip

    // fill in SDP source & flag fields
    my_msg.flags = 0x07;
    my_msg.srce_port = 3;
    my_msg.srce_addr = sv->p2p_addr;

    spin1_callback_on(FRPL_PACKET_RECEIVED, receive_data, MC_PACKET);

    log_info("Initialising data in");

    // Get the address this core's DTCM data starts at from SRAM
    data_in_config_t *chip_key_map = (data_in_config_t *)
            data_specification_get_region(CHIP_TO_KEY, ds_regions);

    uint n_chips = chip_key_map->n_chips;
    for (uint i = 0; i < n_chips; i++) {
        uint x_coord = chip_key_map->chip_to_key[i].x_coord;
        uint y_coord = chip_key_map->chip_to_key[i].y_coord;
        uint base_key = chip_key_map->chip_to_key[i].base_key;

        data_in_mc_key_map[x_coord][y_coord] = base_key;
    }

    spin1_callback_on(SDP_PACKET_RX, data_in_receive_sdp_data, SDP);

    // Set up the timeout system
    time = 0;
    wait_until = 0;
    spin1_set_timer_tick(TIMER_INTERVAL);
    spin1_callback_on(TIMER_TICK, check_for_timeout, TIMER);
    log_info("receive timeout is %dus", TIMER_INTERVAL * TIMEOUT);
}


/****f*
 *
 * SUMMARY
 *  This function is called at application start-up.
 *  It is used to register event callbacks and begin the simulation.
 *
 * SYNOPSIS
 *  int c_main()
 *
 * SOURCE
 */
void c_main(void) {
    log_info("Configuring packet gatherer");

    // initialise the code
    initialise();

    // start execution
    log_info("Starting");

    spin1_start(SYNC_NOWAIT);
}

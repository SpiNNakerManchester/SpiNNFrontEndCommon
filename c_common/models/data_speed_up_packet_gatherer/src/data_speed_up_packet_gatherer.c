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
        uint data[ITEMS_PER_DATA_PACKET - 2];
    } first;
    struct {
        uint command;
        uint data[ITEMS_PER_DATA_PACKET - 1];
    } more;
} sdp_msg_out_payload_t;

//! control value, which says how many timer ticks to run for before exiting
static uint32_t simulation_ticks = 0;
static uint32_t infinite_run = 0;
static uint32_t time = 0;

//! int as a bool to represent if this simulation should run forever
static uint32_t infinite_run;

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
    DMA = 0
} callback_priorities;

static uint data_in_mc_key_map[MAX_CHIP_ID][MAX_CHIP_ID] = {{0}};
static uint chip_x = 0;
static uint chip_y = 0;
static bit_field_t missing_seq_nums_store = NULL;
static uint total_received_seq_nums = 0;
static uint last_seen_seq_num = 0;
static uint start_sdram_address = 0;

//! Human readable definitions of the offsets for multicast key elements.
//! These act as commands sent to the target extra monitor core.
typedef enum key_offsets {
    SDRAM_KEY_OFFSET = 0,
    DATA_KEY_OFFSET = 1,
    RESTART_KEY_OFFSET = 2
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
    while (!spin1_send_sdp_msg((sdp_msg_t *) &my_msg, SDP_TIMEOUT)) {
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

//! \brief sends multicast messages accordingly for an SDP message
//! \param[in] data: the actual data from the SDP message
//! \param[in] n_elements: the number of data items in the SDP message
//! \param[in] send_sdram_address: bool flag for if we should send the sdram
//                                 address of this set of data
//! \param[in] sdram_address: the sdram address where this block of data is
//                            to be written on
static void process_sdp_message_into_mc_messages(
        const uint *data, uint n_elements, bool send_sdram_address,
        uint sdram_address) {
    // determine size of data to send
    //log_info("starting process sdp message for chip %d, %d", chip_x, chip_y);
    log_info("writing %u elements to 0x%08x", n_elements, sdram_address);

    // send mc message with SDRAM location to correct chip
    if (send_sdram_address) {
        //log_info("sending sdram address with key %08x, payload %08x",
        //         data_in_mc_key_map[chip_x][chip_y] + SDRAM_KEY_OFFSET,
        //         msg.data[SDRAM_ADDRESS]);
        send_mc_message(SDRAM_KEY_OFFSET, sdram_address);
    }

    // send mc messages containing rest of sdp data
    //log_info("sending data");
    for (uint data_index = 0; data_index < n_elements; data_index++) {
        //log_info("sending data with key %08x, payload %08x",
        //          data_in_mc_key_map[chip_x][chip_y] + DATA_KEY_OFFSET,
        //          data[data_index]);
        send_mc_message(DATA_KEY_OFFSET, data[data_index]);
    }
}

//! try allocating bitfield to DTCM for missing seq nums
static inline bool allocate_dtcm_bitfield(uint size) {
    missing_seq_nums_store = spin1_malloc(size * sizeof(uint32_t));
    return (missing_seq_nums_store != NULL);
}

//! \brief creates a store for seq nums in a memory store.
//! \param[in] max_seq_num: the max seq num expected during this stage
static void create_sequence_number_bitfield(uint size) {
    max_seq_num = size;
    uint size_of_bitfield = get_bit_field_size(size);
    if (size >= SDRAM_VS_DTCM_THRESHOLD ||
            !allocate_dtcm_bitfield(size_of_bitfield)) {
        missing_seq_nums_store = sark_xalloc(
                sv->sdram_heap, size_of_bitfield * sizeof(uint32_t), 0,
                ALLOC_LOCK | ALLOC_ID | (sark_vec->app_id << 8));
        if (missing_seq_nums_store == NULL) {
            log_error("Failed to allocate %u bytes for missing seq num store",
                    size_of_bitfield * sizeof(uint32_t));
            rt_error(RTE_SWERR);
        }
    }
    log_info("clearing bit field");
    clear_bit_field(missing_seq_nums_store, size_of_bitfield);
}

//! \brief determines how many missing seq packets will be needed.
static inline uint data_in_n_missing_seq_packets(void) {
    uint missing_seq = max_seq_num - total_received_seq_nums;
    missing_seq -= ITEMS_PER_DATA_PACKET - 2;
    const uint denom = ITEMS_PER_DATA_PACKET - 1;
    uint num = missing_seq / denom, rem = missing_seq % denom;
    return num + (rem > 0);
}

//! \brief calculates the new sdram location for a given seq num
//! \param[in] seq_num: the seq num to figure offset for
//! \return the new sdram location.
static inline uint calculate_sdram_address_from_seq_num(uint seq_num) {
    //log_info("seq num is %d", seq_num);
    if (seq_num == 0) {
        //log_info("first packet");
        return start_sdram_address;
    } else if (seq_num == 1) {
        //log_info("first data packet");
        return start_sdram_address + (
                DATA_IN_ADDRESS_PACKET_WORDS * sizeof(uint));
    }

    //log_info("start address is %d, first packet size is %d, seq num offset is %d",
    //    start_sdram_address, DATA_IN_ADDRESS_PACKET_WORDS * sizeof(uint),
    //    sizeof(uint) * DATA_IN_NORMAL_PACKET_WORDS * seq_num);
    //log_info("part 1 =%d, part 2 =%d part 3 =%d part 4= %d, part5 = %d",
    //         sizeof(uint), DATA_IN_NORMAL_PACKET_WORDS, seq_num,
    //         sizeof(uint) * DATA_IN_NORMAL_PACKET_WORDS,
    //         DATA_IN_NORMAL_PACKET_WORDS * seq_num);
    //log_info("issue %d", value);
    return start_sdram_address
            + sizeof(uint) * DATA_IN_ADDRESS_PACKET_WORDS
            + sizeof(uint) * DATA_IN_NORMAL_PACKET_WORDS * seq_num;
}

//! \brief searches through received seq nums and transmits missing ones back
//! to host for retransmission
void process_missing_seq_nums_and_request_retransmission(void) {
    sdp_msg_out_payload_t *payload = (sdp_msg_out_payload_t *) my_msg.data;
    // check that missing seq transmission is actually needed, or
    // have we finished
    //log_info(" total recieved = %d, max seq is %d",
    //         total_received_seq_nums, max_seq_num);
    if (total_received_seq_nums == max_seq_num) {
        payload->command = SDP_SEND_FINISHED_DATA_IN_CMD;
        my_msg.length = sizeof(sdp_hdr_t) + sizeof(int);
        //log_info("length of end data = %d", my_msg.length);
        send_sdp_message();
        log_info("sent end flag");
        sark_free(missing_seq_nums_store);
        missing_seq_nums_store = NULL;
        total_received_seq_nums = 0;
        return;
    }

    // sending missing seq nums

    log_info("looking for %u missing packets",
            max_seq_num - total_received_seq_nums);
    payload->first.command = SDP_SEND_FIRST_MISSING_SEQ_DATA_IN_CMD;
    payload->first.n_packets = data_in_n_missing_seq_packets();
    uint *buffer = payload->first.data;
    const uint *end_of_buffer = (uint *) (payload + 1);
    uint *data_ptr = buffer;
    for (uint bit = 0; bit < max_seq_num; bit++) {
        if (bit_field_test(missing_seq_nums_store, bit)) {
            continue;
        }

        //log_info("adding missing seq num %d", bit + 1);
        *(data_ptr++) = bit + 1;
        if (data_ptr >= end_of_buffer) {
            //log_info("sending missing data packet");
            my_msg.length = sizeof(sdp_hdr_t) + (data_ptr - buffer) * sizeof(uint);
            send_sdp_message();
            payload->more.command = SDP_SEND_MISSING_SEQ_DATA_IN_CMD;
            data_ptr = buffer = payload->more.data;
        }
    }
    // send final message if required
    //log_info("checking final packet");
    if (data_ptr > buffer) {
        my_msg.length = sizeof(sdp_hdr_t) + (data_ptr - buffer) * sizeof(uint);
        //log_info("sending missing final packet");
        send_sdp_message();
    }
}

//! \brief Calculates the number of words of data in an SDP message.
//! \param[in] msg: the SDP message, as received from SARK
//! \param[in] data_start: where in the message the data actually starts
static inline uint n_elements_in_msg(
        const sdp_msg_pure_data *msg, const uint *data_start) {
    // Offset in bytes from the start of the SDP message to where the data is
    uint offset = &msg->flags - (uint8_t *) data_start;
    return (msg->length - offset) / sizeof(uint);
}

static inline void receive_data_to_location(const sdp_msg_pure_data *msg) {
    const receive_data_to_location_msg_t *receive_data_cmd =
            (receive_data_to_location_msg_t *) msg->data;
    // translate elements to variables
    //log_info("starting data in command");
    uint prev_x = chip_x, prev_y = chip_y;
    chip_x = receive_data_cmd->chip_x;
    chip_y = receive_data_cmd->chip_y;
    if (prev_x != chip_x || prev_y != chip_y) {
        log_info("changed stream target chip to %d,%d", chip_x, chip_y);
    }

    // allocate location for holding the seq numbers
    create_sequence_number_bitfield(receive_data_cmd->max_seq_num);

    // set start of last seq number
    last_seen_seq_num = 0;
    // store where the sdram started, for out-of-order UDP packets.
    start_sdram_address = (uint) receive_data_cmd->address;

    uint n_elements = n_elements_in_msg(msg, receive_data_cmd->data);
    if (chip_x == 0 && chip_y == 0) {
        // directly write the data to where it belongs
        spin1_memcpy(receive_data_cmd->address, receive_data_cmd->data,
                n_elements * sizeof(uint));
    } else {
        // send start key, so that monitor is configured to start
        send_mc_message(RESTART_KEY_OFFSET, 0);

        // send mc messages for first packet; the data lasts to the end of the
        // message
        process_sdp_message_into_mc_messages(
                receive_data_cmd->data, n_elements, true, start_sdram_address);
    }
}

static inline void receive_seq_data(const sdp_msg_pure_data *msg) {
    const receive_seq_data_msg_t *receive_data_cmd =
            (receive_seq_data_msg_t *) msg->data;
    uint seq = receive_data_cmd->seq_num - 1;
    log_info("sequence data (seq:%u)", seq);
    if (seq >= max_seq_num) {
        log_error("bad sequence number %u when max is %u", seq, max_seq_num);
        return;
    }

    uint this_sdram_address = calculate_sdram_address_from_seq_num(seq);
    bool send_sdram_address = (last_seen_seq_num != seq);

    if (!bit_field_test(missing_seq_nums_store, seq)) {
        bit_field_set(missing_seq_nums_store, seq);
        total_received_seq_nums++;
    }
    last_seen_seq_num = receive_data_cmd->seq_num;

    uint n_elements = n_elements_in_msg(msg, receive_data_cmd->data);
    if (chip_x == 0 && chip_y == 0) {
        // directly write the data to where it belongs
        spin1_memcpy((address_t) this_sdram_address, receive_data_cmd->data,
                n_elements * sizeof(uint));
    } else {
        // transmit data to chip; the data lasts to the end of the message
        process_sdp_message_into_mc_messages(
                receive_data_cmd->data,  n_elements,
                send_sdram_address, this_sdram_address);
    }
}

//! \brief processes sdp messages
//! \param[in] mailbox: the sdp message
//! \param[in] port: the port associated with this sdp message
void data_in_receive_sdp_data(uint mailbox, uint port) {
    // use as not important
    use(port);

    //log_info("received packet at port %d", port);

    // convert mailbox into correct sdp format
    sdp_msg_pure_data *msg = (sdp_msg_pure_data *) mailbox;
    uint command = msg->data[COMMAND_ID];

    //log_info("command code is %d", msg->data[COMMAND_ID_POSITION]);

    // check for separate commands
    switch (command) {
    case SDP_SEND_DATA_TO_LOCATION_CMD:
        receive_data_to_location(msg);
        break;
    case SDP_SEND_SEQ_DATA_CMD:
        receive_seq_data(msg);
        break;
    case SDP_SEND_MISSING_SEQ_NUMS_BACK_TO_HOST_CMD:
        log_info("checking for missing");
        process_missing_seq_nums_and_request_retransmission();
        break;
    case SDP_LAST_DATA_IN_CMD:
        log_info("received final flag");
        process_missing_seq_nums_and_request_retransmission();
        break;
    default:
        log_info("Failed to recognise command id %u", command);
    }

    // free the message to stop overload
    spin1_msg_free((sdp_msg_t *) msg);
    //log_info("freed message");
}

void resume_callback(void) {
    time = UINT32_MAX;
}

void send_data(void) {
    //log_info("last element is %d", data[position_in_store - 1]);
    //log_info("first element is %d", data[0]);

    spin1_memcpy(&my_msg.data, data, position_in_store * sizeof(uint));
    my_msg.length = sizeof(sdp_hdr_t) + position_in_store * sizeof(uint);
    //log_info("my length is %d with position %d", my_msg.length, position_in_store);

    if (seq_num > max_seq_num) {
        log_error("got a funky seq num in sending. max is %d, received %d",
                max_seq_num, seq_num);
    }

    send_sdp_message();

    position_in_store = 1;
    seq_num++;
    data[0] = seq_num;
}

void receive_data(uint key, uint payload) {
    //log_info("packet!");
    if (key == new_sequence_key) {
        if (position_in_store != 1) {
            send_data();
        }
        //log_info("finding new seq num %d", payload);
        //log_info("position in store is %d", position_in_store);
        data[0] = payload;
        seq_num = payload;
        position_in_store = 1;

        if (payload > max_seq_num) {
            log_error("got a funky seq num. max is %d, received %d",
                    max_seq_num, payload);
        }
    } else {
        //log_info(" payload = %d posiiton = %d", payload, position_in_store);
        data[position_in_store] = payload;
        position_in_store++;
        //log_info("payload is %d", payload);

        if (key == first_data_key) {
            //log_info("resetting seq and position");
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

            //log_info("position = %d with seq num %d", position_in_store, seq_num);
            //log_info("last payload was %d", payload);
            send_data();
        } else if (position_in_store == ITEMS_PER_DATA_PACKET) {
            //log_info("position = %d with seq num %d", position_in_store, seq_num);
            //log_info("last payload was %d", payload);
            send_data();
        }
    }
}

static bool initialise(uint32_t *timer_period) {
    // Get the address this core's DTCM data starts at from SRAM
    address_t address = data_specification_get_data_address();

    // Read the header
    if (!data_specification_read_header(address)) {
        log_error("failed to read the data spec header");
        return false;
    }

    // Get the timing details and set up the simulation interface
    if (!simulation_initialise(
            data_specification_get_region(SYSTEM_REGION, address),
            APPLICATION_NAME_HASH, timer_period, &simulation_ticks,
            &infinite_run, SDP, DMA)) {
        return false;
    }

    log_info("Initialising data out");

    data_out_config_t *config = (data_out_config_t *)
            data_specification_get_region(CONFIG, address);
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

    log_info("Initialising data in");

    spin1_callback_on(SDP_PACKET_RX, data_in_receive_sdp_data, SDP);

    // Get the address this core's DTCM data starts at from SRAM
    data_in_config_t *chip_key_map = (data_in_config_t *)
            data_specification_get_region(CHIP_TO_KEY, address);

    uint n_chips = chip_key_map->n_chips;
    for (uint i = 0; i < n_chips; i++) {
        uint x_coord = chip_key_map->chip_to_key[i].x_coord;
        uint y_coord = chip_key_map->chip_to_key[i].y_coord;
        uint base_key = chip_key_map->chip_to_key[i].base_key;

        //log_info("for chip %d, %d, base key is %d",
        //         x_coord, y_coord, base_key);

        data_in_mc_key_map[x_coord][y_coord] = base_key;
    }
    return true;
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
    log_info("configuring packet gatherer");

    // Load DTCM data
    uint32_t timer_period;

    // initialise the code
    if (!initialise(&timer_period)) {
        rt_error(RTE_SWERR);
    }

    spin1_callback_on(FRPL_PACKET_RECEIVED, receive_data, MC_PACKET);

    // start execution
    log_info("Starting");

    // Start the time at "-1" so that the first tick will be 0
    time = UINT32_MAX;

    spin1_start(SYNC_NOWAIT);
}

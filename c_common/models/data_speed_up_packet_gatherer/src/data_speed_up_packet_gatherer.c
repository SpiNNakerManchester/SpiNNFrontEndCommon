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

//! extra length adjustment for the SDP header
#define LENGTH_OF_SDP_HEADER 8

//! convert between words to bytes
#define WORD_TO_BYTE_MULTIPLIER 4

// max id needed to cover the chips in either direction on a spinn-5 board
#define MAX_CHIP_ID 8

//! size of the command code in bytes
#define COMMAND_ID_SIZE_IN_BYTES 4

//! size of the command code in elements
#define COMMAND_ID_SIZE_IN_ELEMENTS 1

//! size of total missing seq packets as elements
#define TOTAL_MISSING_SEQ_PACKETS_IN_ELEMENTS 1

// bit shift to find x coord from the chip int in sdp message
#define BIT_SHIFT_CHIP_X_COORD 16

// mask for getting y coord from the chip int in sdp message
#define BIT_MASK_FOR_CHIP_Y_COORD 0x0000FFFF

// sdp port commands received
enum sdp_port_commands {
    // received
    SDP_SEND_DATA_TO_LOCATION_COMMAND_ID = 200,
    SDP_SEND_SEQ_DATA_COMMAND_ID = 2000,
    SDP_SEND_MISSING_SEQ_NUMS_BACK_TO_HOST_COMMAND_ID = 2001,
    SDP_LAST_DATA_IN_COMMAND_ID = 2002,
    // sent
    SDP_PACKET_SEND_FIRST_MISSING_SEQ_DATA_IN_COMMAND_ID = 2003,
    SDP_PACKET_SEND_MISSING_SEQ_DATA_IN_COMMAND_ID = 2004,
    SDP_PACKET_SEND_FINISHED_DATA_IN_COMMAND_ID = 2005
};

// threshold for sdram vs dtcm missing seq store.
#define SDRAM_VS_DTCM_THRESHOLD 40000

// location of command ids in sdp message
#define COMMAND_ID_POSITION 0

//! offset with just command and seq in bytes
#define OFFSET_AFTER_COMMAND_AND_SEQUENCE_IN_BYTES 8

//! offset with command, x, y, address in bytes
#define OFFSET_AFTER_COMMAND_AND_ADDRESS_IN_BYTES 16

//! size of data stored in packet with command and address
//! defined from calculation:
// DATA_PER_FULL_PACKET - (OFFSET_AFTER_COMMAND_AND_ADDRESS_IN_BYTES /
//                         WORD_TO_BYTE_CONVERTER)
#define DATA_IN_FULL_PACKET_WITH_ADDRESS_NUM 64

//! size of data stored in packet with command and seq
//! defined from calculation:
//DATA_PER_FULL_PACKET - (OFFSET_AFTER_COMMAND_AND_SEQUENCE_IN_BYTES /
//                        WORD_TO_BYTE_CONVERTER)
#define DATA_IN_FULL_PACKET_WITH_NO_ADDRESS_NUM 66

//-----------------------------------------------------------------------------
// TYPES AND GLOBALS
//-----------------------------------------------------------------------------

//! struct for a SDP message with pure data, no SCP header
typedef struct sdp_msg_pure_data {	// SDP message (=292 bytes)
    struct sdp_msg *next;	// Next in free list
    uint16_t length;		// length
    uint16_t checksum;		// checksum (if used)

    // sdp_hdr_t
    uint8_t flags;	    	// SDP flag byte
    uint8_t tag;		// SDP IPtag
    uint8_t dest_port;		// SDP destination port/CPU
    uint8_t srce_port;		// SDP source port/CPU
    uint16_t dest_addr;		// SDP destination address
    uint16_t srce_addr;		// SDP source address

    // User data (272 bytes when no SCP header)
    uint32_t data[ITEMS_PER_DATA_PACKET];

    uint32_t _PAD;		// Private padding
} sdp_msg_pure_data;

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
sdp_msg_pure_data my_msg;


//! human readable definitions of each region in SDRAM
typedef enum regions_e {
    SYSTEM_REGION, CONFIG, CHIP_TO_KEY
} regions_e;

//! human readable definitions of the data in each region
typedef enum config_elements {
    NEW_SEQ_KEY, FIRST_DATA_KEY, END_FLAG_KEY, TAG_ID
} config_elements;

//! values for the priority for each callback
typedef enum callback_priorities{
    MC_PACKET = -1, SDP = 0, DMA = 0
} callback_priorities;

static uint data_in_mc_key_map[MAX_CHIP_ID][MAX_CHIP_ID] = {{0}};
static uint chip_x = 0;
static uint chip_y = 0;
static bit_field_t missing_seq_nums_store = NULL;
static bool received_address_packet = false;
static uint size_of_bitfield = 0;
static uint total_received_seq_nums = 0;
static uint last_seen_seq_num = 0;
static uint start_sdram_address = 0;

//! human readable definitions for each element in first data SDP packet
typedef enum data_positions_in_first_sdp_packet {
    SDRAM_ADDRESS = 1,
    CHIP_DATA = 2,
    MAX_SEQ_NUM = 3,
    START_OF_DATA_FIRST_SDP = 4
} data_positions_in_first_sdp_packet;

//! human readable definitions for each element in the send missing seq first
//! packet
typedef enum data_elements_for_missing_seq_first_packet {
    N_MISSING_SEQ_PACKETS = 1,
    DATA_STARTS = 2
} data_elements_for_missing_seq_first_packet;

//! human readable definitions for each element in data sdp packet
typedef enum data_positions_in_data_sdp_packet {
    SEQ_NUM = 1,
    START_OF_DATA_IN_DATA_SDP = 2
} data_positions_in_data_sdp_packet;

//! human readable definitions of the offsets for key elements
typedef enum key_offsets{
    SDRAM_KEY_OFFSET = 0, DATA_KEY_OFFSET = 1, RESTART_KEY_OFFSET = 2
} key_offsets;

typedef struct data_in_data_t {
    uint32_t n_chips;
    struct chip_key_data_t {
        uint32_t x_coord;
        uint32_t y_coord;
        uint32_t base_key;
    } chip_to_key[];
} data_in_data_t;

//-----------------------------------------------------------------------------
// FUNCTIONS
//-----------------------------------------------------------------------------

static void send_sdp_message(void) {
    while (!spin1_send_sdp_msg((sdp_msg_t *) &my_msg, SDP_TIMEOUT)) {
        spin1_delay_us(MESSAGE_DELAY_TIME_WHEN_FAIL);
    }
}

//! \brief sends mc messages accordingly for a the first sdp message
//! \param[in] msg: the sdp message with no scp header
//! \param[in] chip_x: the chip_x coord where this data is headed to
//! \param[in] chip_y: the chip y coord where this data is headed to
//! \param[in] send_sdram_address: bool flag for if we should send the sdram
//                                 address of this set of data
//! \param[in] start_of_data_sdp_position: where data is in the sdp message
//! \param[in] sdram_address: the sdram address where this block of data is
//                            to be written on
void process_sdp_message_into_mc_messages(
        sdp_msg_pure_data *msg, uint chip_x, uint chip_y,
        bool send_sdram_address, uint start_of_data_sdp_position,
        uint sdram_address) {
    // determine size of data to send
    //log_info("starting process sdp message for chip %d, %d", chip_x, chip_y);
    uint n_elements = (msg->length -
            ((start_of_data_sdp_position * WORD_TO_BYTE_MULTIPLIER)
                    + LENGTH_OF_SDP_HEADER)) / WORD_TO_BYTE_MULTIPLIER;
    //log_info("n elements %d", n_elements);

    // send mc message with SDRAM location to correct chip
    //log_info("send sdram address %d", send_sdram_address);
    if (send_sdram_address) {
        //log_info("key is %u payload %u",
        //         data_in_mc_key_map[chip_x][chip_y] + SDRAM_KEY_OFFSET,
        //         msg.data[SDRAM_ADDRESS]);
        //log_info("firing with key %d",
        //         data_in_mc_key_map[chip_x][chip_y] + SDRAM_KEY_OFFSET);
        while (spin1_send_mc_packet(
                data_in_mc_key_map[chip_x][chip_y] + SDRAM_KEY_OFFSET,
                sdram_address, WITH_PAYLOAD) == 0) {
            spin1_delay_us(MESSAGE_DELAY_TIME_WHEN_FAIL);
        }
    }

    // send mc messages containing rest of sdp data
    //log_info("sending data");
    // log_info("firing with key %d",
    //         data_in_mc_key_map[chip_x][chip_y] + DATA_KEY_OFFSET);
    for (uint data_index = 0; data_index < n_elements; data_index++) {
        //log_info("sending data with key %u payload %u",
        //          data_in_mc_key_map[chip_x][chip_y] + DATA_KEY_OFFSET,
        //          msg.data[start_of_data_sdp_position + data_index]);
        while (spin1_send_mc_packet(
                data_in_mc_key_map[chip_x][chip_y] + DATA_KEY_OFFSET,
                msg->data[start_of_data_sdp_position + data_index],
                WITH_PAYLOAD) == 0) {
            spin1_delay_us(MESSAGE_DELAY_TIME_WHEN_FAIL);
        }
    }
}

//! \brief allocates bitfield to SDRAM for missing seq nums
//! \param[in] max_seq_num: the expected max seq num to be seen during this
//! block of data
static inline void allocate_to_sdram(uint max_seq_num) {
    size_of_bitfield = get_bit_field_size(max_seq_num);
    missing_seq_nums_store = (bit_field_t) sark_xalloc(
            sv->sdram_heap, size_of_bitfield * sizeof(uint32_t), 0,
            ALLOC_LOCK | ALLOC_ID | (sark_vec->app_id << 8));
    if (missing_seq_nums_store == NULL) {
        log_error("Failed to allocate memory for missing seq num store");
        rt_error(RTE_SWERR);
    }
}

//! try allocating bitfield to DTCM for missing seq nums
static inline bool allocate_to_dtcm(uint max_seq_num) {
    size_of_bitfield = get_bit_field_size(max_seq_num);
    missing_seq_nums_store =
            spin1_malloc(size_of_bitfield * sizeof(uint32_t));
    if (missing_seq_nums_store == NULL) {
        return false;
    }
    return true;
}

//! \brief creates a store for seq nums in a memory store.
//! \param[in] max_seq_num: the max seq num expected during this stage
void process_sdram_location_for_seq_nums(uint max_seq_num) {
    if (max_seq_num >= SDRAM_VS_DTCM_THRESHOLD){
        log_info("allocate bitfield in SDRAM");
        allocate_to_sdram(max_seq_num);
    } else {
        log_info("allocate bitfield in DTCM");
        if (!allocate_to_dtcm(max_seq_num)) {
            log_info("trying SDRAM as DTCM allocate failed");
            allocate_to_sdram(max_seq_num);
        }
    }
    log_info("starting bit field clear");
    clear_bit_field(missing_seq_nums_store, size_of_bitfield);
    log_info("finished bit field clearing");
}

//! \brief determines how many missing seq packets will be needed.
static inline uint data_in_n_missing_seq_packets(void) {
    uint missing_seq = max_seq_num - total_received_seq_nums;
    missing_seq = missing_seq - (
            ITEMS_PER_DATA_PACKET - COMMAND_ID_SIZE_IN_ELEMENTS -
            TOTAL_MISSING_SEQ_PACKETS_IN_ELEMENTS);
    const uint denom = ITEMS_PER_DATA_PACKET - COMMAND_ID_SIZE_IN_ELEMENTS;
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
            DATA_IN_FULL_PACKET_WITH_ADDRESS_NUM * WORD_TO_BYTE_MULTIPLIER);
    }

    //log_info("start address is %d, first packet size is %d, seq num offset is %d",
    //    start_sdram_address, DATA_IN_FULL_PACKET_WITH_ADDRESS_NUM * WORD_TO_BYTE_MULTIPLIER,
    //    WORD_TO_BYTE_MULTIPLIER * DATA_IN_FULL_PACKET_WITH_NO_ADDRESS_NUM * seq_num);
    //log_info("part 1 =%d, part 2 =%d part 3 =%d part 4= %d, part5 = %d",
    //         WORD_TO_BYTE_MULTIPLIER, DATA_IN_FULL_PACKET_WITH_NO_ADDRESS_NUM, seq_num,
    //         WORD_TO_BYTE_MULTIPLIER * DATA_IN_FULL_PACKET_WITH_NO_ADDRESS_NUM,
    //         DATA_IN_FULL_PACKET_WITH_NO_ADDRESS_NUM * seq_num);
    //log_info("issue %d", value);
    return start_sdram_address
            + (DATA_IN_FULL_PACKET_WITH_ADDRESS_NUM * WORD_TO_BYTE_MULTIPLIER)
            + (WORD_TO_BYTE_MULTIPLIER *
                    DATA_IN_FULL_PACKET_WITH_NO_ADDRESS_NUM * seq_num);
}

//! \brief searches through received seq nums and transmits missing ones back
//! to host for retransmission
void process_missing_seq_nums_and_request_retransmission(void) {
    // check that missing seq transmission is actually needed, or
    // have we finished
    //log_info(" total recieved = %d, max seq is %d",
    //         total_received_seq_nums, max_seq_num);
    if (total_received_seq_nums == max_seq_num) {
        my_msg.data[COMMAND_ID_POSITION] =
                SDP_PACKET_SEND_FINISHED_DATA_IN_COMMAND_ID;
        my_msg.length = COMMAND_ID_SIZE_IN_BYTES + LENGTH_OF_SDP_HEADER;
        //log_info("length of end data = %d", my_msg.length);
        send_sdp_message();
        log_info("sent end flag");
        sark_free(missing_seq_nums_store);
        total_received_seq_nums = 0;
    } else {
        // sending missing seq nums

        log_info("looking for %u missing packets",
                max_seq_num - total_received_seq_nums);
        my_msg.data[COMMAND_ID_POSITION] =
                SDP_PACKET_SEND_FIRST_MISSING_SEQ_DATA_IN_COMMAND_ID;
        my_msg.data[N_MISSING_SEQ_PACKETS] = data_in_n_missing_seq_packets();
        uint position_in_data = DATA_STARTS;
        for (uint bit = 0; bit < max_seq_num; bit++) {
            if (bit_field_test(missing_seq_nums_store, bit)) {
                continue;
            }

            //log_info("adding missing seq num %d", bit + 1);
            my_msg.data[position_in_data] = bit + 1;
            position_in_data++;
            if (position_in_data == ITEMS_PER_DATA_PACKET) {
                //log_info("sending missing data packet");
                my_msg.length = LENGTH_OF_SDP_HEADER +
                        position_in_data * WORD_TO_BYTE_MULTIPLIER;
                send_sdp_message();
                my_msg.data[COMMAND_ID_POSITION] =
                        SDP_PACKET_SEND_MISSING_SEQ_DATA_IN_COMMAND_ID;
                position_in_data = 1;
            }
        }
        // send final message if required
        //log_info("checking final packet");
        if (position_in_data > DATA_STARTS) {
            my_msg.length = LENGTH_OF_SDP_HEADER +
                    position_in_data * WORD_TO_BYTE_MULTIPLIER;
            //log_info("sending missing final packet");
            send_sdp_message();
        }
    }
}

static inline void receive_data_to_location(sdp_msg_pure_data *msg) {
    // translate elements to variables
    //log_info("starting data in command");
    uint prev_x = chip_x, prev_y = chip_y;
    chip_x = msg->data[CHIP_DATA] >> BIT_SHIFT_CHIP_X_COORD;
    chip_y = msg->data[CHIP_DATA] & BIT_MASK_FOR_CHIP_Y_COORD;
    if (prev_x != chip_x || prev_y != chip_y) {
        log_info("changed stream target chip to %d,%d", chip_x, chip_y);
    }
    received_address_packet = true;
    max_seq_num = msg->data[MAX_SEQ_NUM];
    //log_info("got chip ids of %d, %d, and max seq of %d",
    //         chip_x, chip_y, max_seq_num);

    // allocate sdram location for holding the seq numbers
    process_sdram_location_for_seq_nums(max_seq_num);

    // send start key, so that monitor is configured to start
    while (spin1_send_mc_packet(
            data_in_mc_key_map[chip_x][chip_y] + RESTART_KEY_OFFSET, 0,
            WITH_PAYLOAD) == 0) {
        spin1_delay_us(MESSAGE_DELAY_TIME_WHEN_FAIL);
    }

    // set start of last seq number
    last_seen_seq_num = 0;

    // send mc messages for first packet
    process_sdp_message_into_mc_messages(
            msg, chip_x, chip_y, true, START_OF_DATA_FIRST_SDP,
            msg->data[SDRAM_ADDRESS]);

    // store where the sdram started, for out-of-order UDP packets.
    start_sdram_address = msg->data[SDRAM_ADDRESS];
    //log_info("start address = %d", start_sdram_address);

    //log_info("processed");
}

static inline void receive_seq_data(sdp_msg_pure_data *msg) {
    uint seq = msg->data[SEQ_NUM] - 1;
    log_info("sequence data (seq:%u)", seq);
    // store seq number in store for later processing
    bool send_sdram_address = false;
    uint this_sdram_address = 0;

    // if not next in line, figure sdram address, send and reset tracker
    if (last_seen_seq_num != seq) {
        //log_info("last seq was %d, what we have is %d",
        //    last_seen_seq_num, msg->data[SEQ_NUM]);
        send_sdram_address = true;
        this_sdram_address = calculate_sdram_address_from_seq_num(seq);
        //log_info("the new sdram address for seq num %d is %d with first data %d",
        //         msg->data[SEQ_NUM], this_sdram_address,
        //         msg->data[START_OF_DATA_IN_DATA_SDP]);
    }

    //log_info("received seq number %d", msg->data[SEQ_NUM]);
    if (!bit_field_test(missing_seq_nums_store, seq)) {
        bit_field_set(missing_seq_nums_store, seq);
        total_received_seq_nums ++;
    }
    last_seen_seq_num = msg->data[SEQ_NUM];

    // transmit data to chip
    process_sdp_message_into_mc_messages(
            msg, chip_x, chip_y, send_sdram_address,
            START_OF_DATA_IN_DATA_SDP, this_sdram_address);
}

//! \brief processes sdp messages
//! \param[in] mailbox: the sdp message
//! \param[in] port: the port assocated with this sdp message
void data_in_receive_sdp_data(uint mailbox, uint port) {
    // use as not important
    use(port);

    //log_info("received packet at port %d", port);

    // convert mailbox into correct sdp format
    sdp_msg_pure_data *msg = (sdp_msg_pure_data *) mailbox;

    //log_info("command code is %d", msg->data[COMMAND_ID_POSITION]);

    // check for separate commands
    switch (msg->data[COMMAND_ID_POSITION]) {
    case SDP_SEND_DATA_TO_LOCATION_COMMAND_ID:
        receive_data_to_location(msg);
        break;
    case SDP_SEND_SEQ_DATA_COMMAND_ID:
        receive_seq_data(msg);
        break;
    case SDP_SEND_MISSING_SEQ_NUMS_BACK_TO_HOST_COMMAND_ID:
        log_info("checking for missing");
        process_missing_seq_nums_and_request_retransmission();
        break;
    case SDP_LAST_DATA_IN_COMMAND_ID:
        log_info("received final flag");
        process_missing_seq_nums_and_request_retransmission();
        break;
    default:
        log_info("Failed to recognise command id %u",
                 msg->data[COMMAND_ID_POSITION]);
    }

    // free the message to stop overload
    spin1_msg_free((sdp_msg_t *) msg);
    //log_info("freed message");
}

void resume_callback() {
    time = UINT32_MAX;
}

void send_data(){
    //log_info("last element is %d", data[position_in_store - 1]);
    //log_info("first element is %d", data[0]);

    spin1_memcpy(&my_msg.data, data,
	    position_in_store * WORD_TO_BYTE_MULTIPLIER);
    my_msg.length =
	    LENGTH_OF_SDP_HEADER + (position_in_store * WORD_TO_BYTE_MULTIPLIER);
    //log_info("my length is %d with position %d", my_msg.length, position_in_store);

    if (seq_num > max_seq_num){
        log_error(
            "got a funky seq num in sending. max is %d, received %d",
            max_seq_num, seq_num);
    }

    send_sdp_message();

    position_in_store = 1;
    seq_num += 1;
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

        if (payload > max_seq_num){
            log_error(
                "got a funky seq num. max is %d, received %d",
                max_seq_num, payload);
        }
    } else {

        //log_info(" payload = %d posiiton = %d", payload, position_in_store);
        data[position_in_store] = payload;
        position_in_store += 1;
        //log_info("payload is %d", payload);

        if (key == first_data_key) {
            //log_info("resetting seq and position");
            seq_num = FIRST_SEQ_NUM;
            data[0] = seq_num;
            position_in_store = 1;
            max_seq_num = payload;
        }

        if (key == end_flag_key){
            // set end flag bit in seq num
            data[0] = data[0] + (1 << 31);

            // adjust size as last payload not counted
            position_in_store = position_in_store - 1;

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

    address_t config_address = data_specification_get_region(CONFIG, address);
    new_sequence_key = config_address[NEW_SEQ_KEY];
    first_data_key = config_address[FIRST_DATA_KEY];
    end_flag_key = config_address[END_FLAG_KEY];

    my_msg.tag = config_address[TAG_ID];	// IPTag 1
    my_msg.dest_port = PORT_ETH;		// Ethernet
    my_msg.dest_addr = sv->eth_addr;		// Nearest Ethernet chip

    // fill in SDP source & flag fields
    my_msg.flags = 0x07;
    my_msg.srce_port = 3;
    my_msg.srce_addr = sv->p2p_addr;

    log_info("Initialising data in");

    spin1_callback_on(SDP_PACKET_RX, data_in_receive_sdp_data, SDP);

     // Get the address this core's DTCM data starts at from SRAM
    data_in_data_t *chip_key_map = (data_in_data_t *)
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
void c_main() {
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

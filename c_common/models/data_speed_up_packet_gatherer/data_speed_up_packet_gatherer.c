//! imports
#include "spin1_api.h"
#include "common-typedefs.h"
#include <data_specification.h>
#include <debug.h>
#include <bit_field.h>
#include <math.h>
//-----------------------------------------------------------------------------
// COMMON MAGIC NUMBERS
//-----------------------------------------------------------------------------

//! timeout used in sending sdp messages
#define SDP_TIMEOUT 100

//! whatever sdp flags do
#define SDP_FLAGS 0x07

//! the soruce port for the sdp messages. possibly used by host
#define SDP_SOURCE_PORT 3

//! the time to wait before trying again to send a message (MC, SDP)
#define MESSAGE_DELAY_TIME_WHEN_FAIL 1

//! How many mc packets are to be received per sdp packet
#define ITEMS_PER_DATA_INDEX  68

//-----------------------------------------------------------------------------
// DATA IN MAGIC NUMBERS
//-----------------------------------------------------------------------------

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
#define SDP_SEND_DATA_TO_LOCATION_COMMAND_ID 200
#define SDP_SEND_SEQ_DATA_COMMAND_ID 2000
#define SDP_SEND_MISSING_SEQ_NUMS_BACK_TO_HOST_COMMAND_ID 2001
#define SDP_LAST_DATA_IN_COMMAND_ID 2002

// sdp port commands sent
#define SDP_PACKET_SEND_FIRST_MISSING_SEQ_DATA_IN_COMMAND_ID 2003
#define SDP_PACKET_SEND_MISSING_SEQ_DATA_IN_COMMAND_ID 2004
#define SDP_PACKET_SEND_FINISHED_DATA_IN_COMMAND_ID 2005

// threshold for sdram vs dtcm missing seq store.
#define SDRAM_VS_DTCM_THRESHOLD 40000

// location of command ids in sdp message
#define COMMAND_ID_POSITION 0

//-----------------------------------------------------------------------------
// DATA OUT MAGIC NUMBERS
//-----------------------------------------------------------------------------

//! first sequence number to use and reset to
#define FIRST_SEQ_NUM 0

//! extra length adjustment for the sdp header
#define LENGTH_OF_SDP_HEADER 8

//! convert between words to bytes
#define WORD_TO_BYTE_MULTIPLIER 4

//! end flag bit shift
#define DATA_OUT_END_FLAG_BIT_SHIFT 31

//! struct for a SDP message with pure data, no scp header
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

    // User data (272 bytes when no scp header)
    uint32_t data[ITEMS_PER_DATA_INDEX ];

    uint32_t _PAD;		// Private padding
} sdp_msg_pure_data;

//-----------------------------------------------------------------------------
// DATA IN VARIABLES
//-----------------------------------------------------------------------------

uint data_in_mc_key_map[MAX_CHIP_ID][MAX_CHIP_ID] = {{0}};
uint max_seq_num = 0;
uint chip_x = 0;
uint chip_y = 0;
bitfield *missing_seq_nums_store = NULL;
bool received_address_packet = false;
uint size_of_bitfield = 0;
uint total_received_seq_nums = 0;

//-----------------------------------------------------------------------------
// DATA OUT VARIABLES
//-----------------------------------------------------------------------------

//! the key that causes sequence number to be processed
static uint32_t new_sequence_key = 0;
static uint32_t first_data_key = 0;
static uint32_t end_flag_key = 0;

//! default seq num
static uint32_t seq_num = FIRST_SEQ_NUM;
static uint32_t max_seq_num = 0;

//! data holders for the sdp packet
static uint32_t data[ITEMS_PER_DATA_INDEX ];
static uint32_t position_in_store = 0;

//! sdp message holder for transmissions
sdp_msg_pure_data my_msg;

//-----------------------------------------------------------------------------
// ENUMS
//-----------------------------------------------------------------------------

//! human readable definitions for each element in first data sdp packet
typedef enum data_positions_in_first_sdp_packet{
    SDRAM_ADDRESS = 1, CHIP_DATA = 2, MAX_SEQ_NUM = 3,
    START_OF_DATA_FIRST_SDP = 4
}data_positions_in_first_sdp_packet;

//! human readable definitions for each element in data sdp packet
typedef enum data_positions_in_data_sdp_packet{
    SEQ_NUM = 1, START_OF_DATA_IN_DATA_SDP = 2
}data_positions_in_data_sdp_packet;


//! human readable definitions of the offsets for key elements
typedef enum key_offsets{
    SDRAM_KEY_OFFSET = 0, DATA_KEY_OFFSET = 1
}key_offsets;

//! human readable definitions of each region in SDRAM
typedef enum regions_e {
    SYSTEM_REGION, CONFIG, DATA_IN_CHIP_TO_KEY_SPACE
} regions_e;

typedef enum data_in_data_positions{
    N_CHIPS = 0, X_COORD = 1 Y_COORD = 2, BASE_KEY = 3,
    CHIP_KEY_DATA_SIZE = 3
}data_in_data_positions;

//! human readable definitions of the data in each region
typedef enum config_elements {
    NEW_SEQ_KEY, FIRST_DATA_KEY, END_FLAG_KEY, TAG_ID
} config_elements;

//! values for the priority for each callback
typedef enum callback_priorities{
    FR_PACKET = -1, SDP = 0, DMA = 0
} callback_priorities;

//-----------------------------------------------------------------------------
// DATA IN FUNCTIONALITY
//-----------------------------------------------------------------------------

//TODO could change the missing seq into a DMA'ed sdram missing seq num. may improve speed.

//! \brief sends mc messages accordingly for a the first sdp message
//! \param[in] msg: the sdp message with no scp header
//! \param[in] chip_x: the chip_x coord where this data is headed to
//! \param[in] chip_y: the chip y coord where this data is headed to
void process_first_sdp_message_into_mc_messages(
        sdp_msg_pure_data msg, uint chip_x, uint chip_y, 
        bool send_sdram_address, uint START_OF_DATA_FIRST_SDP_position){
    // determine size of data to send
    n_elements = (msg->length - (START_OF_DATA_FIRST_SDP * WORD_TO_BYTE_MULTIPLIER))
                 / WORD_TO_BYTE_MULTIPLIER;

    // send mc message with SDRAM location to correct chip
    if (send_sdram_address){
        while(!spin1_send_mc_packet(
                data_in_mc_key_map[chip_x][chip_y] + SDRAM_KEY_OFFSET,
                msg->data[SDRAM_ADDRESS], WITH_PAYLOAD)){
            spin1_delay_us(MESSAGE_DELAY_TIME_WHEN_FAIL);
        }
    }

    // send mc messages containing rest of sdp data
    for(uint data_index = 0; data_index < n_elements; data_index++){
        while(!spin1_send_mc_packet(
                data_in_mc_key_map[chip_x][chip_y] + DATA_KEY_OFFSET,
                msg->data[START_OF_DATA_FIRST_SDP_position + data_index], WITH_PAYLOAD)){
            spin1_delay_us(MESSAGE_DELAY_TIME_WHEN_FAIL);
        }
    }
}


//! \brief allocates bitfield to SDRAM for missing seq nums
//! \param[in] max_seq_num: the expected max seq num to be seen during this
//! block of data
void allocate_to_sdram(uint max_seq_num){
    using_bitfield = false;
    size_of_bitfield = get_bit_field_size(max_seq_num);
    missing_seq_nums_store = (bitfield*) = sark_xalloc(
        sv->sdram_heap,
        size_of_bitfield * sizeof(uint32_t),
        0,
        ALLOC_LOCK + ALLOC_ID + (sark_vec->app_id << 8));
    if (missing_seq_nums_store_sdram == NULL){
        log_error("Failed to allocate memory for missing seq num store");
        rt_error(RTE_SWERR);
    }
    clear_bit_field(missing_seq_nums_store, bitfield_size_in_ints);
}

//! try allocating bitfield to DTCM for missing seq nums
bool allocate_to_dtcm(uint max_seq_num){
    size_of_bitfield = get_bit_field_size(max_seq_num);
    missing_seq_nums_store = (bitfield*) spin1_malloc(
        1, size_of_bitfield * sizeof(uint32_t));
    if (missing_seq_nums_store) == NULL{
        return false;
    }
    clear_bit_field(missing_seq_nums_store, bitfield_size_in_ints);
    return true;
}

//! \brief creates a store for seq nums in a memory store.
//! \param[in] max_seq_num: the max seq num expected during this stage
void process_sdram_location_for_seq_nums(uint max_seq_num){
    if (max_seq_num >= SDRAM_VS_DTCM_THRESHOLD){
        allocate_to_sdram(max_seq_num);
    }
    else{
        if(!allocate_to_dtcm(max_seq_num)){
            allocate_to_sdram(max_seq_num);
        }
    }
}

//! \brief determines how many missing seq packets will be needed.
uint data_in_n_missing_seq_packets(){
   uint missing_seq = max_seq_num - total_received_seq_nums;
   missing_seq = missing_seq - (
       ITEMS_PER_DATA_INDEX - COMMAND_ID_SIZE_IN_ELEMENTS -
       TOTAL_MISSING_SEQ_PACKETS_IN_ELEMENTS);
   return ceil(missing_seq / (
       ITEMS_PER_DATA_INDEX - COMMAND_ID_SIZE_IN_ELEMENTS));
}

//! updates the memory in msg, and then sends missing seq if full. updates
//! command code accordingly.
//! \param[in] missing_seq_num: the missing seq num to fill in
//! \param[in] position_in_msg: where in msg we are.
uint update_and_send_sdp_if_required(
        uint missing_seq_num, uint position_in_msg){
    my_msg.data[position_in_data] = missing_seq_num;
    position_in_data ++;
    if (position_in_data = ITEMS_PER_DATA_INDEX){
        my_msg.len = LENGTH_OF_SDP_HEADER + (
            position_in_data * WORD_TO_BYTE_MULTIPLIER);
        while (!spin1_send_sdp_msg((sdp_msg_t *) &my_msg, SDP_TIMEOUT)) {
	        spin1_delay_us(MESSAGE_DELAY_TIME_WHEN_FAIL);
        }
        my_msg.data[COMMAND_ID_POSITION] =
            SDP_PACKET_SEND_MISSING_SEQ_DATA_IN_COMMAND_ID;
        position_in_data = 1;
    }
    return position_in_data;
}

//! \brief searches through received seq nums and transmits missing ones back 
//! to host for retransmission
void process_missing_seq_nums_and_request_retransmission(){

    // check that missing seq transmission is actually needed, or
    // have we finished
    if (total_received_seq_nums == max_seq_num){
        my_msg.data[0] = SDP_PACKET_SEND_FINISHED_DATA_IN_COMMAND_ID;
        my_msg.len = COMMAND_ID_SIZE_IN_BYTES;
        while (!spin1_send_sdp_msg((sdp_msg_t *) &my_msg, SDP_TIMEOUT)) {
	        spin1_delay_us(MESSAGE_DELAY_TIME_WHEN_FAIL);
        }
    }
    // sending missing seq nums
    else{
        my_msg.data[0] = SDP_PACKET_SEND_FIRST_MISSING_SEQ_DATA_IN_COMMAND_ID;
        n_packets_for_missing_seq_nums = data_in_n_missing_seq_packets();
        uint position_in_data = 1;
        for(uint bit=0; bit < size_of_bitfield; bit ++){
            if(!bit_field_test(missing_seq_nums_store, bit)){
                position_in_data = update_and_send_sdp_if_required(bit + 1);
            }
        }
        // send final message if required
        if (position_in_data > 0){
            my_msg.len = LENGTH_OF_SDP_HEADER + (
                position_in_data * WORD_TO_BYTE_MULTIPLIER);
            while (!spin1_send_sdp_msg((sdp_msg_t *) &my_msg, SDP_TIMEOUT)) {
                spin1_delay_us(MESSAGE_DELAY_TIME_WHEN_FAIL);
            }
        }
    }
}

//! \brief processes sdp messages
//! \param[in] mailbox: the sdp message
//! \param[in] port: the port assocated with this sdp message
void data_in_receive_sdp_data(uint mailbox, uint port) {
    sdp_msg_pure_data *msg = (sdp_msg_pure_data *) mailbox;
    if (msg->data[COMMAND_ID_POSITION] ==
            SDP_SEND_DATA_TO_LOCATION_COMMAND_ID){

        // translate elements to variables
        chip_x = msg->data[CHIP_DATA] >> BIT_SHIFT_CHIP_X_COORD;
        chip_y = msg->data[CHIP_DATA] & BIT_MASK_FOR_CHIP_Y_COORD;
        received_address_packet = true;
        max_seq_num = msg->data[MAX_SEQ_NUM];

        // allocate sdram location for holding the seq numbers
        process_sdram_location_for_seq_nums(max_seq_num);

        // send mc messages for first packet
        process_first_sdp_message_into_mc_messages(
            msg, chip_x, chip_y, true, START_OF_DATA_FIRST_SDP);
    }
    else if (msg->data[COMMAND_ID_POSITION] ==
            SDP_SEND_SEQ_DATA_COMMAND_ID){

        // store seq number in store for later processing
        bit_field_set(missing_seq_nums_store, msg->data[SEQ_NUM] -1);
        total_received_seq_nums ++;

        // transmit data to chip
        process_first_sdp_message_into_mc_messages(
            msg, chip_x, chip_y, false, START_OF_DATA_IN_DATA_SDP);
    }

    else if (msg->data[COMMAND_ID_POSITION] ==
            SDP_SEND_MISSING_SEQ_NUMS_BACK_TO_HOST_COMMAND_ID){
        process_missing_seq_nums_and_request_retransmission();
    }
    else if (msg->data[COMMAND_ID_POSITION] == SDP_LAST_DATA_IN_COMMAND_ID){
        process_missing_seq_nums_and_request_retransmission();
    }
    else{
        log_info("Failed to recongise command id %u",
                 msg->data[COMMAND_ID_POSITION]);
    }

    // free the message to stop overload
    spin1_msg_free(msg);
}


//-----------------------------------------------------------------------------
// DATA OUT FUNCTIONALITY
//-----------------------------------------------------------------------------

//! \brief sed sdp message with data
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

    while (!spin1_send_sdp_msg((sdp_msg_t *) &my_msg, SDP_TIMEOUT)) {
	    spin1_delay_us(MESSAGE_DELAY_TIME_WHEN_FAIL);
    }

    position_in_store = 1;
    seq_num += 1;
    data[0] = seq_num;
}

//! \brief receives a mc packet with payload
//! \param[in] key: the mc key
//! \param[in] payload: the mc payload
void data_out_receive_data(uint key, uint payload) {
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
            data[0] = data[0] + (1 << DATA_OUT_END_FLAG_BIT_SHIFT);

            // adjust size as last payload not counted
            position_in_store = position_in_store - 1;

            //log_info("position = %d with seq num %d", position_in_store, seq_num);
            //log_info("last payload was %d", payload);
            send_data();
        } else if (position_in_store == ITEMS_PER_DATA_INDEX ) {
            //log_info("position = %d with seq num %d", position_in_store, seq_num);
            //log_info("last payload was %d", payload);
            send_data();
        }
    }
}

//! \brief sets up state and callbacks for data out
static bool initialize_data_out() {
    log_info("Initialising data out\n");

    // set up callbacks required
    spin1_callback_on(FRPL_PACKET_RECEIVED, data_out_receive_data, FR_PACKET);

    // Get the address this core's DTCM data starts at from SRAM
    address_t address = data_specification_get_data_address();

    // Read the header
    if (!data_specification_read_header(address)) {
        log_error("failed to read the data spec header");
        return false;
    }

    address_t config_address = data_specification_get_region(CONFIG, address);
    new_sequence_key = config_address[NEW_SEQ_KEY];
    first_data_key = config_address[FIRST_DATA_KEY];
    end_flag_key = config_address[END_FLAG_KEY];
    
    // set up sdp packet components
    my_msg.tag = config_address[TAG_ID];	// IPTag 1
    my_msg.dest_port = PORT_ETH;		// Ethernet
    my_msg.dest_addr = sv->eth_addr;		// Nearest Ethernet chip

    // fill in SDP source & flag fields
    my_msg.flags = SDP_FLAGS;
    my_msg.srce_port = SDP_SOURCE_PORT;
    my_msg.srce_addr = sv->p2p_addr;

    return true;
}

//! \brief sets up state and callbacks for data in
static bool initialize_data_in() {
    log_info("Initialising data in\n");
    spin1_callback_on(SDP_PACKET_RX, data_in_receive_sdp_data, SDP);

    // Get the address this core's DTCM data starts at from SRAM
    address_t address = data_specification_get_data_address();

    address_t chip_to_key_space_sdram_loc = data_specification_get_region(
        DATA_IN_CHIP_TO_KEY_SPACE, address);

    for(uint chip_count = 0; chip_count <
            chip_to_key_space_sdram_loc[N_CHIPS]; chip_count++){

        uint x_coord = chip_to_key_space_sdram_loc[
            (chip_count * CHIP_KEY_DATA_SIZE) + X_COORD];
        uint y_coord = chip_to_key_space_sdram_loc[
            (chip_count * CHIP_KEY_DATA_SIZE) + Y_COORD];
        uint base_key = chip_to_key_space_sdram_loc[
                (chip_count * CHIP_KEY_DATA_SIZE) + BASE_KEY];

        data_in_mc_key_map[x_coord][y_coord] = base_key;
    }
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
    log_info("starting packet gatherer\n");

    // initialise the out processing
    if (!initialize_data_out()) {
        rt_error(RTE_SWERR);
    }

    // initialise the in processing
    if (!initialize_data_in()){
        rt_error(RTE_SWERR);
    }

    // start execution
    log_info("Starting\n");

    spin1_start(SYNC_NOWAIT);
}

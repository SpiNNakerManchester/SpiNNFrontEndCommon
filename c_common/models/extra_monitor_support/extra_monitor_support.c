// SARK-based program
#include <sark.h>
#include <stdbool.h>
#include <math.h>
#include <common-typedefs.h>

extern void spin1_wfi();
extern INT_HANDLER sark_int_han(void);

// ------------------------------------------------------------------------
// constants
// ------------------------------------------------------------------------

//-----------------------------------------------------------------------------
// common
//-----------------------------------------------------------------------------

//! size of dsg header in memory space
#define DSG_HEADER 2

//-----------------------------------------------------------------------------
//! stuff to do with SARK DMA
//-----------------------------------------------------------------------------

//! ???????????????????
#define DMA_BURST_SIZE 4

//! ??????????????????
#define DMA_WIDTH 1

//! marker for doing a DMA read
#define DMA_READ  0

//! marker for doing DMA write (don't think this is used in here yet)
#define DMA_WRITE 1

//! the number of DMA buffers to build
#define N_DMA_BUFFERS 2

//-----------------------------------------------------------------------------
// magic numbers for data speed up extractor
//-----------------------------------------------------------------------------

//! flag size for saying ended
#define END_FLAG_SIZE 4

//! flag for saying stuff has ended
#define END_FLAG 0xFFFFFFFF

//! items per SDP packet for sending
#define ITEMS_PER_DATA_PACKET 68

//! convert between words to bytes
#define WORD_TO_BYTE_MULTIPLIER 4

#define SEQUENCE_NUMBER_SIZE 1

#define TX_NOT_FULL_MASK 0x10000000
//-----------------------------------------------------------------------------
//! SDP flags
//-----------------------------------------------------------------------------

//! send data command id in SDP
#define SDP_COMMAND_FOR_SENDING_DATA 100

//! start missing SDP sequence numbers in SDP
//! (this includes n SDP packets expected)
#define SDP_COMMAND_FOR_START_OF_MISSING_SDP_PACKETS 1000

//! other missing SDP sequence numbers in SDP
#define SDP_COMMAND_FOR_MORE_MISSING_SDP_PACKETS 1001

//! timeout for trying to end SDP packet
#define SDP_TIMEOUT 1000

//! extra length adjustment for the SDP header
#define LENGTH_OF_SDP_HEADER 8

//-----------------------------------------------------------------------------
// reinjection functionality magic numbers
//-----------------------------------------------------------------------------

//! throttle power on the MC transmissions if needed (assume not needed)
#define TDMA_WAIT_PERIOD 0

// The initial timeout of the router
#define ROUTER_INITIAL_TIMEOUT 0x004f0000

// Amount to call the timer callback
#define TICK_PERIOD        10

// dumped packet queue length
#define PKT_QUEUE_SIZE     4096

//-----------------------------------------------------------------------------
// VIC stuff
//-----------------------------------------------------------------------------

// CPU VIC slot (WDOG and SDP)
#define CPU_SLOT           SLOT_0

// communications controller VIC slot
#define CC_SLOT            SLOT_1

// timer VIC slot
#define TIMER_SLOT         SLOT_2

// DMA slot
#define DMA_SLOT           SLOT_3

#define RTR_BLOCKED_BIT    25
#define RTR_DOVRFLW_BIT    30
#define RTR_DENABLE_BIT    2
#define RTR_FPE_BIT        17
#define RTR_LE_BIT         6


#define RTR_BLOCKED_MASK   (1 << RTR_BLOCKED_BIT)   // router blocked
#define RTR_DOVRFLW_MASK   (1 << RTR_DOVRFLW_BIT)   // router dump overflow
#define RTR_DENABLE_MASK   (1 << RTR_DENABLE_BIT)   // enable dump interrupts
#define RTR_FPE_MASK       ((1 << RTR_FPE_BIT) - 1)  // if the dumped packet was a processor failure
#define RTR_LE_MASK        ((1 << RTR_LE_BIT) -1) // if the dumped packet was a link failure

#define PKT_CONTROL_SHFT   16
#define PKT_PLD_SHFT       17
#define PKT_TYPE_SHFT      22
#define PKT_ROUTE_SHFT     24

#define PKT_CONTROL_MASK   (0xff << PKT_CONTROL_SHFT)
#define PKT_PLD_MASK       (1 << PKT_PLD_SHFT)
#define PKT_TYPE_MASK      (3 << PKT_TYPE_SHFT)
#define PKT_ROUTE_MASK     (7 << PKT_ROUTE_SHFT)

#define PKT_TYPE_MC        (0 << PKT_TYPE_SHFT)
#define PKT_TYPE_PP        (1 << PKT_TYPE_SHFT)
#define PKT_TYPE_NN        (2 << PKT_TYPE_SHFT)
#define PKT_TYPE_FR        (3 << PKT_TYPE_SHFT)

#define ROUTER_TIMEOUT_MASK 0xFF

// ------------------------------------------------------------------------
// structs used in system
// ------------------------------------------------------------------------

//! struct for a SDP message with pure data, no SCP header
typedef struct sdp_msg_pure_data {	// SDP message (=292 bytes)
    struct sdp_msg *next;		// Next in free list
    uint16_t length;		// length
    uint16_t checksum;		// checksum (if used)

    // sdp_hdr_t
    uint8_t flags;	    	// SDP flag byte
    uint8_t tag;		      	// SDP IPtag
    uint8_t dest_port;		// SDP destination port/CPU
    uint8_t srce_port;		// SDP source port/CPU
    uint16_t dest_addr;		// SDP destination address
    uint16_t srce_addr;		// SDP source address

    // User data (272 bytes when no SCP header)
    uint32_t data[ITEMS_PER_DATA_PACKET];

    uint32_t _PAD;		// Private padding
} sdp_msg_pure_data;

//! dumped packet type
typedef struct {
    uint hdr;
    uint key;
    uint pld;
} dumped_packet_t;

//! packet queue type
typedef struct {
    uint head;
    uint tail;
    dumped_packet_t queue[PKT_QUEUE_SIZE];
} pkt_queue_t;

//! SDP tags used by the sdram reader component.
typedef enum dma_tags_for_data_speed_up {
    //! DMA complete tag for original transmission, this isn't used yet, but
    //! needed for full protocol
    DMA_TAG_READ_FOR_TRANSMISSION = 0,
    //! DMA complete tag for retransmission of data sequence numbers
    DMA_TAG_READ_FOR_RETRANSMISSION = 1,
    //! DMA complete tag for the reading from sdram of data to be retransmitted
    DMA_TAG_RETRANSMISSION_READING = 2,
    //! DMA complete tag for writing the missing SEQ numbers to SDRAM
    DMA_TAG_FOR_WRITING_MISSING_SEQ_NUMS = 3
} dma_tags_for_data_speed_up;

//! \brief message positions for the separate data speed up SDP messages
typedef enum sending_data_sdp_data_positions {
    COMMAND_ID_POSITION = 0,
    SDRAM_POSITION = 1,
    LENGTH_OF_DATA_READ = 2
} sending_data_sdp_data_positions;

//! \brief position in SDP message for missing sequence numbers
typedef enum missing_seq_num_sdp_data_positions {
    POSITION_OF_NO_MISSING_SEQ_SDP_PACKETS = 1,
    START_OF_MISSING_SEQ_NUMS = 2
} missing_seq_num_sdp_data_positions;


// Dropped packet re-injection internal control commands (RC of SCP message)
typedef enum reinjector_command_codes {
    CMD_DPRI_SET_ROUTER_TIMEOUT = 0,
    CMD_DPRI_SET_ROUTER_EMERGENCY_TIMEOUT = 1,
    CMD_DPRI_SET_PACKET_TYPES = 2,
    CMD_DPRI_GET_STATUS = 3,
    CMD_DPRI_RESET_COUNTERS = 4,
    CMD_DPRI_EXIT = 5
} reinjector_command_codes;

//! flag positions for packet types being reinjected
typedef enum reinjection_flag_positions {
    DPRI_PACKET_TYPE_MC = 1,
    DPRI_PACKET_TYPE_PP = 2,
    DPRI_PACKET_TYPE_NN = 4,
    DPRI_PACKET_TYPE_FR = 8
} reinjection_flag_positions;

//! positions in response packet for reinjector status
typedef enum reinjector_status_response_packet_format {
    ROUTER_TIME_OUT_POSITION = 0,
    ROUTER_EMERGENCY_TIMEOUT_POSITION = 1,
    NUMBER_DROPPED_PACKETS_POSITION = 2,
    NUMBER_MISSED_DROPPED_PACKETS_POSITION = 3,
    NUMBER_DROPPED_PACKETS_OVERFLOWS_POSITION = 4,
    NUMBER_REINJECTED_PACKETS_POSITION = 5,
    NUMBER_LINK_DUMPED_PACKETS_POSITION = 6,
    NUMBER_PROCESSOR_DUMPED_PACKETS_POSITION = 7,
    PACKET_TYPES_REINJECTED_POSITION = 8,
    LENGTH_OF_DATA_FOR_STATUS_RESPONSE = 9
} reinjector_status_response_packet_format;

//! values for the position of data in memory.
typedef enum positions_in_memory_for_the_reinject_flags {
    REINJECT_MULTICAST = 0,
    REINJECT_POINT_To_POINT = 1,
    REINJECT_FIXED_ROUTE = 2,
    REINJECT_NEAREST_NEIGHBOUR = 3
} positions_in_memory_for_the_reinject_flags;

//! values for port numbers this core will respond to
typedef enum functionality_to_port_num_map {
    RE_INJECTION_FUNCTIONALITY = 4,
    DATA_SPEED_UP_FUNCTIONALITY = 5
} functionality_to_port_num_map;

typedef enum data_spec_regions{
    CONFIG_REINJECTION = 0,
    CONFIG_DATA_SPEED_UP = 1
} data_spec_regions;

//! human readable definitions of each element in the transmission region
typedef enum data_speed_config_data_elements {
    MY_KEY, NEW_SEQ_KEY, FIRST_DATA_KEY, END_FLAG_KEY, MB
} data_speed_config_data_elements;

//! values for the priority for each callback
typedef enum callback_priorities {
    SDP = 0,
    DMA = 0
} callback_priorities;

// ------------------------------------------------------------------------
// global variables for reinjector functionality
// ------------------------------------------------------------------------

// The content of the communications controller SAR register
static uint cc_sar;

// dumped packet queue
static pkt_queue_t pkt_queue;

// statistics
static uint n_dropped_packets;
static uint n_missed_dropped_packets;
static uint n_dropped_packet_overflows;
static uint n_reinjected_packets;
static uint n_link_dumped_packets;
static uint n_processor_dumped_packets;

// Determine what to reinject
static bool reinject_mc;
static bool reinject_pp;
static bool reinject_nn;
static bool reinject_fr;
static bool run = true;

// VIC
typedef void (*isr_t) ();
volatile isr_t* const vic_vectors  = (isr_t *) (VIC_BASE + 0x100);
volatile uint* const vic_controls = (uint *) (VIC_BASE + 0x200);

// ------------------------------------------------------------------------
// global variables for data speed up functionality
// ------------------------------------------------------------------------

//! transmission stuff
static uint32_t *data_to_transmit[N_DMA_BUFFERS];
static uint32_t transmit_dma_pointer = 0;
static uint32_t position_in_store = 0;
static uint32_t num_items_read = 0;
static bool first_transmission = true;
static bool has_finished = false;
static uint32_t retransmitted_seq_num_items_read = 0;

//! retransmission stuff
static uint32_t number_of_missing_seq_sdp_packets = 0;
static uint32_t number_of_missing_seq_nums_in_sdram = 0;
static uint32_t number_of_elements_to_read_from_sdram = 0;
address_t missing_sdp_seq_num_sdram_address = NULL;
static uint32_t max_seq_num = 0;

//! retransmission DMA stuff
static uint32_t retransmit_seq_nums[ITEMS_PER_DATA_PACKET];
static uint32_t current_dma_pointer = 0;
static uint32_t position_for_retransmission = 0;
static uint32_t missing_seq_num_being_processed = 0;
static uint32_t position_in_read_data = 0;
static uint32_t dma_port_last_used = 0;
static bool in_re_transmission_mode = false;

//! SDP message holder for transmissions
sdp_msg_pure_data my_msg;

//! state for how many bytes it needs to send, gives approximate bandwidth if
//! round number.
static uint32_t bytes_to_read_write;
static address_t *store_address = NULL;
static uint32_t basic_data_key = 0;
static uint32_t new_sequence_key = 0;
static uint32_t first_data_key = 0;
static uint32_t end_flag_key = 0;

// ------------------------------------------------------------------------
// reinjector main functions
// ------------------------------------------------------------------------

//! \brief the plugin callback for the timer
INT_HANDLER reinjection_timer_callback() {
    // clear interrupt in timer,
    tc[T1_INT_CLR] = 1;

    // check if router not blocked
    if ((rtr[RTR_STATUS] & RTR_BLOCKED_MASK) == 0) {
        // access packet queue with FIQ disabled,
        uint cpsr = cpu_fiq_disable();

        // if queue not empty turn on packet bouncing,
        if (pkt_queue.tail != pkt_queue.head) {
            // restore FIQ after queue access,
            cpu_int_restore(cpsr);

            // enable communications controller. interrupt to bounce packets
            vic[VIC_ENABLE] = 1 << CC_TNF_INT;
        } else {
            // restore FIQ after queue access
            cpu_int_restore(cpsr);
        }
    }

    // and tell VIC we're done
    vic[VIC_VADDR] = (uint) vic;
}

//! \brief the plugin callback for sending packets????
INT_HANDLER reinjection_ready_to_send_callback() {
    // TODO: may need to deal with packet timestamp.

    // check if router not blocked
    if ((rtr[RTR_STATUS] & RTR_BLOCKED_MASK) == 0) {
        // access packet queue with FIQ disabled,
        uint cpsr = cpu_fiq_disable();

        // if queue not empty bounce packet,
        if (pkt_queue.tail != pkt_queue.head) {
            // dequeue packet,
            uint hdr = pkt_queue.queue[pkt_queue.head].hdr;
            uint pld = pkt_queue.queue[pkt_queue.head].pld;
            uint key = pkt_queue.queue[pkt_queue.head].key;

            // update queue pointer,
            pkt_queue.head = (pkt_queue.head + 1) % PKT_QUEUE_SIZE;

            // restore FIQ queue access,
            cpu_int_restore(cpsr);

            // write header and route,
            cc[CC_TCR] = hdr & PKT_CONTROL_MASK;
            cc[CC_SAR] = cc_sar | (hdr & PKT_ROUTE_MASK);

            // maybe write payload,
            if (hdr & PKT_PLD_MASK) {
                cc[CC_TXDATA] = pld;
            }

            // write key to fire packet,
            cc[CC_TXKEY] = key;

            // Add to statistics
            n_reinjected_packets += 1;
        } else {
            // restore FIQ after queue access,
            cpu_int_restore(cpsr);

            // and disable communications controller interrupts
            vic[VIC_DISABLE] = 1 << CC_TNF_INT;
        }
    } else {
        // disable communications controller interrupts
        vic[VIC_DISABLE] = 1 << CC_TNF_INT;
    }

    // and tell VIC we're done
    vic[VIC_VADDR] = (uint) vic;
}

//! \brief the callback plugin for handling dropped packets
INT_HANDLER reinjection_dropped_packet_callback() {
    // get packet from router,
    uint hdr = rtr[RTR_DHDR];
    uint pld = rtr[RTR_DDAT];
    uint key = rtr[RTR_DKEY];

    // clear dump status and interrupt in router,
    uint rtr_dstat = rtr[RTR_DSTAT];
    uint rtr_dump_outputs = rtr[RTR_DLINK];
    uint is_processor_dump = (rtr_dump_outputs >> 6) & RTR_FPE_MASK;
    uint is_link_dump = rtr_dump_outputs & RTR_LE_MASK;

    // only reinject if configured
    uint packet_type = (hdr & PKT_TYPE_MASK);
    if (((packet_type == PKT_TYPE_MC) && reinject_mc) ||
            ((packet_type == PKT_TYPE_PP) && reinject_pp) ||
            ((packet_type == PKT_TYPE_NN) && reinject_nn) ||
            ((packet_type == PKT_TYPE_FR) && reinject_fr)) {

        // check for overflow from router
        if (rtr_dstat & RTR_DOVRFLW_MASK) {
            n_missed_dropped_packets += 1;
        } else {
            // Note that the processor_dump and link_dump flags are sticky
            // so you can only really count these if you *haven't* missed a
            // dropped packet - hence this being split out

            if (is_processor_dump > 0) {
                // add to the count the number of active bits from this dumped
                // packet, as this indicates how many processors this packet
                // was meant to go to.
                n_processor_dumped_packets +=
                    __builtin_popcount(is_processor_dump);
            }

            if (is_link_dump > 0) {
                // add to the count the number of active bits from this dumped
                // packet, as this indicates how many links this packet was
                // meant to go to.
                n_link_dumped_packets +=
                    __builtin_popcount(is_link_dump);
            }
        }

        // Only update this counter if this is a packet to reinject
        n_dropped_packets += 1;

        // try to insert dumped packet in the queue,
        uint new_tail = (pkt_queue.tail + 1) % PKT_QUEUE_SIZE;

        // check for space in the queue
        if (new_tail != pkt_queue.head) {
            // queue packet,
            pkt_queue.queue[pkt_queue.tail].hdr = hdr;
            pkt_queue.queue[pkt_queue.tail].key = key;
            pkt_queue.queue[pkt_queue.tail].pld = pld;

            // update queue pointer,
            pkt_queue.tail = new_tail;
        } else {
            // The queue of packets has overflowed
            n_dropped_packet_overflows += 1;
        }
    }
}

//! \brief reads a memory location to set packet types for reinjection
//! \param[in] address: memory address to read the reinjection packet types
void reinjection_read_packet_types(address_t address){
    // process mc reinject flag
    if (address[REINJECT_MULTICAST] == 1) {
        reinject_mc = false;
    } else {
        reinject_mc = true;
    }

    // process point to point flag
    if (address[REINJECT_POINT_To_POINT] == 1) {
        reinject_pp = false;
    } else {
        reinject_pp = true;
    }

    // process fixed route flag
    if (address[REINJECT_FIXED_ROUTE] == 1) {
        reinject_fr = false;
    } else {
        reinject_fr = true;
    }

    // process fixed route flag
    if (address[REINJECT_NEAREST_NEIGHBOUR] == 1) {
        reinject_nn = false;
    } else {
        reinject_nn = true;
    }
}

//! \brief handles the commands for the reinjector code.
//! \param[in] msg: the message with the commands
//! \return the length of extra data put into the message for return
static uint handle_reinjection_command(sdp_msg_t *msg) {
    if (msg->cmd_rc == CMD_DPRI_SET_ROUTER_TIMEOUT) {
        // Set the router wait1 timeout
        if (msg->arg1 > ROUTER_TIMEOUT_MASK) {
            msg->cmd_rc = RC_ARG;
            return 0;
        }
        rtr[RTR_CONTROL] = (rtr[RTR_CONTROL] & 0xff00ffff)
                | ((msg->arg1 & ROUTER_TIMEOUT_MASK) << 16);

        // set SCP command to OK , as successfully completed
        msg->cmd_rc = RC_OK;
        return 0;

    } else if (msg->cmd_rc == CMD_DPRI_SET_ROUTER_EMERGENCY_TIMEOUT) {
        // Set the router wait2 timeout
        if (msg->arg1 > ROUTER_TIMEOUT_MASK) {
            msg->cmd_rc = RC_ARG;
            return 0;
        }
        rtr[RTR_CONTROL] = (rtr[RTR_CONTROL] & 0x00ffffff)
                | ((msg->arg1 & ROUTER_TIMEOUT_MASK) << 24);

        // set SCP command to OK , as successfully completed
        msg->cmd_rc = RC_OK;
        return 0;

    } else if (msg->cmd_rc == CMD_DPRI_SET_PACKET_TYPES) {
        // Set the re-injection options
        reinjection_read_packet_types((address_t) msg->arg1);

        // set SCP command to OK , as successfully completed
        msg->cmd_rc = RC_OK;
        return 0;

    } else if (msg->cmd_rc == CMD_DPRI_GET_STATUS) {
        // Get the status and put it in the packet
        uint *data = &(msg->arg1);

        // Put the router timeouts in the packet
        uint control = (uint) (rtr[RTR_CONTROL] & 0xFFFF0000);
        data[ROUTER_TIME_OUT_POSITION] = (control >> 16) & ROUTER_TIMEOUT_MASK;
        data[ROUTER_EMERGENCY_TIMEOUT_POSITION] =
            (control >> 24) & ROUTER_TIMEOUT_MASK;

        // Put the statistics in the packet
        data[NUMBER_DROPPED_PACKETS_POSITION] = n_dropped_packets;
        data[NUMBER_MISSED_DROPPED_PACKETS_POSITION] =
            n_missed_dropped_packets;
        data[NUMBER_DROPPED_PACKETS_OVERFLOWS_POSITION] =
            n_dropped_packet_overflows;
        data[NUMBER_REINJECTED_PACKETS_POSITION] = n_reinjected_packets;
        data[NUMBER_LINK_DUMPED_PACKETS_POSITION] = n_link_dumped_packets;
        data[NUMBER_PROCESSOR_DUMPED_PACKETS_POSITION] =
            n_processor_dumped_packets;

        io_printf(IO_BUF, "dropped packets %d\n", n_dropped_packets);

        // Put the current services enabled in the packet
        data[PACKET_TYPES_REINJECTED_POSITION] = 0;
        bool values_to_check[] = {reinject_mc, reinject_pp,
                                  reinject_nn, reinject_fr};
        int flags[] = {DPRI_PACKET_TYPE_MC, DPRI_PACKET_TYPE_PP,
                       DPRI_PACKET_TYPE_NN, DPRI_PACKET_TYPE_FR};
        for (int i = 0; i < 4; i++) {
            if (values_to_check[i]) {
                data[PACKET_TYPES_REINJECTED_POSITION] |= flags[i];
            }
        }

        // set SCP command to OK , as successfully completed
        msg->cmd_rc = RC_OK;
        // Return the number of bytes in the packet
        return LENGTH_OF_DATA_FOR_STATUS_RESPONSE * 4;

    } else if (msg->arg1 == CMD_DPRI_RESET_COUNTERS) {
        // Reset the counters
        n_dropped_packets = 0;
        n_missed_dropped_packets = 0;
        n_dropped_packet_overflows = 0;
        n_reinjected_packets = 0;
        n_link_dumped_packets = 0;
        n_processor_dumped_packets = 0;

        // set SCP command to OK , as successfully completed
        msg->cmd_rc = RC_OK;
        return 0;
    } else if (msg->arg1 == CMD_DPRI_EXIT) {
        uint int_select = (1 << TIMER1_INT) | (1 << RTR_DUMP_INT);
        vic[VIC_DISABLE] = int_select;
        vic[VIC_DISABLE] = (1 << CC_TNF_INT);
        vic[VIC_SELECT] = 0;
        run = false;

        // set SCP command to OK , as successfully completed
        msg->cmd_rc = RC_OK;
        return 0;
    }

    // If we are here, the command was not recognised, so fail (ARG as the
    // command is an argument)
    msg->cmd_rc = RC_ARG;
    return 0;
}

// \brief SARK level timer interrupt setup
void reinjection_configure_timer() {
    // Clear the interrupt
    tc[T1_CONTROL] = 0;
    tc[T1_INT_CLR] = 1;

    // Set the timer times
    tc[T1_LOAD] = sv->cpu_clk * TICK_PERIOD;
    tc[T1_BG_LOAD] = sv->cpu_clk * TICK_PERIOD;
}

// \brief pass, not a clue.
void reinjection_configure_comms_controller() {
    // remember SAR register contents (p2p source ID)
    cc_sar = cc[CC_SAR] & 0x0000ffff;
}

// \brief sets up SARK and router to have a interrupt when a packet is dropped
void reinjection_configure_router() {
    // re-configure wait values in router
    rtr[RTR_CONTROL] = (rtr[RTR_CONTROL] & 0x0000ffff) |
	    ROUTER_INITIAL_TIMEOUT;

    // clear router interrupts,
    (void) rtr[RTR_STATUS];

    // clear router dump status,
    (void) rtr[RTR_DSTAT];

    // and enable router interrupts when dumping packets
    rtr[RTR_CONTROL] |= RTR_DENABLE_MASK;
}


//-----------------------------------------------------------------------------
// data speed up main functions
//-----------------------------------------------------------------------------

static inline void send_fixed_route_packet(uint32_t key, uint32_t data) {
    // Wait for a router slot
    while ((cc[CC_TCR] & TX_NOT_FULL_MASK) == 0) {
	// Empty body; CC array is volatile
    }
    cc[CC_TCR] = PKT_FR_PL;
    cc[CC_TXDATA] = data;
    cc[CC_TXKEY] = key;
}

//! \brief takes a DMA'ed block and transmits its contents as mc packets.
//! \param[in] current_dma_pointer: the DMA pointer for the 2 buffers
//! \param[in] number_of_elements_to_send: the number of mc packets to send
//! \param[in] first_packet_key: the first key to transmit with, afterward,
//! defaults to the default key.
void send_data_block(
        uint32_t current_dma_pointer, uint32_t number_of_elements_to_send,
        uint32_t first_packet_key) {
    //log_info("first data is %d", data_to_transmit[current_dma_pointer][0]);

    // send data
    for (uint data_position = 0; data_position < number_of_elements_to_send;
            data_position++) {
        uint32_t current_data =
        	data_to_transmit[current_dma_pointer][data_position];

        send_fixed_route_packet(first_packet_key, current_data);

        // update key to transmit with
        first_packet_key = basic_data_key;
    }
    //log_info("last data is %d",
    //         data_to_transmit[current_dma_pointer][number_of_elements_to_send - 1]);
}

//! \brief sets off a DMA reading a block of SDRAM
//! \param[in] items_to_read the number of word items to read
//! \param[in] dma_tag the DMA tag associated with this read.
//!            transmission or retransmission
//! \param[in] offset where in the data array to start writing to
void read(uint32_t dma_tag, uint32_t offset, uint32_t items_to_read) {
    // set off DMA
    transmit_dma_pointer = (transmit_dma_pointer + 1) % N_DMA_BUFFERS;

    address_t data_sdram_position = (address_t)
	    &store_address[position_in_store];

    // update positions as needed
    position_in_store += items_to_read;
    num_items_read = items_to_read;

    // set off DMA
    uint desc = DMA_WIDTH << 24 | DMA_BURST_SIZE << 21 | DMA_READ << 19 |
	    (items_to_read * WORD_TO_BYTE_MULTIPLIER);

    dma_port_last_used = dma_tag;
    dma[DMA_ADRS] = (uint) data_sdram_position;
    dma[DMA_ADRT] = (uint) &(data_to_transmit[transmit_dma_pointer][offset]);
    dma[DMA_DESC] = desc;

}

//! \brief sends a end flag via multicast
void data_speed_up_send_end_flag() {
    send_fixed_route_packet(end_flag_key, END_FLAG);
}

//! \brief DMA complete callback for reading for original transmission
void dma_complete_reading_for_original_transmission(){
    // set up state
    uint32_t current_dma_pointer = transmit_dma_pointer;
    uint32_t key_to_transmit = basic_data_key;
    uint32_t items_read_this_time = num_items_read;

    // put size in bytes if first send
    //log_info("in original read complete callback");
    if (first_transmission) {
        //io_printf(IO_BUF, "in first\n");
        data_to_transmit[current_dma_pointer][0] = max_seq_num;
        key_to_transmit = first_data_key;
        first_transmission = false;
        items_read_this_time += 1;
    }

    // stopping procedure
    // if a full packet, read another and try again
    //io_printf(IO_BUF, "next position %d, elements %d\n", position_in_store,
    //          number_of_elements_to_read_from_sdram);
    if (position_in_store < number_of_elements_to_read_from_sdram - 1) {
        //io_printf(IO_BUF, "setting off another DMA\n");
        //log_info("setting off another DMA");
        uint32_t num_items_to_read =
        	ITEMS_PER_DATA_PACKET - SEQUENCE_NUMBER_SIZE;

        uint32_t next_position_in_store = position_in_store +
        	(ITEMS_PER_DATA_PACKET - SEQUENCE_NUMBER_SIZE);

        // if less data needed request less data
        if (next_position_in_store >= number_of_elements_to_read_from_sdram) {
            num_items_to_read = number_of_elements_to_read_from_sdram -
        	    position_in_store;
            //log_info("reading %d items", num_items_to_read);
            //log_info("position in store = %d, new position in store = %d",
            //         position_in_store, next_position_in_store);
        }

        // set off another read and transmit DMA'ed one
        read(DMA_TAG_READ_FOR_TRANSMISSION, 0, num_items_to_read);

        //log_info("sending data");
        send_data_block(
        	current_dma_pointer, items_read_this_time, key_to_transmit);
        //log_info("finished sending data");
    } else {
        //io_printf(IO_BUF, "sending last data \n");
        send_data_block(
        	current_dma_pointer, items_read_this_time, key_to_transmit);
        //io_printf(IO_BUF, "sending end flag\n");

        // send end flag.
        data_speed_up_send_end_flag();

        //log_info("finished sending original data with end flag");
        has_finished = true;
        number_of_missing_seq_sdp_packets = 0;
    }

    if (TDMA_WAIT_PERIOD != 0) {
        sark_delay_us(TDMA_WAIT_PERIOD);
    }
}

//! \brief write SDP sequence numbers to sdram that need retransmitting
//! \param[in] data: data to write into sdram
//! \param[in] length: length of data
//! \param[in] start_offset: where in the data to start writing in from.
void write_missing_sdp_seq_nums_into_sdram(
        uint32_t data[], ushort length, uint32_t start_offset) {
    for (ushort offset=start_offset; offset < length; offset ++) {
        missing_sdp_seq_num_sdram_address[
		number_of_missing_seq_nums_in_sdram +
		(offset - start_offset)] = data[offset];
        if (data[offset] > max_seq_num){
            io_printf(IO_BUF, "storing some bad seq num. WTF %d %d\n",
            data[offset], max_seq_num);
        } else {
            //io_printf(IO_BUF, "storing seq num. %d \n", data[offset]);
            //log_info("data writing into sdram is %d", data[offset]);
        }
    }
    number_of_missing_seq_nums_in_sdram += length - start_offset;
}

//! \brief entrance method for storing SDP sequence numbers into SDRAM
//! \param[in] data: the message data to read into sdram
//! \param[in] length: how much data to read
//! \param[in] first: if first packet about missing sequence numbers. If so
//! there is different behaviour
void store_missing_seq_nums(uint32_t data[], ushort length, bool first) {
    uint32_t start_reading_offset = 1;
    if (first){
        number_of_missing_seq_sdp_packets =
        	data[POSITION_OF_NO_MISSING_SEQ_SDP_PACKETS];

        //uint32_t total_missing_seq_nums = (
        //    (ITEMS_PER_DATA_PACKET - 2) +
        //    ((number_of_missing_seq_sdp_packets  - 1) *
        //    (ITEMS_PER_DATA_PACKET - 1)));
        //log_info("final sequence number count is %d", total_missing_seq_nums);

        uint32_t size_of_data =
        	(number_of_missing_seq_sdp_packets * ITEMS_PER_DATA_PACKET *
        		WORD_TO_BYTE_MULTIPLIER) + END_FLAG_SIZE;

        //log_info("doing first with allocation of %d bytes", size_of_data);
        if (missing_sdp_seq_num_sdram_address != NULL) {
            sark_xfree(sv->sdram_heap, missing_sdp_seq_num_sdram_address,
                       ALLOC_LOCK + ALLOC_ID + (sark_vec->app_id << 8));
            missing_sdp_seq_num_sdram_address = NULL;
        }
        missing_sdp_seq_num_sdram_address = sark_xalloc(
        	sv->sdram_heap, size_of_data, 0,
		ALLOC_LOCK + ALLOC_ID + (sark_vec->app_id << 8));
        start_reading_offset = START_OF_MISSING_SEQ_NUMS;
        //log_info("address to write to is %d",
        //         missing_sdp_seq_num_sdram_address);
    }

    // write data to sdram and update packet counter
    write_missing_sdp_seq_nums_into_sdram(data, length, start_reading_offset);
    number_of_missing_seq_sdp_packets -= 1;
}

//! \brief sets off a DMA for retransmission stuff
void retransmission_dma_read() {
    // locate where we are in sdram
    address_t data_sdram_position =
	    &missing_sdp_seq_num_sdram_address[position_for_retransmission];
    //log_info(" address to DMA from is %d", data_sdram_position);
    //log_info(" DMA pointer = %d", dma_pointer);
    //log_info("size to read is %d",
    //         ITEMS_PER_DATA_PACKET * WORD_TO_BYTE_MULTIPLIER);

    // set off DMA via SARK commands
    //log_info("setting off DMA");
    uint desc =
	    DMA_WIDTH << 24 | DMA_BURST_SIZE << 21 | DMA_READ << 19 |
	    (ITEMS_PER_DATA_PACKET * WORD_TO_BYTE_MULTIPLIER);
    dma_port_last_used = DMA_TAG_READ_FOR_RETRANSMISSION;
    dma[DMA_ADRS] = (uint) data_sdram_position;
    dma[DMA_ADRT] = (uint) retransmit_seq_nums;
    dma[DMA_DESC] = desc;
}

//! \brief reads in missing sequence numbers and sets off the reading of
//! sdram for the equivalent data
void the_dma_complete_read_missing_seqeuence_nums() {
    //! check if at end of read missing sequence numbers
    if (position_in_read_data > ITEMS_PER_DATA_PACKET) {
        position_for_retransmission += ITEMS_PER_DATA_PACKET;
        if (number_of_missing_seq_nums_in_sdram >
		position_for_retransmission) {
            position_in_read_data = 0;
            retransmission_dma_read();
        }
    } else {
        // get next sequence number to regenerate
        missing_seq_num_being_processed = (uint32_t)
        	retransmit_seq_nums[position_in_read_data];
        //io_printf(IO_BUF, "dealing with seq num %d \n",
        //         missing_seq_num_being_processed);
        if (missing_seq_num_being_processed != END_FLAG) {

            // regenerate data
            position_in_store = missing_seq_num_being_processed *
        	    (ITEMS_PER_DATA_PACKET - SEQUENCE_NUMBER_SIZE);
            uint32_t left_over_portion =
        	    bytes_to_read_write / WORD_TO_BYTE_MULTIPLIER -
		    position_in_store;

            //io_printf(IO_BUF, "for seq %d, pos = %d, left %d\n",
            //missing_seq_num_being_processed, position_in_store,
            //left_over_portion);

            if (left_over_portion <
                    ITEMS_PER_DATA_PACKET - SEQUENCE_NUMBER_SIZE) {
                retransmitted_seq_num_items_read = left_over_portion + 1;
                read(DMA_TAG_RETRANSMISSION_READING, 1, left_over_portion);
            } else {
                retransmitted_seq_num_items_read = ITEMS_PER_DATA_PACKET;
                read(DMA_TAG_RETRANSMISSION_READING, 1,
                	ITEMS_PER_DATA_PACKET - SEQUENCE_NUMBER_SIZE);
            }
        } else {        // finished data send, tell host its done
            data_speed_up_send_end_flag();
            in_re_transmission_mode = false;
            missing_sdp_seq_num_sdram_address = NULL;
            position_in_read_data = 0;
            position_for_retransmission = 0;
            number_of_missing_seq_nums_in_sdram = 0;
        }
    }
}

//! \brief DMA complete callback for have read missing sequence number data
void dma_complete_reading_retransmission_data() {
    //log_info("just read data for a given missing sequence number");

    // set sequence number as first element
    data_to_transmit[transmit_dma_pointer][0] =
        missing_seq_num_being_processed;

    if (missing_seq_num_being_processed > max_seq_num) {
	io_printf(
		IO_BUF, "Got some bad seq num here. max is %d and got %d \n",
	        max_seq_num, missing_seq_num_being_processed);
    }

    // send new data back to host
    //log_info("doing retransmission !!!!!!");
    send_data_block(transmit_dma_pointer, retransmitted_seq_num_items_read,
                    new_sequence_key);

    position_in_read_data += 1;
    the_dma_complete_read_missing_seqeuence_nums();
}

//! \brief DMA complete callback for have read missing sequence number data
void dma_complete_writing_missing_seq_to_sdram() {
    io_printf(IO_BUF, "Need to figure what to do here\n");
}

//! \brief the handler for all messages coming in for data speed up
//! functionality.
//! \param[in] msg: the SDP message (without SCP header)
void handle_data_speed_up(sdp_msg_pure_data *msg) {

    if (msg->data[COMMAND_ID_POSITION] == SDP_COMMAND_FOR_SENDING_DATA) {

        //io_printf(IO_BUF, "starting the send of original data\n");
        // set sdram position and length
        store_address = (address_t*) msg->data[SDRAM_POSITION];
        bytes_to_read_write = msg->data[LENGTH_OF_DATA_READ];
        sark_msg_free((sdp_msg_t *) msg);

        max_seq_num = (float)bytes_to_read_write / (float)(67 * 4);
        max_seq_num = ceil(max_seq_num);
        //io_printf(IO_BUF, "address %d, bytes to write %d\n", store_address,
        //          bytes_to_read_write);

        // reset states
        first_transmission = true;
        transmit_dma_pointer = 0;
        position_in_store = 0;
        number_of_elements_to_read_from_sdram =
            (uint)(bytes_to_read_write / WORD_TO_BYTE_MULTIPLIER);
        //io_printf(IO_BUF, "elements to read %d \n",
        //          number_of_elements_to_read_from_sdram);

        if (number_of_elements_to_read_from_sdram <
                ITEMS_PER_DATA_PACKET - SEQUENCE_NUMBER_SIZE) {
            read(DMA_TAG_READ_FOR_TRANSMISSION, 1,
                number_of_elements_to_read_from_sdram);
        } else {
            read(DMA_TAG_READ_FOR_TRANSMISSION, 1,
                ITEMS_PER_DATA_PACKET - SEQUENCE_NUMBER_SIZE);
        }
    }
    // start or continue to gather missing packet list
    else if (msg->data[COMMAND_ID_POSITION] ==
            SDP_COMMAND_FOR_START_OF_MISSING_SDP_PACKETS ||
            msg->data[COMMAND_ID_POSITION] ==
            SDP_COMMAND_FOR_MORE_MISSING_SDP_PACKETS) {
        //log_info("starting re send mode");

        // if aready in a retrnamission phase, dont process as normal
        if (msg->data[COMMAND_ID_POSITION] ==
                    SDP_COMMAND_FOR_START_OF_MISSING_SDP_PACKETS &&
                    number_of_missing_seq_sdp_packets != 0){
                //io_printf(IO_BUF, "forcing start of retranmission packet\n");
                sark_msg_free((sdp_msg_t *) msg);
                number_of_missing_seq_sdp_packets = 0;
                missing_sdp_seq_num_sdram_address[
                    number_of_missing_seq_nums_in_sdram] = END_FLAG;
                number_of_missing_seq_nums_in_sdram += 1;
                position_in_read_data = 0;
                position_for_retransmission = 0;
                in_re_transmission_mode = true;
                retransmission_dma_read();
        } else {
            // reset state, as could be here from multiple attempts
            if (!in_re_transmission_mode) {

                // put missing sequence numbers into sdram
                //io_printf(IO_BUF, "storing thing\n");
                store_missing_seq_nums(
                    msg->data,
                    (msg->length - LENGTH_OF_SDP_HEADER) /
                     WORD_TO_BYTE_MULTIPLIER,
                    msg->data[COMMAND_ID_POSITION] ==
                        SDP_COMMAND_FOR_START_OF_MISSING_SDP_PACKETS);

                //log_info("free message");
                //io_printf(IO_BUF, "freeing SDP packet\n");
                sark_msg_free((sdp_msg_t *) msg);

                // if got all missing packets, start retransmitting them to host
                if (number_of_missing_seq_sdp_packets == 0) {
                    // packets all received, add finish flag for DMA stoppage

                    //io_printf(IO_BUF, "starting resend process\n");
                    missing_sdp_seq_num_sdram_address[
                    number_of_missing_seq_nums_in_sdram] = END_FLAG;
                    number_of_missing_seq_nums_in_sdram += 1;
                    position_in_read_data = 0;
                    position_for_retransmission = 0;

                    //log_info("start retransmission");
                    // start DMA off
                    in_re_transmission_mode = true;
                    retransmission_dma_read();
                }
            }
        }
    } else {
        io_printf(IO_BUF, "received unknown SDP packet\n");
    }
}

//! \brief the handler for all DMA'S complete!
INT_HANDLER speed_up_handle_dma(){
    // reset the interrupt.
    dma[DMA_CTRL] = 0x8;
    if (dma_port_last_used == DMA_TAG_READ_FOR_TRANSMISSION) {
        dma_complete_reading_for_original_transmission();
    } else if (dma_port_last_used == DMA_TAG_READ_FOR_RETRANSMISSION) {
        the_dma_complete_read_missing_seqeuence_nums();
    } else if (dma_port_last_used == DMA_TAG_RETRANSMISSION_READING) {
        dma_complete_reading_retransmission_data();
    } else if (dma_port_last_used == DMA_TAG_FOR_WRITING_MISSING_SEQ_NUMS) {
        dma_complete_writing_missing_seq_to_sdram();
    } else {
        io_printf(IO_BUF, "NOT VALID DMA CALLBACK PORT!!!!\n");
    }
    // and tell VIC we're done
    vic[VIC_VADDR] = (uint) vic;
}

//-----------------------------------------------------------------------------
// common code
//-----------------------------------------------------------------------------
void __real_sark_int(void *pc);
void __wrap_sark_int(void *pc) {
    // Check for extra messages added by this core
    uint cmd = sark.vcpu->mbox_ap_cmd;
    if (cmd == SHM_MSG) {
        sc[SC_CLR_IRQ] = SC_CODE + (1 << sark.phys_cpu);
        sark.vcpu->mbox_ap_cmd = SHM_IDLE;

        sdp_msg_t *shm_msg = (sdp_msg_t *) sark.vcpu->mbox_ap_msg;
        sdp_msg_t *msg = sark_msg_get();

        if (msg != NULL) {
            sark_msg_cpy(msg, shm_msg);
            sark_shmsg_free(shm_msg);

            io_printf(IO_BUF, "port %d\n", (msg->dest_port & PORT_MASK) >> PORT_SHIFT);

            switch ((msg->dest_port & PORT_MASK) >> PORT_SHIFT) {
            case RE_INJECTION_FUNCTIONALITY:
                msg->length = 12 + handle_reinjection_command(msg);
                uint dest_port = msg->dest_port;
                uint dest_addr = msg->dest_addr;

                msg->dest_port = msg->srce_port;
                msg->srce_port = dest_port;

                msg->dest_addr = msg->srce_addr;
                msg->srce_addr = dest_addr;

                sark_msg_send(msg, 10);
                break;
            case DATA_SPEED_UP_FUNCTIONALITY:
                handle_data_speed_up((sdp_msg_pure_data *) msg);
                break;
            default:
                io_printf(IO_BUF, "port %d\n",
                          (msg->dest_port & PORT_MASK) >> PORT_SHIFT);
        	// Do nothing
            }
            sark_msg_free(msg);
        } else {
            sark_shmsg_free(shm_msg);
        }
    } else {
        // Run the default callback
        __real_sark_int(pc);
    }
}

//-----------------------------------------------------------------------------
// initializers
//-----------------------------------------------------------------------------


//! \brief sets up data required by the reinjection functionality
void reinjection_initialise() {
    // set up config region
    // Get the address this core's DTCM data starts at from SRAM
    vcpu_t *sark_virtual_processor_info = (vcpu_t*) SV_VCPU;
    address_t address =
        (address_t) sark_virtual_processor_info[sark.virt_cpu].user0;
    address = (address_t) (address[DSG_HEADER + CONFIG_REINJECTION]);

    // process data
    reinjection_read_packet_types(address);

    // Setup the CPU interrupt for WDOG
    vic_controls[sark_vec->sark_slot] = 0;
    vic_vectors[CPU_SLOT]  = sark_int_han;
    vic_controls[CPU_SLOT] = 0x20 | CPU_INT;

    // Setup the communications controller interrupt
    vic_vectors[CC_SLOT]  = reinjection_ready_to_send_callback;
    vic_controls[CC_SLOT] = 0x20 | CC_TNF_INT;

    // Setup the timer interrupt
    vic_vectors[TIMER_SLOT]  = reinjection_timer_callback;
    vic_controls[TIMER_SLOT] = 0x20 | TIMER1_INT;

    // Setup the router interrupt as a fast interrupt
    sark_vec->fiq_vec = reinjection_dropped_packet_callback;
    vic[VIC_SELECT] = 1 << RTR_DUMP_INT;
}

//! \brief sets up data required by the data speed up functionality
void data_speed_up_initialise() {
    vcpu_t *sark_virtual_processor_info = (vcpu_t*) SV_VCPU;
    address_t address =
        (address_t) sark_virtual_processor_info[sark.virt_cpu].user0;
    address = (address_t) (address[DSG_HEADER + CONFIG_DATA_SPEED_UP]);
    basic_data_key = address[MY_KEY];
    new_sequence_key = address[NEW_SEQ_KEY];
    first_data_key = address[FIRST_DATA_KEY];
    end_flag_key = address[END_FLAG_KEY];


    vic_vectors[DMA_SLOT]  = speed_up_handle_dma;
    vic_controls[DMA_SLOT] = 0x20 | DMA_DONE_INT;

    for (uint32_t i = 0; i < 2; i++) {
        data_to_transmit[i] = (uint32_t*) sark_xalloc(
            sark.heap, ITEMS_PER_DATA_PACKET * sizeof(uint32_t), 0,
        ALLOC_LOCK);
        if (data_to_transmit[i] == NULL){
            io_printf(IO_BUF, "failed to allocate dtcm for DMA buffers\n");
            rt_error(RTE_SWERR);
        }
    }

    // configuration for the DMA's by the speed data loader
    dma[DMA_CTRL] = 0x3f; // Abort pending and active transfers
    dma[DMA_CTRL] = 0x0d; // clear possible transfer done and restart
    dma[DMA_GCTL] = 0x000c00; // enable DMA done interrupt
}

//-----------------------------------------------------------------------------
// main method
//-----------------------------------------------------------------------------
void c_main() {
    sark_cpu_state(CPU_STATE_RUN);

    // Configure
    reinjection_configure_timer();
    reinjection_configure_comms_controller();
    reinjection_configure_router();

    // Initialise the statistics
    n_dropped_packets = 0;
    n_reinjected_packets = 0;
    n_missed_dropped_packets = 0;
    n_dropped_packet_overflows = 0;

    // set up VIC callbacks and interrupts accordingly
    // Disable the interrupts that we are configuring (except CPU for WDOG)
    uint int_select = (1 << TIMER1_INT) | (1 << RTR_DUMP_INT) |
        (1 << DMA_DONE_INT);
    vic[VIC_DISABLE] = int_select;
    vic[VIC_DISABLE] = (1 << CC_TNF_INT);

    // set up reinjection functionality
    reinjection_initialise();

    // set up data speed up functionality
    data_speed_up_initialise();

    // Enable interrupts and timer
    vic[VIC_ENABLE] = int_select;
    tc[T1_CONTROL] = 0xe2;

    // Run until told to exit
    while (run) {
        spin1_wfi();
    }
}
// ------------------------------------------------------------------------

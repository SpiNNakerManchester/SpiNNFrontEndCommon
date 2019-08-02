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

// SARK-based program
#include <sark.h>
#include <stdbool.h>
#include <common-typedefs.h>

extern void spin1_wfi(void);
extern INT_HANDLER sark_int_han(void);

// ------------------------------------------------------------------------
// constants
// ------------------------------------------------------------------------

//-----------------------------------------------------------------------------
//! stuff to do with SARK DMA
//-----------------------------------------------------------------------------

//! ???????????????????
#define DMA_BURST_SIZE 4

//! ??????????????????
#define DMA_WIDTH 1

//! the number of DMA buffers to build
#define N_DMA_BUFFERS 2

enum {
    //! marker for doing a DMA read
    DMA_READ = 0,
    //! marker for doing DMA write (don't think this is used in here yet)
    DMA_WRITE = 1
};

//-----------------------------------------------------------------------------
// magic numbers for data speed up extractor
//-----------------------------------------------------------------------------

//! flag size for saying ended
#define END_FLAG_SIZE 4

//! flag for saying stuff has ended
#define END_FLAG 0xFFFFFFFF

//! items per SDP packet for sending
#define ITEMS_PER_DATA_PACKET 68

#define SEQUENCE_NUMBER_SIZE 1

#define SDP_PAYLOAD_WORDS (ITEMS_PER_DATA_PACKET - SEQUENCE_NUMBER_SIZE)
#define SDP_PAYLOAD_BYTES (SDP_PAYLOAD_WORDS * sizeof(uint))

#define TX_NOT_FULL_MASK 0x10000000

//-----------------------------------------------------------------------------
//! SDP flags
//-----------------------------------------------------------------------------

typedef enum data_out_sdp_commands {
    //! send data command ID in SDP
    SDP_CMD_START_SENDING_DATA = 100,
    //! start missing SDP sequence numbers in SDP
    //! (this includes number of SDP packets expected)
    SDP_CMD_START_OF_MISSING_SDP_PACKETS = 1000,
    //! other missing SDP sequence numbers in SDP
    SDP_CMD_MORE_MISSING_SDP_PACKETS = 1001,
    //! stop sending now!
    SDP_CMD_CLEAR = 2000
} data_out_sdp_commands;

//! timeout for trying to end SDP packet
#define SDP_TIMEOUT 1000

//! extra length adjustment for the SDP header, in bytes
#define LENGTH_OF_SDP_HEADER 8

//-----------------------------------------------------------------------------
// speed up Data in stuff
//-----------------------------------------------------------------------------

//! max router entries
#define N_ROUTER_ENTRIES           1024

//! hardcoded invalud router entry state for key
#define INVALID_ROUTER_ENTRY_KEY   0xFFFFFFFF

//! hardcoded invalid router entry state for mask
#define INVALID_ROUTER_ENTRY_MASK  0x00000000

//! hardcoded invalid router entry state for route
#define INVALID_ROUTER_ENTRY_ROUTE 0xFF000000

//! mask to get app id from free entry of rtr_entry_t
#define APP_ID_MASK_FROM_FREE      0x000000FF

//! offset for getting app id from free
#define APP_ID_OFFSET_FROM_FREE    24

#define N_BASIC_SYSTEM_ROUTER_ENTRIES 1

#define N_USABLE_ROUTER_ENTRIES    (N_ROUTER_ENTRIES - N_BASIC_SYSTEM_ROUTER_ENTRIES)

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

enum {
    // CPU VIC slot (WDOG and SDP)
    CPU_SLOT = SLOT_0,
    // communications controller VIC slot
    CC_SLOT = SLOT_1,
    // timer VIC slot
    TIMER_SLOT = SLOT_2,
    // DMA slot
    DMA_SLOT = SLOT_3,
    // DMA error VIC slot
    DMA_ERROR_SLOT = SLOT_4,
    // DMA timeout VIC slot
    DMA_TIMEOUT_SLOT = SLOT_5,
    // MC payload slot
    MC_PAYLOAD_SLOT = SLOT_6
};

enum {
    RTR_DOVRFLW_BIT = 30,
    RTR_BLOCKED_BIT = 25,
    RTR_FPE_BIT = 17,
    RTR_LE_BIT = 6,
    RTR_DENABLE_BIT = 2
};

enum {
    RTR_BLOCKED_MASK = 1 << RTR_BLOCKED_BIT,   // router blocked
    RTR_DOVRFLW_MASK = 1 << RTR_DOVRFLW_BIT,   // router dump overflow
    RTR_DENABLE_MASK = 1 << RTR_DENABLE_BIT,   // enable dump interrupts
    RTR_FPE_MASK = (1 << RTR_FPE_BIT) - 1,     // if the dumped packet was a processor failure
    RTR_LE_MASK = (1 << RTR_LE_BIT) - 1        // if the dumped packet was a link failure
};

enum {
    PKT_CONTROL_SHFT = 16,
    PKT_PLD_SHFT = 17,
    PKT_TYPE_SHFT = 22,
    PKT_ROUTE_SHFT = 24
};

enum {
    PKT_CONTROL_MASK = 0xff << PKT_CONTROL_SHFT,
    PKT_PLD_MASK = 1 << PKT_PLD_SHFT,
    PKT_TYPE_MASK = 3 << PKT_TYPE_SHFT,
    PKT_ROUTE_MASK = 7 << PKT_ROUTE_SHFT
};

enum {
    PKT_TYPE_MC = 0 << PKT_TYPE_SHFT,
    PKT_TYPE_PP = 1 << PKT_TYPE_SHFT,
    PKT_TYPE_NN = 2 << PKT_TYPE_SHFT,
    PKT_TYPE_FR = 3 << PKT_TYPE_SHFT
};

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
typedef struct dumped_packet_t {
    uint hdr;
    uint key;
    uint pld;
} dumped_packet_t;

//! packet queue type
typedef struct pkt_queue_t {
    uint head;
    uint tail;
    dumped_packet_t queue[PKT_QUEUE_SIZE];
} pkt_queue_t;

//! SDP tags used by the SDRAM reader component.
enum dma_tags_for_data_speed_up {
    //! DMA complete tag for original transmission, this isn't used yet, but
    //! needed for full protocol
    DMA_TAG_READ_FOR_TRANSMISSION = 0,
    //! DMA complete tag for retransmission of data sequence numbers
    DMA_TAG_READ_FOR_RETRANSMISSION = 1,
    //! DMA complete tag for the reading from SDRAM of data to be retransmitted
    DMA_TAG_RETRANSMISSION_READING = 2,
    //! DMA complete tag for writing the missing SEQ numbers to SDRAM
    DMA_TAG_FOR_WRITING_MISSING_SEQ_NUMS = 3
};

//! \brief message payload for the data speed up out SDP messages
typedef struct sdp_data_out_t {
    data_out_sdp_commands command;
    address_t sdram_location;
    uint length;
} sdp_data_out_t;

//! \brief router entry positions in sdram
typedef struct router_entry_t {
    uint32_t key;
    uint32_t mask;
    uint32_t route;
} router_entry_t;

//! \brief data positions in sdram for data in config
typedef struct data_in_data_items {
    uint32_t address_mc_key;
    uint32_t data_mc_key;
    uint32_t boundary_mc_key;
    uint32_t n_system_router_entries;
    router_entry_t system_router_entries[];
} data_in_data_items_t;

//! \brief position in SDP message for missing sequence numbers
enum missing_seq_num_sdp_data_positions {
    POSITION_OF_NO_MISSING_SEQ_SDP_PACKETS = 1,
    START_OF_MISSING_SEQ_NUMS = 2
};

// Dropped packet re-injection internal control commands (RC of SCP message)
enum reinjector_command_codes {
    CMD_DPRI_SET_ROUTER_TIMEOUT = 0,
    CMD_DPRI_SET_ROUTER_EMERGENCY_TIMEOUT = 1,
    CMD_DPRI_SET_PACKET_TYPES = 2,
    CMD_DPRI_GET_STATUS = 3,
    CMD_DPRI_RESET_COUNTERS = 4,
    CMD_DPRI_EXIT = 5,
    CMD_DPRI_CLEAR = 6
};

//! flag positions for packet types being reinjected
enum reinjection_flag_positions {
    DPRI_PACKET_TYPE_MC = 1,
    DPRI_PACKET_TYPE_PP = 2,
    DPRI_PACKET_TYPE_NN = 4,
    DPRI_PACKET_TYPE_FR = 8
};

//! defintion of response packet for reinjector status
typedef struct reinjector_status_response_packet_t {
    uint router_timeout;
    uint router_emergency_timeout;
    uint n_dropped_packets;
    uint n_missed_dropped_packets;
    uint n_dropped_packets_overflows;
    uint n_reinjected_packets;
    uint n_link_dumped_packets;
    uint n_processor_dumped_packets;
    uint packet_types_reinjected;
} reinjector_status_response_packet_t;

//! how the reinjection configuration is laid out in memory.
typedef struct reinject_config_t {
    uint multicast_flag;
    uint point_to_point_flag;
    uint fixed_route_flag;
    uint nearest_neighbour_flag;
} reinject_config_t;

//! values for port numbers this core will respond to
enum functionality_to_port_num_map {
    REINJECTION_PORT = 4,
    DATA_SPEED_UP_OUT_PORT = 5,
    DATA_SPEED_UP_IN_PORT = 6
};

enum data_spec_regions {
    CONFIG_REINJECTION = 0,
    CONFIG_DATA_SPEED_UP_OUT = 1,
    CONFIG_DATA_SPEED_UP_IN = 2
};

enum speed_up_in_command {
    //! read in application mc routes
    SDP_COMMAND_FOR_SAVING_APPLICATION_MC_ROUTING = 6,
    //! load application mc routes
    SDP_COMMAND_FOR_LOADING_APPLICATION_MC_ROUTES = 7,
    //! load system mc routes
    SDP_COMMAND_FOR_LOADING_SYSTEM_MC_ROUTES = 8
};

//! human readable definitions of each element in the transmission region
typedef struct data_speed_out_config_t {
    uint my_key;
    uint new_seq_key;
    uint first_data_key;
    uint end_flag_key;
} data_speed_out_config_t;

//! values for the priority for each callback
enum callback_priorities {
    SDP = 0,
    DMA = 0
};

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
typedef void (*isr_t) (void);
static volatile isr_t* const vic_vectors = (isr_t *) (VIC_BASE + 0x100);
static volatile uint* const vic_controls = (uint *) (VIC_BASE + 0x200);

// ------------------------------------------------------------------------
// global variables for data speed up in functionality
// ------------------------------------------------------------------------

//! data in variables
static router_entry_t *saved_application_router_table = NULL;
static uint data_in_address_key = 0;
static uint data_in_data_key = 0;
static uint data_in_boundary_key = 0;
static address_t data_in_write_address = NULL, first_write_address = NULL;

// ------------------------------------------------------------------------
// global variables for data speed up out functionality
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
static uint32_t n_missing_seq_sdp_packets = 0;
static uint32_t n_missing_seq_nums_in_sdram = 0;
static uint32_t n_elements_to_read_from_sdram = 0;
static address_t missing_sdp_seq_num_sdram_address = NULL;
static uint32_t max_seq_num = 0;

//! retransmission DMA stuff
static uint32_t retransmit_seq_nums[ITEMS_PER_DATA_PACKET];
static uint32_t position_for_retransmission = 0;
static uint32_t missing_seq_num_being_processed = 0;
static uint32_t position_in_read_data = 0;
static uint32_t dma_port_last_used = 0;
static bool in_retransmission_mode = false;

//! SDP message holder for transmissions
static ushort my_addr;

//! state for how many bytes it needs to send, gives approximate bandwidth if
//! round number.
static uint32_t bytes_to_read_write;
static address_t store_address = NULL;
static uint32_t basic_data_key = 0;
static uint32_t new_sequence_key = 0;
static uint32_t first_data_key = 0;
static uint32_t end_flag_key = 0;
static uint32_t stop = 0;

// ------------------------------------------------------------------------
// support functions
// ------------------------------------------------------------------------

static vcpu_t *const sark_virtual_processor_info = (vcpu_t *) SV_VCPU;

typedef struct dsg_header_t {
    uint dse_magic_number;      // Magic number (== 0xAD130AD6)
    uint dse_version;           // Version (== 0x00010000)
    void *regions[];            // Pointers to DSG regions
} dsg_header_t;

static inline void *dsg_block(uint index) {
    dsg_header_t *dsg_header = (dsg_header_t *)
            sark_virtual_processor_info[sark.virt_cpu].user0;
    return dsg_header->regions[index];
}

static inline void *sdram_alloc(uint size) {
    return sark_xalloc(sv->sdram_heap, size, 0,
            ALLOC_LOCK | ALLOC_ID | (sark_vec->app_id << 8));
}

static inline void sdram_free(void *data) {
    sark_xfree(sv->sdram_heap, data,
            ALLOC_LOCK | ALLOC_ID | (sark_vec->app_id << 8));
}

static inline uint sdram_max_block_size(void) {
    return sark_heap_max(sv->sdram_heap, ALLOC_LOCK);
}

// ------------------------------------------------------------------------
// reinjector main functions
// ------------------------------------------------------------------------

//! \brief the plugin callback for the timer
static INT_HANDLER reinjection_timer_callback(void) {
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
static INT_HANDLER reinjection_ready_to_send_callback(void) {
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
static INT_HANDLER reinjection_dropped_packet_callback(void) {
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

        // Disable FIQ for queue access
        uint cpsr = cpu_fiq_disable();

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

        // restore FIQ after queue access,
        cpu_int_restore(cpsr);
    }
}

//! \brief reads a memory location to set packet types for reinjection
//! \param[in] address: memory address to read the reinjection packet types
static void reinjection_read_packet_types(reinject_config_t *config) {
    // process multicast reinject flag
    if (config->multicast_flag == 1) {
        reinject_mc = false;
    } else {
        reinject_mc = true;
    }

    // process point to point flag
    if (config->point_to_point_flag == 1) {
        reinject_pp = false;
    } else {
        reinject_pp = true;
    }

    // process fixed route flag
    if (config->fixed_route_flag == 1) {
        reinject_fr = false;
    } else {
        reinject_fr = true;
    }

    // process fixed route flag
    if (config->nearest_neighbour_flag == 1) {
        reinject_nn = false;
    } else {
        reinject_nn = true;
    }
}

//! \brief Set the router wait1 timeout.
static inline int reinjection_set_timeout(sdp_msg_t *msg) {
    if (msg->arg1 > ROUTER_TIMEOUT_MASK) {
        msg->cmd_rc = RC_ARG;
        return 0;
    }
    rtr[RTR_CONTROL] = (rtr[RTR_CONTROL] & 0xff00ffff)
            | ((msg->arg1 & ROUTER_TIMEOUT_MASK) << 16);

    // set SCP command to OK , as successfully completed
    msg->cmd_rc = RC_OK;
    return 0;
}

//! \brief Set the router wait2 timeout.
static inline int reinjection_set_emergency_timeout(sdp_msg_t *msg) {
    if (msg->arg1 > ROUTER_TIMEOUT_MASK) {
        msg->cmd_rc = RC_ARG;
        return 0;
    }
    rtr[RTR_CONTROL] = (rtr[RTR_CONTROL] & 0x00ffffff)
            | ((msg->arg1 & ROUTER_TIMEOUT_MASK) << 24);

    // set SCP command to OK , as successfully completed
    msg->cmd_rc = RC_OK;
    return 0;
}

//! \brief Set the re-injection options.
static inline int reinjection_set_packet_types(sdp_msg_t *msg) {
    reinject_mc = msg->arg1;
    reinject_pp = msg->arg2;
    reinject_fr = msg->arg3;
    reinject_nn = msg->data[0];

    // set SCP command to OK , as successfully completed
    msg->cmd_rc = RC_OK;
    return 0;
}

//! \brief Get the status and put it in the packet
static inline int reinjection_get_status(sdp_msg_t *msg) {
    reinjector_status_response_packet_t *data =
            (reinjector_status_response_packet_t *) &msg->arg1;

    // Put the router timeouts in the packet
    uint control = (uint) (rtr[RTR_CONTROL] & 0xFFFF0000);
    data->router_timeout = (control >> 16) & ROUTER_TIMEOUT_MASK;
    data->router_emergency_timeout = (control >> 24) & ROUTER_TIMEOUT_MASK;

    // Put the statistics in the packet
    data->n_dropped_packets = n_dropped_packets;
    data->n_missed_dropped_packets = n_missed_dropped_packets;
    data->n_dropped_packets_overflows = n_dropped_packet_overflows;
    data->n_reinjected_packets = n_reinjected_packets;
    data->n_link_dumped_packets = n_link_dumped_packets;
    data->n_processor_dumped_packets = n_processor_dumped_packets;

    io_printf(IO_BUF, "dropped packets %d\n", n_dropped_packets);

    // Put the current services enabled in the packet
    data->packet_types_reinjected = 0;
    bool values_to_check[] = {reinject_mc, reinject_pp,
                              reinject_nn, reinject_fr};
    int flags[] = {DPRI_PACKET_TYPE_MC, DPRI_PACKET_TYPE_PP,
                   DPRI_PACKET_TYPE_NN, DPRI_PACKET_TYPE_FR};
    for (int i = 0; i < 4; i++) {
        if (values_to_check[i]) {
            data->packet_types_reinjected |= flags[i];
        }
    }

    // set SCP command to OK , as successfully completed
    msg->cmd_rc = RC_OK;
    // Return the number of bytes in the packet
    return sizeof(reinjector_status_response_packet_t);
}

//! \brief Reset the counters
static inline int reinjection_reset_counters(sdp_msg_t *msg) {
    n_dropped_packets = 0;
    n_missed_dropped_packets = 0;
    n_dropped_packet_overflows = 0;
    n_reinjected_packets = 0;
    n_link_dumped_packets = 0;
    n_processor_dumped_packets = 0;

    // set SCP command to OK , as successfully completed
    msg->cmd_rc = RC_OK;
    return 0;
}

static inline int reinjection_exit(sdp_msg_t *msg) {
    uint int_select = (1 << TIMER1_INT) | (1 << RTR_DUMP_INT);
    vic[VIC_DISABLE] = int_select;
    vic[VIC_DISABLE] = (1 << CC_TNF_INT);
    vic[VIC_SELECT] = 0;
    run = false;

    // set SCP command to OK , as successfully completed
    msg->cmd_rc = RC_OK;
    return 0;
}

static inline int reinjection_clear(sdp_msg_t *msg) {
    // Disable FIQ for queue access
    uint cpsr = cpu_fiq_disable();
    // Clear any stored dropped packets
    pkt_queue.head = 0;
    pkt_queue.tail = 0;
    // restore FIQ after queue access,
    cpu_int_restore(cpsr);
    // and disable communications controller interrupts
    vic[VIC_DISABLE] = 1 << CC_TNF_INT;
    // set SCP command to OK , as successfully completed
    msg->cmd_rc = RC_OK;
    return 0;
}

//! \brief handles the commands for the reinjector code.
//! \param[in] msg: the message with the commands
//! \return the length of extra data put into the message for return
static uint reinjection_sdp_command(sdp_msg_t *msg) {
    switch (msg->cmd_rc) {
    case CMD_DPRI_SET_ROUTER_TIMEOUT:
        return reinjection_set_timeout(msg);
    case CMD_DPRI_SET_ROUTER_EMERGENCY_TIMEOUT:
        return reinjection_set_emergency_timeout(msg);
    case CMD_DPRI_SET_PACKET_TYPES:
        return reinjection_set_packet_types(msg);
    case CMD_DPRI_GET_STATUS:
        return reinjection_get_status(msg);
    case CMD_DPRI_RESET_COUNTERS:
        return reinjection_reset_counters(msg);
    case CMD_DPRI_EXIT:
        return reinjection_exit(msg);
    case CMD_DPRI_CLEAR:
        return reinjection_clear(msg);
    default:
        // If we are here, the command was not recognised, so fail (ARG as the
        // command is an argument)
        msg->cmd_rc = RC_ARG;
        return 0;
    }
}

// \brief SARK level timer interrupt setup
static void reinjection_configure_timer(void) {
    // Clear the interrupt
    tc[T1_CONTROL] = 0;
    tc[T1_INT_CLR] = 1;

    // Set the timer times
    tc[T1_LOAD] = sv->cpu_clk * TICK_PERIOD;
    tc[T1_BG_LOAD] = sv->cpu_clk * TICK_PERIOD;
}

// \brief pass, not a clue.
static void reinjection_configure_comms_controller(void) {
    // remember SAR register contents (p2p source ID)
    cc_sar = cc[CC_SAR] & 0x0000ffff;
}

// \brief sets up SARK and router to have a interrupt when a packet is dropped
static void reinjection_configure_router(void) {
    // re-configure wait values in router
    rtr[RTR_CONTROL] = (rtr[RTR_CONTROL] & 0x0000ffff) | ROUTER_INITIAL_TIMEOUT;

    // clear router interrupts,
    (void) rtr[RTR_STATUS];

    // clear router dump status,
    (void) rtr[RTR_DSTAT];

    // and enable router interrupts when dumping packets
    rtr[RTR_CONTROL] |= RTR_DENABLE_MASK;
}

//-----------------------------------------------------------------------------
// data in speed up main functions
//-----------------------------------------------------------------------------

static void data_in_clear_router(void) {
    rtr_entry_t router_entry;

    // clear the currently loaded routing table entries
    for (uint entry_id = N_BASIC_SYSTEM_ROUTER_ENTRIES;
            entry_id < N_ROUTER_ENTRIES; entry_id++) {
        //io_printf(IO_BUF, "clearing entry %d \n", entry_id);
        if (rtr_mc_get(entry_id, &router_entry) &&
                router_entry.key != INVALID_ROUTER_ENTRY_KEY &&
                router_entry.mask != INVALID_ROUTER_ENTRY_MASK) {
            rtr_free(entry_id, 1);
        }
    }
}

static inline void data_in_process_boundary(void) {
    if (data_in_write_address) {
        uint written_words = data_in_write_address - first_write_address;
        io_printf(IO_BUF, "Wrote %u words\n", written_words);
        data_in_write_address = NULL;
    }
    first_write_address = NULL;
}

static inline void data_in_process_address(uint data) {
    if (data_in_write_address) {
        data_in_process_boundary();
    }
    io_printf(IO_BUF, "Setting write address to 0x%08x\n", data);
    data_in_write_address = (address_t) data;
    first_write_address = data_in_write_address;
}

static inline void data_in_process_data(uint data) {
    // data keys require writing to next point in sdram

    if (data_in_write_address == NULL) {
        io_printf(IO_BUF, "Write address not set when write data received!\n");
        rt_error(RTE_SWERR);
    }
    *data_in_write_address = data;
    data_in_write_address++;
}

//! \brief process a mc packet with payload
static INT_HANDLER data_in_process_mc_payload_packet(void) {
    // get data from comm controller
    uint data = cc[CC_RXDATA];
    uint key = cc[CC_RXKEY];

    // check if key is address or data key
    // address key means the payload is where to start writing from
    if (key == data_in_address_key) {
        data_in_process_address(data);
    } else if (key == data_in_data_key) {
        data_in_process_data(data);
    } else if (key == data_in_boundary_key) {
        data_in_process_boundary();
    } else {
        io_printf(IO_BUF, "Failed to recognise mc key %u; "
                "only understand keys (%u, %u, %u)\n",
                key, data_in_address_key, data_in_data_key, data_in_boundary_key);
    }
    // and tell VIC we're done
    vic[VIC_VADDR] = (uint) vic;
}

//! \brief private method for writing router entries to the router.
//! \param[in] sdram_address: the sdram address where the router entries reside
//! \param[in] n_entries: how many router entries to read in
static void data_in_load_router(
        router_entry_t *sdram_address, uint n_entries) {
    io_printf(IO_BUF, "Writing %u router entries\n", n_entries);
    if (n_entries == 0) {
        return;
    }
    uint start_entry_id = rtr_alloc_id(n_entries, sark_app_id());
    if (start_entry_id == 0) {
        io_printf(IO_BUF, "Received error with requesting %u router entries."
                " Shutting down\n", n_entries);
        rt_error(RTE_SWERR);
    }

    for (uint idx = 0; idx < n_entries; idx++) {
        // check for invalid entries (possible during alloc and free or
        // just not filled in.
        if (sdram_address[idx].key != INVALID_ROUTER_ENTRY_KEY &&
                sdram_address[idx].mask != INVALID_ROUTER_ENTRY_MASK &&
                sdram_address[idx].route != INVALID_ROUTER_ENTRY_ROUTE) {
#if 0
            // Produces quite a lot of debugging output when enabled
            io_printf(IO_BUF,
                    "Setting key %08x, mask %08x, route %08x for entry %u\n",
                    sdram_address[idx].key, sdram_address[idx].mask,
                    sdram_address[idx].route, idx + start_entry_id);
#endif
            // try setting the valid router entry
            if (rtr_mc_set(idx + start_entry_id, sdram_address[idx].key,
                    sdram_address[idx].mask, sdram_address[idx].route) != 1) {
                io_printf(IO_BUF, "Failed to write router entry %d, "
                        "with key %08x, mask %08x, route %08x\n",
                        idx + start_entry_id, sdram_address[idx].key,
                        sdram_address[idx].mask, sdram_address[idx].route);
            }
        }
    }
}

//! \brief reads in routers entries and places in application sdram location
static void data_in_save_router(void) {
    rtr_entry_t router_entry;

    for (uint entry_id = N_BASIC_SYSTEM_ROUTER_ENTRIES, i = 0;
            entry_id < N_ROUTER_ENTRIES; entry_id++, i++) {
        (void) rtr_mc_get(entry_id, &router_entry);
        // move to sdram
        saved_application_router_table[i].key = router_entry.key;
        saved_application_router_table[i].mask = router_entry.mask;
        saved_application_router_table[i].route = router_entry.route;
    }
}

//! \brief sets up system routes on router. required by the data in speed
//! up functionality
static void data_in_speed_up_load_in_system_tables(
        data_in_data_items_t *items) {
    // read in router table into app store in sdram (in case its changed
    // since last time)
    io_printf(IO_BUF, "Saving existing router table\n");
    data_in_save_router();

    // clear the currently loaded routing table entries to avoid conflicts
    data_in_clear_router();

    // read in and load routing table entries
    io_printf(IO_BUF, "Loading system (Fast Data In) routes\n");
    data_in_load_router(
            items->system_router_entries, items->n_system_router_entries);
}

//! \brief sets up application routes on router. required by data in speed up
//! functionality
static void data_in_speed_up_load_in_application_routes(void) {
    // clear the currently loaded routing table entries
    data_in_clear_router();

    // load app router entries from sdram
    io_printf(IO_BUF, "Loading application routes\n");
    data_in_load_router(
            saved_application_router_table, N_USABLE_ROUTER_ENTRIES);
}

//! \brief the handler for all messages coming in for data in speed up
//! functionality.
//! \param[in] msg: the SDP message (without SCP header)
//! \return: complete code if successful
static uint data_in_speed_up_command(sdp_msg_t *msg) {
    switch (msg->cmd_rc) {
    case SDP_COMMAND_FOR_SAVING_APPLICATION_MC_ROUTING:
        io_printf(IO_BUF, "Reading application router entries from router\n");
        data_in_save_router();
        msg->cmd_rc = RC_OK;
        break;
    case SDP_COMMAND_FOR_LOADING_APPLICATION_MC_ROUTES:
        io_printf(IO_BUF, "Loading application router entries into router\n");
        data_in_speed_up_load_in_application_routes();
        msg->cmd_rc = RC_OK;
        break;
    case SDP_COMMAND_FOR_LOADING_SYSTEM_MC_ROUTES:
        io_printf(IO_BUF, "Loading system router entries into router\n");
        data_in_speed_up_load_in_system_tables(
                dsg_block(CONFIG_DATA_SPEED_UP_IN));
        msg->cmd_rc = RC_OK;
        break;
    default:
        io_printf(IO_BUF,
                "Received unknown SDP packet in data in speed up port with"
                "command id %d\n", msg->cmd_rc);
    }
    return 0;
}

//-----------------------------------------------------------------------------
// data speed up out main functions
//-----------------------------------------------------------------------------

static inline void send_fixed_route_packet(uint32_t key, uint32_t data) {
    // If stop, don't send anything
    if (stop) {
        return;
    }

    // Wait for a router slot
    while ((cc[CC_TCR] & TX_NOT_FULL_MASK) == 0) {
        // Empty body; CC array is volatile
    }
    cc[CC_TCR] = PKT_FR_PL;
    cc[CC_TXDATA] = data;
    cc[CC_TXKEY] = key;
}

//! \brief takes a DMA'ed block and transmits its contents as multicast packets.
//! \param[in] current_dma_pointer: the DMA pointer for the 2 buffers
//! \param[in] number_of_elements_to_send: the number of multicast packets to send
//! \param[in] first_packet_key: the first key to transmit with, afterward,
//! defaults to the default key.
static void data_out_send_data_block(
        uint32_t current_dma_pointer, uint32_t n_elements_to_send,
        uint32_t first_packet_key) {
    // send data
    for (uint i = 0; i < n_elements_to_send; i++) {
        uint32_t current_data = data_to_transmit[current_dma_pointer][i];

        send_fixed_route_packet(first_packet_key, current_data);

        // update key to transmit with
        first_packet_key = basic_data_key;
    }
}

static inline void data_out_dma_read(
        uint32_t dma_tag, void *source, void *destination, uint n_words) {
    uint desc = DMA_WIDTH << 24 | DMA_BURST_SIZE << 21 | DMA_READ << 19 |
            (n_words * sizeof(uint));
    dma_port_last_used = dma_tag;
    dma[DMA_ADRS] = (uint) source;
    dma[DMA_ADRT] = (uint) destination;
    dma[DMA_DESC] = desc;
}

//! \brief sets off a DMA reading a block of SDRAM
//! \param[in] items_to_read the number of word items to read
//! \param[in] dma_tag the DMA tag associated with this read.
//!            transmission or retransmission
//! \param[in] offset where in the data array to start writing to
static void data_out_read(
        uint32_t dma_tag, uint32_t offset, uint32_t items_to_read) {
    // set off DMA
    transmit_dma_pointer = (transmit_dma_pointer + 1) % N_DMA_BUFFERS;

    address_t data_sdram_position = &store_address[position_in_store];

    // update positions as needed
    position_in_store += items_to_read;
    num_items_read = items_to_read;

    // set off DMA
    data_out_dma_read(dma_tag, data_sdram_position,
            &data_to_transmit[transmit_dma_pointer][offset], items_to_read);
}

//! \brief sends a end flag via multicast
static void data_out_send_end_flag(void) {
    send_fixed_route_packet(end_flag_key, END_FLAG);
}

//! \brief DMA complete callback for reading for original transmission
static void data_out_dma_complete_reading_for_original_transmission(void) {
    // set up state
    uint32_t current_dma_pointer = transmit_dma_pointer;
    uint32_t key_to_transmit = basic_data_key;
    uint32_t items_read_this_time = num_items_read;

    // put size in bytes if first send
    if (first_transmission) {
        //io_printf(IO_BUF, "in first\n");
        data_to_transmit[current_dma_pointer][0] = max_seq_num;
        key_to_transmit = first_data_key;
        first_transmission = false;
        items_read_this_time += 1;
    }

    // stopping procedure
    // if a full packet, read another and try again
    if (position_in_store < n_elements_to_read_from_sdram) {
        uint32_t num_items_to_read = SDP_PAYLOAD_WORDS;
        uint32_t next_position_in_store =
                position_in_store + SDP_PAYLOAD_WORDS;

        // if less data needed request less data
        if (next_position_in_store >= n_elements_to_read_from_sdram) {
            num_items_to_read =
                    n_elements_to_read_from_sdram - position_in_store;
        }

        // set off another read and transmit DMA'ed one
        data_out_read(DMA_TAG_READ_FOR_TRANSMISSION, 0, num_items_to_read);
        data_out_send_data_block(current_dma_pointer, items_read_this_time,
                key_to_transmit);
    } else {
        data_out_send_data_block(current_dma_pointer, items_read_this_time,
                key_to_transmit);

        // send end flag.
        data_out_send_end_flag();

        has_finished = true;
        n_missing_seq_sdp_packets = 0;
    }

    if (TDMA_WAIT_PERIOD != 0) {
        sark_delay_us(TDMA_WAIT_PERIOD);
    }
}

//! \brief write SDP sequence numbers to SDRAM that need retransmitting
//! \param[in] data: data to write into SDRAM
//! \param[in] length: length of data
//! \param[in] start_offset: where in the data to start writing in from.
static void data_out_write_missing_sdp_seq_nums_into_sdram(
        uint32_t data[], uint length, uint32_t start_offset) {
    for (uint i = start_offset, j = n_missing_seq_nums_in_sdram; i < length;
            i++, j++) {
        missing_sdp_seq_num_sdram_address[j] = data[i];
        if (data[i] > max_seq_num) {
            io_printf(IO_BUF, "Storing some bad seq num. WTF! %d %d\n",
                    data[i], max_seq_num);
        }
    }
    n_missing_seq_nums_in_sdram += length - start_offset;
}

//! \brief entrance method for storing SDP sequence numbers into SDRAM
//! \param[in] data: the message data to read into SDRAM
//! \param[in] length: how much data to read
//! \param[in] first: if first packet about missing sequence numbers. If so
//! there is different behaviour
static void data_out_store_missing_seq_nums(
        uint32_t data[], uint length, bool first) {
    uint32_t start_reading_offset = 1;
    if (first) {
        n_missing_seq_sdp_packets =
                data[POSITION_OF_NO_MISSING_SEQ_SDP_PACKETS];

        uint32_t size_of_data =
                (n_missing_seq_sdp_packets * ITEMS_PER_DATA_PACKET * sizeof(uint))
                + END_FLAG_SIZE;

        if (missing_sdp_seq_num_sdram_address != NULL) {
            sdram_free(missing_sdp_seq_num_sdram_address);
            missing_sdp_seq_num_sdram_address = NULL;
        }
        missing_sdp_seq_num_sdram_address = sdram_alloc(size_of_data);

        // if not got enough sdram to alllocate all missing seq nums
        if (missing_sdp_seq_num_sdram_address == NULL) {
            // biggest sdram block
            uint32_t max_bytes = sdram_max_block_size();

            // if can hold more than this packets worth of data
            if (max_bytes >= SDP_PAYLOAD_BYTES + END_FLAG_SIZE) {
                io_printf(IO_BUF, "Activate bacon protocol!");
                // allocate biggest block
                missing_sdp_seq_num_sdram_address = sdram_alloc(max_bytes);
                // determine max full seq num packets to store
                max_bytes -= END_FLAG_SIZE + SDP_PAYLOAD_BYTES;
                n_missing_seq_sdp_packets = 1
                        + max_bytes / (ITEMS_PER_DATA_PACKET * sizeof(uint));
            } else {
                io_printf(IO_BUF,
                        "Can't allocate SDRAM for missing seq nums!!\n");
                rt_error(RTE_SWERR);
            }
        }
        start_reading_offset = START_OF_MISSING_SEQ_NUMS;
    }
    if (n_missing_seq_sdp_packets > 0) {
        // write data to SDRAM and update packet counter
        data_out_write_missing_sdp_seq_nums_into_sdram(
                data, length, start_reading_offset);
        n_missing_seq_sdp_packets -= 1;
    } else {
        io_printf(IO_BUF,
                "Unable to save missing sequence number\n");
    }
}

//! \brief sets off a DMA for retransmission stuff
static void data_out_retransmission_dma_read(void) {
    // locate where we are in SDRAM
    address_t data_sdram_position =
            &missing_sdp_seq_num_sdram_address[position_for_retransmission];

    // set off DMA
    data_out_dma_read(DMA_TAG_READ_FOR_RETRANSMISSION, data_sdram_position,
            retransmit_seq_nums, ITEMS_PER_DATA_PACKET);
}

//! \brief reads in missing sequence numbers and sets off the reading of
//! SDRAM for the equivalent data
static void data_out_dma_complete_read_missing_seqeuence_nums(void) {
    //! check if at end of read missing sequence numbers
    if (position_in_read_data > ITEMS_PER_DATA_PACKET) {
        position_for_retransmission += ITEMS_PER_DATA_PACKET;
        if (n_missing_seq_nums_in_sdram > position_for_retransmission) {
            position_in_read_data = 0;
            data_out_retransmission_dma_read();
        }
        return;
    }

    // get next sequence number to regenerate
    missing_seq_num_being_processed = (uint32_t)
            retransmit_seq_nums[position_in_read_data];
    if (missing_seq_num_being_processed != END_FLAG) {
        // regenerate data
        position_in_store = missing_seq_num_being_processed * SDP_PAYLOAD_WORDS;
        uint32_t left_over_portion =
                bytes_to_read_write / sizeof(uint) - position_in_store;

        if (left_over_portion < SDP_PAYLOAD_WORDS) {
            retransmitted_seq_num_items_read = left_over_portion + 1;
            data_out_read(DMA_TAG_RETRANSMISSION_READING, 1, left_over_portion);
        } else {
            retransmitted_seq_num_items_read = ITEMS_PER_DATA_PACKET;
            data_out_read(DMA_TAG_RETRANSMISSION_READING, 1, SDP_PAYLOAD_WORDS);
        }
    } else {        // finished data send, tell host its done
        data_out_send_end_flag();
        in_retransmission_mode = false;
        missing_sdp_seq_num_sdram_address = NULL;
        position_in_read_data = 0;
        position_for_retransmission = 0;
        n_missing_seq_nums_in_sdram = 0;
    }
}

//! \brief DMA complete callback for have read missing sequence number data
static void data_out_dma_complete_reading_retransmission_data(void) {
    // set sequence number as first element
    data_to_transmit[transmit_dma_pointer][0] = missing_seq_num_being_processed;

    if (missing_seq_num_being_processed > max_seq_num) {
        io_printf(IO_BUF,
                "Got some bad seq num here. max is %d and got %d \n",
                max_seq_num, missing_seq_num_being_processed);
    }

    // send new data back to host
    data_out_send_data_block(transmit_dma_pointer, retransmitted_seq_num_items_read,
            new_sequence_key);

    position_in_read_data += 1;
    data_out_dma_complete_read_missing_seqeuence_nums();
}

//! \brief DMA complete callback for have read missing sequence number data
static void data_out_dma_complete_writing_missing_seq_to_sdram(void) {
    io_printf(IO_BUF, "Need to figure what to do here\n");
}

//! \brief the handler for all messages coming in for data speed up
//! functionality.
//! \param[in] msg: the SDP message (without SCP header)
static void data_out_speed_up_command(sdp_msg_pure_data *msg) {
    sdp_data_out_t *message = (sdp_data_out_t *) msg->data;
    switch (message->command) {
    case SDP_CMD_START_SENDING_DATA: {
        stop = 0;

        // set SDRAM position and length
        store_address = message->sdram_location;
        bytes_to_read_write = message->length;

        uint32_t seq = bytes_to_read_write / (67 * 4),
                mod = bytes_to_read_write % (67 * 4);
        seq += mod > 0;
        max_seq_num = seq;

        // reset states
        first_transmission = true;
        transmit_dma_pointer = 0;
        position_in_store = 0;
        n_elements_to_read_from_sdram = bytes_to_read_write / sizeof(uint);

        if (n_elements_to_read_from_sdram < SDP_PAYLOAD_WORDS) {
            data_out_read(DMA_TAG_READ_FOR_TRANSMISSION, 1,
                    n_elements_to_read_from_sdram);
        } else {
            data_out_read(DMA_TAG_READ_FOR_TRANSMISSION, 1, SDP_PAYLOAD_WORDS);
        }
        return;
    }
    case SDP_CMD_START_OF_MISSING_SDP_PACKETS:
        // start or continue to gather missing packet list

        // if already in a retransmission phase, don't process as normal
        if (n_missing_seq_sdp_packets != 0) {
            //io_printf(IO_BUF, "forcing start of retransmission packet\n");
            n_missing_seq_sdp_packets = 0;
            missing_sdp_seq_num_sdram_address[
                    n_missing_seq_nums_in_sdram++] = END_FLAG;
            position_in_read_data = 0;
            position_for_retransmission = 0;
            in_retransmission_mode = true;
            data_out_retransmission_dma_read();
            return;
        }
        // fall through
    case SDP_CMD_MORE_MISSING_SDP_PACKETS:
        // reset state, as could be here from multiple attempts
        if (!in_retransmission_mode) {
            // put missing sequence numbers into SDRAM
            data_out_store_missing_seq_nums(
                    msg->data,
                    (msg->length - LENGTH_OF_SDP_HEADER) / sizeof(uint),
                    message->command == SDP_CMD_START_OF_MISSING_SDP_PACKETS);

            // if got all missing packets, start retransmitting them to host
            if (n_missing_seq_sdp_packets == 0) {
                // packets all received, add finish flag for DMA stoppage

                if (n_missing_seq_nums_in_sdram != 0) {
                    //io_printf(IO_BUF, "starting resend process\n");
                    missing_sdp_seq_num_sdram_address[
                            n_missing_seq_nums_in_sdram++] = END_FLAG;
                    position_in_read_data = 0;
                    position_for_retransmission = 0;

                    // start DMA off
                    in_retransmission_mode = true;
                    data_out_retransmission_dma_read();
                }
            }
        }
        return;
    case SDP_CMD_CLEAR:
        stop = 1;
        break;
    default:
        io_printf(IO_BUF, "Received unknown SDP packet: %d\n",
                message->command);
    }
}

//! \brief the handler for all DMAs complete
static INT_HANDLER data_out_dma_complete(void) {
    // reset the interrupt.
    dma[DMA_CTRL] = 0x8;
    if (!stop) {
        // Only do something if we have not been told to stop
        switch (dma_port_last_used) {
        case DMA_TAG_READ_FOR_TRANSMISSION:
            data_out_dma_complete_reading_for_original_transmission();
            break;
        case DMA_TAG_READ_FOR_RETRANSMISSION:
            data_out_dma_complete_read_missing_seqeuence_nums();
            break;
        case DMA_TAG_RETRANSMISSION_READING:
            data_out_dma_complete_reading_retransmission_data();
            break;
        case DMA_TAG_FOR_WRITING_MISSING_SEQ_NUMS:
            data_out_dma_complete_writing_missing_seq_to_sdram();
            break;
        default:
            io_printf(IO_BUF, "Invalid DMA callback port: %d!\n",
                    dma_port_last_used);
            rt_error(RTE_SWERR);
        }
    }
    // and tell VIC we're done
    vic[VIC_VADDR] = (uint) vic;
}

//! \brief the handler for DMA errors
static INT_HANDLER data_out_dma_error(void) {
    io_printf(IO_BUF, "DMA failed: 0x%08x!\n", dma[DMA_STAT]);
    dma[DMA_CTRL] = 0x4;
    vic[VIC_VADDR] = (uint) vic;
    rt_error(RTE_DABT);
}

//! \brief the handler for DMA timeouts (hopefully unlikely...)
static INT_HANDLER data_out_dma_timeout(void) {
    io_printf(IO_BUF, "DMA timeout: 0x%08x!\n", dma[DMA_STAT]);
    dma[DMA_CTRL] = 0x10;
    vic[VIC_VADDR] = (uint) vic;
}

//-----------------------------------------------------------------------------
// common code
//-----------------------------------------------------------------------------

#define SDP_REPLY_HEADER_LEN 12

static inline void reflect_sdp_message(sdp_msg_t *msg, uint body_length) {
    msg->length = SDP_REPLY_HEADER_LEN + body_length;
    uint dest_port = msg->dest_port;
    uint dest_addr = msg->dest_addr;

    msg->dest_port = msg->srce_port;
    msg->srce_port = dest_port;

    msg->dest_addr = msg->srce_addr;
    msg->srce_addr = dest_addr;
}

static inline sdp_msg_t *get_message_from_mailbox(void) {
    sdp_msg_t *shm_msg = (sdp_msg_t *) sark.vcpu->mbox_ap_msg;
    sdp_msg_t *msg = sark_msg_get();
    if (msg != NULL) {
        sark_msg_cpy(msg, shm_msg);
    }
    sark_shmsg_free(shm_msg);
    sark.vcpu->mbox_ap_cmd = SHM_IDLE;
    return msg;
}

void __real_sark_int(void *pc);
// Check for extra messages added by this core
void __wrap_sark_int(void *pc) {
    // Get the message from SCAMP and see if t belongs to SARK
    if (sark.vcpu->mbox_ap_cmd != SHM_MSG) {
        // Run the default callback
        __real_sark_int(pc);
        return;
    }

    // Make a copy so we can release the mailbox, and flag as ready for
    // interrupt again
    sdp_msg_t *msg = get_message_from_mailbox();
    sc[SC_CLR_IRQ] = SC_CODE + (1 << sark.phys_cpu);
    if (msg == NULL) {
        return;
    }

    switch ((msg->dest_port & PORT_MASK) >> PORT_SHIFT) {
    case REINJECTION_PORT:
        reflect_sdp_message(msg, reinjection_sdp_command(msg));
        while (!sark_msg_send(msg, 10)) {
            io_printf(IO_BUF, "timeout when sending reinjection reply\n");
        }
        break;
    case DATA_SPEED_UP_OUT_PORT:
        // These are all one-way messages; replies are out of band
        data_out_speed_up_command((sdp_msg_pure_data *) msg);
        break;
    case DATA_SPEED_UP_IN_PORT:
        reflect_sdp_message(msg, data_in_speed_up_command(msg));
        while (!sark_msg_send(msg, 10)) {
            io_printf(IO_BUF, "timeout when sending speedup ctl reply\n");
        }
        break;
    default:
        io_printf(IO_BUF, "unexpected port %d\n",
                (msg->dest_port & PORT_MASK) >> PORT_SHIFT);
        io_printf(IO_BUF,
                "from:%04x:%02x to:%04x:%02x cmd:%04x len:%d iam:%04x\n",
                msg->srce_addr, msg->srce_port,
                msg->dest_addr, msg->dest_port,
                msg->cmd_rc, msg->length, my_addr);
        // Do nothing
    }
    sark_msg_free(msg);
}

//-----------------------------------------------------------------------------
// initializers
//-----------------------------------------------------------------------------

#ifndef VIC_ENABLE_VECTOR
#define VIC_ENABLE_VECTOR (0x20)
#endif //VIC_ENABLE_VECTOR

static inline void set_vic_callback(uint8_t slot, uint type, isr_t callback) {
    vic_vectors[slot] = callback;
    vic_controls[slot] = VIC_ENABLE_VECTOR | type;
}

//! \brief sets up data required by the reinjection functionality
static void reinjection_initialise(void) {
    // set up config region
    // Get the address this core's DTCM data starts at from SRAM
    reinjection_read_packet_types(dsg_block(CONFIG_REINJECTION));

    // Setup the CPU interrupt for WDOG
    vic_controls[sark_vec->sark_slot] = 0;
    set_vic_callback(CPU_SLOT, CPU_INT, sark_int_han);

    // Setup the communications controller interrupt
    set_vic_callback(CC_SLOT, CC_TNF_INT, reinjection_ready_to_send_callback);

    // Setup the timer interrupt
    set_vic_callback(TIMER_SLOT, TIMER1_INT, reinjection_timer_callback);

    // Setup the router interrupt as a fast interrupt
    sark_vec->fiq_vec = reinjection_dropped_packet_callback;
    vic[VIC_SELECT] = 1 << RTR_DUMP_INT;
}

//! \brief sets up data required by the data speed up functionality
static void data_out_initialise(void) {
    data_speed_out_config_t *config = dsg_block(CONFIG_DATA_SPEED_UP_OUT);
    basic_data_key = config->my_key;
    new_sequence_key = config->new_seq_key;
    first_data_key = config->first_data_key;
    end_flag_key = config->end_flag_key;

    // Various DMA callbacks
    set_vic_callback(DMA_SLOT, DMA_DONE_INT, data_out_dma_complete);
    set_vic_callback(DMA_ERROR_SLOT, DMA_ERR_INT, data_out_dma_error);
    set_vic_callback(DMA_TIMEOUT_SLOT, DMA_TO_INT, data_out_dma_timeout);

    for (uint32_t i = 0; i < 2; i++) {
        data_to_transmit[i] =
                sark_alloc(ITEMS_PER_DATA_PACKET, sizeof(uint32_t));
        if (data_to_transmit[i] == NULL) {
            io_printf(IO_BUF, "failed to allocate DTCM for DMA buffers\n");
            rt_error(RTE_SWERR);
        }
    }

    // configuration for the DMA's by the speed data loader
    dma[DMA_CTRL] = 0x3f; // Abort pending and active transfers
    dma[DMA_CTRL] = 0x0d; // clear possible transfer done and restart
    dma[DMA_GCTL] = 0x1ffc00; // enable DMA done and error interrupt
}

//! \brief sets up data required by the data in speed up functionality
static void data_in_initialise(void) {
    saved_application_router_table = sdram_alloc(
            N_USABLE_ROUTER_ENTRIES * sizeof(router_entry_t));
    if (saved_application_router_table == NULL) {
        io_printf(IO_BUF,
                "failed to allocate SDRAM for application mc router entries\n");
        rt_error(RTE_SWERR);
    }

    data_in_data_items_t *items = dsg_block(CONFIG_DATA_SPEED_UP_IN);

    data_in_address_key = items->address_mc_key;
    data_in_data_key = items->data_mc_key;
    data_in_boundary_key = items->boundary_mc_key;
    // Save the current (application?) state
    data_in_save_router();

    // set up mc interrupts to deal with data writing
    set_vic_callback(MC_PAYLOAD_SLOT, CC_MC_INT, data_in_process_mc_payload_packet);
}

//-----------------------------------------------------------------------------
// main method
//-----------------------------------------------------------------------------
void c_main(void) {
    sark_cpu_state(CPU_STATE_RUN);

    // Configure
    my_addr = sv->p2p_addr;
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
            (1 << DMA_DONE_INT) | (1 << CC_MC_INT) |
            (1 << DMA_ERR_INT) | (1 << DMA_TO_INT);
    vic[VIC_DISABLE] = int_select;
    vic[VIC_DISABLE] = 1 << CC_TNF_INT;

    // set up reinjection functionality
    reinjection_initialise();

    // set up data speed up functionality
    data_out_initialise();
    data_in_initialise();

    // Enable interrupts and timer
    vic[VIC_ENABLE] = int_select;
    tc[T1_CONTROL] = 0xe2;

    // Run until told to exit
    while (run) {
        spin1_wfi();
    }
}
// ------------------------------------------------------------------------

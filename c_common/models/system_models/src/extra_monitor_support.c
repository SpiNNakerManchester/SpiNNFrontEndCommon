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

//! \file
//! \brief The implementation of the Extra Monitor.
//! \details
//!     The purpose of this application is to provide extra monitor functions
//!     (such as reinjection control) that do not fit in SCAMP, and to provide
//!     an endpoint on each chip for streaming data in and out at high speed
//!     (while the main user application is not running).

// SARK-based program
#include <sark.h>
#include <stdbool.h>
#include <common-typedefs.h>
#include "common.h"

// Debugging control
//#define DEBUG_DATA_IN
#undef DEBUG_DATA_IN

// ------------------------------------------------------------------------
// constants
// ------------------------------------------------------------------------

//-----------------------------------------------------------------------------
// stuff to do with SARK DMA
//-----------------------------------------------------------------------------

//! \brief Use DMA bursts of 16 words (2<sup>16</sup>)
//! \details See [SpiNNaker Data Sheet][datasheet], Section 7.4, register r3
//!
//! [datasheet]: https://spinnakermanchester.github.io/docs/SpiNN2DataShtV202.pdf
#define DMA_BURST_SIZE 4

//! \brief Use a DMA width of double words
//! \details See [SpiNNaker Data Sheet][datasheet], Section 7.4, register r3
//!
//! [datasheet]: https://spinnakermanchester.github.io/docs/SpiNN2DataShtV202.pdf
#define DMA_WIDTH 1

//! The number of DMA buffers to build
#define N_DMA_BUFFERS 2

//! Flags for the type of DMA to request
enum {
    //! marker for doing a DMA read
    DMA_READ = 0,
    //! marker for doing DMA write (don't think this is used in here yet)
    DMA_WRITE = 1
};

//-----------------------------------------------------------------------------
// magic numbers for data speed up extractor
//-----------------------------------------------------------------------------

//! Flag size for saying ended, in bytes
#define END_FLAG_SIZE 4
//! Flag for saying stuff has ended
#define END_FLAG      0xFFFFFFFF

//! Sizes of things to do with data speed up out message sizes
enum {
    //! Size of the sequence number, in words
    SEQUENCE_NUMBER_SIZE = 1,
    //! Size of the transaction ID, in words
    TRANSACTION_ID_SIZE = 1,
    //! Effective size of the SDP packet payload, in words of actual content
    SDP_PAYLOAD_WORDS =
            ITEMS_PER_DATA_PACKET - SEQUENCE_NUMBER_SIZE - TRANSACTION_ID_SIZE,
    //! Effective size of the SDP packet payload, in bytes of actual content
    SDP_PAYLOAD_BYTES = SDP_PAYLOAD_WORDS * sizeof(uint)
};

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

//! number of entries in the multicast router for SARK and SCAMP
#define N_BASIC_SYSTEM_ROUTER_ENTRIES 1

//! number of entries in the multicast router that we can manage
#define N_USABLE_ROUTER_ENTRIES    (N_ROUTER_ENTRIES - N_BASIC_SYSTEM_ROUTER_ENTRIES)

//-----------------------------------------------------------------------------
// reinjection functionality magic numbers
//-----------------------------------------------------------------------------

//! Throttle power on the MC transmissions if needed (assume not needed)
#define TDMA_WAIT_PERIOD   0

//! The initial timeout of the router
#define ROUTER_INITIAL_TIMEOUT 0x004f0000

//! Amount to call the timer callback
#define TICK_PERIOD        10

//! dumped packet queue length
#define PKT_QUEUE_SIZE     4096

//-----------------------------------------------------------------------------
// VIC slots assigned
//-----------------------------------------------------------------------------

//! VIC slot definitions
enum {
    //! CPU VIC slot (WDOG and SDP; message from SCAMP for SARK)
    CPU_SLOT = SLOT_0,
    //! Communications controller VIC slot
    CC_SLOT = SLOT_1,
    //! Timer VIC slot
    TIMER_SLOT = SLOT_2,
    //! DMA completed VIC slot
    DMA_SLOT = SLOT_3,
    //! DMA error VIC slot
    DMA_ERROR_SLOT = SLOT_4,
    //! DMA timeout VIC slot
    DMA_TIMEOUT_SLOT = SLOT_5,
    //! Multicast-with-payload message arrived VIC slot
    MC_PAYLOAD_SLOT = SLOT_6
};

//! Positions of fields in the router status and control registers
enum {
    RTR_DOVRFLW_BIT = 30, //!< router dump overflow
    RTR_BLOCKED_BIT = 25, //!< router blocked
    //! number of bits marking if the dumped packet was due to a processor failure
    RTR_FPE_BITS = 18,
    //! number of bits marking if the dumped packet was due to a link failure
    RTR_LE_BITS = 6,
    RTR_PARITY_COUNT_BIT = 5,   //!< count if the packet had a parity error
    RTR_FRAME_COUNT_BIT = 4,    //!< count if the packet had a framing error
    RTR_TS_COUNT_BIT = 3, //!< count if the packet had a timestamp error
    RTR_DENABLE_BIT = 2   //!< enable dump interrupts
};

//! Masks for fields in the router status and control registers
enum {
    RTR_BLOCKED_MASK = 1 << RTR_BLOCKED_BIT, //!< router blocked
    RTR_DOVRFLW_MASK = 1 << RTR_DOVRFLW_BIT, //!< router dump overflow
    RTR_DENABLE_MASK = 1 << RTR_DENABLE_BIT, //!< enable dump interrupts
    RTR_FPE_MASK = (1 << RTR_FPE_BITS) - 1,  //!< if the dumped packet was a processor failure
    RTR_LE_MASK = (1 << RTR_LE_BITS) - 1,    //!< if the dumped packet was a link failure
    //! router control mask to count the error packets
    RTR_ERRCNT_MASK = (1 << RTR_PARITY_COUNT_BIT) |
                      (1 << RTR_FRAME_COUNT_BIT) |
                      (1 << RTR_TS_COUNT_BIT)
};

//! Positions of fields in communications controller registers
enum {
    //! control field of packet control word
    PKT_CONTROL_SHFT = 16,
    //! payload flag field of packet control word (part of control field)
    PKT_PLD_SHFT = 17,
    //! packet type field of packet control word (part of control field)
    PKT_TYPE_SHFT = 22,
    //! packet route field of packet control word
    PKT_ROUTE_SHFT = 24
};

//! Masks for fields in communications controller registers
enum {
    //! control field of packet control word
    PKT_CONTROL_MASK = 0xff << PKT_CONTROL_SHFT,
    //! payload flag field of packet control word (part of control field)
    PKT_PLD_MASK = 1 << PKT_PLD_SHFT,
    //! packet type field of packet control word (part of control field)
    PKT_TYPE_MASK = 3 << PKT_TYPE_SHFT,
    //! packet route field of packet control word
    PKT_ROUTE_MASK = 7 << PKT_ROUTE_SHFT
};

//! Bits representing packet types
enum packet_types {
    PKT_TYPE_MC = 0 << PKT_TYPE_SHFT, //!< Multicast packet
    PKT_TYPE_PP = 1 << PKT_TYPE_SHFT, //!< Point-to-point packet
    PKT_TYPE_NN = 2 << PKT_TYPE_SHFT, //!< Nearest neighbour packet
    PKT_TYPE_FR = 3 << PKT_TYPE_SHFT  //!< Fixed route packet
};

//! Maximum router timeout value
#define ROUTER_TIMEOUT_MASK 0xFF

// ------------------------------------------------------------------------
// structs used in system
// ------------------------------------------------------------------------

//! Dumped packet type
typedef struct dumped_packet_t {
    uint hdr; //!< Header word of packet
    uint key; //!< Key word of packet
    uint pld; //!< Payload word of packet (might be undefined)
} dumped_packet_t;

//! Packet queue type
typedef struct pkt_queue_t {
    uint head; //!< Index of head of queue in circular buffer
    uint tail; //!< Index of tail of queue in circular buffer
    //! Circular buffer used to implement the queue of packets to reinject
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

//! \brief Message payload for the data speed up out SDP messages
typedef struct sdp_data_out_t {
    //! What operation are we dealing with
    data_out_sdp_commands command;
    //! \brief What is the transaction ID
    //! \details This is used to stop confusion when critical packets get lost
    uint transaction_id;
    //! What location are we talking about
    address_t sdram_location;
    //! How much data are we moving
    uint length;
} sdp_data_out_t;

//! \brief Router entry positions in SDRAM
typedef struct router_entry_t {
    uint32_t key;   //!< The SpiNNaker router key
    uint32_t mask;  //!< The SpiNNaker router mask
    uint32_t route; //!< The SpiNNaker router route (to use when masked key matches)
} router_entry_t;

//! \brief data positions in SDRAM for data in config
typedef struct data_in_data_items {
    //! What key to use to receive an address to write to
    uint32_t address_mc_key;
    //! What key to use to receive a word to write
    uint32_t data_mc_key;
    //! What key to use to receive an instruction that writing is done
    uint32_t boundary_mc_key;
    //! The number of system (non-app, non-SCAMP) router entries to use for Data In
    uint32_t n_system_router_entries;
    //! The system (non-app, non-SCAMP) router entries to use for Data In
    router_entry_t system_router_entries[];
} data_in_data_items_t;

//! \brief position in message for missing sequence numbers
enum missing_seq_num_data_positions {
    POSITION_OF_NO_MISSING_SEQ_PACKETS = 2,
    START_OF_MISSING_MORE = 2,
    START_OF_MISSING_SEQ_NUMS = 3,
};

//! Definition of response packet for reinjector status
typedef struct reinjector_status_response_packet_t {
    //! \brief The current router timeout
    //! \details See [SpiNNaker Data Sheet][datasheet], Section 10.11,
    //!     register r0, field wait1
    //!
    //! [datasheet]: https://spinnakermanchester.github.io/docs/SpiNN2DataShtV202.pdf
    uint router_timeout;
    //! \brief The current router emergency timeout
    //! \details See [SpiNNaker Data Sheet][datasheet], Section 10.11,
    //!     register r0, field wait2
    //!
    //! [datasheet]: https://spinnakermanchester.github.io/docs/SpiNN2DataShtV202.pdf
    uint router_emergency_timeout;
    //! The number of packets that were dropped
    uint n_dropped_packets;
    //! The number of packets that were dumped by the router
    uint n_missed_dropped_packets;
    //! The number of packets that were dropped due to overflow
    uint n_dropped_packets_overflows;
    //! The number of packets that were reinjected
    uint n_reinjected_packets;
    //! The number of packets dropped because a link was busy
    uint n_link_dumped_packets;
    //! The number of packets dropped because a processor was busy
    uint n_processor_dumped_packets;
    //! What packet types are we reinjecting
    uint packet_types_reinjected;
} reinjector_status_response_packet_t;

//! How the reinjection configuration is laid out in memory.
typedef struct reinject_config_t {
    //! \brief Whether we are reinjecting multicast packets
    //! \warning The sense is inverted; 0 means inject, and 1 means don't
    uint multicast_flag;
    //! \brief Whether we are reinjecting point-to-point packets
    //! \warning The sense is inverted; 0 means inject, and 1 means don't
    uint point_to_point_flag;
    //! \brief Whether we are reinjecting fixed route packets
    //! \warning The sense is inverted; 0 means inject, and 1 means don't
    uint fixed_route_flag;
    //! \brief Whether we are reinjecting nearest neighbour packets
    //! \warning The sense is inverted; 0 means inject, and 1 means don't
    uint nearest_neighbour_flag;
    uint reinjection_base_mc_key;
} reinject_config_t;

//! values for SDP port numbers that this core will respond to
enum functionality_to_port_num_map {
    REINJECTION_PORT = 4,
    DATA_SPEED_UP_OUT_PORT = 5,
    DATA_SPEED_UP_IN_PORT = 6
};

//! DSG region identifiers
enum data_spec_regions {
    //! Reinjector configuration
    CONFIG_REINJECTION = 0,
    //! Data Speed Up (Outbound) configuration
    CONFIG_DATA_SPEED_UP_OUT = 1,
    //! Data Speed Up (Inbound) configuration
    CONFIG_DATA_SPEED_UP_IN = 2
};

//! Commands for supporting Data In routing
enum speed_up_in_command {
    //! read in application multicast routes
    SDP_COMMAND_FOR_SAVING_APPLICATION_MC_ROUTING = 6,
    //! load application multicast routes
    SDP_COMMAND_FOR_LOADING_APPLICATION_MC_ROUTES = 7,
    //! load system multicast routes
    SDP_COMMAND_FOR_LOADING_SYSTEM_MC_ROUTES = 8
};

//! Human-readable definitions of each element in the transmission region
typedef struct data_speed_out_config_t {
    //! The key to say here is a piece of data
    uint my_key;
    //! The key to say that we are starting a new sequence
    uint new_seq_key;
    //! The key to say that this data is the first
    uint first_data_key;
    //! The key to say that this data is a transaction identifier
    uint transaction_id_key;
    //! The key to say that we've finished transmitting data
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

//! \brief The content of the communications controller SAR register.
//! \details Specifically, the P2P source identifier.
static uint reinject_p2p_source_id;

//! Dumped packet queue
static pkt_queue_t reinject_pkt_queue;

// statistics
//! Count of all packets dropped by router.
static uint reinject_n_dropped_packets;

//! Count of packets dumped because the router was itself overloaded.
static uint reinject_n_missed_dropped_packets;

//! Count of packets lost because we ran out of queue space.
static uint reinject_n_dropped_packet_overflows;

//! Count of all packets reinjected.
static uint reinject_n_reinjected_packets;

//! \brief Estimated count of packets dropped by router because a destination
//!     link is busy.
static uint reinject_n_link_dumped_packets;

//! \brief Estimated count of packets dropped by router because a destination
//!     core (local) is busy.
static uint reinject_n_processor_dumped_packets;

// Determine what to reinject

//! Whether to reinject multicast packets.
static bool reinject_mc;

//! Whether to reinject point-to-point packets.
static bool reinject_pp;

//! Whether to reinject nearest neighbour packets.
static bool reinject_nn;

//! Whether to reinject fixed route packets.
static bool reinject_fr;

//! Whether we are running the reinjector
static bool reinject_run = true;

// ------------------------------------------------------------------------
// global variables for data speed up in functionality
// ------------------------------------------------------------------------

// data in variables
//! \brief Where we save a copy of the application code's router table while the
//!     system router table entries are loaded.
static router_entry_t *data_in_saved_application_router_table = NULL;

//! This packet contains the address of the start of a stream.
static uint data_in_address_key = 0;

//! This packet contains a word of data in the stream.
static uint data_in_data_key = 0;

//! This packet is the end of a stream.
static uint data_in_boundary_key = 0;

//! Where we will write the next received word. `NULL` if not in a stream.
static address_t data_in_write_address = NULL;

//! Where we wrote the first word in the stream. `NULL` if not in a stream.
static address_t data_in_first_write_address = NULL;

//! The size of the ::data_in_saved_application_router_table
static int data_in_application_table_n_valid_entries = 0;

//! Do we have the system router table loaded?
static bool data_in_last_table_load_was_system = false;

// ------------------------------------------------------------------------
// global variables for data speed up out functionality
// ------------------------------------------------------------------------

// transmission stuff

//! The DTCM buffers holding data to transmit. DMA targets.
static uint32_t data_out_data_to_transmit[N_DMA_BUFFERS][ITEMS_PER_DATA_PACKET];

//! \brief Which ::data_out_data_to_transmit buffer is the target of the current
//!     DMA transfer.
static uint32_t data_out_transmit_dma_pointer = 0;

//! Index (by words) into the block of SDRAM being read.
static uint32_t data_out_position_in_store = 0;

//! Size of the current DMA transfer.
static uint32_t data_out_num_items_read = 0;

//! \brief The current transaction identifier, identifying the stream of items
//!     being moved.
//! \details Also written to the user1 SARK register
static uint32_t data_out_transaction_id = 0;

//! Whether we are about the first transmission in a stream.
static bool data_out_first_transmission = true;

//! Whether we have reached the end of a stream.
static bool data_out_has_finished = false;

//! The size of payload DMA'd into the send buffer.
static uint32_t data_out_retransmitted_seq_num_items_read = 0;

// retransmission stuff

//! The number of missing packets that the host wants us to resend.
static uint32_t data_out_n_missing_seq_packets = 0;

//! The number of sequence numbers of missing packets that we've accumulated.
static uint32_t data_out_n_missing_seq_nums_in_sdram = 0;

//! The number of words that remain to be read from SDRAM.
static uint32_t data_out_n_elements_to_read_from_sdram = 0;

//! Buffer in SDRAM where the sequence numbers of missing packets are stored.
static address_t data_out_missing_seq_num_sdram_address = NULL;

//! The maximum sequence number that can be in a transmission stream.
static uint32_t data_out_max_seq_num = 0;

// retransmission DMA stuff

//! \brief DTCM buffer of sequence numbers to be retransmitted.
//! \details Gets filled from ::data_out_missing_seq_num_sdram_address by DMA
static uint32_t data_out_retransmit_seq_nums[ITEMS_PER_DATA_PACKET];

//! Used to track where we are in the retransmissions.
static uint32_t data_out_position_for_retransmission = 0;

//! The current sequence number for the chunk being being DMA'd in.
static uint32_t data_out_missing_seq_num_being_processed = 0;

//! \brief Index into ::data_out_retransmit_seq_nums used to track where we are
//!     in a chunk of sequence numbers to retransmit.
static uint32_t data_out_read_data_position = 0;

//! The tag of the current DMA.
static uint32_t data_out_dma_port_last_used = 0;

//! Whether we're transmitting or retransmitting.
static bool data_out_in_retransmission_mode = false;

//! The location in SDRAM where data is being read out from.
static address_t data_out_store_address = NULL;

//! The SpiNNaker packet key for a piece of data.
static uint32_t data_out_basic_data_key = 0;

//! The SpiNNaker packet key for the start of a sequence.
static uint32_t data_out_new_sequence_key = 0;

//! The SpiNNaker packet key for the first piece of data of some data.
static uint32_t data_out_first_data_key = 0;

//! The SpiNNaker packet key for the transaction ID.
static uint32_t data_out_transaction_id_key = 0;

//! The SpiNNaker packet key for the end of a stream.
static uint32_t data_out_end_flag_key = 0;

//! Whether the data out streaming has been asked to stop.
static bool data_out_stop = false;

// ------------------------------------------------------------------------
// support functions and variables
// ------------------------------------------------------------------------

//! Wait for interrupt. (Undisclosed import from Spin1API.)
extern void spin1_wfi(void);

//! The standard SARK CPU interrupt handler.
extern INT_HANDLER sark_int_han(void);

//! Basic type of an interrupt handler.
typedef void (*isr_t) (void);

//! The table of interrupt handlers in the VIC
static volatile isr_t* const _vic_vectors = (isr_t *) (VIC_BASE + 0x100);

//! The table mapping priorities to interrupt sources in the VIC
static volatile uint* const _vic_controls = (uint *) (VIC_BASE + 0x200);

//! \brief Where are we (as a P2P address)?
//! \details Used for error reporting.
static ushort my_addr;

//! The SARK virtual processor information table in SRAM.
static vcpu_t *const _sark_virtual_processor_info = (vcpu_t *) SV_VCPU;

//! \brief DSG metadata
//! \details Must structurally match data_specification_metadata_t
typedef struct dsg_header_t {
    uint dse_magic_number;      //!< Magic number (== 0xAD130AD6)
    uint dse_version;           //!< Version (== 0x00010000)
    void *regions[];            //!< Pointers to DSG regions
} dsg_header_t;

//! \brief Get the DSG region with the given index.
//! \details Does *not* validate the DSG header!
//! \param[in] index: The index into the region table.
//! \return The address of the region
static inline void *dsg_block(uint index) {
    dsg_header_t *dsg_header = (dsg_header_t *)
            _sark_virtual_processor_info[sark.virt_cpu].user0;
    return dsg_header->regions[index];
}

//! \brief Publish the current transaction ID to the user1 register.
//! \details The register is a place where it can be read from host and by
//!     debugging tools.
//! \param[in] transaction_id: The value to store
static void publish_transaction_id(int transaction_id) {
    _sark_virtual_processor_info[sark.virt_cpu].user1 = transaction_id;
}

//! \brief Allocate a block of SDRAM (to be freed with sdram_free())
//! \param[in] size: the size of the block
//! \return a pointer to the block, or `NULL` if allocation failed
static inline void *sdram_alloc(uint size) {
    return sark_xalloc(sv->sdram_heap, size, 0,
            ALLOC_LOCK | ALLOC_ID | (sark_vec->app_id << 8));
}

//! \brief Free a block of SDRAM allocated with sdram_alloc()
//! \param[in] data: the block to free
static inline void sdram_free(void *data) {
    sark_xfree(sv->sdram_heap, data,
            ALLOC_LOCK | ALLOC_ID | (sark_vec->app_id << 8));
}

//! \brief The maximum SDRAM block size
//! \return The maximum size of heap memory block that may be allocated in SDRAM
static inline uint sdram_max_block_size(void) {
    return sark_heap_max(sv->sdram_heap, ALLOC_LOCK);
}

//! \brief Get an SDP message out of the mailbox correctly.
//! \return The retrieved message, or `NULL` if message buffer allocation
//!     failed.
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

//! Mark the end of an interrupt handler from the VIC's perspective.
static inline void vic_interrupt_done(void) {
    vic[VIC_VADDR] = (uint) vic;
}

//! \brief Install an interrupt handler.
//! \param[in] slot: Where to install the handler (controls priority).
//! \param[in] type: What we are handling.
//! \param[in] callback: The interrupt handler to install.
static inline void set_vic_callback(uint8_t slot, uint type, isr_t callback) {
#ifndef VIC_ENABLE_VECTOR
    enum {
        VIC_ENABLE_VECTOR = 0x20
    };
#endif //VIC_ENABLE_VECTOR

    _vic_vectors[slot] = callback;
    _vic_controls[slot] = VIC_ENABLE_VECTOR | type;
}

// ------------------------------------------------------------------------
// reinjector main functions
// ------------------------------------------------------------------------

//! \brief Enable the interrupt when the Communications Controller can accept
//!     another packet.
static inline void reinjection_enable_comms_interrupt(void) {
    vic[VIC_ENABLE] = 1 << CC_TNF_INT;
}

//! \brief Disable the interrupt when the Communications Controller can accept
//!     another packet.
static inline void reinjection_disable_comms_interrupt(void) {
    vic[VIC_DISABLE] = 1 << CC_TNF_INT;
}

//! \brief The plugin callback for the timer
static INT_HANDLER reinjection_timer_callback(void) {
    // clear interrupt in timer,
    tc[T1_INT_CLR] = 1;

    // check if router not blocked
    if ((rtr[RTR_STATUS] & RTR_BLOCKED_MASK) == 0) {
        // access packet queue with FIQ disabled,
        uint cpsr = cpu_fiq_disable();

        // if queue not empty turn on packet bouncing,
        if (reinject_pkt_queue.tail != reinject_pkt_queue.head) {
            // restore FIQ after queue access,
            cpu_int_restore(cpsr);

            // enable communications controller. interrupt to bounce packets
            reinjection_enable_comms_interrupt();
        } else {
            // restore FIQ after queue access
            cpu_int_restore(cpsr);
        }
    }

    // and tell VIC we're done
    vic_interrupt_done();
}

//! \brief Do the actual reinjection of a packet.
//! \param[in] pkt: The packet to reinject.
static inline void reinjection_reinject_packet(const dumped_packet_t *pkt) {
    // write header and route,
    cc[CC_TCR] = pkt->hdr & PKT_CONTROL_MASK;
    cc[CC_SAR] = reinject_p2p_source_id | (pkt->hdr & PKT_ROUTE_MASK);

    // maybe write payload,
    if (pkt->hdr & PKT_PLD_MASK) {
        cc[CC_TXDATA] = pkt->pld;
    }

    // write key to fire packet,
    cc[CC_TXKEY] = pkt->key;

    // Add to statistics
    reinject_n_reinjected_packets++;
}

//! \brief Called when the router can accept a packet and the reinjection queue
//!     is non-empty.
static INT_HANDLER reinjection_ready_to_send_callback(void) {
    // TODO: may need to deal with packet timestamp.

    // check if router not blocked
    if ((rtr[RTR_STATUS] & RTR_BLOCKED_MASK) == 0) {
        // access packet queue with FIQ disabled,
        uint cpsr = cpu_fiq_disable();

        // if queue not empty bounce packet,
        if (reinject_pkt_queue.tail != reinject_pkt_queue.head) {
            // dequeue packet and update queue pointer
            dumped_packet_t pkt =
                    reinject_pkt_queue.queue[reinject_pkt_queue.head];
            reinject_pkt_queue.head =
                    (reinject_pkt_queue.head + 1) % PKT_QUEUE_SIZE;

            // restore FIQ queue access,
            cpu_int_restore(cpsr);

            // reinject the packet
            reinjection_reinject_packet(&pkt);
        } else {
            // restore FIQ after queue access,
            cpu_int_restore(cpsr);

            // and disable communications controller interrupts; queue empty!
            reinjection_disable_comms_interrupt();
        }
    } else {
        // disable communications controller interrupts
        reinjection_disable_comms_interrupt();
    }

    // and tell VIC we're done
    vic_interrupt_done();
}

//! \brief The callback plugin for handling dropped packets.
static INT_HANDLER reinjection_dropped_packet_callback(void) {
    // get packet from router,
    uint hdr = rtr[RTR_DHDR];
    uint pld = rtr[RTR_DDAT];
    uint key = rtr[RTR_DKEY];

    // clear dump status and interrupt in router,
    uint rtr_dstat = rtr[RTR_DSTAT];
    uint rtr_dump_outputs = rtr[RTR_DLINK];
    uint is_processor_dump = (rtr_dump_outputs >> RTR_LE_BITS) & RTR_FPE_MASK;
    uint is_link_dump = rtr_dump_outputs & RTR_LE_MASK;

    // only reinject if configured
    uint packet_type = (hdr & PKT_TYPE_MASK);
    if (((packet_type == PKT_TYPE_MC) && reinject_mc) ||
            ((packet_type == PKT_TYPE_PP) && reinject_pp) ||
            ((packet_type == PKT_TYPE_NN) && reinject_nn) ||
            ((packet_type == PKT_TYPE_FR) && reinject_fr)) {
        // check for overflow from router
        if (rtr_dstat & RTR_DOVRFLW_MASK) {
            reinject_n_missed_dropped_packets++;
        } else {
            // Note that the processor_dump and link_dump flags are sticky
            // so you can only really count these if you *haven't* missed a
            // dropped packet - hence this being split out

            if (is_processor_dump > 0) {
                // add to the count the number of active bits from this dumped
                // packet, as this indicates how many processors this packet
                // was meant to go to.
                reinject_n_processor_dumped_packets +=
                        __builtin_popcount(is_processor_dump);
            }

            if (is_link_dump > 0) {
                // add to the count the number of active bits from this dumped
                // packet, as this indicates how many links this packet was
                // meant to go to.
                reinject_n_link_dumped_packets +=
                        __builtin_popcount(is_link_dump);
            }
        }

        // Only update this counter if this is a packet to reinject
        reinject_n_dropped_packets++;

        // Disable FIQ for queue access
        uint cpsr = cpu_fiq_disable();

        // try to insert dumped packet in the queue,
        uint new_tail = (reinject_pkt_queue.tail + 1) % PKT_QUEUE_SIZE;

        // check for space in the queue
        if (new_tail != reinject_pkt_queue.head) {
            // queue packet,
            reinject_pkt_queue.queue[reinject_pkt_queue.tail].hdr = hdr;
            reinject_pkt_queue.queue[reinject_pkt_queue.tail].key = key;
            reinject_pkt_queue.queue[reinject_pkt_queue.tail].pld = pld;

            // update queue pointer,
            reinject_pkt_queue.tail = new_tail;
        } else {
            // The queue of packets has overflowed
            reinject_n_dropped_packet_overflows++;
        }

        // restore FIQ after queue access,
        cpu_int_restore(cpsr);
    }
}

//! \brief Read a DSG memory region to set packet types for reinjection
//! \param[in] config: where to read the reinjection packet types from
static void reinjection_read_packet_types(const reinject_config_t *config) {
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

    io_printf(IO_BUF,
            "Setting reinject mc to %d\nSetting reinject pp to %d\n"
            "Setting reinject fr to %d\nSetting reinject nn to %d\n",
            reinject_mc, reinject_pp, reinject_fr, reinject_nn);

    // set the reinjection mc api
    initialise_reinjection_mc_api(config->reinjection_base_mc_key);
}

//! \brief Set the wait1 router timeout.
//! \param[in] payload: The encoded value to set. Must be in legal range.
static inline void reinjection_set_timeout(uint payload) {
    rtr[RTR_CONTROL] = (rtr[RTR_CONTROL] & 0xff00ffff)
            | ((payload & ROUTER_TIMEOUT_MASK) << 16);
}

//! \brief Set the wait2 router timeout.
//! \param[in] payload: The encoded value to set. Must be in legal range.
static inline void reinjection_set_emergency_timeout(uint payload) {
    rtr[RTR_CONTROL] = (rtr[RTR_CONTROL] & 0x00ffffff)
            | ((payload & ROUTER_TIMEOUT_MASK) << 24);
}

//! \brief Set the router wait1 timeout.
//! \details Delegates to reinjection_set_timeout()
//! \param[in,out] msg:
//!     The message requesting the change. Will be updated with response
//! \return The payload size of the response message.
static inline int reinjection_set_timeout_sdp(sdp_msg_t *msg) {
    io_printf(IO_BUF, "setting router timeouts via sdp\n");
    if (msg->arg1 > ROUTER_TIMEOUT_MASK) {
        msg->cmd_rc = RC_ARG;
        return 0;
    }
    reinjection_set_timeout(msg->arg1);
    // set SCP command to OK , as successfully completed
    msg->cmd_rc = RC_OK;
    return 0;
}

//! \brief Set the router wait2 timeout.
//! \details Delegates to reinjection_set_emergency_timeout()
//! \param[in,out] msg:
//!     The message requesting the change. Will be updated with response
//! \return The payload size of the response message.
static inline int reinjection_set_emergency_timeout_sdp(sdp_msg_t *msg) {
    io_printf(IO_BUF, "setting router emergency timeouts via sdp\n");
    if (msg->arg1 > ROUTER_TIMEOUT_MASK) {
        msg->cmd_rc = RC_ARG;
        return 0;
    }

    reinjection_set_emergency_timeout(msg->arg1);

    // set SCP command to OK, as successfully completed
    msg->cmd_rc = RC_OK;
    return 0;
}

//! \brief Set the re-injection options.
//! \param[in,out] msg:
//!     The message requesting the change. Will be updated with response
//! \return The payload size of the response message.
static inline int reinjection_set_packet_types(sdp_msg_t *msg) {
    reinject_mc = msg->arg1;
    reinject_pp = msg->arg2;
    reinject_fr = msg->arg3;
    reinject_nn = msg->data[0];

    io_printf(IO_BUF,
            "Setting reinject mc to %d\nSetting reinject pp to %d\n"
            "Setting reinject fr to %d\nSetting reinject nn to %d\n",
            reinject_mc, reinject_pp, reinject_fr, reinject_nn);

    // set SCP command to OK, as successfully completed
    msg->cmd_rc = RC_OK;
    return 0;
}

//! \brief Get the status and put it in the packet
//! \param[in,out] msg:
//!     The message requesting the change. Will be updated with response
//! \return The payload size of the response message.
static inline int reinjection_get_status(sdp_msg_t *msg) {
    reinjector_status_response_packet_t *data =
            (reinjector_status_response_packet_t *) &msg->arg1;

    // Put the router timeouts in the packet
    uint control = (uint) (rtr[RTR_CONTROL] & 0xFFFF0000);
    data->router_timeout = (control >> 16) & ROUTER_TIMEOUT_MASK;
    data->router_emergency_timeout = (control >> 24) & ROUTER_TIMEOUT_MASK;

    // Put the statistics in the packet
    data->n_dropped_packets = reinject_n_dropped_packets;
    data->n_missed_dropped_packets = reinject_n_missed_dropped_packets;
    data->n_dropped_packets_overflows = reinject_n_dropped_packet_overflows;
    data->n_reinjected_packets = reinject_n_reinjected_packets;
    data->n_link_dumped_packets = reinject_n_link_dumped_packets;
    data->n_processor_dumped_packets = reinject_n_processor_dumped_packets;

    io_printf(IO_BUF, "dropped packets %d\n", reinject_n_dropped_packets);

    // Put the current services enabled in the packet
    data->packet_types_reinjected = 0;
    bool values_to_check[] = {reinject_mc, reinject_pp,
                              reinject_nn, reinject_fr};
    for (int i = 0; i < 4; i++) {
        data->packet_types_reinjected |= (values_to_check[i] << i);
    }

    // set SCP command to OK, as successfully completed
    msg->cmd_rc = RC_OK;
    // Return the number of bytes in the packet
    return sizeof(reinjector_status_response_packet_t);
}

//! \brief Reset the counters
//! \param[in,out] msg:
//!     The message requesting the change. Will be updated with response
//! \return The payload size of the response message.
static inline int reinjection_reset_counters(sdp_msg_t *msg) {
    reinject_n_dropped_packets = 0;
    reinject_n_missed_dropped_packets = 0;
    reinject_n_dropped_packet_overflows = 0;
    reinject_n_reinjected_packets = 0;
    reinject_n_link_dumped_packets = 0;
    reinject_n_processor_dumped_packets = 0;

    // set SCP command to OK, as successfully completed
    msg->cmd_rc = RC_OK;
    return 0;
}

//! \brief Stop the reinjector.
//! \param[in,out] msg:
//!     The message requesting the change. Will be updated with response
//! \return The payload size of the response message.
static inline int reinjection_exit(sdp_msg_t *msg) {
    uint int_select = (1 << TIMER1_INT) | (1 << RTR_DUMP_INT);
    vic[VIC_DISABLE] = int_select;
    reinjection_disable_comms_interrupt();
    vic[VIC_SELECT] = 0;
    reinject_run = false;

    // set SCP command to OK, as successfully completed
    msg->cmd_rc = RC_OK;
    return 0;
}

//! Clear the queue of messages to reinject.
static void reinjection_clear(void) {
    // Disable FIQ for queue access
    uint cpsr = cpu_fiq_disable();
    // Clear any stored dropped packets
    reinject_pkt_queue.head = 0;
    reinject_pkt_queue.tail = 0;
    // restore FIQ after queue access,
    cpu_int_restore(cpsr);
    // and disable communications controller interrupts
    reinjection_disable_comms_interrupt();
}

//! \brief Clear the queue of messages to reinject.
//! \details Delegates to reinjection_clear()
//! \param[in,out] msg:
//!     The message requesting the change. Will be updated with response
//! \return The payload size of the response message.
static inline int reinjection_clear_message(sdp_msg_t *msg) {
    reinjection_clear();
    // set SCP command to OK, as successfully completed
    msg->cmd_rc = RC_OK;
    return 0;
}

//! \brief Handle the commands for the reinjector code.
//! \param[in,out] msg:
//!     The message with the command. Will be updated with response.
//! \return the length of extra data put into the message for return
static uint reinjection_sdp_command(sdp_msg_t *msg) {
    switch (msg->cmd_rc) {
    //io_printf(IO_BUF, "seq %d\n", msg->seq);
    case CMD_DPRI_SET_ROUTER_TIMEOUT:
        //io_printf(IO_BUF, "router timeout\n");
        return reinjection_set_timeout_sdp(msg);
    case CMD_DPRI_SET_ROUTER_EMERGENCY_TIMEOUT:
        //io_printf(IO_BUF, "router emergency timeout\n");
        return reinjection_set_emergency_timeout_sdp(msg);
    case CMD_DPRI_SET_PACKET_TYPES:
        //io_printf(IO_BUF, "router set packet type\n");
        return reinjection_set_packet_types(msg);
    case CMD_DPRI_GET_STATUS:
        //io_printf(IO_BUF, "router get status\n");
        return reinjection_get_status(msg);
    case CMD_DPRI_RESET_COUNTERS:
        //io_printf(IO_BUF, "router reset\n");
        return reinjection_reset_counters(msg);
    case CMD_DPRI_EXIT:
        //io_printf(IO_BUF, "router exit\n");
        return reinjection_exit(msg);
    case CMD_DPRI_CLEAR:
        //io_printf(IO_BUF, "router clear\n");
        return reinjection_clear_message(msg);
    default:
        // If we are here, the command was not recognised, so fail (ARG as the
        // command is an argument)
        msg->cmd_rc = RC_ARG;
        return 0;
    }
}

//! \brief SARK level timer interrupt setup
static void reinjection_configure_timer(void) {
    // Clear the interrupt
    tc[T1_CONTROL] = 0;
    tc[T1_INT_CLR] = 1;

    // Set the timer times
    tc[T1_LOAD] = sv->cpu_clk * TICK_PERIOD;
    tc[T1_BG_LOAD] = sv->cpu_clk * TICK_PERIOD;
}

//! Store this chip's p2p address for future use.
static void reinjection_configure_comms_controller(void) {
    // remember SAR register contents (p2p source ID)
    reinject_p2p_source_id = cc[CC_SAR] & 0x0000ffff;
}

//! Set up SARK and router to have a interrupt when a packet is dropped
static void reinjection_configure_router(void) {
    // re-configure wait values in router
    rtr[RTR_CONTROL] = (rtr[RTR_CONTROL] & 0x0000ffff) | ROUTER_INITIAL_TIMEOUT;

    // clear router interrupts,
    (void) rtr[RTR_STATUS];

    // clear router dump status,
    (void) rtr[RTR_DSTAT];

    // clear router error status,
    (void) rtr[RTR_ESTAT];

    // and enable router interrupts when dumping packets, and count errors
    rtr[RTR_CONTROL] |= RTR_DENABLE_MASK | RTR_ERRCNT_MASK;
}

//-----------------------------------------------------------------------------
// data in speed up main functions
//-----------------------------------------------------------------------------

//! Clear all (non-SARK/SCAMP) entries from the router.
static void data_in_clear_router(void) {
    rtr_entry_t router_entry;

    // clear the currently loaded routing table entries
    for (uint entry_id = N_BASIC_SYSTEM_ROUTER_ENTRIES;
            entry_id < N_ROUTER_ENTRIES; entry_id++) {
#ifdef DEBUG_DATA_IN
        io_printf(IO_BUF, "clearing entry %d\n", entry_id);
#endif
        if (rtr_mc_get(entry_id, &router_entry) &&
                router_entry.key != INVALID_ROUTER_ENTRY_KEY &&
                router_entry.mask != INVALID_ROUTER_ENTRY_MASK) {
            rtr_free(entry_id, 1);
        }
    }
#ifdef DEBUG_DATA_IN
    io_printf(IO_BUF, "max free block is %d\n", rtr_alloc_max());
#endif
}

//! Reset the state due to reaching the end of a data stream
static inline void data_in_process_boundary(void) {
    if (data_in_write_address) {
#ifdef DEBUG_DATA_IN
        io_printf(IO_BUF, "Wrote %u words\n",
                data_in_write_address - data_in_first_write_address);
#endif
        data_in_write_address = NULL;
    }
    data_in_first_write_address = NULL;
}

//! \brief Set the next location to write data at
//! \param[in] data: The address to write at
static inline void data_in_process_address(uint data) {
    if (data_in_write_address) {
        data_in_process_boundary();
    }
#ifdef DEBUG_DATA_IN
    io_printf(IO_BUF, "Setting write address to 0x%08x\n", data);
#endif
    data_in_first_write_address = data_in_write_address = (address_t) data;
}

//! \brief Write a word in a stream and advances the write pointer.
//! \param[in] data: The word to write
static inline void data_in_process_data(uint data) {
    // data keys require writing to next point in sdram

    if (data_in_write_address == NULL) {
        io_printf(IO_BUF, "Write address not set when write data received!\n");
        rt_error(RTE_SWERR);
    }
    *data_in_write_address = data;
    data_in_write_address++;
}

//! \brief Process a multicast packet with payload.
//! \details Shared between the reinjection and data in code paths. Calls one of:
//!
//! * reinjection_set_timeout()
//! * reinjection_set_emergency_timeout()
//! * reinjection_clear()
//! * data_in_process_address()
//! * data_in_process_data()
//! * data_in_process_boundary()
static INT_HANDLER process_mc_payload_packet(void) {
    // get data from comm controller
    uint data = cc[CC_RXDATA];
    uint key = cc[CC_RXKEY];
#if 0
    io_printf(IO_BUF, "received key %08x payload %08x\n", key, data);
#endif

    if (key == reinject_timeout_mc_key) {
        reinjection_set_timeout(data);
    } else if (key == reinject_emergency_timeout_mc_key) {
        reinjection_set_emergency_timeout(data);
    } else if (key == reinject_clear_mc_key) {
        reinjection_clear();
    } else if (key == data_in_address_key) {
        data_in_process_address(data);
    } else if (key == data_in_data_key) {
        data_in_process_data(data);
    } else if (key == data_in_boundary_key) {
        data_in_process_boundary();
    } else {
        io_printf(IO_BUF,
                "WARNING: failed to recognise multicast packet key 0x%08x\n",
                key);
    }

    // and tell VIC we're done
    vic_interrupt_done();
}

//! \brief Write router entries to the router.
//! \param[in] sdram_address: the SDRAM address where the router entries reside
//! \param[in] n_entries: how many router entries to read in
static void data_in_load_router(
        router_entry_t *sdram_address, uint n_entries) {
#ifdef DEBUG_DATA_IN
    io_printf(IO_BUF, "Writing %u router entries\n", n_entries);
#endif
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
#ifdef DEBUG_DATA_IN
            // Produces quite a lot of debugging output when enabled
            io_printf(IO_BUF,
                    "Setting key %08x, mask %08x, route %08x for entry %u\n",
                    sdram_address[idx].key, sdram_address[idx].mask,
                    sdram_address[idx].route, idx + start_entry_id);
#endif
            // try setting the valid router entry
            if (rtr_mc_set(idx + start_entry_id, sdram_address[idx].key,
                    sdram_address[idx].mask, sdram_address[idx].route) != 1) {
                io_printf(IO_BUF, "WARNING: failed to write router entry %d, "
                        "with key %08x, mask %08x, route %08x\n",
                        idx + start_entry_id, sdram_address[idx].key,
                        sdram_address[idx].mask, sdram_address[idx].route);
            }
        }
    }
}

//! \brief Copy router entries to the application router-table SDRAM store.
static void data_in_save_router(void) {
    rtr_entry_t router_entry;
    data_in_application_table_n_valid_entries = 0;
    for (uint entry_id = N_BASIC_SYSTEM_ROUTER_ENTRIES, i = 0;
            entry_id < N_ROUTER_ENTRIES; entry_id++, i++) {
        (void) rtr_mc_get(entry_id, &router_entry);

        if (router_entry.key != INVALID_ROUTER_ENTRY_KEY &&
                router_entry.mask != INVALID_ROUTER_ENTRY_MASK &&
                router_entry.route != INVALID_ROUTER_ENTRY_ROUTE) {
            // move to sdram
            data_in_saved_application_router_table[
                    data_in_application_table_n_valid_entries].key = router_entry.key;
            data_in_saved_application_router_table[
                    data_in_application_table_n_valid_entries].mask = router_entry.mask;
            data_in_saved_application_router_table[
                    data_in_application_table_n_valid_entries].route = router_entry.route;
            data_in_application_table_n_valid_entries++;
        }
    }
}

//! \brief Set up system routes on router.
//! \details Required by the data in speed up functionality.
//! \param[in] items: The collection of system routes to load.
static void data_in_speed_up_load_in_system_tables(
        data_in_data_items_t *items) {
    // read in router table into app store in sdram (in case its changed
    // since last time)
#ifdef DEBUG_DATA_IN
    io_printf(IO_BUF, "Saving existing router table\n");
#endif
    data_in_save_router();

    // clear the currently loaded routing table entries to avoid conflicts
    data_in_clear_router();

    // read in and load routing table entries
#ifdef DEBUG_DATA_IN
    io_printf(IO_BUF, "Loading system routes\n");
#endif
    data_in_load_router(
            items->system_router_entries, items->n_system_router_entries);
}

//! \brief Set up application routes on router.
//! \details Required by data in speed up functionality.
static void data_in_speed_up_load_in_application_routes(void) {
    // clear the currently loaded routing table entries
    data_in_clear_router();

    // load app router entries from sdram
#ifdef DEBUG_DATA_IN
    io_printf(IO_BUF, "Loading application routes\n");
#endif
    data_in_load_router(
            data_in_saved_application_router_table,
            data_in_application_table_n_valid_entries);
}

//! \brief The handler for all control messages coming in for data in speed up
//!     functionality.
//! \param[in,out] msg:
//!     the SDP message (without SCP header); will be updated with response
//! \return the length of the body of the SDP response message
static uint data_in_speed_up_command(sdp_msg_t *msg) {
    switch (msg->cmd_rc) {
    case SDP_COMMAND_FOR_SAVING_APPLICATION_MC_ROUTING:
#ifdef DEBUG_DATA_IN
        io_printf(IO_BUF, "Saving application router entries from router\n");
#endif
        data_in_save_router();
        msg->cmd_rc = RC_OK;
        break;
    case SDP_COMMAND_FOR_LOADING_APPLICATION_MC_ROUTES:
        data_in_speed_up_load_in_application_routes();
        msg->cmd_rc = RC_OK;
        data_in_last_table_load_was_system = false;
        break;
    case SDP_COMMAND_FOR_LOADING_SYSTEM_MC_ROUTES:
        if (data_in_last_table_load_was_system) {
            io_printf(IO_BUF,
                    "Already loaded system router; ignoring but replying\n");
            msg->cmd_rc = RC_OK;
            break;
        }
        data_in_speed_up_load_in_system_tables(
                dsg_block(CONFIG_DATA_SPEED_UP_IN));
        msg->cmd_rc = RC_OK;
        data_in_last_table_load_was_system = true;
        break;
    default:
        io_printf(IO_BUF,
                "Received unknown SDP packet in data in speed up port with"
                "command id %d\n", msg->cmd_rc);
        msg->cmd_rc = RC_ARG;
    }
    return 0;
}

//-----------------------------------------------------------------------------
// data speed up out main functions
//-----------------------------------------------------------------------------

//! \brief Send a fixed route packet with payload.
//! \param[in] key: The "key" (first word) of the packet.
//! \param[in] data: The "data" (second word) of the packet.
static inline void send_fixed_route_packet(uint32_t key, uint32_t data) {
    enum {
        //! Whether the comms controller can accept another packet
        TX_NOT_FULL_MASK = 0x10000000
    };

    // If stop, don't send anything
    if (data_out_stop) {
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

//! \brief Take a DMA'ed block and transmit its contents as fixed route
//!     packets to the packet gatherer.
//! \param[in] current_dma_pointer: the DMA pointer for the 2 buffers
//! \param[in] n_elements_to_send: the number of multicast packets to send
//! \param[in] first_packet_key: the first key to transmit with.
//! \param[in] second_packet_key: the second key to transmit with; all
//!     subsequent packets use the default key.
static void data_out_send_data_block(
        uint32_t current_dma_pointer, uint32_t n_elements_to_send,
        uint32_t first_packet_key, uint32_t second_packet_key) {
    // send data
    for (uint i = 0; i < n_elements_to_send; i++) {
        uint32_t current_data = data_out_data_to_transmit[current_dma_pointer][i];

        send_fixed_route_packet(first_packet_key, current_data);

        // update key to transmit with
        if (i == 0) {
            first_packet_key = second_packet_key;
        } else {
            first_packet_key = data_out_basic_data_key;
        }
    }
}

//! \brief Initiate a DMA read, copying from SDRAM into DTCM.
//! \details This is a basic operation. It does not include any safeguards.
//! \param[in] dma_tag: A label for what is being read. Should be one of the
//!     values in dma_tags_for_data_speed_up
//! \param[in] source: Where in SDRAM to read from.
//! \param[in] destination: Where in DTCM to write to.
//! \param[in] n_words: The number of _words_ to transfer. Can be up to 32k
//!     _words_.
static inline void data_out_start_dma_read(
        uint32_t dma_tag, void *source, void *destination, uint n_words) {
    uint desc = DMA_WIDTH << 24 | DMA_BURST_SIZE << 21 | DMA_READ << 19 |
            (n_words * sizeof(uint));
    data_out_dma_port_last_used = dma_tag;
    dma[DMA_ADRS] = (uint) source;
    dma[DMA_ADRT] = (uint) destination;
    dma[DMA_DESC] = desc;
}

//! \brief Set off a DMA reading a block of SDRAM in preparation for sending to
//!     the packet gatherer
//! \param[in] dma_tag: the DMA tag associated with this read.
//!     transmission or retransmission
//! \param[in] offset: where in the data array to start writing to
//! \param[in] items_to_read: the number of word items to read
static void data_out_read(
        uint32_t dma_tag, uint32_t offset, uint32_t items_to_read) {
    // set off DMA
    data_out_transmit_dma_pointer =
            (data_out_transmit_dma_pointer + 1) % N_DMA_BUFFERS;

    address_t data_sdram_position =
            &data_out_store_address[data_out_position_in_store];

    // update positions as needed
    data_out_position_in_store += items_to_read;
    data_out_num_items_read = items_to_read;

    // set off DMA
    data_out_start_dma_read(dma_tag, data_sdram_position,
            &data_out_data_to_transmit[data_out_transmit_dma_pointer][offset],
            items_to_read);
}

//! \brief Send the end flag to the packet gatherer.
static void data_out_send_end_flag(void) {
    send_fixed_route_packet(data_out_end_flag_key, END_FLAG);
}

//! \brief DMA complete callback for reading for original transmission
//! \details
//!     Uses a pair of buffers in DTCM so data can be read in from SDRAM while
//!     the previous is being transferred over the network.
//!
//! Callback associated with ::DMA_TAG_READ_FOR_TRANSMISSION
static void data_out_dma_complete_reading_for_original_transmission(void) {
    // set up state
    uint32_t current_dma_pointer = data_out_transmit_dma_pointer;
    uint32_t key_to_transmit = data_out_basic_data_key;
    uint32_t second_key_to_transmit = data_out_basic_data_key;
    uint32_t items_read_this_time = data_out_num_items_read;

    // put size in bytes if first send
    if (data_out_first_transmission) {
        //io_printf(IO_BUF, "in first\n");
        data_out_data_to_transmit[current_dma_pointer][0] = data_out_max_seq_num;
        data_out_data_to_transmit[current_dma_pointer][1] = data_out_transaction_id;
        key_to_transmit = data_out_first_data_key;
        second_key_to_transmit = data_out_transaction_id_key;
        data_out_first_transmission = false;
        items_read_this_time += 2;
    }

    // stopping procedure
    // if a full packet, read another and try again
    if (data_out_position_in_store < data_out_n_elements_to_read_from_sdram) {
        uint32_t num_items_to_read = SDP_PAYLOAD_WORDS;
        uint32_t next_position_in_store =
                data_out_position_in_store + SDP_PAYLOAD_WORDS;

        // if less data needed request less data
        if (next_position_in_store >= data_out_n_elements_to_read_from_sdram) {
            num_items_to_read =
                    data_out_n_elements_to_read_from_sdram -
                    data_out_position_in_store;
        }

        // set off another read and transmit DMA'ed one
        data_out_read(DMA_TAG_READ_FOR_TRANSMISSION, 0, num_items_to_read);
        data_out_send_data_block(current_dma_pointer, items_read_this_time,
                key_to_transmit, second_key_to_transmit);
    } else {
        data_out_send_data_block(current_dma_pointer, items_read_this_time,
                key_to_transmit, second_key_to_transmit);

        // send end flag.
        data_out_send_end_flag();

        data_out_has_finished = true;
        data_out_n_missing_seq_packets = 0;
    }

    if (TDMA_WAIT_PERIOD != 0) {
        sark_delay_us(TDMA_WAIT_PERIOD);
    }
}

//! \brief Basic write sequence numbers to SDRAM that need retransmitting
//! \param[in] data: data to write into SDRAM
//! \param[in] length: length of data
//! \param[in] start_offset: where in the data to start writing in from.
static void data_out_write_missing_seq_nums_into_sdram(
        uint32_t data[], uint length, uint32_t start_offset) {
    for (uint i = start_offset, j = data_out_n_missing_seq_nums_in_sdram;
            i < length; i++, j++) {
        data_out_missing_seq_num_sdram_address[j] = data[i];
        if (data[i] > data_out_max_seq_num) {
            io_printf(IO_BUF, "Storing some bad seq num. WTF! %d %d\n",
                    data[i], data_out_max_seq_num);
        }
    }
    data_out_n_missing_seq_nums_in_sdram += length - start_offset;
}

//! \brief Store sequence numbers into SDRAM.
//! \details
//!     Acts as a memory management front end to
//!     data_out_write_missing_seq_nums_into_sdram()
//! \param[in] data: the message data to read into SDRAM
//! \param[in] length: how much data to read
//! \param[in] first: if first packet about missing sequence numbers. If so
//!     there is different behaviour
static void data_out_store_missing_seq_nums(
        uint32_t data[], uint length, bool first) {
    uint32_t start_reading_offset = START_OF_MISSING_MORE;
    if (first) {
        data_out_n_missing_seq_packets =
                data[POSITION_OF_NO_MISSING_SEQ_PACKETS];

        uint32_t size_of_data =
                (data_out_n_missing_seq_packets * ITEMS_PER_DATA_PACKET * sizeof(uint))
                + END_FLAG_SIZE;

        if (data_out_missing_seq_num_sdram_address != NULL) {
            sdram_free(data_out_missing_seq_num_sdram_address);
            data_out_missing_seq_num_sdram_address = NULL;
        }
        data_out_missing_seq_num_sdram_address = sdram_alloc(size_of_data);

        // if not got enough sdram to alllocate all missing seq nums
        if (data_out_missing_seq_num_sdram_address == NULL) {
            // biggest sdram block
            uint32_t max_bytes = sdram_max_block_size();
            // if can't hold more than this packets worth of data, blow up
            if (max_bytes < SDP_PAYLOAD_BYTES + END_FLAG_SIZE) {
                io_printf(IO_BUF,
                        "Can't allocate SDRAM for missing seq nums\n");
                rt_error(RTE_SWERR);
            }

            io_printf(IO_BUF, "Activate bacon protocol!");

            // allocate biggest block
            data_out_missing_seq_num_sdram_address = sdram_alloc(max_bytes);
            // determine max full seq num packets to store
            max_bytes -= END_FLAG_SIZE + SDP_PAYLOAD_BYTES;
            data_out_n_missing_seq_packets = 1
                    + max_bytes / (ITEMS_PER_DATA_PACKET * sizeof(uint));
        }
        start_reading_offset = START_OF_MISSING_SEQ_NUMS;
    }
    if (data_out_n_missing_seq_packets > 0) {
        // write data to SDRAM and update packet counter
        data_out_write_missing_seq_nums_into_sdram(
                data, length, start_reading_offset);
        data_out_n_missing_seq_packets--;
    } else {
        io_printf(IO_BUF, "Unable to save missing sequence number\n");
    }
}

//! \brief Set off a DMA for retransmission stuff
static void data_out_retransmission_dma_read(void) {
    // locate where we are in SDRAM
    address_t data_sdram_position =
            &data_out_missing_seq_num_sdram_address[data_out_position_for_retransmission];

    // set off DMA
    data_out_start_dma_read(DMA_TAG_READ_FOR_RETRANSMISSION,
            data_sdram_position, data_out_retransmit_seq_nums,
            ITEMS_PER_DATA_PACKET);
}

//! \brief Read in missing sequence numbers and set off the reading of
//!     SDRAM for the equivalent data
//! \details Callback associated with ::DMA_TAG_READ_FOR_RETRANSMISSION
static void data_out_dma_complete_read_missing_seqeuence_nums(void) {
    // check if at end of read missing sequence numbers
    if (data_out_read_data_position > ITEMS_PER_DATA_PACKET) {
        data_out_position_for_retransmission += ITEMS_PER_DATA_PACKET;
        if (data_out_n_missing_seq_nums_in_sdram >
                data_out_position_for_retransmission) {
            data_out_read_data_position = 0;
            data_out_retransmission_dma_read();
        }
        return;
    }

    // get next sequence number to regenerate
    data_out_missing_seq_num_being_processed = (uint32_t)
            data_out_retransmit_seq_nums[data_out_read_data_position];
    if (data_out_missing_seq_num_being_processed != END_FLAG) {
        // regenerate data
        data_out_position_in_store =
                data_out_missing_seq_num_being_processed * SDP_PAYLOAD_WORDS;
        uint32_t left_over_portion =
                data_out_n_elements_to_read_from_sdram -
                data_out_position_in_store;

        if (left_over_portion < SDP_PAYLOAD_WORDS) {
            data_out_retransmitted_seq_num_items_read = left_over_portion + 1;
            data_out_read(DMA_TAG_RETRANSMISSION_READING, 1, left_over_portion);
        } else {
            data_out_retransmitted_seq_num_items_read =
                    ITEMS_PER_DATA_PACKET - TRANSACTION_ID_SIZE;
            data_out_read(DMA_TAG_RETRANSMISSION_READING, 1, SDP_PAYLOAD_WORDS);
        }
    } else {        // finished data send, tell host its done
        data_out_send_end_flag();
        data_out_in_retransmission_mode = false;
        data_out_missing_seq_num_sdram_address = NULL;
        data_out_read_data_position = 0;
        data_out_position_for_retransmission = 0;
        data_out_n_missing_seq_nums_in_sdram = 0;
    }
}

//! \brief DMA complete callback for have read missing sequence number data.
//! \details Callback associated with ::DMA_TAG_RETRANSMISSION_READING
static void data_out_dma_complete_reading_retransmission_data(void) {
    // set sequence number as first element
    data_out_data_to_transmit[data_out_transmit_dma_pointer][0] =
            data_out_missing_seq_num_being_processed;
    if (data_out_missing_seq_num_being_processed > data_out_max_seq_num) {
        io_printf(IO_BUF,
                "Got some bad seq num here; max is %d, got %d\n",
                data_out_max_seq_num, data_out_missing_seq_num_being_processed);
    }

    // send new data back to host
    data_out_send_data_block(
            data_out_transmit_dma_pointer,
            data_out_retransmitted_seq_num_items_read,
            data_out_new_sequence_key, data_out_basic_data_key);

    data_out_read_data_position++;
    data_out_dma_complete_read_missing_seqeuence_nums();
}

//! \brief DMA complete callback for have read missing sequence number data
static void data_out_dma_complete_writing_missing_seq_to_sdram(void) {
    io_printf(IO_BUF, "Need to figure what to do here\n");
}

//! \brief Handler for all messages coming in for data speed up
//!     functionality.
//! \param[in] msg: the SDP message (without SCP header)
static void data_out_speed_up_command(sdp_msg_pure_data *msg) {
    sdp_data_out_t *message = (sdp_data_out_t *) msg->data;

    switch (message->command) {
    case SDP_CMD_START_SENDING_DATA: {
        // updater transaction id if it hits the cap
        if (((data_out_transaction_id + 1) & TRANSACTION_CAP) == 0) {
            data_out_transaction_id = 0;
            publish_transaction_id(data_out_transaction_id);
        }

        // if transaction id is not as expected. ignore it as its from the past.
        // and worthless
        if (message->transaction_id != data_out_transaction_id + 1) {
            io_printf(IO_BUF,
                    "received start message with unexpected "
                    "transaction id %d; mine is %d\n",
                    message->transaction_id, data_out_transaction_id + 1);
            return;
        }

        //extract transaction id and update
        data_out_transaction_id = message->transaction_id;
        publish_transaction_id(data_out_transaction_id);

        data_out_stop = false;

        // set SDRAM position and length
        data_out_store_address = message->sdram_location;
        // state for how many bytes it needs to send, gives approximate
        // bandwidth if round number.
        uint32_t bytes_to_read_write = message->length;

        data_out_max_seq_num = bytes_to_read_write / SDP_PAYLOAD_BYTES;
        uint32_t mod = bytes_to_read_write % SDP_PAYLOAD_BYTES;
        data_out_max_seq_num += mod > 0;

        // reset states
        data_out_first_transmission = true;
        data_out_transmit_dma_pointer = 0;
        data_out_position_in_store = 0;
        data_out_n_elements_to_read_from_sdram =
                bytes_to_read_write / sizeof(uint);

        if (data_out_n_elements_to_read_from_sdram < SDP_PAYLOAD_WORDS) {
            data_out_read(DMA_TAG_READ_FOR_TRANSMISSION, 2,
                    data_out_n_elements_to_read_from_sdram);
        } else {
            data_out_read(DMA_TAG_READ_FOR_TRANSMISSION, 2, SDP_PAYLOAD_WORDS);
        }
        return;
    }
    case SDP_CMD_START_OF_MISSING_SDP_PACKETS:
        if (message->transaction_id != data_out_transaction_id) {
            io_printf(IO_BUF,
                    "received data from a different transaction for "
                    "start of missing. expected %d got %d\n",
                    data_out_transaction_id, message->transaction_id);
            return;
        }

        // if already in a retransmission phase, don't process as normal
        if (data_out_n_missing_seq_packets != 0) {
            io_printf(IO_BUF, "forcing start of retransmission packet\n");
            data_out_n_missing_seq_packets = 0;
            data_out_missing_seq_num_sdram_address[data_out_n_missing_seq_nums_in_sdram++] =
                    END_FLAG;
            data_out_read_data_position = 0;
            data_out_position_for_retransmission = 0;
            data_out_in_retransmission_mode = true;
            data_out_retransmission_dma_read();
            return;
        }
        // fall through
    case SDP_CMD_MORE_MISSING_SDP_PACKETS:
        if (message->transaction_id != data_out_transaction_id) {
            io_printf(IO_BUF,
                    "received data from different transaction for more "
                    "missing; expected %d, got %d\n",
                    data_out_transaction_id, message->transaction_id);
            return;
        }

        // reset state, as could be here from multiple attempts
        if (!data_out_in_retransmission_mode) {
            // put missing sequence numbers into SDRAM
            data_out_store_missing_seq_nums(
                    msg->data,
                    (msg->length - LENGTH_OF_SDP_HEADER) / sizeof(uint),
                    message->command == SDP_CMD_START_OF_MISSING_SDP_PACKETS);

            // if got all missing packets, start retransmitting them to host
            if (data_out_n_missing_seq_packets == 0) {
                // packets all received, add finish flag for DMA stoppage

                if (data_out_n_missing_seq_nums_in_sdram != 0) {
                    data_out_missing_seq_num_sdram_address[
                            data_out_n_missing_seq_nums_in_sdram++] = END_FLAG;
                    data_out_read_data_position = 0;
                    data_out_position_for_retransmission = 0;

                    // start DMA off
                    data_out_in_retransmission_mode = true;
                    data_out_retransmission_dma_read();
                }
            }
        }
        return;
    case SDP_CMD_CLEAR:
        if (message->transaction_id != data_out_transaction_id) {
            io_printf(IO_BUF,
                    "received data from different transaction for "
                    "clear; expected %d, got %d\n",
                    data_out_transaction_id, message->transaction_id);
            return;
        }
        io_printf(IO_BUF, "data out clear\n");
        data_out_stop = true;
        break;
    default:
        io_printf(IO_BUF, "Received unknown SDP packet: %d\n",
                message->command);
    }
}

//! \brief The handler for all DMAs complete.
//! \details Depending on the dma_tag used with data_out_start_dma_read(),
//! calls one of:
//!
//! * data_out_dma_complete_reading_for_original_transmission()
//! * data_out_dma_complete_read_missing_seqeuence_nums()
//! * data_out_dma_complete_reading_retransmission_data()
//! * data_out_dma_complete_writing_missing_seq_to_sdram() (tag unused?)
static INT_HANDLER data_out_dma_complete(void) {
    // reset the interrupt.
    dma[DMA_CTRL] = 0x8;
    if (!data_out_stop) {
        // Only do something if we have not been told to stop
        switch (data_out_dma_port_last_used) {
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
            io_printf(IO_BUF, "Invalid DMA callback port: %d\n",
                    data_out_dma_port_last_used);
            rt_error(RTE_SWERR);
        }
    }
    // and tell VIC we're done
    vic_interrupt_done();
}

//! Handler for DMA errors
static INT_HANDLER data_out_dma_error(void) {
    io_printf(IO_BUF, "DMA failed: 0x%08x\n", dma[DMA_STAT]);
    dma[DMA_CTRL] = 0x4;
    vic_interrupt_done();
    rt_error(RTE_DABT);
}

//! Handler for DMA timeouts (hopefully unlikely...)
static INT_HANDLER data_out_dma_timeout(void) {
    io_printf(IO_BUF, "DMA timeout: 0x%08x\n", dma[DMA_STAT]);
    dma[DMA_CTRL] = 0x10;
    vic_interrupt_done();
}

//-----------------------------------------------------------------------------
// common code
//-----------------------------------------------------------------------------

void __real_sark_int(void *pc);
//! Check for extra messages added by this core.
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
    //io_printf(IO_BUF, "seq is %d\n", msg->seq);
    sc[SC_CLR_IRQ] = SC_CODE + (1 << sark.phys_cpu);
    if (msg == NULL) {
        return;
    }

    io_printf(IO_BUF, "received sdp message\n");

    switch ((msg->dest_port & PORT_MASK) >> PORT_SHIFT) {
    case REINJECTION_PORT:
#if 0
        io_printf(IO_BUF, "reinjection port\n");
#endif
        reflect_sdp_message(msg, reinjection_sdp_command(msg));
        while (!sark_msg_send(msg, 10)) {
            io_printf(IO_BUF, "timeout when sending reinjection reply\n");
        }
        break;
    case DATA_SPEED_UP_OUT_PORT:
        // These are all one-way messages; replies are out of band
#if 0
        io_printf(IO_BUF, "out port\n");
#endif
        data_out_speed_up_command((sdp_msg_pure_data *) msg);
        break;
    case DATA_SPEED_UP_IN_PORT:
#if 0
        io_printf(IO_BUF, "in port\n");
#endif
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

//! \brief Set up data and callbacks required by the reinjection system.
static void reinjection_initialise(void) {
    // set up config region
    // Get the address this core's DTCM data starts at from SRAM
    reinjection_read_packet_types(dsg_block(CONFIG_REINJECTION));

    // Setup the CPU interrupt for WDOG
    _vic_controls[sark_vec->sark_slot] = 0;
    set_vic_callback(CPU_SLOT, CPU_INT, sark_int_han);

    // Setup the communications controller interrupt
    set_vic_callback(CC_SLOT, CC_TNF_INT, reinjection_ready_to_send_callback);

    // Setup the timer interrupt
    set_vic_callback(TIMER_SLOT, TIMER1_INT, reinjection_timer_callback);

    // Setup the router interrupt as a fast interrupt
    sark_vec->fiq_vec = reinjection_dropped_packet_callback;
    vic[VIC_SELECT] = 1 << RTR_DUMP_INT;
}

//! \brief Set up data and callbacks required by the data speed up system.
static void data_out_initialise(void) {
    data_speed_out_config_t *config = dsg_block(CONFIG_DATA_SPEED_UP_OUT);
    data_out_basic_data_key = config->my_key;
    data_out_new_sequence_key = config->new_seq_key;
    data_out_first_data_key = config->first_data_key;
    data_out_transaction_id_key = config->transaction_id_key;
    data_out_end_flag_key = config->end_flag_key;

    io_printf(IO_BUF,
            "new seq key = %d, first data key = %d, transaction id key = %d, "
            "end flag key = %d, basic_data_key = %d\n",
            data_out_new_sequence_key, data_out_first_data_key, data_out_transaction_id_key,
            data_out_end_flag_key, data_out_basic_data_key);

    // Various DMA callbacks
    set_vic_callback(DMA_SLOT, DMA_DONE_INT, data_out_dma_complete);
    set_vic_callback(DMA_ERROR_SLOT, DMA_ERR_INT, data_out_dma_error);
    set_vic_callback(DMA_TIMEOUT_SLOT, DMA_TO_INT, data_out_dma_timeout);

    // configuration for the DMA's by the speed data loader
    dma[DMA_CTRL] = 0x3f; // Abort pending and active transfers
    dma[DMA_CTRL] = 0x0d; // clear possible transfer done and restart
    dma[DMA_GCTL] = 0x1ffc00; // enable DMA done and error interrupt
}

//! \brief Set up data and callback required by the data in speed up system.
static void data_in_initialise(void) {
    data_in_saved_application_router_table = sdram_alloc(
            N_USABLE_ROUTER_ENTRIES * sizeof(router_entry_t));
    if (data_in_saved_application_router_table == NULL) {
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

    // load user 1 in case this is a consecutive load
    publish_transaction_id(data_out_transaction_id);

    // set up mc interrupts to deal with data writing
    set_vic_callback(
        MC_PAYLOAD_SLOT, CC_MC_INT, process_mc_payload_packet);
}

//-----------------------------------------------------------------------------
//! main entry point
//-----------------------------------------------------------------------------
void c_main(void) {
    sark_cpu_state(CPU_STATE_RUN);

    // Configure
    my_addr = sv->p2p_addr;
    reinjection_configure_timer();
    reinjection_configure_comms_controller();
    reinjection_configure_router();

    // Initialise the statistics
    reinject_n_dropped_packets = 0;
    reinject_n_reinjected_packets = 0;
    reinject_n_missed_dropped_packets = 0;
    reinject_n_dropped_packet_overflows = 0;

    // set up VIC callbacks and interrupts accordingly
    // Disable the interrupts that we are configuring (except CPU for WDOG)
    uint int_select = (1 << TIMER1_INT) | (1 << RTR_DUMP_INT) |
            (1 << DMA_DONE_INT) | (1 << CC_MC_INT) |
            (1 << DMA_ERR_INT) | (1 << DMA_TO_INT);
    vic[VIC_DISABLE] = int_select;
    reinjection_disable_comms_interrupt();

    // set up reinjection functionality
    reinjection_initialise();

    // set up data speed up functionality
    data_out_initialise();
    data_in_initialise();

    // Enable interrupts and timer
    vic[VIC_ENABLE] = int_select;
    tc[T1_CONTROL] = 0xe2;

    // Run until told to exit
    while (reinject_run) {
        spin1_wfi();
    }
}
// ------------------------------------------------------------------------

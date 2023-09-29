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
//! \brief The implementation of the Extra Monitor.
//!
//! The purpose of this application is to provide extra monitor functions (such
//! as reinjection control) that do not fit in SCAMP, and to provide an
//! endpoint on each chip for streaming data in and out at high speed (while
//! the main user application is not running).
//!
//! \note This application does not use spin1_api as it needs low-level access
//! to interrupts.

// SARK-based program
#include <sark.h>
#include <stdbool.h>
#include <common-typedefs.h>
#include <spinn_extra.h>
#include "common.h"
#include "data_specification.h"
#include <wfi.h>

// Debugging control
//#define DEBUG_DATA_IN
#undef DEBUG_DATA_IN

// ------------------------------------------------------------------------
// constants
// ------------------------------------------------------------------------

//-----------------------------------------------------------------------------
// stuff to do with SARK DMA
//-----------------------------------------------------------------------------

//! \brief Use DMA bursts of 16 (2<sup>4</sup>) transfer units (double words)
//!
//! See [SpiNNaker Data Sheet][datasheet], Section 7.4, register r3
//!
//! [datasheet]: https://spinnakermanchester.github.io/docs/SpiNN2DataShtV202.pdf
#define DMA_BURST_SIZE 4

//! the number of DMA buffers to build
#define N_DMA_BUFFERS 2

//-----------------------------------------------------------------------------
// magic numbers for data speed up extractor
//-----------------------------------------------------------------------------

//! flag size for saying ended, in bytes
#define END_FLAG_SIZE 4
//! flag for saying stuff has ended
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
#define ROUTER_INITIAL_TIMEOUT 0x4f

//! Amount to call the timer callback
#define TICK_PERIOD        10

//! dumped packet queue length
#define PKT_QUEUE_SIZE     4096

//! Maximum router timeout value
#define ROUTER_TIMEOUT_MAX 0xFF

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

// ------------------------------------------------------------------------
// structs used in system
// ------------------------------------------------------------------------

//! dumped packet type
typedef struct dumped_packet_t {
    router_packet_header_t hdr; //!< Header word of packet
    uint key;                   //!< Key word of packet
    uint pld;                   //!< Payload word of packet (might be undefined)
} dumped_packet_t;

//! packet queue type
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

//! \brief message payload for the data speed up out SDP messages
typedef struct sdp_data_out_t {
    //! What operation are we dealing with
    data_out_sdp_commands command;
    //! \brief What is the transaction ID
    //!
    //! This is used to stop confusion when critical packets get lost
    uint transaction_id;
    //! What location are we talking about
    address_t sdram_location;
    //! How much data are we moving
    uint length;
} sdp_data_out_t;

//! \brief router entry positions in sdram
typedef struct router_entry_t {
    uint32_t key;   //!< The SpiNNaker router key
    uint32_t mask;  //!< The SpiNNaker router mask
    uint32_t route; //!< The SpiNNaker router route (to use when masked key matches)
} router_entry_t;

//! \brief data positions in sdram for data in config
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

//! defintion of response packet for reinjector status
typedef struct reinjector_status_response_packet_t {
    //! \brief The current router timeout
    //!
    //! See [SpiNNaker Data Sheet][datasheet], Section 10.11, register r0, field wait1
    //!
    //! [datasheet]: https://spinnakermanchester.github.io/docs/SpiNN2DataShtV202.pdf
    uint router_timeout;
    //! \brief The current router emergency timeout
    //!
    //! See [SpiNNaker Data Sheet][datasheet], Section 10.11, register r0, field wait2
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
    //! The link / processor bit fields of dropped packets
    uint link_proc_bits;
} reinjector_status_response_packet_t;

//! how the reinjection configuration is laid out in memory.
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
    CONFIG_DATA_SPEED_UP_IN = 2,
    //! Provenance collection region (format: ::extra_monitor_provenance_t)
    PROVENANCE_REGION = 3
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

//! human readable definitions of each element in the transmission region
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

//! The information in the provenance region
typedef struct extra_monitor_provenance_t {
    //! The total number of relevant SDP packets processed
    uint n_sdp_packets;
    //! The number of times we've streamed data in
    uint n_in_streams;
    //! The number of times we've streamed data out
    uint n_out_streams;
    //! The number of times we've modified the router
    uint n_router_changes;
} extra_monitor_provenance_t;

//! values for the priority for each callback
enum callback_priorities {
    SDP = 0,
    DMA = 0
};

// ------------------------------------------------------------------------
// global variables for reinjector functionality
// ------------------------------------------------------------------------

//! \brief The content of the communications controller SAR register.
//!
//! Specifically, the P2P source identifier.
static uint reinject_p2p_source_id;

//! \brief dumped packet queue
static pkt_queue_t reinject_pkt_queue;

// statistics
//! \brief Count of all packets dropped by router.
static uint reinject_n_dropped_packets;

//! \brief Count of packets dumped because the router was itself overloaded.
static uint reinject_n_missed_dropped_packets;

//! \brief Count of packets lost because we ran out of queue space.
static uint reinject_n_dropped_packet_overflows;

//! \brief Count of all packets reinjected.
static uint reinject_n_reinjected_packets;

//! \brief Estimated count of packets dropped by router because a destination
//! link is busy.
static uint reinject_n_link_dumped_packets;

//! \brief Estimated count of packets dropped by router because a destination
//! core (local) is busy.
static uint reinject_n_processor_dumped_packets;

//! \brief Which links and processors packets were dumped from (cumulative bit field)
static uint reinject_link_proc_bits;

// Determine what to reinject

//! \brief Flag: whether to reinject multicast packets.
static bool reinject_mc;

//! \brief Flag: whether to reinject point-to-point packets.
static bool reinject_pp;

//! \brief Flag: whether to reinject nearest neighbour packets.
static bool reinject_nn;

//! \brief Flag: whether to reinject fixed route packets.
static bool reinject_fr;

//! Whether we are running the reinjector
static bool reinject_run = true;

// ------------------------------------------------------------------------
// global variables for data speed up in functionality
// ------------------------------------------------------------------------

// data in variables
//! \brief Where we save a copy of the application code's router table while the
//! system router table entries are loaded.
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
//! DMA transfer.
static uint32_t data_out_transmit_dma_pointer = 0;

//! Index (by words) into the block of SDRAM being read.
static uint32_t data_out_position_in_store = 0;

//! Size of the current DMA transfer.
static uint32_t data_out_num_items_read = 0;

//! \brief The current transaction identifier, identifying the stream of items
//! being moved.
//!
//! Also written to the user1 SARK register
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
//!
//! Gets filled from ::data_out_missing_seq_num_sdram_address by DMA
static uint32_t data_out_retransmit_seq_nums[ITEMS_PER_DATA_PACKET];

//! Used to track where we are in the retransmissions.
static uint32_t data_out_position_for_retransmission = 0;

//! The current sequence number for the chunk being being DMA'd in.
static uint32_t data_out_missing_seq_num_being_processed = 0;

//! \brief Index into ::data_out_retransmit_seq_nums used to track where we are
//! in a chunk of sequence numbers to retransmit.
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

//! The standard SARK CPU interrupt handler.
extern INT_HANDLER sark_int_han(void);

//! \brief Where are we (as a P2P address)?
//!
//! Used for error reporting.
static ushort my_addr;

//! The SARK virtual processor information table in SRAM.
static vcpu_t *const _sark_virtual_processor_info = (vcpu_t *) SV_VCPU;

//! Where we collect provenance in SDRAM.
static extra_monitor_provenance_t *prov;

//! The DSE regions structure
static data_specification_metadata_t *dse_regions;

//! \brief Get the DSG region with the given index.
//!
//! Does *not* validate the DSG header!
//!
//! \param[in] index: The index into the region table.
//! \return The address of the region
static inline void *dse_block(uint index) {
    return data_specification_get_region(index, dse_regions);
}

//! \brief publishes the current transaction ID to the user1 register.
//!
//! The register is a place where it can be read from host and by debugging
//! tools.
//!
//! \param[in] transaction_id: The value to store
static void publish_transaction_id(int transaction_id) {
    _sark_virtual_processor_info[sark.virt_cpu].user1 = transaction_id;
}

//! \brief allocate a block of SDRAM (to be freed with sdram_free())
//! \param[in] size: the size of the block
//! \return a pointer to the block, or `NULL` if allocation failed
static inline void *sdram_alloc(uint size) {
    return sark_xalloc(sv->sdram_heap, size, 0,
            ALLOC_LOCK | ALLOC_ID | (sark_vec->app_id << 8));
}

//! \brief free a block of SDRAM allocated with sdram_alloc()
//! \param[in] data: the block to free
static inline void sdram_free(void *data) {
    sark_xfree(sv->sdram_heap, data,
            ALLOC_LOCK | ALLOC_ID | (sark_vec->app_id << 8));
}

//! \brief the maximum SDRAM block size
//! \return The maximum size of heap memory block that may be allocated in SDRAM
static inline uint sdram_max_block_size(void) {
    return sark_heap_max(sv->sdram_heap, ALLOC_LOCK);
}

//! \brief How to get an SDP message out of the mailbox correctly.
//! \return The retrieved message, or `NULL` if message buffer allocation
//! failed.
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

//! Marks the end of an interrupt handler from the VIC's perspective.
static inline void vic_interrupt_done(void) {
    vic_control->vector_address = (vic_interrupt_handler_t) vic;
}

//! \brief Install an interrupt handler.
//! \param[in] slot: Where to install the handler (controls priority).
//! \param[in] type: What we are handling.
//! \param[in] callback: The interrupt handler to install.
static inline void set_vic_callback(
        uint8_t slot, uint type, vic_interrupt_handler_t callback) {
    vic_interrupt_vector[slot] = callback;
    vic_interrupt_control[slot] = (vic_vector_control_t) {
        .source = type,
        .enable = true
    };
}

// ------------------------------------------------------------------------
// reinjector main functions
// ------------------------------------------------------------------------

//! \brief Enable the interrupt when the Communications Controller can accept
//! another packet.
static inline void reinjection_enable_comms_interrupt(void) {
    vic_control->int_enable = (vic_mask_t) {
        .cc_tx_not_full = true
    };
}

//! \brief Disable the interrupt when the Communications Controller can accept
//! another packet.
static inline void reinjection_disable_comms_interrupt(void) {
    vic_control->int_disable = (vic_mask_t) {
        .cc_tx_not_full = true
    };
}

//! \brief Whether the comms hardware can accept packet now.
//! \return True if the router output stage is empty.
static inline bool reinjection_can_send_now(void) {
    return router_control->status.output_stage == ROUTER_OUTPUT_STAGE_EMPTY;
}

//! \brief the plugin callback for the timer
static INT_HANDLER reinjection_timer_callback(void) {
    // clear interrupt in timer,
    timer1_control->interrupt_clear = true;

    // check if router not blocked
    if (reinjection_can_send_now()) {
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

//! \brief Does the actual reinjection of a packet.
//! \param[in] pkt: The packet to reinject.
static inline void reinjection_reinject_packet(const dumped_packet_t *pkt) {
    // write header and route
    comms_control->tx_control = (comms_tx_control_t) {
        .control_byte = pkt->hdr.control
    };
    comms_control->source_addr = (comms_source_addr_t) {
        .p2p_source_id = reinject_p2p_source_id,
        .route = pkt->hdr.route
    };

    // maybe write payload,
    spinnaker_packet_control_byte_t control =
            (spinnaker_packet_control_byte_t) pkt->hdr.control;
    if (control.payload) {
        comms_control->tx_data = pkt->pld;
    }

    // write key to fire packet,
    comms_control->tx_key = pkt->key;

    // Add to statistics
    reinject_n_reinjected_packets++;
}

//! \brief Called when the router can accept a packet and the reinjection queue
//! is non-empty.
static INT_HANDLER reinjection_ready_to_send_callback(void) {
    // TODO: may need to deal with packet timestamp.

    // check if router not blocked
    if (reinjection_can_send_now()) {
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

//! \brief the callback plugin for handling dropped packets
static INT_HANDLER reinjection_dropped_packet_callback(void) {
    // get packet from router,
    router_packet_header_t hdr = router_control->dump.header;
    uint pld = router_control->dump.payload;
    uint key = router_control->dump.key;

    // clear dump status and interrupt in router,
    router_dump_outputs_t rtr_dump_outputs = router_control->dump.outputs;
    router_dump_status_t rtr_dstat = router_control->dump.status;

    // only reinject if configured

    uint packet_type = ((spinnaker_packet_control_byte_t) hdr.control).type;
    if (((packet_type == SPINNAKER_PACKET_TYPE_MC) && reinject_mc) ||
            ((packet_type == SPINNAKER_PACKET_TYPE_P2P) && reinject_pp) ||
            ((packet_type == SPINNAKER_PACKET_TYPE_NN) && reinject_nn) ||
            ((packet_type == SPINNAKER_PACKET_TYPE_FR) && reinject_fr)) {

        // check for overflow from router
        if (rtr_dstat.overflow) {
            reinject_n_missed_dropped_packets++;
        } else {
            // Note that the processor_dump and link_dump flags are sticky
            // so you can only really count these if you *haven't* missed a
            // dropped packet - hence this being split out

            if (rtr_dump_outputs.processor > 0) {
                // add to the count the number of active bits from this dumped
                // packet, as this indicates how many processors this packet
                // was meant to go to.
                reinject_n_processor_dumped_packets +=
                        __builtin_popcount(rtr_dump_outputs.processor);
                reinject_link_proc_bits |= rtr_dump_outputs.processor << 6;
            }

            if (rtr_dump_outputs.link > 0) {
                // add to the count the number of active bits from this dumped
                // packet, as this indicates how many links this packet was
                // meant to go to.
                reinject_n_link_dumped_packets +=
                        __builtin_popcount(rtr_dump_outputs.link);
                reinject_link_proc_bits |= rtr_dump_outputs.link & 0x3F;
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

//! \brief reads a DSG memory region to set packet types for reinjection
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
            "[INFO] Setting reinject mc to %d\n[INFO] Setting reinject pp to %d\n"
            "[INFO] Setting reinject fr to %d\n[INFO] Setting reinject nn to %d\n",
            reinject_mc, reinject_pp, reinject_fr, reinject_nn);

    // set the reinjection mc api
    initialise_reinjection_mc_api(config->reinjection_base_mc_key);

}

//! \brief Set the wait1 router timeout.
//! \param[in] payload: The encoded value to set. Must be in legal range.
static inline void reinjection_set_wait1_timeout(uint payload) {
    router_control->control.begin_emergency_wait_time = payload;
    prov->n_router_changes++;
}

//! \brief Set the wait2 router timeout.
//! \param[in] payload: The encoded value to set. Must be in legal range.
static inline void reinjection_set_wait2_timeout(uint payload) {
    router_control->control.drop_wait_time = payload;
    prov->n_router_changes++;
}

//! \brief Set the router wait1 timeout.
//!
//! Delegates to reinjection_set_timeout()
//!
//! \param[in,out] msg: The message requesting the change. Will be updated with
//! response
//! \return The payload size of the response message.
static inline int reinjection_set_timeout_sdp(sdp_msg_t *msg) {
#ifdef DEBUG_REINJECTOR
    io_printf(IO_BUF, "[DEBUG] setting router timeouts via sdp\n");
#endif
    if (msg->arg1 > ROUTER_TIMEOUT_MAX) {
        msg->cmd_rc = RC_ARG;
        return 0;
    }

    router_control->control.begin_emergency_wait_time = msg->arg1;
    prov->n_router_changes++;

    // set SCP command to OK, as successfully completed
    msg->cmd_rc = RC_OK;
    return 0;
}

//! \brief Set the router wait2 timeout.
//!
//! Delegates to reinjection_set_emergency_timeout()
//!
//! \param[in,out] msg: The message requesting the change. Will be updated with
//! response
//! \return The payload size of the response message.
static inline int reinjection_set_emergency_timeout_sdp(sdp_msg_t *msg) {
#ifdef DEBUG_REINJECTOR
    io_printf(IO_BUF, "[DEBUG] setting router emergency timeouts via sdp\n");
#endif
    if (msg->arg1 > ROUTER_TIMEOUT_MAX) {
        msg->cmd_rc = RC_ARG;
        return 0;
    }

    router_control->control.drop_wait_time = msg->arg1;
    prov->n_router_changes++;

    // set SCP command to OK, as successfully completed
    msg->cmd_rc = RC_OK;
    return 0;
}

//! \brief Set the re-injection options.
//! \param[in,out] msg: The message requesting the change. Will be updated with
//! response
//! \return The payload size of the response message.
static inline int reinjection_set_packet_types(sdp_msg_t *msg) {
    reinject_mc = msg->arg1;
    reinject_pp = msg->arg2;
    reinject_fr = msg->arg3;
    reinject_nn = msg->data[0];
    prov->n_router_changes++;

    io_printf(IO_BUF,
            "[INFO] Setting reinject mc to %d\n[INFO] Setting reinject pp to %d\n"
            "[INFO] Setting reinject fr to %d\n[INFO] Setting reinject nn to %d\n",
            reinject_mc, reinject_pp, reinject_fr, reinject_nn);

    // set SCP command to OK, as successfully completed
    msg->cmd_rc = RC_OK;
    return 0;
}

//! \brief Get the status and put it in the packet
//! \param[in,out] msg: The message requesting the change. Will be updated with
//! response
//! \return The payload size of the response message.
static inline int reinjection_get_status(sdp_msg_t *msg) {
    reinjector_status_response_packet_t *data =
            (reinjector_status_response_packet_t *) &msg->arg1;

    // Put the router timeouts in the packet
    router_control_t control = router_control->control;
    data->router_timeout = control.begin_emergency_wait_time;
    data->router_emergency_timeout = control.drop_wait_time;

    // Put the statistics in the packet
    data->n_dropped_packets = reinject_n_dropped_packets;
    data->n_missed_dropped_packets = reinject_n_missed_dropped_packets;
    data->n_dropped_packets_overflows = reinject_n_dropped_packet_overflows;
    data->n_reinjected_packets = reinject_n_reinjected_packets;
    data->n_link_dumped_packets = reinject_n_link_dumped_packets;
    data->n_processor_dumped_packets = reinject_n_processor_dumped_packets;
    data->link_proc_bits = reinject_link_proc_bits;

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
//! \param[in,out] msg: The message requesting the change. Will be updated with
//! response
//! \return The payload size of the response message.
static inline int reinjection_reset_counters(sdp_msg_t *msg) {
    reinject_n_dropped_packets = 0;
    reinject_n_missed_dropped_packets = 0;
    reinject_n_dropped_packet_overflows = 0;
    reinject_n_reinjected_packets = 0;
    reinject_n_link_dumped_packets = 0;
    reinject_n_processor_dumped_packets = 0;
    reinject_link_proc_bits = 0;

    // set SCP command to OK, as successfully completed
    msg->cmd_rc = RC_OK;
    return 0;
}

//! \brief Stop the reinjector.
//! \param[in,out] msg: The message requesting the change. Will be updated with
//! response
//! \return The payload size of the response message.
static inline int reinjection_exit(sdp_msg_t *msg) {
    vic_control->int_disable = (vic_mask_t) {
        .timer1 = true,
        .router_dump = true
    };
    reinjection_disable_comms_interrupt();
    vic_control->int_select = (vic_mask_t) {
        // Also all the rest are not FIQ
        .router_dump = false
    };
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
//! \param[in,out] msg: The message requesting the change. Will be updated with
//! response
//! \return The payload size of the response message.
static inline int reinjection_clear_message(sdp_msg_t *msg) {
    reinjection_clear();
    prov->n_router_changes++;
    // set SCP command to OK, as successfully completed
    msg->cmd_rc = RC_OK;
    return 0;
}

//! \brief handles the commands for the reinjector code.
//! \param[in,out] msg: The message with the command. Will be updated with
//! response.
//! \return the length of extra data put into the message for return
static uint reinjection_sdp_command(sdp_msg_t *msg) {
    switch (msg->cmd_rc) {
#ifdef DEBUG_REINJECTOR
    io_printf(IO_BUF, "[DEBUG] seq %d\n", msg->seq);
#endif
    case CMD_DPRI_SET_ROUTER_TIMEOUT:
#ifdef DEBUG_REINJECTOR
        io_printf(IO_BUF, "[DEBUG] router timeout\n");
#endif
        return reinjection_set_timeout_sdp(msg);
    case CMD_DPRI_SET_ROUTER_EMERGENCY_TIMEOUT:
#ifdef DEBUG_REINJECTOR
        io_printf(IO_BUF, "[DEBUG] router emergency timeout\n");
#endif
        return reinjection_set_emergency_timeout_sdp(msg);
    case CMD_DPRI_SET_PACKET_TYPES:
#ifdef DEBUG_REINJECTOR
        io_printf(IO_BUF, "[DEBUG] router set packet type\n");
#endif
        return reinjection_set_packet_types(msg);
    case CMD_DPRI_GET_STATUS:
#ifdef DEBUG_REINJECTOR
        io_printf(IO_BUF, "[DEBUG] router get status\n");
#endif
        return reinjection_get_status(msg);
    case CMD_DPRI_RESET_COUNTERS:
#ifdef DEBUG_REINJECTOR
        io_printf(IO_BUF, "[DEBUG] router reset\n");
#endif
        return reinjection_reset_counters(msg);
    case CMD_DPRI_EXIT:
#ifdef DEBUG_REINJECTOR
        io_printf(IO_BUF, "[DEBUG] router exit\n");
#endif
        return reinjection_exit(msg);
    case CMD_DPRI_CLEAR:
#ifdef DEBUG_REINJECTOR
        io_printf(IO_BUF, "[DEBUG] router clear\n");
#endif
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
    timer1_control->control = (timer_control_t) {
        .enable = false,
        .interrupt_enable = false
    };
    timer1_control->interrupt_clear = true;

    // Set the timer times
    timer1_control->load_value = sv->cpu_clk * TICK_PERIOD;
    timer1_control->background_load_value = sv->cpu_clk * TICK_PERIOD;
}

//! \brief Store this chip's p2p address for future use.
static void reinjection_configure_comms_controller(void) {
    // remember SAR register contents (p2p source ID)
    reinject_p2p_source_id = comms_control->source_addr.p2p_source_id;
}

//! \brief sets up SARK and router to have a interrupt when a packet is dropped
static void reinjection_configure_router(void) {
    // re-configure wait values in router
    router_control_t control = router_control->control;
    control.begin_emergency_wait_time = ROUTER_INITIAL_TIMEOUT;
    control.drop_wait_time = 0;
    router_control->control = control;

    // clear router interrupts,
    (void) router_control->status;

    // clear router dump status,
    (void) router_control->dump.status;

    // clear router error status,
    (void) router_control->error.status;

    // and enable router interrupts when dumping packets, and count errors
    control.dump_interrupt_enable = true;
    control.count_framing_errors = true;
    control.count_parity_errors = true;
    control.count_timestamp_errors = true;
    router_control->control = control;
}

//-----------------------------------------------------------------------------
// data in speed up main functions
//-----------------------------------------------------------------------------

//! Clears all (non-SARK/SCAMP) entries from the router.
static void data_in_clear_router(void) {
    rtr_entry_t router_entry;

    // clear the currently loaded routing table entries
    for (uint entry_id = N_BASIC_SYSTEM_ROUTER_ENTRIES;
            entry_id < N_ROUTER_ENTRIES; entry_id++) {
        if (rtr_mc_get(entry_id, &router_entry) &&
                router_entry.key != INVALID_ROUTER_ENTRY_KEY &&
                router_entry.mask != INVALID_ROUTER_ENTRY_MASK) {
            rtr_free(entry_id, 1);
        }
    }
#ifdef DEBUG_DATA_IN
    io_printf(IO_BUF, "[DEBUG] max free block is %d\n", rtr_alloc_max());
#endif
}

//! Resets the state due to reaching the end of a data stream
static inline void data_in_process_boundary(void) {
    if (data_in_write_address) {
#ifdef DEBUG_DATA_IN
        io_printf(IO_BUF, "[DEBUG] Wrote %u words\n",
                data_in_write_address - data_in_first_write_address);
#endif
        data_in_write_address = NULL;
    }
    data_in_first_write_address = NULL;
}

//! \brief Sets the next location to write data at
//! \param[in] data: The address to write at
static inline void data_in_process_address(uint data) {
    if (data_in_write_address) {
        data_in_process_boundary();
    }
#ifdef DEBUG_DATA_IN
    io_printf(IO_BUF, "[DEBUG] Setting write address to 0x%08x\n", data);
#endif
    data_in_first_write_address = data_in_write_address = (address_t) data;
}

//! \brief Writes a word in a stream and advances the write pointer.
//! \param[in] data: The word to write
static inline void data_in_process_data(uint data) {
    // data keys require writing to next point in sdram

    if (data_in_write_address == NULL) {
        io_printf(IO_BUF, "[ERROR] Write address not set when write data received!\n");
        rt_error(RTE_SWERR);
    }
    *data_in_write_address = data;
    data_in_write_address++;
}

//! \brief Process a multicast packet with payload.
//!
//! Shared between the reinjection and data in code paths. Calls one of:
//!
//! * reinjection_set_timeout()
//! * reinjection_set_emergency_timeout()
//! * reinjection_clear()
//! * data_in_process_address()
//! * data_in_process_data()
//! * data_in_process_boundary()
static INT_HANDLER process_mc_payload_packet(void) {
    // get data from comm controller
    uint data = comms_control->rx_data;
    uint key = comms_control->rx_key;

    if (key == reinject_timeout_mc_key) {
        reinjection_set_wait1_timeout(data);
    } else if (key == reinject_emergency_timeout_mc_key) {
        reinjection_set_wait2_timeout(data);
    } else if (key == reinject_clear_mc_key) {
        reinjection_clear();
    } else if (key == data_in_address_key) {
        data_in_process_address(data);
    } else if (key == data_in_data_key) {
        data_in_process_data(data);
    } else if (key == data_in_boundary_key) {
        prov->n_in_streams++;
        data_in_process_boundary();
    } else {
        io_printf(IO_BUF,
                "[WARNING] failed to recognise multicast packet key 0x%08x\n",
                key);
    }

    // and tell VIC we're done
    vic_interrupt_done();
}

//! \brief Writes router entries to the router.
//! \param[in] sdram_address: the sdram address where the router entries reside
//! \param[in] n_entries: how many router entries to read in
static void data_in_load_router(
        router_entry_t *sdram_address, uint n_entries) {
#ifdef DEBUG_DATA_IN
    io_printf(IO_BUF, "[DEBUG] Writing %u router entries\n", n_entries);
#endif
    if (n_entries == 0) {
        return;
    }
    uint start_entry_id = rtr_alloc_id(n_entries, sark_app_id());
    if (start_entry_id == 0) {
        io_printf(IO_BUF,
                "[ERROR] Received error with requesting %u router entries.\n",
                n_entries);
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
                    "[DEBUG] Setting key %08x, mask %08x, route %08x for entry %u\n",
                    sdram_address[idx].key, sdram_address[idx].mask,
                    sdram_address[idx].route, idx + start_entry_id);
#endif
            // try setting the valid router entry
            if (rtr_mc_set(idx + start_entry_id, sdram_address[idx].key,
                    sdram_address[idx].mask, sdram_address[idx].route) != 1) {
                io_printf(IO_BUF, "[WARNING] failed to write router entry %d, "
                        "with key %08x, mask %08x, route %08x\n",
                        idx + start_entry_id, sdram_address[idx].key,
                        sdram_address[idx].mask, sdram_address[idx].route);
            }
        }
    }
    prov->n_router_changes++;
}

//! \brief reads in routers entries and places in application sdram location
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

//! \brief Sets up system routes on router.
//!
//! Required by the data in speed up functionality.
//! \param[in] items: The collection of system routes to load.
static void data_in_speed_up_load_in_system_tables(
        data_in_data_items_t *items) {
    // read in router table into app store in sdram (in case its changed
    // since last time)
    data_in_save_router();

    // clear the currently loaded routing table entries to avoid conflicts
    data_in_clear_router();

    // read in and load routing table entries
#ifdef DEBUG_DATA_IN
    io_printf(IO_BUF, "[INFO] Loading system routes\n");
#endif
    data_in_load_router(
            items->system_router_entries, items->n_system_router_entries);
}

//! \brief Sets up application routes on router.
//!
//! Required by data in speed up functionality.
static void data_in_speed_up_load_in_application_routes(void) {
    // clear the currently loaded routing table entries
    data_in_clear_router();

    // load app router entries from sdram
#ifdef DEBUG_DATA_IN
    io_printf(IO_BUF, "[INFO] Loading application routes\n");
#endif
    data_in_load_router(
            data_in_saved_application_router_table,
            data_in_application_table_n_valid_entries);
}

//! \brief The handler for all control messages coming in for data in speed up
//! functionality.
//! \param[in,out] msg: the SDP message (without SCP header); will be updated
//! with response
//! \return complete code if successful
static uint data_in_speed_up_command(sdp_msg_t *msg) {
    switch (msg->cmd_rc) {
    case SDP_COMMAND_FOR_SAVING_APPLICATION_MC_ROUTING:
#ifdef DEBUG_DATA_IN
        io_printf(IO_BUF, "[INFO] Saving application router entries from router\n");
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
#ifdef DEBUG_DATA_IN
            io_printf(IO_BUF,
                    "[WARNING] Already loaded system router; ignoring but replying\n");
#endif
            msg->cmd_rc = RC_OK;
            break;
        }
        data_in_speed_up_load_in_system_tables(
                dse_block(CONFIG_DATA_SPEED_UP_IN));
        msg->cmd_rc = RC_OK;
        data_in_last_table_load_was_system = true;
        break;
    default:
        io_printf(IO_BUF,
                "[WARNING] Received unknown SDP packet in data in speed up port"
                " with command id %d\n", msg->cmd_rc);
        msg->cmd_rc = RC_ARG;
    }
    return 0;
}

//-----------------------------------------------------------------------------
// data speed up out main functions
//-----------------------------------------------------------------------------

//! \brief Sends a fixed route packet with payload.
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
    while (!comms_control->tx_control.not_full) {
        // Empty body; CC array is volatile
    }
    const spinnaker_packet_control_byte_t fixed_route_with_payload = {
        .payload = true,
        .type = SPINNAKER_PACKET_TYPE_FR
    };
    comms_control->tx_control = (comms_tx_control_t) {
        .control_byte = fixed_route_with_payload.value
    };
    comms_control->tx_data = data;
    comms_control->tx_key = key;
}

//! \brief takes a DMA'ed block and transmits its contents as fixed route
//! packets to the packet gatherer.
//! \param[in] current_dma_pointer: the DMA pointer for the 2 buffers
//! \param[in] n_elements_to_send: the number of multicast packets to send
//! \param[in] first_packet_key: the first key to transmit with.
//! \param[in] second_packet_key: the second key to transmit with; all
//! subsequent packets use the default key.
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
//!
//! This is a basic operation. It does not include any safeguards.
//!
//! \param[in] dma_tag: A label for what is being read. Should be one of the
//! values in dma_tags_for_data_speed_up
//! \param[in] source: Where in SDRAM to read from.
//! \param[in] destination: Where in DTCM to write to.
//! \param[in] n_words: The number of _words_ to transfer. Can be up to 32k
//! _words_.
static inline void data_out_start_dma_read(
        uint32_t dma_tag, void *source, void *destination, uint n_words) {
    data_out_dma_port_last_used = dma_tag;
    dma_control->sdram_address = source;
    dma_control->tcm_address = destination;
    dma_control->description = (dma_description_t) {
        .width = DMA_TRANSFER_DOUBLE_WORD,
        .burst = DMA_BURST_SIZE,
        .direction = DMA_DIRECTION_READ,
        .length_words = n_words
    };
}

//! \brief sets off a DMA reading a block of SDRAM in preparation for sending to
//! the packet gatherer
//! \param[in] dma_tag: the DMA tag associated with this read.
//!            transmission or retransmission
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

//! \brief Sends the end flag to the packet gatherer.
static void data_out_send_end_flag(void) {
    send_fixed_route_packet(data_out_end_flag_key, END_FLAG);
}

//! \brief DMA complete callback for reading for original transmission
//!
//! Uses a pair of buffers in DTCM so data can be read in from SDRAM while the
//! previous is being transferred over the network.
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
#ifdef DEBUG_DATA_OUT
        if (data[i] > data_out_max_seq_num) {
            io_printf(IO_BUF, "[WARNING] Storing bad seq num. %d %d\n",
                    data[i], data_out_max_seq_num);
        }
#endif
    }
    data_out_n_missing_seq_nums_in_sdram += length - start_offset;
}

//! \brief Store sequence numbers into SDRAM.
//!
//! Acts as a memory management front end to
//! data_out_write_missing_seq_nums_into_sdram()
//!
//! \param[in] data: the message data to read into SDRAM
//! \param[in] length: how much data to read
//! \param[in] first: if first packet about missing sequence numbers. If so
//! there is different behaviour
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
                        "[ERROR] Can't allocate SDRAM for missing seq nums\n");
                rt_error(RTE_SWERR);
            }
#ifdef DEBUG_DATA_OUT
            io_printf(IO_BUF, "[DEBUG] Activate bacon protocol!\n");
#endif
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
#ifdef DEBUG_DATA_OUT
    } else {
        io_printf(IO_BUF, "[WARNING] Unable to save missing sequence number\n");
#endif
    }
}

//! \brief sets off a DMA for retransmission stuff
static void data_out_retransmission_dma_read(void) {
    // locate where we are in SDRAM
    address_t data_sdram_position =
            &data_out_missing_seq_num_sdram_address[data_out_position_for_retransmission];

    // set off DMA
    data_out_start_dma_read(DMA_TAG_READ_FOR_RETRANSMISSION,
            data_sdram_position, data_out_retransmit_seq_nums,
            ITEMS_PER_DATA_PACKET);
}

//! \brief reads in missing sequence numbers and sets off the reading of
//! SDRAM for the equivalent data
//!
//! Callback associated with ::DMA_TAG_READ_FOR_RETRANSMISSION
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
        if (data_out_missing_seq_num_sdram_address != NULL) {
            sdram_free(data_out_missing_seq_num_sdram_address);
            data_out_missing_seq_num_sdram_address = NULL;
        }
        data_out_read_data_position = 0;
        data_out_position_for_retransmission = 0;
        data_out_n_missing_seq_nums_in_sdram = 0;
    }
}

//! \brief DMA complete callback for have read missing sequence number data.
//!
//! Callback associated with ::DMA_TAG_RETRANSMISSION_READING
static void data_out_dma_complete_reading_retransmission_data(void) {
    // set sequence number as first element
    data_out_data_to_transmit[data_out_transmit_dma_pointer][0] =
            data_out_missing_seq_num_being_processed;
#ifdef DEBUG_DATA_OUT
    if (data_out_missing_seq_num_being_processed > data_out_max_seq_num) {
        io_printf(IO_BUF,
                "[WARNING] Got some bad seq num here; max is %d, got %d\n",
                data_out_max_seq_num, data_out_missing_seq_num_being_processed);
    }
#endif

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
#ifdef DEBUG_DATA_OUT
    io_printf(IO_BUF, "[INFO] Need to figure what to do here\n");
#endif
}

//! \brief the handler for all messages coming in for data speed up
//! functionality.
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
                    "[WARNING] received start message with unexpected "
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
        prov->n_out_streams++;
        return;
    }
    case SDP_CMD_START_OF_MISSING_SDP_PACKETS:
        if (message->transaction_id != data_out_transaction_id) {
            io_printf(IO_BUF,
                    "[WARNING] received data from a different transaction for "
                    "start of missing. expected %d got %d\n",
                    data_out_transaction_id, message->transaction_id);
            return;
        }

        // if already in a retransmission phase, don't process as normal
        if (data_out_n_missing_seq_packets != 0) {
#ifdef DEBUG_DATA_OUT
            io_printf(IO_BUF, "[INFO] forcing start of retransmission packet\n");
#endif
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
                    "[WARNING] received data from different transaction for "
                    "more missing; expected %d, got %d\n",
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
                    "[WARNING] received data from different transaction for "
                    "clear; expected %d, got %d\n",
                    data_out_transaction_id, message->transaction_id);
            return;
        }
#ifdef DEBUG_DATA_OUT
        io_printf(IO_BUF, "[INFO] data out clear\n");
#endif
        data_out_stop = true;
        break;
    default:
        io_printf(IO_BUF, "[WARNING] Received unknown SDP packet: %d\n",
                message->command);
    }
}

//! \brief The handler for all DMAs complete.
//!
//! Depending on the dma_tag used with data_out_start_dma_read(), calls one of:
//! * data_out_dma_complete_reading_for_original_transmission()
//! * data_out_dma_complete_read_missing_seqeuence_nums()
//! * data_out_dma_complete_reading_retransmission_data()
//! * data_out_dma_complete_writing_missing_seq_to_sdram() (tag unused?)
static INT_HANDLER data_out_dma_complete(void) {
    // reset the interrupt.
    dma_control->control = (dma_control_t) {
        .clear_done_int = true
    };
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
            io_printf(IO_BUF, "[ERROR] Invalid DMA callback port: %d\n",
                    data_out_dma_port_last_used);
            rt_error(RTE_SWERR);
        }
    }
    // and tell VIC we're done
    vic_interrupt_done();
}

//! \brief the handler for DMA errors
static INT_HANDLER data_out_dma_error(void) {
    io_printf(IO_BUF, "[WARNING] DMA failed: 0x%08x\n", dma_control->status);
    dma_control->control = (dma_control_t) {
        // Clear the error
        .restart = true
    };
    vic_interrupt_done();
    rt_error(RTE_DABT);
}

//! \brief the handler for DMA timeouts (hopefully unlikely...)
static INT_HANDLER data_out_dma_timeout(void) {
    io_printf(IO_BUF, "[WARNING] DMA timeout: 0x%08x\n", dma_control->status);
    dma_control->control = (dma_control_t) {
        .clear_timeout_int = true
    };
    vic_interrupt_done();
}

//-----------------------------------------------------------------------------
// common code
//-----------------------------------------------------------------------------

void __real_sark_int(void *pc);
//! Check for extra messages added by this core.
// This function is why this code *can't* use Spin1API.
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
    system_control->clear_cpu_irq = (sc_magic_proc_map_t) {
        .security_code = SYSTEM_CONTROLLER_MAGIC_NUMBER,
        .select = 1 << sark.phys_cpu,
    };
    if (msg == NULL) {
        return;
    }

    switch ((msg->dest_port & PORT_MASK) >> PORT_SHIFT) {
    case REINJECTION_PORT:
        reflect_sdp_message(msg, reinjection_sdp_command(msg));
        while (!sark_msg_send(msg, 10)) {
#ifdef DEBUG_REINJECTOR
            io_printf(IO_BUF, "[DEBUG] timeout when sending reinjection reply\n");
#endif
        }
        prov->n_sdp_packets++;
        break;
    case DATA_SPEED_UP_OUT_PORT:
        // These are all one-way messages; replies are out of band
        data_out_speed_up_command((sdp_msg_pure_data *) msg);
        prov->n_sdp_packets++;
        break;
    case DATA_SPEED_UP_IN_PORT:
        reflect_sdp_message(msg, data_in_speed_up_command(msg));
        while (!sark_msg_send(msg, 10)) {
#ifdef DEBUG_DATA_IN
            io_printf(IO_BUF, "[DEBUG] timeout when sending speedup ctl reply\n");
#endif
        }
        prov->n_sdp_packets++;
        break;
    default:
        io_printf(IO_BUF, "[WARNING] unexpected port %d\n",
                (msg->dest_port & PORT_MASK) >> PORT_SHIFT);
        io_printf(IO_BUF,
                "[INFO] from:%04x:%02x to:%04x:%02x cmd:%04x len:%d iam:%04x\n",
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

//! \brief Sets up data and callbacks required by the reinjection system.
static void reinjection_initialise(void) {
    // set up config region
    // Get the address this core's DTCM data starts at from SRAM
    reinjection_read_packet_types(dse_block(CONFIG_REINJECTION));

    // Setup the CPU interrupt for WDOG
    vic_interrupt_control[sark_vec->sark_slot] = (vic_vector_control_t) {
        .enable = false
    };
    set_vic_callback(CPU_SLOT, CPU_INT, sark_int_han);

    // Setup the communications controller interrupt
    set_vic_callback(CC_SLOT, CC_TNF_INT, reinjection_ready_to_send_callback);

    // Setup the timer interrupt
    set_vic_callback(TIMER_SLOT, TIMER1_INT, reinjection_timer_callback);

    // Setup the router interrupt as a fast interrupt
    sark_vec->fiq_vec = reinjection_dropped_packet_callback;
    vic_control->int_select = (vic_mask_t) {
        .router_dump = true
    };
}

//! \brief Sets up data and callbacks required by the data speed up system.
static void data_out_initialise(void) {
    data_speed_out_config_t *config = dse_block(CONFIG_DATA_SPEED_UP_OUT);
    data_out_basic_data_key = config->my_key;
    data_out_new_sequence_key = config->new_seq_key;
    data_out_first_data_key = config->first_data_key;
    data_out_transaction_id_key = config->transaction_id_key;
    data_out_end_flag_key = config->end_flag_key;

#ifdef DEBUG_DATA_OUT
    io_printf(IO_BUF,
            "[INFO] new seq key = %d, first data key = %d, transaction id key = %d, "
            "end flag key = %d, basic_data_key = %d\n",
            data_out_new_sequence_key, data_out_first_data_key, data_out_transaction_id_key,
            data_out_end_flag_key, data_out_basic_data_key);
#endif

    // Various DMA callbacks
    set_vic_callback(DMA_SLOT, DMA_DONE_INT, data_out_dma_complete);
    set_vic_callback(DMA_ERROR_SLOT, DMA_ERR_INT, data_out_dma_error);
    set_vic_callback(DMA_TIMEOUT_SLOT, DMA_TO_INT, data_out_dma_timeout);

    // configuration for the DMA's by the speed data loader
    dma_control->control = (dma_control_t) {
        // Abort pending and active transfers
        .uncommit = true,
        .abort = true,
        .restart = true,
        .clear_done_int = true,
        .clear_timeout_int = true,
        .clear_write_buffer_int = true
    };
    dma_control->control = (dma_control_t) {
        // clear possible transfer done and restart
        .uncommit = true,
        .restart = true,
        .clear_done_int = true
    };
    dma_control->global_control = (dma_global_control_t) {
        // enable DMA done and error interrupt
        .transfer_done_interrupt = true,
        .transfer2_done_interrupt = true,
        .timeout_interrupt = true,
        .crc_error_interrupt = true,
        .tcm_error_interrupt = true,
        .axi_error_interrupt = true, // SDRAM error
        .user_abort_interrupt = true,
        .soft_reset_interrupt = true,
        .write_buffer_error_interrupt = true
    };
}

//! \brief Sets up data and callback required by the data in speed up system.
static void data_in_initialise(void) {
    data_in_saved_application_router_table = sdram_alloc(
            N_USABLE_ROUTER_ENTRIES * sizeof(router_entry_t));
    if (data_in_saved_application_router_table == NULL) {
        io_printf(IO_BUF,
                "[ERROR] failed to allocate SDRAM for application mc router entries\n");
        rt_error(RTE_SWERR);
    }

    data_in_data_items_t *items = dse_block(CONFIG_DATA_SPEED_UP_IN);

    data_in_address_key = items->address_mc_key;
    data_in_data_key = items->data_mc_key;
    data_in_boundary_key = items->boundary_mc_key;
    // Save the current (application?) state
    data_in_save_router();

    // load user 1 in case this is a consecutive load
    publish_transaction_id(data_out_transaction_id);

    // set up mc interrupts to deal with data writing
    set_vic_callback(MC_PAYLOAD_SLOT, CC_MC_INT, process_mc_payload_packet);
}

//! Set up where we collect provenance
static void provenance_initialise(void) {
    prov = dse_block(PROVENANCE_REGION);
    prov->n_sdp_packets = 0;
    prov->n_in_streams = 0;
    prov->n_out_streams = 0;
    prov->n_router_changes = 0;
}

//-----------------------------------------------------------------------------
//! main entry point
//-----------------------------------------------------------------------------
void c_main(void) {
    sark_cpu_state(CPU_STATE_RUN);

    dse_regions = data_specification_get_data_address();
    if (!data_specification_read_header(dse_regions)) {
        rt_error(RTE_SWERR);
    }

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
    const vic_mask_t int_select = {
        .timer1 = true,
        .router_dump = true,
        .dma_done = true,
        .dma_error = true,
        .dma_timeout = true,
        .cc_rx_mc = true,
    };
    vic_control->int_disable = int_select;
    reinjection_disable_comms_interrupt();

    // set up provenance area
    provenance_initialise();

    // set up reinjection functionality
    reinjection_initialise();

    // set up data speed up functionality
    data_out_initialise();
    data_in_initialise();

    // Enable interrupts and timer
    vic_control->int_enable = int_select;
    timer1_control->control = (timer_control_t) {
        .size = 1,
        .interrupt_enable = true,
        .periodic_mode = true,
        .enable = true
    };

    io_printf(IO_BUF, "[INFO] extra monitor initialisation complete\n");

    // Run until told to exit
    while (reinject_run) {
        wait_for_interrupt();
    }
}
// ------------------------------------------------------------------------

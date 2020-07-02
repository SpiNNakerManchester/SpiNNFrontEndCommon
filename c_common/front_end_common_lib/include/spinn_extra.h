/*
 * Copyright (c) 2019-2020 The University of Manchester
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

// ------------------------------------------------------------------------
//! \file
//! \brief Extra definitions of things on SpiNNaker chips that aren't already
//!     mentioned in spinnaker.h, or where the description is miserable.
//!
//! This models data structures described in the [SpiNNaker datasheet][sheet].
//! Before using anything in this file, you should read the relevant section of
//! the datasheet so as you can understand the correct usage patterns for the
//! underlying hardware.
//!
//! [sheet]: [https://spinnakermanchester.github.io/docs/SpiNN2DataShtV202.pdf]
//!
//! \nosubgrouping
// ------------------------------------------------------------------------

#ifndef __SPINN_EXTRA_H__
#define __SPINN_EXTRA_H__

#include <spinnaker.h>
#include <stdbool.h>
#if defined(__GNUC__) && __GNUC__ < 6
// This particular warning (included in -Wextra) is retarded wrong for client
// code of this file. Only really a problem on Travis.
#pragma GCC diagnostic ignored "-Wmissing-field-initializers"
#endif // __GNUC__

//! \brief Generates valid code if the named type is one word long, and invalid
//!     code otherwise.
//! \details It would be simpler if we used `static_assert`, but Eclipse
//!     seems to hate that.
//! \param type_ident: The name of the type that we are asserting is one word
//!     long.
#define ASSERT_WORD_SIZED(type_ident) \
    struct __static_word_sized_assert_ ## type_ident { \
        char _dummy[2 * (sizeof(type_ident) == sizeof(uint)) - 1]; \
    }

// ---------------------------------------------------------------------
// 1. Chip Organization

// No registers

// ---------------------------------------------------------------------
// 2. System Architecture

// No registers

// ---------------------------------------------------------------------
// 3. ARM968 Processing Subsystem

// No registers

// ---------------------------------------------------------------------
// 4. ARM 968

// No special registers here

// ---------------------------------------------------------------------
//! \name 5. Vectored Interrupt Controller
//! \brief The VIC is used to enable and disable interrupts from various
//!     sources, and to wake the processor from sleep mode when required.
//! \{

//! The type of an interrupt handler
typedef void (*vic_interrupt_handler_t) (void);

//! \brief Mask describing interrupts that can be selected.
typedef union {
    //! See datasheet section **5.4 Interrupt sources**
    struct {
        uint watchdog : 1;          //!< Watchdog timer interrupt
        uint software : 1;          //!< Local software interrupt generation
        uint comm_rx : 1;           //!< Debug communications receiver interrupt
        uint comm_tx : 1;           //!< Debug communications transmitter interrupt
        uint timer1 : 1;            //!< Counter/timer interrupt 1
        uint timer2 : 1;            //!< Counter/timer interrupt 2
        uint cc_rx_ready : 1;       //!< Comms controller packet received
        uint cc_rx_parity_error : 1;    //!< Comms controller received packet parity error
        uint cc_rx_framing_error : 1;   //!< Comms controller received packet framing error
        uint cc_tx_full : 1;        //!< Comms controller transmit buffer full
        uint cc_tx_overflow : 1;    //!< Comms controller transmit buffer overflow
        uint cc_tx_empty : 1;       //!< Comms controller transmit buffer empty
        uint dma_done : 1;          //!< DMA controller transfer complete
        uint dma_error : 1;         //!< DMA controller error
        uint dma_timeout : 1;       //!< DMA controller transfer timed out
        uint router_diagnostic : 1; //!< Router diagnostic counter event has occurred
        uint router_dump : 1;       //!< Router packet dumped - indicates failed delivery
        uint router_error : 1;      //!< Router error - packet parity, framing, or time stamp error
        uint cpu : 1;               //!< System Controller interrupt bit set for this processor
        uint ethernet_tx : 1;       //!< Ethernet transmit frame interrupt
        uint ethernet_rx : 1;       //!< Ethernet receive frame interrupt
        uint ethernet_phy : 1;      //!< Ethernet PHY/external interrupt
        uint slow_clock : 1;        //!< System-wide slow (nominally 32 KHz) timer interrupt
        uint cc_tx_not_full : 1;    //!< Comms controller can accept new Tx packet
        uint cc_rx_mc : 1;          //!< Comms controller multicast packet received
        uint cc_rx_p2p : 1;         //!< Comms controller point-to-point packet received
        uint cc_rx_nn : 1;          //!< Comms controller nearest neighbour packet received
        uint cc_rx_fr : 1;          //!< Comms controller fixed route packet received
        uint int0 : 1;              //!< External interrupt request 0
        uint int1 : 1;              //!< External interrupt request 1
        uint gpio8 : 1;             //!< Signal on GPIO[8]
        uint gpio9 : 1;             //!< Signal on GPIO[9]
    };
    uint value;
} vic_mask_t;

//! VIC registers
typedef struct {
    const vic_mask_t irq_status;    //!< IRQ status register
    const vic_mask_t fiq_status;    //!< FIQ status register
    const vic_mask_t raw_status;    //!< raw interrupt status register
    vic_mask_t int_select;          //!< interrupt select register
    vic_mask_t int_enable;          //!< interrupt enable set register
    vic_mask_t int_disable;         //!< interrupt enable clear register
    vic_mask_t soft_int_enable;     //!< soft interrupt set register
    vic_mask_t soft_int_disable;    //!< soft interrupt clear register
    bool protection;                //!< protection register
    const uint _padding[3];
    vic_interrupt_handler_t vector_address;         //!< vector address register
    vic_interrupt_handler_t default_vector_address; //!< default vector address register
} vic_control_t;

//! VIC individual vector control
typedef struct {
    uint source : 5;                //!< interrupt source
    uint enable : 1;                //!< interrupt enable
    uint : 26;
} vic_vector_control_t;

ASSERT_WORD_SIZED(vic_mask_t);
ASSERT_WORD_SIZED(vic_interrupt_handler_t);
ASSERT_WORD_SIZED(vic_vector_control_t);

//! VIC registers
static volatile vic_control_t *const vic_control =
        (vic_control_t *) VIC_BASE_UNBUF; // NB unbuffered!
//! VIC interrupt handlers. Array of 32 elements.
static volatile vic_interrupt_handler_t *const vic_interrupt_vector =
        (vic_interrupt_handler_t *) (VIC_BASE + 0x100);
//! VIC individual interrupt control. Array of 32 elements.
static volatile vic_vector_control_t *const vic_interrupt_control =
        (vic_vector_control_t *) (VIC_BASE + 0x200);

//! \}

// ---------------------------------------------------------------------
//! \name 6. Counter/Timer
//! \brief Every core has a pair of counters/timers.
//! \{

//! Timer control register
typedef struct {
    uint one_shot : 1;          //!< 0 = wrapping mode, 1 = one shot
    uint size : 1;              //!< 0 = 16 bit, 1 = 32 bit
    uint pre_divide : 2;        //!< divide input clock (see ::timer_pre_divide)
    uint : 1;
    uint interrupt_enable : 1;  //!< enable interrupt (1 = enabled)
    uint periodic_mode : 1;     //!< 0 = free-running; 1 = periodic
    uint enable : 1;            //!< enable counter/timer (1 = enabled)
    uint : 24;
} timer_control_t;

//! Values for ::timer_control_t::pre_divide
enum timer_pre_divide {
    TIMER_PRE_DIVIDE_1 = 0,     //!< Divide by 1
    TIMER_PRE_DIVIDE_16 = 1,    //!< Divide by 16
    TIMER_PRE_DIVIDE_256 = 2    //!< Divide by 256
};

//! Timer interrupt status flag
typedef struct {
    uint status : 1;            //!< The flag bit
    uint : 31;
} timer_interrupt_status_t;

//! Timer controller registers
typedef struct {
    uint load_value;            //!< Load value for Timer
    const uint current_value;   //!< Current value of Timer
    timer_control_t control;    //!< Timer control register
    uint interrupt_clear;       //!< Interrupt clear (any value may be written)
    const timer_interrupt_status_t raw_interrupt_status; //!< Timer raw interrupt status
    const timer_interrupt_status_t masked_interrupt_status; //!< Timer masked interrupt status
    uint background_load_value; //!< Background load value for Timer
    uint _dummy;
} timer_controller_t;

ASSERT_WORD_SIZED(timer_control_t);
ASSERT_WORD_SIZED(timer_interrupt_status_t);

//! Timer 1 control registers
static volatile timer_controller_t *const timer1_control =
        (timer_controller_t *) TIMER1_BASE;
//! Timer 2 control registers
static volatile timer_controller_t *const timer2_control =
        (timer_controller_t *) TIMER2_BASE;

//! \}

// ---------------------------------------------------------------------
//! \name 7. DMA Controller
//! \brief Each ARM968 processing subsystem includes a DMA controller.
//! \details The DMA controller is primarily used for transferring inter-neural
//!     connection data from the SDRAM in large blocks in response to an input
//!     event arriving at a fascicle processor, and for returning updated
//!     connection data during learning. In addition, the DMA controller can
//!     transfer data to/from other targets on the System NoC such as the
//!     System RAM and Boot ROM.
//!
//!     As a secondary function the DMA controller incorporates a ‘Bridge’
//!     across which its host ARM968 has direct read and write access to
//!     System NoC devices, including the SDRAM. The ARM968 can use the
//!     Bridge whether or not DMA transfers are active.
//! \{

//! DMA descriptor
typedef struct {
    uint _zeroes : 2;       //!< Must be zero
    uint length_words : 15; //!< length of the DMA transfer, in words
    uint : 2;
    uint direction : 1;     //!< read from (0) or write to (1) system bus
    uint crc : 1;           //!< check (read) or generate (write) CRC
    uint burst : 3;         //!< burst length = 2<sup>B</sup>&times;Width, B = 0..4 (i.e max 16)
    uint width : 1;         //!< transfer width, see ::dma_transfer_unit_t
    uint privilege : 1;     //!< DMA transfer mode is user (0) or privileged (1)
    uint transfer_id : 6;   //!< software defined transfer ID
} dma_description_t;

//! DMA burst width, see ::dma_description_t::width
enum dma_transfer_unit_t {
    DMA_TRANSFER_WORD,          //!< Transfer in words
    DMA_TRANSFER_DOUBLE_WORD    //!< Transfer in double-words
};

//! DMA control register
typedef struct {
    uint uncommit : 1;      //!< setting this bit uncommits a queued transfer
    uint abort : 1;         //!< end current transfer and discard data
    uint restart : 1;       //!< resume transfer (clears DMA errors)
    uint clear_done_int : 1;            //!< clear Done interrupt request
    uint clear_timeout_int : 1;         //!< clear Timeout interrupt request
    uint clear_write_buffer_int : 1;    //!< clear Write Buffer interrupt request
    uint : 26;
} dma_control_t;

//! DMA status register
typedef struct {
    uint transferring : 1;  //!< DMA transfer in progress
    uint paused : 1;        //!< DMA transfer is PAUSED
    uint queued : 1;        //!< DMA transfer is queued - registers are full
    uint write_buffer_full : 1;     //!< write buffer is full
    uint write_buffer_active : 1;   //!< write buffer is not empty
    uint : 5;
    uint transfer_done : 1; //!< a DMA transfer has completed without error
    uint transfer2_done : 1;        //!< 2nd DMA transfer has completed without error
    uint timeout : 1;       //!< a burst transfer has not completed in time
    uint crc_error : 1;     //!< the calculated and received CRCs differ
    uint tcm_error : 1;     //!< the TCM AHB interface has signalled an error
    uint axi_error : 1;     //!< the AXI interface (SDRAM) has signalled a transfer error
    uint user_abort : 1;    //!< the user has aborted the transfer (via ::dma_control_t::abort)
    uint soft_reset : 1;    //!< a soft reset of the DMA controller has happened
    uint : 2;               // Not allocated
    uint write_buffer_error : 1;    //!< a buffered write transfer has failed
    uint : 3;
    uint processor_id : 8;  //!< hardwired processor ID identifies CPU on chip
} dma_status_t;

//! DMA global control register
typedef struct {
    uint bridge_buffer_enable : 1;  //!< enable Bridge write buffer
    uint : 9;
    uint transfer_done_interrupt : 1;   //!< interrupt if ::dma_status_t::transfer_done set
    uint transfer2_done_interrupt : 1;  //!< interrupt if ::dma_status_t::transfer2_done set
    uint timeout_interrupt : 1;         //!< interrupt if ::dma_status_t::timeout set
    uint crc_error_interrupt : 1;       //!< interrupt if ::dma_status_t::crc_error set
    uint tcm_error_interrupt : 1;       //!< interrupt if ::dma_status_t::tcm_error set
    uint axi_error_interrupt : 1;       //!< interrupt if ::dma_status_t::axi_error set
    uint user_abort_interrupt : 1;      //!< interrupt if ::dma_status_t::user_abort set
    uint soft_reset_interrupt : 1;      //!< interrupt if ::dma_status_t::soft_reset set
    uint : 2;                           // Not allocated
    uint write_buffer_error_interrupt : 1;  //!< interrupt if ::dma_status_t::write_buffer_error set
    uint : 10;
    uint timer : 1;         //!< system-wide slow timer status and clear
} dma_global_control_t;

//! DMA timeout register
typedef struct {
    uint _zeroes : 5;       //!< Must be zero
    uint value : 5;         //!< The timeout
    uint : 22;
} dma_timeout_t;

//! DMA statistics control register
typedef struct {
    uint enable : 1;        //!< Enable collecting DMA statistics
    uint clear : 1;         //!< Clear the statistics registers (if 1)
    uint : 30;
} dma_stats_control_t;

//! DMA controller registers
typedef struct {
    const uint _unused1[1];
    void *sdram_address;            //!< DMA address on the system interface
    void *tcm_address;              //!< DMA address on the TCM interface
    volatile dma_description_t description; //!< DMA transfer description; note that setting this commits a DMA
    volatile dma_control_t control; //!< Control DMA transfer
    const dma_status_t status;      //!< Status of DMA and other transfers
    volatile dma_global_control_t global_control; //!< Control of the DMA device
    const uint crcc;                //!< CRC value calculated by CRC block
    const uint crcr;                //!< CRC value in received block
    dma_timeout_t timeout;          //!< Timeout value
    dma_stats_control_t statistics_control; //!< Statistics counters control
    const uint _unused2[5];
    const uint statistics[8];       //!< Statistics counters
    const uint _unused3[41];
    const void *current_sdram_address;      //!< Active system address
    const void *current_tcm_address;        //!< Active TCM address
    const dma_description_t current_description; //!< Active transfer description
    const uint _unused4[29];
    uint crc_polynomial[32];        //!< CRC polynomial matrix
} dma_t;

ASSERT_WORD_SIZED(dma_description_t);
ASSERT_WORD_SIZED(dma_control_t);
ASSERT_WORD_SIZED(dma_status_t);
ASSERT_WORD_SIZED(dma_global_control_t);
ASSERT_WORD_SIZED(dma_timeout_t);
ASSERT_WORD_SIZED(dma_stats_control_t);

//! DMA control registers
static volatile dma_t *const dma_control = (dma_t *) DMA_BASE;

//! \}

// ---------------------------------------------------------------------
//! \name 8. Communications controller
//! \brief Each processor node on SpiNNaker includes a communications
//!     controller which is responsible for generating and receiving packets
//!     to and from the communications network.
//! \{

//! The control byte of a SpiNNaker packet
typedef union {
    //! Common fields
    struct {
        uchar parity : 1;       //!< Packet parity
        uchar payload : 1;      //!< Payload-word-present flag
        uchar timestamp : 2;    //!< Timestamp (not used for NN packets)
        uchar : 2;
        uchar type : 2;         //!< Should be one of ::spinnaker_packet_type_t
    };
    //! Multicast packet only fields
    struct {
        uchar : 4;
        uchar emergency_routing : 2; //!< Emergency routing control
        uchar : 2;
    } mc;
    //! Peer-to-peer packet only fields
    struct {
        uchar : 4;
        uchar seq_code : 2;     //!< Sequence code
        uchar : 2;
    } p2p;
    //! Nearest-neighbour packet only fields
    struct {
        uchar : 2;
        uchar route : 3;        //!< Routing information
        uchar mem_or_normal : 1; //!< Type indicator
        uchar : 2;
    } nn;
    //! Fixed-route packet only fields
    struct {
        uchar : 4;
        uchar emergency_routing : 2; //!< Emergency routing control
        uchar : 2;
    } fr;
    uchar value;
} spinnaker_packet_control_byte_t;

//! SpiNNaker packet type codes
enum spinnaker_packet_type_t {
    SPINNAKER_PACKET_TYPE_MC = 0,   //!< Multicast packet
    SPINNAKER_PACKET_TYPE_P2P = 1,  //!< Peer-to-peer packet
    SPINNAKER_PACKET_TYPE_NN = 2,   //!< Nearest-neighbour packet
    SPINNAKER_PACKET_TYPE_FR = 3,   //!< Fixed-route packet
};

//! Controls packet transmission
typedef struct {
    uint : 16;
    uint control_byte : 8;      //!< control byte of next sent packet
    uint : 4;
    uint not_full : 1;          //!< Tx buffer not full, so it is safe to send a packet
    uint overrun : 1;           //!< Tx buffer overrun (sticky)
    uint full : 1;              //!< Tx buffer full (sticky)
    uint empty : 1;             //!< Tx buffer empty
} comms_tx_control_t;

//! Indicates packet reception status
typedef struct {
    uint multicast : 1;         //!< error-free multicast packet received
    uint point_to_point : 1;    //!< error-free point-to-point packet received
    uint nearest_neighbour : 1; //!< error-free nearest-neighbour packet received
    uint fixed_route : 1;       //!< error-free fixed-route packet received
    uint : 12;
    uint control_byte : 8;      //!< Control byte of last Rx packet
    uint route : 3;             //!< Rx route field from packet
    uint : 1;
    uint error_free : 1;        //!< Rx packet received without error
    uint framing_error : 1;     //!< Rx packet framing error (sticky)
    uint parity_error : 1;      //!< Rx packet parity error (sticky)
    uint received : 1;          //!< Rx packet received
} comms_rx_status_t;

//! P2P source address
typedef struct {
    uint p2p_source_id : 16;    //!< 16-bit chip source ID for P2P packets
    uint : 8;
    uint route : 3;             //!< Set 'fake' route in packet
    uint : 5;
} comms_source_addr_t;

//! SpiNNaker communications controller registers
typedef struct {
    comms_tx_control_t tx_control; //!< Controls packet transmission
    uint tx_data;               //!< 32-bit data for transmission
    //! Send MC key/P2P dest ID & seq code; writing this commits a send
    uint tx_key;
    comms_rx_status_t rx_status; //!< Indicates packet reception status
    const uint rx_data;         //!< 32-bit received data
    //! Received MC key/P2P source ID & seq code; reading this clears the received packet
    const uint rx_key;
    comms_source_addr_t source_addr; //!< P2P source address
    const uint _test;           //!< Used for test purposes
} comms_ctl_t;

ASSERT_WORD_SIZED(comms_tx_control_t);
ASSERT_WORD_SIZED(comms_rx_status_t);
ASSERT_WORD_SIZED(comms_source_addr_t);

//! Communications controller registers
static volatile comms_ctl_t *const comms_control = (comms_ctl_t *) CC_BASE;

//! \}

// ---------------------------------------------------------------------
// 9. Communications NoC

// No registers

// ---------------------------------------------------------------------
//! \name 10. SpiNNaker Router
//! \brief The Router is responsible for routing all packets that arrive at its
//!     input to one or more of its outputs.
//! \details It is responsible for routing multicast neural event packets,
//!     which it does through an associative multicast router subsystem,
//!     point-to-point packets (for which it uses a look-up table),
//!     nearest-neighbour packets (using a simple algorithmic process),
//!     fixed-route packet routing (defined in a register), default routing
//!     (when a multicast packet does not match any entry in the multicast
//!     router) and emergency routing (when an output link is blocked due to
//!     congestion or hardware failure).
//!
//!     Various error conditions are identified and handled by the Router, for
//!     example packet parity errors, time-out, and output link failure.
//! \{

//! Router control register
typedef struct {
    uint route_packets_enable : 1;      //!< enable packet routing
    uint error_interrupt_enable : 1;    //!< enable error packet interrupt
    uint dump_interrupt_enable : 1;     //!< enable dump packet interrupt
    uint count_timestamp_errors : 1;    //!< enable count of packet time stamp errors
    uint count_framing_errors : 1;      //!< enable count of packet framing errors
    uint count_parity_errors : 1;       //!< enable count of packet parity errors
    uint time_phase : 2;                //!< time phase (c.f. packet time stamps)
    uint monitor_processor : 5;         //!< Monitor Processor ID number
    uint : 2;
    uint reinit_wait_counters : 1;      //!< re-initialise wait counters
    uint begin_emergency_wait_time : 8; //!< `wait1`; wait time before emergency routing
    uint drop_wait_time : 8;            //!< `wait2`; wait time before dropping packet
} router_control_t;

//! Router status
typedef struct {
    //! diagnostic counter interrupt active
    uint interrupt_active_for_diagnostic_counter : 16;
    uint busy : 1;                      //!< busy - active packet(s) in Router pipeline
    uint : 7;
    //! \brief Router output stage status (empty, full but unblocked, blocked
    //!     in wait1, blocked in wait2).
    uint output_stage : 2;
    uint : 3;
    uint interrupt_active_dump : 1;     //!< dump packet interrupt active
    uint interrupt_active_error : 1;    //!< error packet interrupt active
    uint interrupt_active : 1;          //!< combined Router interrupt request
} router_status_t;

//! Stages in ::router_status_t::output_stage
enum output_stage {
    output_stage_empty,             //!< output stage is empty
    output_stage_full,              //!< output stage is full but unblocked
    output_stage_wait1,             //!< output stage is blocked in wait1
    output_stage_wait2              //!< output stage is blocked in wait2
};

//! Router error/dump header
typedef union {
    struct {
        uint : 6;
        uint time_phase : 2;        //!< time phase when packet received/dumped
        uint : 8;
        uint control : 8;           //!< control byte
        uint route : 3;             //!< Rx route field of packet
        uint time_phase_error : 1;  //!< packet time stamp error (error only)
        uint framing_error : 1;     //!< packet framing error (error only)
        uint parity_error : 1;      //!< packet parity error (error only)
        uint : 2;
    };
    struct {
        uint : 17;
        uint payload : 1;           //!< payload-present field from control byte
        uint : 4;
        uint type : 2;              //!< packet-type field from control byte
    };
    uint word;                      //!< as a whole word
} router_packet_header_t;

//! Router error status
typedef struct {
    uint error_count : 16;          //!< 16-bit saturating error count
    uint : 11;
    uint time_phase_error : 1;      //!< packet time stamp error (sticky)
    uint framing_error : 1;         //!< packet framing error (sticky)
    uint parity_error : 1;          //!< packet parity error (sticky)
    uint overflow : 1;              //!< more than one error packet detected
    uint error : 1;                 //!< error packet detected
} router_error_status_t;

//! Router dump outputs
typedef struct {
    uint link : 6;                  //!< Tx link transmit error caused packet dump
    uint processor : 18;            //!< Fascicle Processor link error caused dump
    uint : 8;
} router_dump_outputs_t;

//! Router dump status
typedef struct {
    uint link : 6;                  //!< Tx link error caused dump (sticky)
    uint processor : 18;            //!< Fascicle Proc link error caused dump (sticky)
    uint : 6;
    uint overflow : 1;              //!< more than one packet dumped
    uint dumped : 1;                //!< packet dumped
} router_dump_status_t;

//! Router diagnostic counter enable/reset
typedef struct {
    ushort enable;                  //!< enable diagnostic counter 15..0
    ushort reset;                   //!< write a 1 to reset diagnostic counter 15..0
} router_diagnostic_counter_ctrl_t;

//! Router timing counter controls
typedef struct {
    uint enable_cycle_count : 1;    //!< enable cycle counter
    uint enable_emergency_active_count : 1; //!< enable emergency router active cycle counter
    uint enable_histogram : 1;      //!< enable histogram
    uint : 13;
    uint reset_cycle_count : 1;     //!< reset cycle counter
    uint reset_emergency_active_count : 1; //!< reset emergency router active cycle counter
    uint reset_histogram : 1;       //!< reset histogram
    uint : 13;
} router_timing_counter_ctrl_t;

//! Router diversion rules, used to handle default-routed packets
typedef struct {
    uint L0 : 2;                //!< Diversion rule for link 0
    uint L1 : 2;                //!< Diversion rule for link 1
    uint L2 : 2;                //!< Diversion rule for link 2
    uint L3 : 2;                //!< Diversion rule for link 3
    uint L4 : 2;                //!< Diversion rule for link 4
    uint L5 : 2;                //!< Diversion rule for link 5
    uint : 20;
} router_diversion_t;

//! Diversion rules for the fields of ::router_diversion_t
enum router_diversion_rule_t {
    diversion_normal,           //!< Send on default route
    diversion_monitor,          //!< Divert to local monitor
    diversion_destroy           //!< Destroy default-routed packets
};

//! Fixed route packet routing control
typedef struct {
    uint fixed_route_vector : 24; //!< Fixed-route routing vector
    uint : 2;
    uint nearest_neighbour_broadcast : 6; //!< Nearest-neighbour broadcast link vector
} router_fixed_route_routing_t;

//! SpiNNaker router controller registers
typedef struct {
    //! Router control register
    router_control_t control;
    //! Router status
    const router_status_t status;
    //! Error-related registers
    struct {
        //! error packet control byte and flags
        const router_packet_header_t header;
        //! error packet routing word
        const uint key;
        //! error packet data payload
        const uint payload;
        //! error packet status
        const router_error_status_t status;
    } error;
    //! Packet-dump-related registers
    struct {
        //! dumped packet control byte and flags
        const router_packet_header_t header;
        //! dumped packet routing word
        const uint key;
        //! dumped packet data payload
        const uint payload;
        //! dumped packet intended destinations
        const router_dump_outputs_t outputs;
        //! dumped packet status
        const router_dump_status_t status;
    } dump;
    //! diagnostic counter enables
    router_diagnostic_counter_ctrl_t diagnostic_counter_control;
    //! timing counter controls
    router_timing_counter_ctrl_t timing_counter_control;
    //! counts Router clock cycles
    const uint cycle_count;
    //! counts emergency router active cycles
    const uint emergency_active_cycle_count;
    //! counts packets that do not wait to be issued
    const uint unblocked_count;
    //! packet delay histogram counters
    const uint delay_histogram[16];
    //! divert default packets
    router_diversion_t diversion;
    //! fixed-route packet routing vector
    router_fixed_route_routing_t fixed_route;
} router_t;

//! SpiNNaker router diagnostic filter
typedef struct {
    uint type : 4;                      //!< packet type: fr, nn, p2p, mc
    uint emergency_routing : 4;         //!< Emergency Routing field = 3, 2, 1 or 0
    uint emergency_routing_mode : 1;    //!< Emergency Routing mode
    uint : 1;
    uint pattern_default : 2;           //!< default [x1]/non-default [1x] routed packets
    uint pattern_payload : 2;           //!< packets with [x1]/without [1x] payload
    uint pattern_local : 2;             //!< local [x1]/non-local[1x] packet source
    uint pattern_destination : 9;       //!< packet dest (Tx link[5:0], MP, local ¬MP, dump)
    uint : 4;
    uint counter_event_occurred : 1;    //!< counter event has occurred (sticky)
    uint enable_counter_event_interrupt : 1; //!< enable interrupt on counter event
    uint counter_event_interrupt_active : 1; //!< counter interrupt active: I = E AND C
} router_diagnostic_filter_t;

ASSERT_WORD_SIZED(router_control_t);
ASSERT_WORD_SIZED(router_packet_header_t);
ASSERT_WORD_SIZED(router_error_status_t);
ASSERT_WORD_SIZED(router_dump_outputs_t);
ASSERT_WORD_SIZED(router_dump_status_t);
ASSERT_WORD_SIZED(router_diagnostic_counter_ctrl_t);
ASSERT_WORD_SIZED(router_timing_counter_ctrl_t);
ASSERT_WORD_SIZED(router_diversion_t);
ASSERT_WORD_SIZED(router_fixed_route_routing_t);
ASSERT_WORD_SIZED(router_diagnostic_filter_t);

//! Router controller registers
static volatile router_t *const router_control = (router_t *) RTR_BASE;
//! Router diagnostic filters
static volatile router_diagnostic_filter_t *const router_diagnostic_filter =
        (router_diagnostic_filter_t *) (RTR_BASE + 0x200);
//! Router diagnostic counters
static volatile uint *const router_diagnostic_counter =
        (uint *) (RTR_BASE + 0x300);

//! \}

// ---------------------------------------------------------------------
// 11. Inter-chip transmit and receive interfaces

// No registers

// ---------------------------------------------------------------------
// 12. System NoC

// No registers

// ---------------------------------------------------------------------
//! \name 13. SDRAM interface
//! \brief The SDRAM interface connects the System NoC to an off-chip SDRAM
//!     device. It is the ARM PL340, described in ARM document DDI 0331D.
//! \details Only meaningfully usable by the monitor core when initialising the
//!     overall chip. Use at other times is very much not recommended.
//! \warning Do not use these without talking to Luis first!
//! \{

//! Memory controller status
typedef struct {
    uint status : 2;            //!< Config, ready, paused, low-power
    uint width : 2;             //!< Width of external memory: 2’b01 = 32 bits
    uint ddr : 3;               //!< DDR type: 3b’011 = Mobile DDR
    uint chips : 2;             //!< Number of different chip selects (1, 2, 3, 4)
    uint banks : 1;             //!< Fixed at 1’b01 = 4 banks on a chip
    uint monitors : 2;          //!< Number of exclusive access monitors (0, 1, 2, 4)
    uint : 20;
} sdram_status_t;

//! Memory controller command
typedef struct {
    uint command : 3;           //!< one of ::sdram_command
} sdram_command_t;

//! \brief Memory controller commands, for ::sdram_command_t::command
//! \todo Verify ::SDRAM_CTL_SLEEP, ::SDRAM_CTL_WAKE, ::SDRAM_CTL_ACTIVE_PAUSE
enum sdram_command {
    SDRAM_CTL_GO,               //!< Go
    SDRAM_CTL_SLEEP,            //!< Sleep
    SDRAM_CTL_WAKE,             //!< Wake
    SDRAM_CTL_PAUSE,            //!< Pause
    SDRAM_CTL_CONFIG,           //!< Configure
    SDRAM_CTL_ACTIVE_PAUSE      //!< Active Pause
};

//! \brief Memory controller direct command
//! \details Used to pass a command directly to a memory device attached to the
//!     PL340.
typedef struct {
    uint address : 14;          //!< address passed to memory device
    uint : 2;
    uint bank : 2;              //!< bank passed to memory device
    uint cmd : 2;               //!< command passed to memory device
    uint chip : 2;              //!< chip number
    uint : 10;
} sdram_direct_command_t;

//! \brief Memory direct commands, for ::sdram_direct_command_t::cmd
//! \details Codes from SARK (sark_hw.c, pl340_init)
enum sdram_direct_command {
    SDRAM_DIRECT_PRECHARGE = 0,     //!< Precharge
    SDRAM_DIRECT_AUTOREFRESH = 1,   //!< Auto-Refresh
    SDRAM_DIRECT_MODEREG = 2,       //!< Mode Register
    SDRAM_DIRECT_NOP = 3,           //!< No-op
};

//! Memory configuration
typedef struct {
    uint column : 3;            //!< number of column address bits (8-12)
    uint row : 3;               //!< number of row address bits (11-16)
    uint auto_precharge_position : 1; //!< position of auto-pre-charge bit (10/8)
    uint power_down_delay : 6;  //!< number of memory cycles before auto-power-down
    uint auto_power_down : 1;   //!< auto-power-down memory when inactive
    uint stop_clock : 1;        //!< stop memory clock when no access
    uint burst : 3;             //!< burst length (1, 2, 4, 8, 16)
    uint qos : 3;               //!< selects the 4-bit QoS field from the AXI ARID
    uint active : 2;            //!< active chips: number for refresh generation
    uint : 9;
} sdram_ram_config_t;

//! Memory refresh period
typedef struct {
    uint period : 15;           //!< memory refresh period in memory clock cycles
    uint : 17;
} sdram_refresh_t;

//! Memory CAS latency
typedef struct {
    uint half_cycle : 1;        //!< CAS half cycle - must be set to 1’b0
    uint cas_lat : 3;           //!< CAS latency in memory clock cycles
    uint : 28;
} sdram_cas_latency_t;

//! \brief Memory timimg configuration
//! \details See datasheet for meanings
typedef struct {
    uint t_dqss;                //!< write to DQS time
    uint t_mrd;                 //!< mode register command time
    uint t_ras;                 //!< RAS to precharge delay
    uint t_rc;                  //!< active bank x to active bank x delay
    uint t_rcd;                 //!< RAS to CAS minimum delay
    uint t_rfc;                 //!< auto-refresh command time
    uint t_rp;                  //!< precharge to RAS delay
    uint t_rrd;                 //!< active bank x to active bank y delay
    uint t_wr;                  //!< write to precharge delay
    uint t_wtr;                 //!< write to read delay
    uint t_xp;                  //!< exit power-down command time
    uint t_xsr;                 //!< exit self-refresh command time
    uint t_esr;                 //!< self-refresh command time
} sdram_timing_config_t;

//! Memory controller registers
typedef struct {
    const sdram_status_t status;    //!< memory controller status
    sdram_command_t command;        //!< PL340 command
    sdram_direct_command_t direct;  //!< direct command
    sdram_ram_config_t mem_config;  //!< memory configuration
    sdram_refresh_t refresh;        //!< refresh period
    sdram_cas_latency_t cas_latency;        //!< CAS latency
    sdram_timing_config_t timing_config;    //!< timing configuration
} sdram_controller_t;

//! Memory QoS settings
typedef struct {
    uint enable : 1;            //!< QoS enable
    uint minimum : 1;           //!< minimum QoS
    uint maximum : 8;           //!< maximum QoS
    uint : 22;
} sdram_qos_t;

//! Memory chip configuration
typedef struct {
    uint mask : 8;              //!< address mask
    uint match : 8;             //!< address match
    uint orientation : 1;       //!< bank-rol-column/row-bank-column
    uint : 15;
} sdram_chip_t;

//! Maximum register IDs
enum {
    SDRAM_QOS_MAX = 15,         //!< Maximum memory QoS register
    SDRAM_CHIP_MAX = 3          //!< Maximum memory chip configuration register
};

//! Memory delay-locked-loop (DLL) test and status inputs
typedef struct {
    uint meter : 7;             //!< Current position of bar-code output
    uint : 1;
    uint s0 : 1;                //!< Strobe 0 faster than Clock
    uint c0 : 1;                //!< Clock faster than strobe 0
    uint s1 : 1;                //!< Strobe 1 faster than Clock
    uint c1 : 1;                //!< Clock faster than strobe 1
    uint s2 : 1;                //!< Strobe 2 faster than Clock
    uint c2 : 1;                //!< Clock faster than strobe 2
    uint s3 : 1;                //!< Strobe 3 faster than Clock
    uint c3 : 1;                //!< Clock faster than strobe 3
    uint decing : 1;            //!< Phase comparator is reducing delay
    uint incing : 1;            //!< Phase comparator is increasing delay
    uint locked : 1;            //!< Phase comparator is locked
    uint : 1;
    uint R : 1;                 //!< 3-phase bar-code control output
    uint M : 1;                 //!< 3-phase bar-code control output
    uint L : 1;                 //!< 3-phase bar-code control output
    uint : 9;
} sdram_dll_status_t;

//! Memory delay-locked-loop (DLL) test and control outputs
typedef struct {
    uint s0 : 2;                //!< Input select for delay line 0 {def, alt, 0, 1}
    uint s1 : 2;                //!< Input select for delay line 1 {def, alt, 0, 1}
    uint s2 : 2;                //!< Input select for delay line 2 {def, alt, 0, 1}
    uint s3 : 2;                //!< Input select for delay line 3 {def, alt, 0, 1}
    uint s4 : 2;                //!< Input select for delay line 4 {def, alt, 0, 1}
    uint s5 : 2;                //!< Input select for delay line 5 {def, alt, 0, 1}
    uint : 4;
    uint test_decing : 1;       //!< Force Decing (if ID = 1)
    uint test_incing : 1;       //!< Force Incing (if ID = 1)
    uint enable_force_inc_dec : 1; //!< Enable forcing of Incing and Decing
    uint test_5 : 1;            //!< Substitute delay line 5 for 4 for testing
    uint R : 1;                 //!< Force 3-phase bar-code control inputs
    uint M : 1;                 //!< Force 3-phase bar-code control inputs
    uint L : 1;                 //!< Force 3-phase bar-code control inputs
    uint enable_force_lmr : 1;  //!< Enable forcing of L, M, R
    uint enable : 1;            //!< Enable DLL (0 = reset DLL)
    uint : 7;
} sdram_dll_user_config0_t;

//! Memory delay-locked-loop (DLL) fine-tune control
typedef union {
    //! Tuning fields
    struct {
        uint tune_0 : 4;        //!< Fine tuning control on delay line 0
        uint tune_1 : 4;        //!< Fine tuning control on delay line 1
        uint tune_2 : 4;        //!< Fine tuning control on delay line 2
        uint tune_3 : 4;        //!< Fine tuning control on delay line 3
        uint tune_4 : 4;        //!< Fine tuning control on delay line 4
        uint tune_5 : 4;        //!< Fine tuning control on delay line 5
        uint : 8;
    };
    uint word;                  //!< Tuning control word
} sdram_dll_user_config1_t;

//! SDRAM delay-locked-loop (DLL) control registers
typedef struct {
    const sdram_dll_status_t status;    //!< Status
    sdram_dll_user_config0_t config0;   //!< Test: control
    sdram_dll_user_config1_t config1;   //!< Test: fine tune
} sdram_dll_t;

ASSERT_WORD_SIZED(sdram_status_t);
ASSERT_WORD_SIZED(sdram_command_t);
ASSERT_WORD_SIZED(sdram_direct_command_t);
ASSERT_WORD_SIZED(sdram_ram_config_t);
ASSERT_WORD_SIZED(sdram_refresh_t);
ASSERT_WORD_SIZED(sdram_cas_latency_t);
ASSERT_WORD_SIZED(sdram_qos_t);
ASSERT_WORD_SIZED(sdram_chip_t);
ASSERT_WORD_SIZED(sdram_dll_status_t);
ASSERT_WORD_SIZED(sdram_dll_user_config0_t);
ASSERT_WORD_SIZED(sdram_dll_user_config1_t);

//! \brief SDRAM interface control registers
static volatile sdram_controller_t *const sdram_control =
        (sdram_controller_t *) PL340_BASE;
//! \brief SDRAM QoS control registers
static volatile sdram_qos_t *const sdram_qos_control =
        (sdram_qos_t *) (PL340_BASE + 0x100);
//! \brief SDRAM chip control registers
static volatile sdram_chip_t *const sdram_chip_control =
        (sdram_chip_t *) (PL340_BASE + 0x200);
//! \brief SDRAM delay-locked-loop control registers
static volatile sdram_dll_t *const sdram_dll_control =
        (sdram_dll_t *) (PL340_BASE + 0x300);

//! \}

// ---------------------------------------------------------------------
//! \name 14. System Controller
//! \brief The System Controller incorporates a number of functions for system
//!     start-up, fault-tolerance testing (invoking, detecting and resetting
//!     faults), general performance monitoring, etc.
//! \note All processor IDs should be _physical_ processor IDs.
//! \{

//! \brief System controller processor select
typedef struct {
    uint select : 18;           //!< Bit-map for selecting a processor
    uint : 2;
    uint security_code : 12;    //!< ::SYSTEM_CONTROLLER_MAGIC_NUMBER to enable write
} sc_magic_proc_map_t;

//! System controller subsystem reset target select
typedef struct {
    uint router : 1;            //!< Router
    uint sdram : 1;             //!< PL340 SDRAM controller
    uint system_noc : 1;        //!< System NoC
    uint comms_noc : 1;         //!< Communications NoC
    uint tx_links : 6;          //!< Tx link 0-5
    uint rx_links : 6;          //!< Rx link 0-5
    uint clock_gen : 1;         //!< System AHB & Clock Gen (pulse reset only)
    uint entire_chip : 1;       //!< Entire chip (pulse reset only)
    uint : 2;
    uint security_code : 12;    //!< ::SYSTEM_CONTROLLER_MAGIC_NUMBER to enable write
} sc_magic_subsystem_map_t;

//! System controller last reset status
typedef struct {
    uint reset_code : 3;        //! One of ::sc_reset_codes
    uint : 29;
} sc_reset_code_t;

//! System controller chip reset reasons
enum sc_reset_codes {
    SC_RESET_CODE_POR,          //!< Power-on reset
    SC_RESET_CODE_WDR,          //!< Watchdog reset
    SC_RESET_CODE_UR,           //!< User reset
    SC_RESET_CODE_REC,          //!< Reset entire chip (::sc_magic_subsystem_map_t::entire_chip)
    SC_RESET_CODE_WDI           //!< Watchdog interrupt
};

//! System controller monitor election control
typedef struct {
    uint monitor_id : 5;        //!< Monitor processor identifier
    uint : 3;
    uint arbitrate_request : 1; //!< Write 1 to set MP arbitration bit (see r32-63)
    uint : 7;
    uint reset_on_watchdog : 1; //!< Reset Monitor Processor on Watchdog interrupt
    uint : 3;
    uint security_code : 12;    //!< ::SYSTEM_CONTROLLER_MAGIC_NUMBER to enable write
} sc_monitor_id_t;

//! System controller miscellaneous control
typedef struct {
    uint boot_area_map : 1;     //!< map System ROM (0) or RAM (1) to Boot area
    uint : 14;
    uint jtag_on_chip : 1;      //!< select on-chip (1) or off-chip (0) control of JTAG pins
    uint test : 1;              //!< read value on Test pin
    uint ethermux : 1;          //!< read value on Ethermux pin
    uint clk32 : 1;             //!< read value on Clk32 pin
    uint jtag_tdo : 1;          //!< read value on JTAG_TDO pin
    uint jtag_rtck : 1;         //!< read value on JTAG_RTCK pin
    uint : 11;
} sc_misc_control_t;

//! System controller general chip I/O pin access
typedef union {
    struct {
        uint : 16;
        uint ethernet_receive : 4;  //!< MII RxD port
        uint ethernet_transmit : 4; //!< MII TxD port
        uint jtag : 4;          //!< JTAG interface
        uint : 1;
        uint sdram : 3;         //!< On-package SDRAM control
    };
    uint gpio;                  //!< GPIO pins
} sc_io_t;

//! System controller phase-locked-loop control
typedef struct {
    uint input_multiplier : 6;  //!< input clock multiplier
    uint : 2;
    uint output_divider : 6;    //!< output clock divider
    uint : 2;
    uint freq_range : 2;        //!< frequency range (see ::sc_frequency_range)
    uint power_up : 1;          //!< Power UP
    uint : 5;
    uint _test : 1;             //!< test (=0 for normal operation)
    uint : 7;
} sc_pll_control_t;

//! Frequency range constants for ::sc_pll_control_t::freq_range
enum sc_frequency_range {
    FREQ_25_50,                 //!< 25-50 MHz
    FREQ_50_100,                //!< 50-100 MHz
    FREQ_100_200,               //!< 100-200 MHz
    FREQ_200_400                //!< 200-400 MHz
};

//! System controller clock multiplexing control
typedef struct {
    uint pa : 2;                //!< clock selector for A CPUs (1 2 4 7 8 11 13 14 16);
                                //!< see ::sc_clock_source
    uint adiv : 2;              //!< divide CPU clock A by Adiv+1 (= 1-4)
    uint : 1;
    uint pb : 2;                //!< clock selector for B CPUs (0 3 5 6 9 10 12 15 17);
                                //!< see ::sc_clock_source
    uint bdiv : 2;              //!< divide CPU clock B by Bdiv+1 (= 1-4)
    uint : 1;
    uint mem : 2;               //!< clock selector for SDRAM;
                                //!< see ::sc_clock_source
    uint mdiv : 2;              //!< divide SDRAM clock by Mdiv+1 (= 1-4)
    uint : 1;
    uint rtr : 2;               //!< clock selector for Router;
                                //!< see ::sc_clock_source
    uint rdiv : 2;              //!< divide Router clock by Rdiv+1 (= 1-4)
    uint : 1;
    uint sys : 2;               //!< clock selector for System AHB components;
                                //!< see ::sc_clock_source
    uint sdiv : 2;              //!< divide System AHB clock by Sdiv+1 (= 1-4)
    uint : 7;
    uint invert_b : 1;          //!< invert CPU clock B
} sc_clock_mux_t;

//! \brief System controller clock sources
//! \details Used for ::sc_clock_mux_t::pa, ::sc_clock_mux_t::pb,
//!     ::sc_clock_mux_t::mem, ::sc_clock_mux_t::rtr, ::sc_clock_mux_t::sys
enum sc_clock_source {
    CLOCK_SRC_EXT,              //!< external 10MHz clock input
    CLOCK_SRC_PLL1,             //!< PLL1
    CLOCK_SRC_PLL2,             //!< PLL2
    CLOCK_SRC_EXT4              //!< external 10MHz clock divided by 4
};

//! System controller sleep status
typedef struct {
    uint status : 18;           //!< ARM968 STANDBYWFI signal for each core
    uint : 14;
} sc_sleep_status_t;

//! System controller temperature status/control
typedef struct {
    uint temperature : 24;      //!< temperature sensor reading
    uint sample_finished : 1;   //!< temperature measurement finished
    uint : 6;
    uint start : 1;             //!< start temperature measurement
} sc_temperature_t;

//! System controller mutex/interlock
typedef struct {
    uint : 31;
    uint bit : 1;               //!< The only relevant bit in the word
} sc_mutex_bit_t;

//! System controller router control
typedef struct {
    uint rx_disable : 6;        //!< disables the corresponding link receiver
    uint : 2;
    uint tx_disable : 6;        //!< disables the corresponding link transmitter
    uint : 2;
    uint parity_control : 1;    //!< Router parity control
    uint : 3;
    uint security_code : 12;    //!< ::SYSTEM_CONTROLLER_MAGIC_NUMBER to enable write
} sc_link_disable_t;

//! System controller registers
typedef struct {
    const uint chip_id;         //!< Chip ID register (hardwired)
    sc_magic_proc_map_t processor_disable;  //!< Each bit disables a processor
    sc_magic_proc_map_t set_cpu_irq;        //!< Writing a 1 sets a processor’s interrupt line
    sc_magic_proc_map_t clear_cpu_irq;      //!< Writing a 1 clears a processor’s interrupt line
    uint set_cpu_ok;            //!< Writing a 1 sets a CPU OK bit
    uint clear_cpu_ok;          //!< Writing a 1 clears a CPU OK bit
    sc_magic_proc_map_t cpu_soft_reset_level;       //!< Level control of CPU resets
    sc_magic_proc_map_t cpu_hard_reset_level;       //!< Level control of CPU node resets
    sc_magic_subsystem_map_t subsystem_reset_level; //!< Level control of subsystem resets
    sc_magic_proc_map_t cpu_soft_reset_pulse;       //!< Pulse control of CPU resets
    sc_magic_proc_map_t cpu_hard_reset_pulse;       //!< Pulse control of CPU node resets
    sc_magic_subsystem_map_t subsystem_reset_pulse; //!< Pulse control of subsystem resets
    const sc_reset_code_t reset_code;       //!< Indicates cause of last chip reset
    sc_monitor_id_t monitor_id; //!< ID of Monitor Processor
    sc_misc_control_t misc_control;         //!< Miscellaneous control bits
    sc_io_t gpio_pull_up_down_enable;       //!< General-purpose IO pull up/down enable
    sc_io_t io_port;            //!< I/O pin output register
    sc_io_t io_direction;       //!< External I/O pin is input (1) or output (0)
    sc_io_t io_set;             //!< Writing a 1 sets IO register bit
    sc_io_t io_clear;           //!< Writing a 1 clears IO register bit
    sc_pll_control_t pll1_freq_control;     //!< PLL1 frequency control
    sc_pll_control_t pll2_freq_control;     //!< PLL2 frequency control
    uint set_flags;             //!< Set flags register
    uint reset_flags;           //!< Reset flags register
    sc_clock_mux_t clock_mux_control;       //!< Clock multiplexer controls
    const sc_sleep_status_t cpu_sleep;      //!< CPU sleep (awaiting interrupt) status
    sc_temperature_t temperature[3];        //!< Temperature sensor registers [2:0]
    const uint _padding[3];
    const sc_mutex_bit_t monitor_arbiter[32];       //!< Read sensitive semaphores to determine MP
    const sc_mutex_bit_t test_and_set[32];          //!< Test & Set registers for general software use
    const sc_mutex_bit_t test_and_clear[32];        //!< Test & Clear registers for general software use
    sc_link_disable_t link_disable;         //!< Disables for Tx and Rx link interfaces
} system_controller_t;

//! System controller magic numbers
enum {
    //! Magic number for enabling writing to critical fields
    SYSTEM_CONTROLLER_MAGIC_NUMBER = 0x5ec
};

ASSERT_WORD_SIZED(sc_magic_proc_map_t);
ASSERT_WORD_SIZED(sc_reset_code_t);
ASSERT_WORD_SIZED(sc_monitor_id_t);
ASSERT_WORD_SIZED(sc_misc_control_t);
ASSERT_WORD_SIZED(sc_io_t);
ASSERT_WORD_SIZED(sc_pll_control_t);
ASSERT_WORD_SIZED(sc_clock_mux_t);
ASSERT_WORD_SIZED(sc_sleep_status_t);
ASSERT_WORD_SIZED(sc_temperature_t);
ASSERT_WORD_SIZED(sc_mutex_bit_t);
ASSERT_WORD_SIZED(sc_link_disable_t);

//! System controller registers
static volatile system_controller_t *const system_control =
        (system_controller_t *) SYSCTL_BASE;

//! \}

// ---------------------------------------------------------------------
//! \name 15. Ethernet Media-independent interface (MII)
//! \brief The SpiNNaker system connects to a host machine via Ethernet links.
//! \details Each SpiNNaker chip includes an Ethernet MII interface, although
//!     only a few of the chips are expected to use this interface. These
//!     chips will require an external PHY.
//! \{

//! Ethernet general control
typedef struct {
    uint transmit : 1;              //!< Transmit system enable
    uint receive : 1;               //!< Receive system enable
    uint loopback : 1;              //!< Loopback enable
    uint receive_error_filter : 1;  //!< Receive error filter enable
    uint receive_unicast: 1;        //!< Receive unicast packets enable
    uint receive_multicast : 1;     //!< Receive multicast packets enable
    uint receive_broadcast : 1;     //!< Receive broadcast packets enable
    uint receive_promiscuous : 1;   //!< Receive promiscuous packets enable
    uint receive_vlan : 1;          //!< Receive VLAN enable
    uint reset_drop_counter : 1;    //!< Reset receive dropped frame count (in r1)
    uint hardware_byte_reorder_disable : 1; //!< Disable hardware byte reordering
    uint : 21;
} ethernet_general_command_t;

//! Ethernet general status
typedef struct {
    uint transmit_active : 1;   //!< Transmit MII interface active
    uint unread_counter : 6;    //!< Received unread frame count
    uint : 9;
    uint drop_counter : 16;     //!< Receive dropped frame count
} ethernet_general_status_t;

//! Ethernet frame transmit length
typedef struct {
    uint tx_length : 11;        //!< Length of transmit frame (60 - 1514 bytes)
} ethernet_tx_length_t;

//! Limits of ::ethernet_tx_length_t::tx_length
enum ethernet_tx_length_limits {
    ETHERNET_TX_LENGTH_MIN = 60,    //!< Minimum length of an ethernet frame
    ETHERNET_TX_LENGTH_MAX = 1514   //!< Maximum length of an ethernet frame
};

//! Ethernet PHY (physical layer) control
typedef struct {
    uint reset : 1;             //!< PHY reset (active low)
    uint smi_input : 1;         //!< SMI data input
    uint smi_output : 1;        //!< SMI data output
    uint smi_out_enable : 1;    //!< SMI data output enable
    uint smi_clock : 1;         //!< SMI clock (active rising)
    uint irq_invert_disable : 1; //!< PHY IRQn invert disable
    uint : 26;
} ethernet_phy_control_t;

//! Ethernet interrupt clear register
typedef struct {
    uint transmit : 1;          //!< Clear transmit interrupt request
    uint : 3;
    uint receive : 1;           //!< Clear receive interrupt request
    uint : 27;
} ethernet_interrupt_clear_t;

//! Ethernet receive data pointer
typedef struct {
    uint ptr : 12;              //!< Receive frame buffer read pointer
    uint rollover : 1;          //!< Rollover bit - toggles on address wrap-around
    uint : 19;
} ethernet_receive_pointer_t;

//! Ethernet receive descriptor pointer
typedef struct {
    uint ptr : 6;               //!< Receive descriptor read pointer
    uint rollover : 1;          //!< Rollover bit - toggles on address wrap-around
    uint : 25;
} ethernet_receive_descriptor_pointer_t;

//! Ethernet controller registers
typedef struct {
    ethernet_general_command_t command;         //!< General command
    const ethernet_general_status_t status;     //!< General status
    ethernet_tx_length_t transmit_length;       //!< Transmit frame length
    uint transmit_command;      //!< Transmit command; any value commits transmit
    uint receive_command;       //!< Recieve command; any value completes receive
    uint64 mac_address;         //!< MAC address; low 48 bits only
    ethernet_phy_control_t phy_control;         //!< PHY control
    ethernet_interrupt_clear_t interrupt_clear; //!< Interrupt clear
    //! Receive frame buffer read pointer
    const ethernet_receive_pointer_t receive_read;
    //! Receive frame buffer write pointer
    const ethernet_receive_pointer_t receive_write;
    //! Receive descriptor read pointer
    const ethernet_receive_descriptor_pointer_t receive_desc_read;
    //! Receive descriptor write pointer
    const ethernet_receive_descriptor_pointer_t receive_desc_write;
    uint _test[3];              //!< debug & test use only
} ethernet_controller_t;

//! \brief Ethernet received message descriptor.
//! \warning Cannot find description of rest of this structure; SCAMP only
//!     uses one field.
typedef struct {
    uint length : 11;           //!< Received packet length
    uint : 21; // ???
} ethernet_receive_descriptor_t;

ASSERT_WORD_SIZED(ethernet_general_command_t);
ASSERT_WORD_SIZED(ethernet_general_status_t);
ASSERT_WORD_SIZED(ethernet_tx_length_t);
ASSERT_WORD_SIZED(ethernet_phy_control_t);
ASSERT_WORD_SIZED(ethernet_interrupt_clear_t);
ASSERT_WORD_SIZED(ethernet_receive_pointer_t);
ASSERT_WORD_SIZED(ethernet_receive_descriptor_pointer_t);
ASSERT_WORD_SIZED(ethernet_receive_descriptor_t);

//! Ethernet transmit buffer
static volatile uchar *const ethernet_tx_buffer = (uchar *) ETH_TX_BASE;
//! Ethernet receive buffer
static volatile uchar *const ethernet_rx_buffer = (uchar *) ETH_RX_BASE;
//! Ethernet receive descriptor buffer
static volatile ethernet_receive_descriptor_t *const ethernet_desc_buffer =
        (ethernet_receive_descriptor_t *) ETH_RX_DESC_RAM;
//! Ethernet MII controller registers
static volatile ethernet_controller_t *const ethernet_control =
        (ethernet_controller_t *) ETH_REGS;

//! \}

// ---------------------------------------------------------------------
//! \name 16. Watchdog timer
//! \brief The watchdog timer is an ARM PrimeCell component (ARM part SP805,
//!     documented in ARM DDI 0270B) that is responsible for applying a system
//!     reset when a failure condition is detected.
//! \details Normally, the Monitor Processor will be responsible for resetting
//!     the watchdog periodically to indicate that all is well. If the Monitor
//!     Processor should crash, or fail to reset the watchdog during a
//!     pre-determined period of time, the watchdog will trigger.
//! \{

//! Watchdog timer control register
typedef struct {
    uint interrupt_enable : 1;  //!< Enable Watchdog counter and interrupt (1)
    uint reset_enable : 1;      //!< Enable the Watchdog reset output (1)
    uint : 30;
} watchdog_control_t;

//! Watchdog timer status registers
typedef struct {
    uint interrupted : 1;       //!< True if interrupt asserted
    uint : 31;
} watchdog_status_t;

//! Watchdog timer lock register
typedef union {
    //! The fields in the lock register
    struct {
        uint lock : 1;          //!< Write access enabled (0) or disabled (1)
        uint magic : 31;        //!< Access control code
    };
    uint whole_value;           //!< Whole value of lock; see ::watchdog_lock_codes
} watchdog_lock_t;

//! Watchdog timer lock codes, for ::watchdog_lock_t
enum watchdog_lock_codes {
    WATCHDOG_LOCK_RESET = 0,        //!< Put the watchdog timer into normal mode
    WATCHDOG_LOCK_MAGIC = WD_CODE   //!< Unlock the watchdog timer for configuration
};

//! Watchdog timer control registers
typedef struct {
    uint load;                  //!< Count load register
    const uint value;           //!< Current count value
    watchdog_control_t control; //!< Control register
    uint interrupt_clear;       //!< Interrupt clear register; any written value will do
    const watchdog_status_t raw_status;     //!< Raw interrupt status register
    const watchdog_status_t masked_status;  //!< Masked interrupt status register
    const uint _padding[0x2fa]; // Lots of padding!
    watchdog_lock_t lock;       //!< Lock register
} watchdog_controller_t;

ASSERT_WORD_SIZED(watchdog_control_t);
ASSERT_WORD_SIZED(watchdog_status_t);
ASSERT_WORD_SIZED(watchdog_lock_t);

//! Watchdog timer controller registers
static volatile watchdog_controller_t *const watchdog_control =
        (watchdog_controller_t *) WDOG_BASE;

//! \}

// ---------------------------------------------------------------------
// 17. System RAM

// No registers

// ---------------------------------------------------------------------
// 18. Boot ROM

// No registers

// ---------------------------------------------------------------------
// 19. JTAG

// No registers

// ---------------------------------------------------------------------
// 20. Input and Output Signals

// No registers

// ---------------------------------------------------------------------
// 21. Packaging

// No registers

// ---------------------------------------------------------------------
// 22. Application Notes

// No registers

// ---------------------------------------------------------------------
#endif // !__SPINN_EXTRA_H__

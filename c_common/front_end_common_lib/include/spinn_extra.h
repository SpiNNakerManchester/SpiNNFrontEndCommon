/*
 * Copyright (c) 2019 The University of Manchester
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
// ------------------------------------------------------------------------

#ifndef __SPINN_EXTRA_H__
#define __SPINN_EXTRA_H__

#include <spinnaker.h>
#include <stdbool.h>

#ifndef DOXYGEN
// Hack for better naming in doxygen while avoiding warnings when building
#define DOXYNAME(x)     /* nothing */
#endif

#if defined(__GNUC__) && __GNUC__ < 6
// This particular warning (included in -Wextra) is retarded wrong for client
// code of this file. Only really a problem on Travis.
#pragma GCC diagnostic ignored "-Wmissing-field-initializers"
#endif // __GNUC__

//! \brief Generates valid code if the named type is one word long, and invalid
//!     code otherwise.
//! \param type_ident: The _name_ of the type that we are asserting is one word
//!     long. This macro assumes that it's a name, and not just any old type.
//! \internal
//!     Wrapped in a function because _Static_assert() is treated as expression
//!     by Eclipse. This is a known bug in the Eclipse C parser, but it is
//!     easier to just work around it. The function we use is static inline and
//!     never used. And does nothing except apply the compile-time assertion.
//!
//!     We don't use <assert.h> because spinn_common supplies one of those that
//!     causes weird incompatibilities. We don't need it.
#define ASSERT_WORD_SIZED(type_ident) \
    static inline void __static_word_sized_assert_ ## type_ident (void) { \
        _Static_assert(sizeof(type_ident) == sizeof(uint),              \
                #type_ident " must be the same size as a word");        \
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
//! \details
//!     Each processor node on an SpiNNaker chip has a vectored interrupt
//!     controller (VIC) that is used to enable and disable interrupts from
//!     various sources, and to wake the processor from sleep mode when
//!     required. The interrupt controller provides centralised management of
//!     IRQ and FIQ sources, and offers an efficient indication of the active
//!     sources for IRQ vectoring purposes.
//!
//!     The VIC is the ARM PL190, described in ARM DDI 0181E.
//! \{

//! The type of an interrupt handler
typedef void (*vic_interrupt_handler_t) (void);

//! \brief Mask describing interrupts that can be selected.
typedef union {
    //! See datasheet section **5.4 Interrupt sources**
    struct DOXYNAME(interrupt_bits) {
        //! Watchdog timer interrupt
        uint watchdog : 1;
        //! Local software interrupt generation
        uint software : 1;
        //! Debug communications receiver interrupt
        uint comm_rx : 1;
        //! Debug communications transmitter interrupt
        uint comm_tx : 1;
        //! Counter/timer interrupt 1
        uint timer1 : 1;
        //! Counter/timer interrupt 2
        uint timer2 : 1;
        //! Comms controller packet received
        uint cc_rx_ready : 1;
        //! Comms controller received packet parity error
        uint cc_rx_parity_error : 1;
        //! Comms controller received packet framing error
        uint cc_rx_framing_error : 1;
        //! Comms controller transmit buffer full
        uint cc_tx_full : 1;
        //! Comms controller transmit buffer overflow
        uint cc_tx_overflow : 1;
        //! Comms controller transmit buffer empty
        uint cc_tx_empty : 1;
        //! DMA controller transfer complete
        uint dma_done : 1;
        //! DMA controller error
        uint dma_error : 1;
        //! DMA controller transfer timed out
        uint dma_timeout : 1;
        //! Router diagnostic counter event has occurred
        uint router_diagnostic : 1;
        //! Router packet dumped - indicates failed delivery
        uint router_dump : 1;
        //! Router error - packet parity, framing, or time stamp error
        uint router_error : 1;
        //! System Controller interrupt bit set for this processor
        uint cpu : 1;
        //! Ethernet transmit frame interrupt
        uint ethernet_tx : 1;
        //! Ethernet receive frame interrupt
        uint ethernet_rx : 1;
        //! Ethernet PHY/external interrupt
        uint ethernet_phy : 1;
        //! System-wide slow (nominally 32 KHz) timer interrupt
        uint slow_clock : 1;
        //! Comms controller can accept new Tx packet
        uint cc_tx_not_full : 1;
        //! Comms controller multicast packet received
        uint cc_rx_mc : 1;
        //! Comms controller point-to-point packet received
        uint cc_rx_p2p : 1;
        //! Comms controller nearest neighbour packet received
        uint cc_rx_nn : 1;
        //! Comms controller fixed route packet received
        uint cc_rx_fr : 1;
        //! External interrupt request 0
        uint int0 : 1;
        //! External interrupt request 1
        uint int1 : 1;
        //! Signal on GPIO[8]
        uint gpio8 : 1;
        //! Signal on GPIO[9]
        uint gpio9 : 1;
    };
    //! Whole mask as integer
    uint value;
} vic_mask_t;

//! VIC registers
typedef struct {
    //! IRQ status register
    const vic_mask_t irq_status;
    //! FIQ status register
    const vic_mask_t fiq_status;
    //! raw interrupt status register
    const vic_mask_t raw_status;
    //! interrupt select register
    vic_mask_t int_select;
    //! interrupt enable set register
    vic_mask_t int_enable;
    //! interrupt enable clear register
    vic_mask_t int_disable;
    //! soft interrupt set register
    vic_mask_t soft_int_enable;
    //! soft interrupt clear register
    vic_mask_t soft_int_disable;
    //! protection register
    bool protection;
    // padding
    const uint _padding[3];
    //! current vector address register
    vic_interrupt_handler_t vector_address;
    //! default vector address register
    vic_interrupt_handler_t default_vector_address;
} vic_control_t;

//! VIC individual vector control
typedef struct {
    //! interrupt source
    uint source : 5;
    //! interrupt enable
    uint enable : 1;
    // padding
    uint : 26;
} vic_vector_control_t;

ASSERT_WORD_SIZED(vic_mask_t);
ASSERT_WORD_SIZED(vic_interrupt_handler_t);
ASSERT_WORD_SIZED(vic_vector_control_t);

//! VIC registers
static volatile vic_control_t *const vic_control =
        // NB unbuffered!
        (vic_control_t *) VIC_BASE_UNBUF;
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
//! \details
//!     The counter/timers use the standard AMBA peripheral device described
//!     on page 4-24 of the AMBA Design Kit Technical Reference Manual ARM DDI
//!     0243A, February 2003. The peripheral has been modified only in that
//!     the APB interface of the original has been replaced by an AHB
//!     interface for direct connection to the ARM968 AHB bus.
//! \{

//! Timer control register
typedef struct {
    //! 0 = wrapping mode, 1 = one shot
    uint one_shot : 1;
    //! 0 = 16 bit, 1 = 32 bit
    uint size : 1;
    //! divide input clock (see ::timer_pre_divide)
    uint pre_divide : 2;
    // padding
    uint : 1;
    //! enable interrupt (1 = enabled)
    uint interrupt_enable : 1;
    //! 0 = free-running; 1 = periodic
    uint periodic_mode : 1;
    //! enable counter/timer (1 = enabled)
    uint enable : 1;
    // padding
    uint : 24;
} timer_control_t;

//! Values for ::timer_control_t::pre_divide
enum timer_pre_divide {
    //! Divide by 1
    TIMER_PRE_DIVIDE_1 = 0,
    //! Divide by 16
    TIMER_PRE_DIVIDE_16 = 1,
    //! Divide by 256
    TIMER_PRE_DIVIDE_256 = 2
};

//! Timer interrupt status flag
typedef struct {
    //! The flag bit
    uint status : 1;
    // padding
    uint : 31;
} timer_interrupt_status_t;

//! Timer controller registers
typedef struct {
    //! Load value for Timer
    uint load_value;
    //! Current value of Timer
    const uint current_value;
    //! Timer control register
    timer_control_t control;
    //! Interrupt clear (any value may be written)
    uint interrupt_clear;
    //! Timer raw interrupt status
    const timer_interrupt_status_t raw_interrupt_status;
    //! Timer masked interrupt status
    const timer_interrupt_status_t masked_interrupt_status;
    //! Background load value for Timer
    uint background_load_value;
    // padding
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
    //! Must be zero
    uint _zeroes : 2;
    //! length of the DMA transfer, in words
    uint length_words : 15;
    // padding
    uint : 2;
    //! read from or write to system bus, see ::dma_direction_t
    uint direction : 1;
    //! check (read) or generate (write) CRC
    uint crc : 1;
    //! burst length = 2<sup>B</sup>&times;Width, B = 0..4 (i.e max 16)
    uint burst : 3;
    //! transfer width, see ::dma_transfer_unit_t
    uint width : 1;
    //! DMA transfer mode is user (0) or privileged (1)
    uint privilege : 1;
    //! software defined transfer ID
    uint transfer_id : 6;
} dma_description_t;

//! DMA transfer direction, see ::dma_description_t::direction
enum dma_direction_t {
    //! read from system bus (SDRAM)
    DMA_DIRECTION_READ,
    //! write to system bus (SDRAM)
    DMA_DIRECTION_WRITE
};

//! DMA burst width, see ::dma_description_t::width
enum dma_transfer_unit_t {
    //! Transfer in words
    DMA_TRANSFER_WORD,
    //! Transfer in double-words
    DMA_TRANSFER_DOUBLE_WORD
};

//! DMA control register
typedef struct {
    //! setting this bit uncommits a queued transfer
    uint uncommit : 1;
    //! end current transfer and discard data
    uint abort : 1;
    //! resume transfer (clears DMA errors)
    uint restart : 1;
    //! clear Done interrupt request
    uint clear_done_int : 1;
    //! clear Timeout interrupt request
    uint clear_timeout_int : 1;
    //! clear Write Buffer interrupt request
    uint clear_write_buffer_int : 1;
    // padding
    uint : 26;
} dma_control_t;

//! DMA status register
typedef struct {
    //! DMA transfer in progress
    uint transferring : 1;
    //! DMA transfer is PAUSED
    uint paused : 1;
    //! DMA transfer is queued - registers are full
    uint queued : 1;
    //! write buffer is full
    uint write_buffer_full : 1;
    //! write buffer is not empty
    uint write_buffer_active : 1;
    // padding
    uint : 5;
    //! a DMA transfer has completed without error
    uint transfer_done : 1;
    //! 2nd DMA transfer has completed without error
    uint transfer2_done : 1;
    //! a burst transfer has not completed in time
    uint timeout : 1;
    //! the calculated and received CRCs differ
    uint crc_error : 1;
    //! the TCM AHB interface has signalled an error
    uint tcm_error : 1;
    //! the AXI interface (SDRAM) has signalled a transfer error
    uint axi_error : 1;
    //! the user has aborted the transfer (via ::dma_control_t::abort)
    uint user_abort : 1;
    //! a soft reset of the DMA controller has happened
    uint soft_reset : 1;
    // not allocated
    uint : 2;
    //! a buffered write transfer has failed
    uint write_buffer_error : 1;
    // padding
    uint : 3;
    //! hardwired processor ID identifies CPU on chip
    uint processor_id : 8;
} dma_status_t;

//! DMA global control register
typedef struct {
    //! enable Bridge write buffer
    uint bridge_buffer_enable : 1;
    // padding
    uint : 9;
    //! interrupt if ::dma_status_t::transfer_done set
    uint transfer_done_interrupt : 1;
    //! interrupt if ::dma_status_t::transfer2_done set
    uint transfer2_done_interrupt : 1;
    //! interrupt if ::dma_status_t::timeout set
    uint timeout_interrupt : 1;
    //! interrupt if ::dma_status_t::crc_error set
    uint crc_error_interrupt : 1;
    //! interrupt if ::dma_status_t::tcm_error set
    uint tcm_error_interrupt : 1;
    //! interrupt if ::dma_status_t::axi_error set
    uint axi_error_interrupt : 1;
    //! interrupt if ::dma_status_t::user_abort set
    uint user_abort_interrupt : 1;
    //! interrupt if ::dma_status_t::soft_reset set
    uint soft_reset_interrupt : 1;
    // not allocated
    uint : 2;
    //! interrupt if ::dma_status_t::write_buffer_error set
    uint write_buffer_error_interrupt : 1;
    // padding
    uint : 10;
    //! system-wide slow timer status and clear
    uint timer : 1;
} dma_global_control_t;

//! DMA timeout register
typedef struct {
    //! Must be zero
    uint _zeroes : 5;
    //! The timeout
    uint value : 5;
    // padding
    uint : 22;
} dma_timeout_t;

//! DMA statistics control register
typedef struct {
    //! Enable collecting DMA statistics
    uint enable : 1;
    //! Clear the statistics registers (if 1)
    uint clear : 1;
    // padding
    uint : 30;
} dma_stats_control_t;

//! DMA controller registers
typedef struct {
    // padding
    const uint _unused1[1];
    //! DMA address on the system interface
    void *sdram_address;
    //! DMA address on the TCM interface
    void *tcm_address;
    //! DMA transfer descriptor; note that setting this commits a DMA
    dma_description_t description;
    //! Control DMA transfer
    dma_control_t control;
    //! Status of DMA and other transfers
    const dma_status_t status;
    //! Control of the DMA device
    dma_global_control_t global_control;
    //! CRC value calculated by CRC block
    const uint crcc;
    //! CRC value in received block
    const uint crcr;
    //! Timeout value
    dma_timeout_t timeout;
    //! Statistics counters control
    dma_stats_control_t statistics_control;
    // padding
    const uint _unused2[5];
    //! Statistics counters
    const uint statistics[8];
    // padding
    const uint _unused3[41];
    //! Active system address
    const void *current_sdram_address;
    //! Active TCM address
    const void *current_tcm_address;
    //! Active transfer description
    const dma_description_t current_description;
    // padding
    const uint _unused4[29];
    //! CRC polynomial matrix
    uint crc_polynomial[32];
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
    struct DOXYNAME(common) {
        //! Packet parity
        uchar parity : 1;
        //! Payload-word-present flag
        uchar payload : 1;
        //! Timestamp (not used for NN packets)
        uchar timestamp : 2;
        // padding
        uchar : 2;
        //! Should be one of ::spinnaker_packet_type_t
        uchar type : 2;
    };
    //! Multicast packet only fields
    struct DOXYNAME(mc) {
        // padding
        uchar : 4;
        //! Emergency routing control
        uchar emergency_routing : 2;
        // padding
        uchar : 2;
    } mc;
    //! Peer-to-peer packet only fields
    struct DOXYNAME(p2p) {
        // padding
        uchar : 4;
        //! Sequence code
        uchar seq_code : 2;
        // padding
        uchar : 2;
    } p2p;
    //! Nearest-neighbour packet only fields
    struct DOXYNAME(nn) {
        // padding
        uchar : 2;
        //! Routing information
        uchar route : 3;
        //! Type indicator
        uchar mem_or_normal : 1;
        // padding
        uchar : 2;
    } nn;
    //! Fixed-route packet only fields
    struct DOXYNAME(fr) {
        // padding
        uchar : 4;
        //! Emergency routing control
        uchar emergency_routing : 2;
        // padding
        uchar : 2;
    } fr;
    uchar value;
} spinnaker_packet_control_byte_t;

//! SpiNNaker packet type codes
enum spinnaker_packet_type_t {
    //! Multicast packet
    SPINNAKER_PACKET_TYPE_MC = 0,
    //! Peer-to-peer packet
    SPINNAKER_PACKET_TYPE_P2P = 1,
    //! Nearest-neighbour packet
    SPINNAKER_PACKET_TYPE_NN = 2,
    //! Fixed-route packet
    SPINNAKER_PACKET_TYPE_FR = 3,
};

//! Controls packet transmission
typedef struct {
    // padding
    uint : 16;
    //! control byte of next sent packet
    uint control_byte : 8;
    // padding
    uint : 4;
    //! Tx buffer not full, so it is safe to send a packet
    uint not_full : 1;
    //! Tx buffer overrun (sticky)
    uint overrun : 1;
    //! Tx buffer full (sticky)
    uint full : 1;
    //! Tx buffer empty
    uint empty : 1;
} comms_tx_control_t;

//! Indicates packet reception status
typedef struct {
    //! error-free multicast packet received
    uint multicast : 1;
    //! error-free point-to-point packet received
    uint point_to_point : 1;
    //! error-free nearest-neighbour packet received
    uint nearest_neighbour : 1;
    //! error-free fixed-route packet received
    uint fixed_route : 1;
    // padding
    uint : 12;
    //! Control byte of last Rx packet
    uint control_byte : 8;
    //! Rx route field from packet
    uint route : 3;
    // padding
    uint : 1;
    //! Rx packet received without error
    uint error_free : 1;
    //! Rx packet framing error (sticky)
    uint framing_error : 1;
    //! Rx packet parity error (sticky)
    uint parity_error : 1;
    //! Rx packet received
    uint received : 1;
} comms_rx_status_t;

//! P2P source address
typedef struct {
    //! 16-bit chip source ID for P2P packets
    uint p2p_source_id : 16;
    // padding
    uint : 8;
    //! Set 'fake' route in packet
    uint route : 3;
    // padding
    uint : 5;
} comms_source_addr_t;

//! SpiNNaker communications controller registers
typedef struct {
    //! Controls packet transmission
    comms_tx_control_t tx_control;
    //! 32-bit data for transmission
    uint tx_data;
    //! Send MC key/P2P dest ID & seq code; writing this commits a send
    uint tx_key;
    //! Indicates packet reception status
    comms_rx_status_t rx_status;
    //! 32-bit received data
    const uint rx_data;
    //! \brief Received MC key/P2P source ID & seq code; reading this clears
    //!     the received packet
    const uint rx_key;
    //! P2P source address
    comms_source_addr_t source_addr;
    //! Used for test purposes
    const uint _test;
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
    //! enable packet routing
    uint route_packets_enable : 1;
    //! enable error packet interrupt
    uint error_interrupt_enable : 1;
    //! enable dump packet interrupt
    uint dump_interrupt_enable : 1;
    //! enable count of packet time stamp errors
    uint count_timestamp_errors : 1;
    //! enable count of packet framing errors
    uint count_framing_errors : 1;
    //! enable count of packet parity errors
    uint count_parity_errors : 1;
    //! time phase (c.f. packet time stamps)
    uint time_phase : 2;
    //! Monitor Processor ID number
    uint monitor_processor : 5;
    // padding
    uint : 2;
    //! re-initialise wait counters
    uint reinit_wait_counters : 1;
    //! `wait1`; wait time before emergency routing
    uint begin_emergency_wait_time : 8;
    //! `wait2`; wait time before dropping packet after entering emergency routing
    uint drop_wait_time : 8;
} router_control_t;

//! Router status
typedef struct {
    //! diagnostic counter interrupt active
    uint interrupt_active_for_diagnostic_counter : 16;
    //! busy - active packet(s) in Router pipeline
    uint busy : 1;
    // padding
    uint : 7;
    //! \brief Router output stage status (see ::router_output_stage)
    uint output_stage : 2;
    // padding
    uint : 3;
    //! dump packet interrupt active
    uint interrupt_active_dump : 1;
    //! error packet interrupt active
    uint interrupt_active_error : 1;
    //! combined Router interrupt request
    uint interrupt_active : 1;
} router_status_t;

//! Stages in ::router_status_t::output_stage
enum router_output_stage {
    //! output stage is empty
    ROUTER_OUTPUT_STAGE_EMPTY,
    //! output stage is full but unblocked
    ROUTER_OUTPUT_STAGE_FULL,
    //! output stage is blocked in `wait1`
    ROUTER_OUTPUT_STAGE_WAIT1,
    //! output stage is blocked in `wait2`
    ROUTER_OUTPUT_STAGE_WAIT2
};

//! Router error/dump header
typedef union {
    //! Fields in ::router_packet_header_t
    struct DOXYNAME(flags) {
        // padding
        uint : 6;
        //! time phase when packet received/dumped
        uint time_phase : 2;
        // padding
        uint : 8;
        //! control byte; really a ::spinnaker_packet_control_byte_t
        uint control : 8;
        //! Rx route field of packet
        uint route : 3;
        //! packet time stamp error (error only)
        uint time_phase_error : 1;
        //! packet framing error (error only)
        uint framing_error : 1;
        //! packet parity error (error only)
        uint parity_error : 1;
        // padding
        uint : 2;
    };
    //! Critical fields in ::router_packet_header_t::flags::control
    struct DOXYNAME(control_field_bits) {
        // padding
        uint : 17;
        //! payload-present field from control byte
        uint payload : 1;
        // padding
        uint : 4;
        //! packet-type field from control byte
        uint type : 2;
    };
    //! as a whole word
    uint word;
} router_packet_header_t;

//! Router error status
typedef struct {
    //! 16-bit saturating error count
    uint error_count : 16;
    // padding
    uint : 11;
    //! packet time stamp error (sticky)
    uint time_phase_error : 1;
    //! packet framing error (sticky)
    uint framing_error : 1;
    //! packet parity error (sticky)
    uint parity_error : 1;
    //! more than one error packet detected
    uint overflow : 1;
    //! error packet detected
    uint error : 1;
} router_error_status_t;

//! Router dump outputs
typedef struct {
    //! Tx link transmit error caused packet dump
    uint link : NUM_LINKS;
    //! Fascicle Processor link error caused dump
    uint processor : NUM_CPUS;
    // padding
    uint : 8;
} router_dump_outputs_t;

//! Router dump status
typedef struct {
    //! Tx link error caused dump (sticky)
    uint link : NUM_LINKS;
    //! Fascicle Proc link error caused dump (sticky)
    uint processor : NUM_CPUS;
    // padding
    uint : 6;
    //! more than one packet dumped
    uint overflow : 1;
    //! packet dumped
    uint dumped : 1;
} router_dump_status_t;

//! Router diagnostic counter enable/reset
typedef struct {
    //! enable diagnostic counter 15..0
    ushort enable;
    //! write a 1 to reset diagnostic counter 15..0
    ushort reset;
} router_diagnostic_counter_ctrl_t;

//! Router timing counter controls
typedef struct {
    //! enable cycle counter
    uint enable_cycle_count : 1;
    //! enable emergency router active cycle counter
    uint enable_emergency_active_count : 1;
    //! enable histogram
    uint enable_histogram : 1;
    // padding
    uint : 13;
    //! reset cycle counter
    uint reset_cycle_count : 1;
    //! reset emergency router active cycle counter
    uint reset_emergency_active_count : 1;
    //! reset histogram
    uint reset_histogram : 1;
    // padding
    uint : 13;
} router_timing_counter_ctrl_t;

//! Router diversion rules, used to handle default-routed packets
typedef struct {
    //! Diversion rule for link 0
    uint L0 : 2;
    //! Diversion rule for link 1
    uint L1 : 2;
    //! Diversion rule for link 2
    uint L2 : 2;
    //! Diversion rule for link 3
    uint L3 : 2;
    //! Diversion rule for link 4
    uint L4 : 2;
    //! Diversion rule for link 5
    uint L5 : 2;
    // padding
    uint : 20;
} router_diversion_t;

//! Diversion rules for the fields of ::router_diversion_t
enum router_diversion_rule_t {
    //! Send on default route
    ROUTER_DIVERSION_NORMAL,
    //! Divert to local monitor
    ROUTER_DIVERSION_MONITOR,
    //! Destroy default-routed packets
    ROUTER_DIVERSION_DESTROY
};

//! Fixed route and nearest neighbour packet routing control
typedef struct {
    //! The links to route FR packets along
    uint fr_links : NUM_LINKS;
    //! The _physical_ processors to route FR packets to
    uint fr_processors : NUM_CPUS;
    // padding
    uint : 2;
    //! Nearest-neighbour broadcast link vector
    uint nn_broadcast_links : NUM_LINKS;
} router_fixed_route_routing_t;

//! SpiNNaker router controller registers
typedef struct {
    //! Router control register
    router_control_t control;
    //! Router status
    const router_status_t status;
    //! Error-related registers
    struct DOXYNAME(error) {
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
    struct DOXYNAME(dump) {
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
    //! packet type: fr, nn, p2p, mc
    uint type : 4;
    //! Emergency Routing field = 3, 2, 1 or 0
    uint emergency_routing : 4;
    //! Emergency Routing mode
    uint emergency_routing_mode : 1;
    // padding
    uint : 1;
    //! default [x1]/non-default [1x] routed packets
    uint pattern_default : 2;
    //! packets with [x1]/without [1x] payload
    uint pattern_payload : 2;
    //! local [x1]/non-local[1x] packet source
    uint pattern_local : 2;
    //! packet dest (Tx link[5:0], MP, local ¬MP, dump)
    uint pattern_destination : 9;
    // padding
    uint : 4;
    //! counter event has occurred (sticky)
    uint counter_event_occurred : 1;
    //! enable interrupt on counter event
    uint enable_counter_event_interrupt : 1;
    //! counter interrupt active: I = E AND C
    uint counter_event_interrupt_active : 1;
} router_diagnostic_filter_t;

//! SpiNNaker router multicast route
typedef union {
    //! Where to route a matching entry to
    struct DOXYNAME(routes) {
        //! The links to route along
        uint links : NUM_LINKS;
        //! The _physical_ processors to route to
        uint processors : NUM_CPUS;
    };
    //! Overall entry packed as number
    uint value;
} router_multicast_route_t;

//! The possible values of a P2P route
typedef enum {
    //! Route east
    ROUTER_P2P_ROUTE_E,
    //! Route north-east
    ROUTER_P2P_ROUTE_NE,
    //! Route north
    ROUTER_P2P_ROUTE_N,
    //! Route west
    ROUTER_P2P_ROUTE_W,
    //! Route south-west
    ROUTER_P2P_ROUTE_SW,
    //! Route south
    ROUTER_P2P_ROUTE_S,
    //! Drop packet
    ROUTER_P2P_ROUTE_DROP,
    //! Send to monitor (as determined by
    //! ::router_control_t::monitor_processor)
    ROUTER_P2P_ROUTE_MONITOR
} router_p2p_route;

//! A packed word in the P2P routing table
typedef union {
    //! The eight individual routes making up a P2P table entry
    struct DOXYNAME(routes) {
        //! First packed route
        router_p2p_route route1 : 3;
        //! Second packed route
        router_p2p_route route2 : 3;
        //! Third packed route
        router_p2p_route route3 : 3;
        //! Fourth packed route
        router_p2p_route route4 : 3;
        //! Fifth packed route
        router_p2p_route route5 : 3;
        //! Sixth packed route
        router_p2p_route route6 : 3;
        //! Seventh packed route
        router_p2p_route route7 : 3;
        //! Eighth packed route
        router_p2p_route route8 : 3;
    };
    //! Overall entry packed as number
    uint value;
} router_p2p_table_entry_t;

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
ASSERT_WORD_SIZED(router_multicast_route_t);
ASSERT_WORD_SIZED(router_p2p_table_entry_t);

//! Router controller registers
static volatile router_t *const router_control = (router_t *) RTR_BASE;
//! Router diagnostic filters
static volatile router_diagnostic_filter_t *const router_diagnostic_filter =
        (router_diagnostic_filter_t *) (RTR_BASE + 0x200);
//! Router diagnostic counters
static volatile uint *const router_diagnostic_counter =
        (uint *) (RTR_BASE + 0x300);
//! Router multicast route table
static volatile router_multicast_route_t *const router_multicast_table =
        (router_multicast_route_t *) RTR_MCRAM_BASE;
//! Router multicast key table (write only!)
static volatile uint *const router_key_table = (uint *) RTR_MCKEY_BASE;
//! Router multicast mask table (write only!)
static volatile uint *const router_mask_table = (uint *) RTR_MCMASK_BASE;
//! Router peer-to-peer route table
static volatile router_p2p_table_entry_t *const router_p2p_route_table =
        (router_p2p_table_entry_t *) RTR_P2P_BASE;

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
    //! Config, ready, paused, low-power
    uint status : 2;
    //! Width of external memory: 2’b01 = 32 bits
    uint width : 2;
    //! DDR type: 3b’011 = Mobile DDR
    uint ddr : 3;
    //! Number of different chip selects (1, 2, 3, 4)
    uint chips : 2;
    //! Fixed at 1’b01 = 4 banks on a chip
    uint banks : 1;
    //! Number of exclusive access monitors (0, 1, 2, 4)
    uint monitors : 2;
    // padding
    uint : 20;
} sdram_status_t;

//! Memory controller command
typedef struct {
    //! one of ::sdram_command
    uint command : 3;
} sdram_command_t;

//! \brief Memory controller commands, for ::sdram_command_t::command
//! \todo Verify ::SDRAM_CTL_SLEEP, ::SDRAM_CTL_WAKE, ::SDRAM_CTL_ACTIVE_PAUSE
enum sdram_command {
    //! Go
    SDRAM_CTL_GO,
    //! Sleep
    SDRAM_CTL_SLEEP,
    //! Wake
    SDRAM_CTL_WAKE,
    //! Pause
    SDRAM_CTL_PAUSE,
    //! Configure
    SDRAM_CTL_CONFIG,
    //! Active Pause
    SDRAM_CTL_ACTIVE_PAUSE
};

//! \brief Memory controller direct command
//! \details Used to pass a command directly to a memory device attached to the
//!     PL340.
typedef struct {
    //! address passed to memory device
    uint address : 14;
    // padding
    uint : 2;
    //! bank passed to memory device
    uint bank : 2;
    //! command passed to memory device
    uint cmd : 2;
    //! chip number
    uint chip : 2;
    // padding
    uint : 10;
} sdram_direct_command_t;

//! \brief Memory direct commands, for ::sdram_direct_command_t::cmd
//! \details Codes from SARK (sark_hw.c, pl340_init)
enum sdram_direct_command {
    //! Precharge
    SDRAM_DIRECT_PRECHARGE = 0,
    //! Auto-Refresh
    SDRAM_DIRECT_AUTOREFRESH = 1,
    //! Mode Register
    SDRAM_DIRECT_MODEREG = 2,
    //! No-op
    SDRAM_DIRECT_NOP = 3,
};

//! Memory configuration
typedef struct {
    //! number of column address bits (8-12)
    uint column : 3;
    //! number of row address bits (11-16)
    uint row : 3;
    //! position of auto-pre-charge bit (10/8)
    uint auto_precharge_position : 1;
    //! number of memory cycles before auto-power-down
    uint power_down_delay : 6;
    //! auto-power-down memory when inactive
    uint auto_power_down : 1;
    //! stop memory clock when no access
    uint stop_clock : 1;
    //! burst length (1, 2, 4, 8, 16)
    uint burst : 3;
    //! selects the 4-bit QoS field from the AXI ARID
    uint qos : 3;
    //! active chips: number for refresh generation
    uint active : 2;
    // padding
    uint : 9;
} sdram_ram_config_t;

//! Memory refresh period
typedef struct {
    //! memory refresh period in memory clock cycles
    uint period : 15;
    // padding
    uint : 17;
} sdram_refresh_t;

//! Memory CAS latency
typedef struct {
    //! CAS half cycle - must be set to 1’b0
    uint half_cycle : 1;
    //! CAS latency in memory clock cycles
    uint cas_lat : 3;
    // padding
    uint : 28;
} sdram_cas_latency_t;

//! \brief Memory timimg configuration
//! \details See datasheet for meanings
typedef struct {
    //! write to DQS time
    uint t_dqss;
    //! mode register command time
    uint t_mrd;
    //! RAS to precharge delay
    uint t_ras;
    //! active bank x to active bank x delay
    uint t_rc;
    //! RAS to CAS minimum delay
    uint t_rcd;
    //! auto-refresh command time
    uint t_rfc;
    //! precharge to RAS delay
    uint t_rp;
    //! active bank x to active bank y delay
    uint t_rrd;
    //! write to precharge delay
    uint t_wr;
    //! write to read delay
    uint t_wtr;
    //! exit power-down command time
    uint t_xp;
    //! exit self-refresh command time
    uint t_xsr;
    //! self-refresh command time
    uint t_esr;
} sdram_timing_config_t;

//! Memory controller registers
typedef struct {
    //! memory controller status
    const sdram_status_t status;
    //! PL340 command
    sdram_command_t command;
    //! direct command
    sdram_direct_command_t direct;
    //! memory configuration
    sdram_ram_config_t mem_config;
    //! refresh period
    sdram_refresh_t refresh;
    //! CAS latency
    sdram_cas_latency_t cas_latency;
    //! timing configuration
    sdram_timing_config_t timing_config;
} sdram_controller_t;

//! Memory QoS settings
typedef struct {
    //! QoS enable
    uint enable : 1;
    //! minimum QoS
    uint minimum : 1;
    //! maximum QoS
    uint maximum : 8;
    // padding
    uint : 22;
} sdram_qos_t;

//! Memory chip configuration
typedef struct {
    //! address mask
    uint mask : 8;
    //! address match
    uint match : 8;
    //! bank-row-column/row-bank-column
    uint orientation : 1;
    // padding
    uint : 15;
} sdram_chip_t;

//! Maximum register IDs
enum sdram_register_maxima {
    //! Maximum memory QoS register
    SDRAM_QOS_MAX = 15,
    //! Maximum memory chip configuration register
    SDRAM_CHIP_MAX = 3
};

//! Memory delay-locked-loop (DLL) test and status inputs
typedef struct {
    //! Current position of bar-code output
    uint meter : 7;
    // padding
    uint : 1;
    //! Strobe 0 faster than Clock
    uint s0 : 1;
    //! Clock faster than strobe 0
    uint c0 : 1;
    //! Strobe 1 faster than Clock
    uint s1 : 1;
    //! Clock faster than strobe 1
    uint c1 : 1;
    //! Strobe 2 faster than Clock
    uint s2 : 1;
    //! Clock faster than strobe 2
    uint c2 : 1;
    //! Strobe 3 faster than Clock
    uint s3 : 1;
    //! Clock faster than strobe 3
    uint c3 : 1;
    //! Phase comparator is reducing delay
    uint decing : 1;
    //! Phase comparator is increasing delay
    uint incing : 1;
    //! Phase comparator is locked
    uint locked : 1;
    // padding
    uint : 1;
    //! 3-phase bar-code control output
    uint R : 1;
    //! 3-phase bar-code control output
    uint M : 1;
    //! 3-phase bar-code control output
    uint L : 1;
    // padding
    uint : 9;
} sdram_dll_status_t;

//! Memory delay-locked-loop (DLL) test and control outputs
typedef struct {
    //! Input select for delay line 0 {def, alt, 0, 1}
    uint s0 : 2;
    //! Input select for delay line 1 {def, alt, 0, 1}
    uint s1 : 2;
    //! Input select for delay line 2 {def, alt, 0, 1}
    uint s2 : 2;
    //! Input select for delay line 3 {def, alt, 0, 1}
    uint s3 : 2;
    //! Input select for delay line 4 {def, alt, 0, 1}
    uint s4 : 2;
    //! Input select for delay line 5 {def, alt, 0, 1}
    uint s5 : 2;
    // padding
    uint : 4;
    //! Force Decing (if ID = 1)
    uint test_decing : 1;
    //! Force Incing (if ID = 1)
    uint test_incing : 1;
    //! Enable forcing of Incing and Decing
    uint enable_force_inc_dec : 1;
    //! Substitute delay line 5 for 4 for testing
    uint test_5 : 1;
    //! Force 3-phase bar-code control inputs
    uint R : 1;
    //! Force 3-phase bar-code control inputs
    uint M : 1;
    //! Force 3-phase bar-code control inputs
    uint L : 1;
    //! Enable forcing of L, M, R
    uint enable_force_lmr : 1;
    //! Enable DLL (0 = reset DLL)
    uint enable : 1;
    // padding
    uint : 7;
} sdram_dll_user_config0_t;

//! Memory delay-locked-loop (DLL) fine-tune control
typedef union {
    //! Tuning fields
    struct DOXYNAME(tuning) {
        //! Fine tuning control on delay line 0
        uint tune_0 : 4;
        //! Fine tuning control on delay line 1
        uint tune_1 : 4;
        //! Fine tuning control on delay line 2
        uint tune_2 : 4;
        //! Fine tuning control on delay line 3
        uint tune_3 : 4;
        //! Fine tuning control on delay line 4
        uint tune_4 : 4;
        //! Fine tuning control on delay line 5
        uint tune_5 : 4;
        // padding
        uint : 8;
    };
    //! Tuning control word
    uint word;
} sdram_dll_user_config1_t;

//! SDRAM delay-locked-loop (DLL) control registers
typedef struct {
    //! Status
    const sdram_dll_status_t status;
    //! Test: control
    sdram_dll_user_config0_t config0;
    //! Test: fine tune
    sdram_dll_user_config1_t config1;
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
//! \details Features:
//!
//! * 'Arbiter' read-sensitive register bit to determine Monitor Processor ID
//!   at start-up.
//! * 32 test-and-set registers for general software use, e.g. to enforce
//!   mutually exclusive access to critical data structures.
//! * individual interrupt, reset and enable controls and 'processor OK'
//!   status bits for each processor.
//! * sundry parallel IO and test and control registers.
//! * PLL and clock management registers.
//! \note All processor IDs should be _physical_ processor IDs.
//! \{

//! \brief System controller processor select
typedef struct {
    //! Bit-map for selecting a processor
    uint select : NUM_CPUS;
    // padding
    uint : 2;
    //! ::SYSTEM_CONTROLLER_MAGIC_NUMBER to enable write
    uint security_code : 12;
} sc_magic_proc_map_t;

//! System controller subsystem reset target select
typedef struct {
    //! Router
    uint router : 1;
    //! PL340 SDRAM controller
    uint sdram : 1;
    //! System NoC
    uint system_noc : 1;
    //! Communications NoC
    uint comms_noc : 1;
    //! Tx link 0-5
    uint tx_links : NUM_LINKS;
    //! Rx link 0-5
    uint rx_links : NUM_LINKS;
    //! System AHB & Clock Gen (pulse reset only)
    uint clock_gen : 1;
    //! Entire chip (pulse reset only)
    uint entire_chip : 1;
    // padding
    uint : 2;
    //! ::SYSTEM_CONTROLLER_MAGIC_NUMBER to enable write
    uint security_code : 12;
} sc_magic_subsystem_map_t;

//! System controller last reset status
typedef struct {
    //! One of ::sc_reset_codes
    uint reset_code : 3;
    // padding
    uint : 29;
} sc_reset_code_t;

//! System controller chip reset reasons
enum sc_reset_codes {
    //! Power-on reset
    SC_RESET_CODE_POR,
    //! Watchdog reset
    SC_RESET_CODE_WDR,
    //! User reset
    SC_RESET_CODE_UR,
    //! Reset entire chip (::sc_magic_subsystem_map_t::entire_chip)
    SC_RESET_CODE_REC,
    //! Watchdog interrupt
    SC_RESET_CODE_WDI
};

//! System controller monitor election control
typedef struct {
    //! Monitor processor identifier
    uint monitor_id : 5;
    // padding
    uint : 3;
    //! Write 1 to set MP arbitration bit (see ::system_controller_t::monitor_arbiter)
    uint arbitrate_request : 1;
    // padding
    uint : 7;
    //! Reset Monitor Processor on Watchdog interrupt
    uint reset_on_watchdog : 1;
    // padding
    uint : 3;
    //! ::SYSTEM_CONTROLLER_MAGIC_NUMBER to enable write
    uint security_code : 12;
} sc_monitor_id_t;

//! System controller miscellaneous control
typedef struct {
    //! map System ROM (0) or RAM (1) to Boot area
    uint boot_area_map : 1;
    // padding
    uint : 14;
    //! select on-chip (1) or off-chip (0) control of JTAG pins
    uint jtag_on_chip : 1;
    //! read value on Test pin
    uint test : 1;
    //! read value on Ethermux pin
    uint ethermux : 1;
    //! read value on Clk32 pin
    uint clk32 : 1;
    //! read value on JTAG_TDO pin
    uint jtag_tdo : 1;
    //! read value on JTAG_RTCK pin
    uint jtag_rtck : 1;
    // padding
    uint : 11;
} sc_misc_control_t;

//! System controller general chip I/O pin access
typedef union {
    //! Control over I/O pins used for non-GPIO purposes
    struct DOXYNAME(io_bits) {
        // padding
        uint : 16;
        //! Ethernet MII RxD port
        uint ethernet_receive : 4;
        //! Ethernet MII TxD port
        uint ethernet_transmit : 4;
        //! JTAG interface
        uint jtag : 4;
        // padding
        uint : 1;
        //! On-package SDRAM control
        uint sdram : 3;
    };
    //! GPIO pins
    uint gpio;
} sc_io_t;

//! System controller phase-locked-loop control
typedef struct {
    //! input clock multiplier
    uint input_multiplier : 6;
    // padding
    uint : 2;
    //! output clock divider
    uint output_divider : 6;
    // padding
    uint : 2;
    //! frequency range (see ::sc_frequency_range)
    uint freq_range : 2;
    //! Power UP
    uint power_up : 1;
    // padding
    uint : 5;
    //! test (=0 for normal operation)
    uint _test : 1;
    // padding
    uint : 7;
} sc_pll_control_t;

//! Frequency range constants for ::sc_pll_control_t::freq_range
enum sc_frequency_range {
    //! 25-50 MHz
    FREQ_25_50,
    //! 50-100 MHz
    FREQ_50_100,
    //! 100-200 MHz
    FREQ_100_200,
    //! 200-400 MHz
    FREQ_200_400
};

//! System controller clock multiplexing control
typedef struct {
    //! clock selector for A CPUs (1 2 4 7 8 11 13 14 16); see ::sc_clock_source
    uint pa : 2;
    //! divide CPU clock A by Adiv+1 (= 1-4)
    uint adiv : 2;
    // padding
    uint : 1;
    //! clock selector for B CPUs (0 3 5 6 9 10 12 15 17); see ::sc_clock_source
    uint pb : 2;
    //! divide CPU clock B by Bdiv+1 (= 1-4)
    uint bdiv : 2;
    // padding
    uint : 1;
    //! clock selector for SDRAM; see ::sc_clock_source
    uint mem : 2;
    //! divide SDRAM clock by Mdiv+1 (= 1-4)
    uint mdiv : 2;
    // padding
    uint : 1;
    //! clock selector for Router; see ::sc_clock_source
    uint rtr : 2;
    //! divide Router clock by Rdiv+1 (= 1-4)
    uint rdiv : 2;
    // padding
    uint : 1;
    //! clock selector for System AHB components; see ::sc_clock_source
    uint sys : 2;
    //! divide System AHB clock by Sdiv+1 (= 1-4)
    uint sdiv : 2;
    // padding
    uint : 7;
    //! invert CPU clock B
    uint invert_b : 1;
} sc_clock_mux_t;

//! \brief System controller clock sources
//! \details Used for ::sc_clock_mux_t::pa, ::sc_clock_mux_t::pb,
//!     ::sc_clock_mux_t::mem, ::sc_clock_mux_t::rtr, ::sc_clock_mux_t::sys
enum sc_clock_source {
    //! external 10MHz clock input
    CLOCK_SRC_EXT,
    //! PLL1
    CLOCK_SRC_PLL1,
    //! PLL2
    CLOCK_SRC_PLL2,
    //! external 10MHz clock divided by 4
    CLOCK_SRC_EXT4
};

//! System controller sleep status
typedef struct {
    //! ARM968 STANDBYWFI signal for each core
    uint status : NUM_CPUS;
    // padding
    uint : 14;
} sc_sleep_status_t;

//! System controller temperature status/control
typedef struct {
    //! temperature sensor reading
    uint temperature : 24;
    //! temperature measurement finished
    uint sample_finished : 1;
    // padding
    uint : 6;
    //! start temperature measurement
    uint start : 1;
} sc_temperature_t;

//! System controller mutex/interlock
typedef struct {
    // padding
    uint : 31;
    //! The only relevant bit in the word
    uint bit : 1;
} sc_mutex_bit_t;

//! System controller link and router control
typedef struct {
    //! disables the corresponding link receiver
    uint rx_disable : NUM_LINKS;
    // padding
    uint : 2;
    //! disables the corresponding link transmitter
    uint tx_disable : NUM_LINKS;
    // padding
    uint : 2;
    //! Router parity control
    uint parity_control : 1;
    // padding
    uint : 3;
    //! ::SYSTEM_CONTROLLER_MAGIC_NUMBER to enable write
    uint security_code : 12;
} sc_link_disable_t;

#define _NUM_TEMPS              3
#define _NUM_ARBITERS           32
#define _NUM_LOCK_REGISTERS     32

//! System controller registers
typedef struct {
    //! Chip ID register (hardwired)
    const uint chip_id;
    //! Each bit disables a processor
    sc_magic_proc_map_t processor_disable;
    //! Writing a 1 sets a processor’s interrupt line
    sc_magic_proc_map_t set_cpu_irq;
    //! Writing a 1 clears a processor’s interrupt line
    sc_magic_proc_map_t clear_cpu_irq;
    //! Writing a 1 sets a CPU OK bit
    uint set_cpu_ok;
    //! Writing a 1 clears a CPU OK bit
    uint clear_cpu_ok;
    //! Level control of CPU resets
    sc_magic_proc_map_t cpu_soft_reset_level;
    //! Level control of CPU node resets
    sc_magic_proc_map_t cpu_hard_reset_level;
    //! Level control of subsystem resets
    sc_magic_subsystem_map_t subsystem_reset_level;
    //! Pulse control of CPU resets
    sc_magic_proc_map_t cpu_soft_reset_pulse;
    //! Pulse control of CPU node resets
    sc_magic_proc_map_t cpu_hard_reset_pulse;
    //! Pulse control of subsystem resets
    sc_magic_subsystem_map_t subsystem_reset_pulse;
    //! Indicates cause of last chip reset
    const sc_reset_code_t reset_code;
    //! ID of Monitor Processor
    sc_monitor_id_t monitor_id;
    //! Miscellaneous control bits
    sc_misc_control_t misc_control;
    //! General-purpose IO pull up/down enable
    sc_io_t gpio_pull_up_down_enable;
    //! I/O pin output register
    sc_io_t io_port;
    //! External I/O pin is input (1) or output (0)
    sc_io_t io_direction;
    //! Writing a 1 sets IO register bit
    sc_io_t io_set;
    //! Writing a 1 clears IO register bit
    sc_io_t io_clear;
    //! PLL1 frequency control
    sc_pll_control_t pll1_freq_control;
    //! PLL2 frequency control
    sc_pll_control_t pll2_freq_control;
    //! Set flags register
    uint set_flags;
    //! Reset flags register
    uint reset_flags;
    //! Clock multiplexer controls
    sc_clock_mux_t clock_mux_control;
    //! CPU sleep (awaiting interrupt) status
    const sc_sleep_status_t cpu_sleep;
    //! Temperature sensor registers [2:0]
    sc_temperature_t temperature[_NUM_TEMPS];
    // padding
    const uint _padding[3];
    //! Read sensitive semaphores to determine MP
    const sc_mutex_bit_t monitor_arbiter[_NUM_ARBITERS];
    //! Test & Set registers for general software use
    const sc_mutex_bit_t test_and_set[_NUM_LOCK_REGISTERS];
    //! Test & Clear registers for general software use
    const sc_mutex_bit_t test_and_clear[_NUM_LOCK_REGISTERS];
    //! Disables for Tx and Rx link interfaces
    sc_link_disable_t link_disable;
} system_controller_t;

//! System controller magic numbers
enum sc_magic {
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
//! \note
//!     The implementation does not provide support for half-duplex operation
//!     (as required by a CSMA/CD MAC algorithm), jumbo or VLAN frames.
//! \{

//! Ethernet general command
typedef struct {
    //! Transmit system enable
    uint transmit : 1;
    //! Receive system enable
    uint receive : 1;
    //! Loopback enable
    uint loopback : 1;
    //! Receive error filter enable
    uint receive_error_filter : 1;
    //! Receive unicast packets enable
    uint receive_unicast: 1;
    //! Receive multicast packets enable
    uint receive_multicast : 1;
    //! Receive broadcast packets enable
    uint receive_broadcast : 1;
    //! Receive promiscuous packets enable
    uint receive_promiscuous : 1;
    //! Receive VLAN enable
    uint receive_vlan : 1;
    //! Reset receive dropped frame count (::ethernet_general_status_t::drop_counter)
    uint reset_drop_counter : 1;
    //! Disable hardware byte reordering
    uint hardware_byte_reorder_disable : 1;
    // padding
    uint : 21;
} ethernet_general_command_t;

//! Ethernet general status
typedef struct {
    //! Transmit MII interface active
    uint transmit_active : 1;
    //! Received unread frame count
    uint unread_counter : 6;
    // padding
    uint : 9;
    //! Receive dropped frame count
    uint drop_counter : 16;
} ethernet_general_status_t;

//! Ethernet frame transmit length
typedef struct {
    //! Length of transmit frame (60 - 1514 bytes)
    uint tx_length : 11;
} ethernet_tx_length_t;

//! Limits of ::ethernet_tx_length_t::tx_length
enum ethernet_tx_length_limits {
    //! Minimum length of an ethernet frame
    ETHERNET_TX_LENGTH_MIN = 60,
    //! Maximum length of an ethernet frame
    ETHERNET_TX_LENGTH_MAX = 1514
};

//! Ethernet PHY (physical layer) control
typedef struct {
    //! PHY reset (active low)
    uint reset : 1;
    //! SMI data input
    uint smi_input : 1;
    //! SMI data output
    uint smi_output : 1;
    //! SMI data output enable
    uint smi_out_enable : 1;
    //! SMI clock (active rising)
    uint smi_clock : 1;
    //! PHY IRQn invert disable
    uint irq_invert_disable : 1;
    // padding
    uint : 26;
} ethernet_phy_control_t;

//! Ethernet interrupt clear register
typedef struct {
    //! Clear transmit interrupt request
    uint transmit : 1;
    // padding
    uint : 3;
    //! Clear receive interrupt request
    uint receive : 1;
    // padding
    uint : 27;
} ethernet_interrupt_clear_t;

//! Ethernet receive data pointer
typedef struct {
    //! Receive frame buffer read pointer
    uint ptr : 12;
    //! Rollover bit - toggles on address wrap-around
    uint rollover : 1;
    // padding
    uint : 19;
} ethernet_receive_pointer_t;

//! Ethernet receive descriptor pointer
typedef struct {
    //! Receive descriptor read pointer
    uint ptr : 6;
    //! Rollover bit - toggles on address wrap-around
    uint rollover : 1;
    // padding
    uint : 25;
} ethernet_receive_descriptor_pointer_t;

//! Ethernet controller registers
typedef struct {
    //! General command
    ethernet_general_command_t command;
    //! General status
    const ethernet_general_status_t status;
    //! Transmit frame length
    ethernet_tx_length_t transmit_length;
    //! Transmit command; any value commits transmit
    uint transmit_command;
    //! Receive command; any value completes receive
    uint receive_command;
    //! MAC address; low 48 bits only
    uint64 mac_address;
    //! PHY control
    ethernet_phy_control_t phy_control;
    //! Interrupt clear
    ethernet_interrupt_clear_t interrupt_clear;
    //! Receive frame buffer read pointer
    const ethernet_receive_pointer_t receive_read;
    //! Receive frame buffer write pointer
    const ethernet_receive_pointer_t receive_write;
    //! Receive descriptor read pointer
    const ethernet_receive_descriptor_pointer_t receive_desc_read;
    //! Receive descriptor write pointer
    const ethernet_receive_descriptor_pointer_t receive_desc_write;
    //! debug & test use only
    uint _test[3];
} ethernet_controller_t;

//! \brief Ethernet received message descriptor.
//! \warning Cannot find description of rest of this structure; SCAMP only
//!     uses one field. Datasheet refers document that appears to be lost.
typedef struct {
    //! Received packet length
    uint length : 11;
    // unknown; might be padding or status bits?
    uint : 21;
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
    //! Enable Watchdog counter and interrupt (1)
    uint interrupt_enable : 1;
    //! Enable the Watchdog reset output (1)
    uint reset_enable : 1;
    // padding
    uint : 30;
} watchdog_control_t;

//! Watchdog timer status registers
typedef struct {
    //! True if interrupt asserted
    uint interrupted : 1;
    // padding
    uint : 31;
} watchdog_status_t;

//! Watchdog timer lock register
typedef union {
    //! The fields in the lock register
    struct DOXYNAME(fields) {
        //! Write access enabled (0) or disabled (1)
        uint lock : 1;
        //! Access control code
        uint magic : 31;
    };
    //! Whole value of lock; see ::watchdog_lock_codes
    uint whole_value;
} watchdog_lock_t;

//! Watchdog timer lock codes, for ::watchdog_lock_t::whole_value
enum watchdog_lock_codes {
    //! Put the watchdog timer into normal mode
    WATCHDOG_LOCK_RESET = 0,
    //! Unlock the watchdog timer for configuration
    WATCHDOG_LOCK_MAGIC = WD_CODE
};

//! Watchdog timer control registers
typedef struct {
    //! Count load register
    uint load;
    //! Current count value
    const uint value;
    //! Control register
    watchdog_control_t control;
    //! Interrupt clear register; any written value will do
    uint interrupt_clear;
    //! Raw interrupt status register
    const watchdog_status_t raw_status;
    //! Masked interrupt status register
    const watchdog_status_t masked_status;
    // Lots of padding!
    const uint _padding[0x2fa];
    //! Lock register
    watchdog_lock_t lock;
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

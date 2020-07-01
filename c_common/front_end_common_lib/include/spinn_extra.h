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

//! \}

// ---------------------------------------------------------------------
//! \name 6. Counter/Timer
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

//! \}

// ---------------------------------------------------------------------
//! \name 7. DMA Controller
//! \{

//! DMA descriptor
typedef struct {
    uint _zeroes : 2;       //!< Must be zero
    uint length_words : 15; //!< length of the DMA transfer, in words
    uint : 2;
    uint direction : 1;     //!< read from (0) or write to (1) system bus
    uint crc : 1;           //!< check (read) or generate (write) CRC
    uint burst : 3;         //!< burst length = 2<sup>B</sup>&times;Width, B = 0..4 (i.e max 16)
    uint width : 1;         //!< transfer width is word (0) or double-word (1)
    uint privilege : 1;     //!< DMA transfer mode is user (0) or privileged (1)
    uint transfer_id : 6;   //!< software defined transfer ID
} dma_description_t;

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
    uint : 2;
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
    uint : 2;
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

//! \}

// ---------------------------------------------------------------------
//! \name 8. Communications controller
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
    volatile uint tx_key;       //!< Send MC key/P2P dest ID & seq code; writing this commits a send
    comms_rx_status_t rx_status; //!< Indicates packet reception status
    const uint rx_data;         //!< 32-bit received data
    volatile const uint rx_key; //!< Received MC key/P2P source ID & seq code; reading this clears the received packet
    comms_source_addr_t source_addr; //!< P2P source address
    const uint _test;           //!< Used for test purposes
} comms_ctl_t;

ASSERT_WORD_SIZED(comms_tx_control_t);
ASSERT_WORD_SIZED(comms_rx_status_t);
ASSERT_WORD_SIZED(comms_source_addr_t);

//! \}

// ---------------------------------------------------------------------
// 9. Communications NoC

// No registers

// ---------------------------------------------------------------------
//! \name 10. SpiNNaker Router
//! \{

typedef struct {
    uint route_packets_enable : 1;
    uint error_interrupt_enable : 1;
    uint dump_interrupt_enable : 1;
    uint count_timestamp_errors : 1;
    uint count_framing_errors : 1;
    uint count_parity_errors : 1;
    uint time_phase : 2;
    uint monitor_processor : 5;
    uint : 2;
    uint reinit_wait_counters : 1;
    uint begin_emergency_wait_time : 8;
    uint drop_wait_time : 8;
} router_control_t;

typedef struct {
    uint interrupt_active_for_diagnostic_counter : 16;
    uint busy : 1;
    uint : 7;
    uint output_stage : 2;
    uint : 3;
    uint interrupt_active_dump : 1;
    uint interrupt_active_error : 1;
    uint interrupt_active : 1;
} router_status_t;

enum output_stage {
    output_stage_empty,
    output_stage_full,
    output_stage_wait1,
    output_stage_wait2
};

typedef union {
    struct {
        uint : 6;
        uint time_phase : 2;
        uint : 8;
        uint control : 8;
        uint route : 3;
        uint time_phase_error : 1;
        uint framing_error : 1;
        uint parity_error : 1;
        uint : 2;
    };
    struct {
        uint : 17;
        uint payload : 1;
        uint : 4;
        uint type : 2;
    };
    uint word;
} router_packet_header_t;

typedef struct {
    uint error_count : 16;
    uint : 11;
    uint time_phase_error : 1;
    uint framing_error : 1;
    uint parity_error : 1;
    uint overflow : 1;
    uint error : 1;
} router_error_status_t;

typedef struct {
    uint link : 6;
    uint processor : 18;
    uint : 8;
} router_dump_outputs_t;

typedef struct {
    uint link : 6;
    uint processor : 18;
    uint : 6;
    uint overflow : 1;
    uint dumped : 1;
} router_dump_status_t;

typedef struct {
    ushort enable;
    ushort reset;
} router_diagnostic_counter_ctrl_t;

typedef struct {
    uint enable_cycle_count : 1;
    uint enable_emergency_active_count : 1;
    uint enable_histogram : 1;
    uint : 13;
    uint reset_cycle_count : 1;
    uint reset_emergency_active_count : 1;
    uint reset_histogram : 1;
    uint : 13;
} router_timing_counter_ctrl_t;

typedef struct {
    uint L0 : 2;
    uint L1 : 2;
    uint L2 : 2;
    uint L3 : 2;
    uint L4 : 2;
    uint L5 : 2;
    uint : 20;
} router_diversion_t;

typedef struct {
    uint fixed_route_vector : 24;
    uint : 2;
    uint nearest_neighbour_broadcast : 6;
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

//! SpiNNaker router diagnostics
typedef struct {
    uint type : 4;
    uint emergency_routing : 4;
    uint emergency_routing_mode : 1;
    uint : 1;
    uint pattern_default : 2;
    uint pattern_payload : 2;
    uint pattern_local : 2;
    uint pattern_destination : 9;
    uint : 4;
    uint counter_event_occurred : 1;
    uint enable_counter_event_interrupt : 1;
    uint counter_event_interrupt_active : 1;
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

//! \}

// ---------------------------------------------------------------------
// 11. Inter-chip transmit and receive interfaces

// No registers

// ---------------------------------------------------------------------
// 12. System NoC

// No registers

// ---------------------------------------------------------------------
//! \name 13. SDRAM interface
//! \warning Do not use these structures without talking to Luis!
//! \{

typedef struct {
    uint status : 2;
    uint width : 2;
    uint ddr : 3;
    uint chips : 2;
    uint banks : 1;
    uint monitors : 2;
    uint : 20;
} sdram_status_t;

typedef struct {
    uint command : 3;
} sdram_command_t;

enum sdram_command {
    SDRAM_CTL_GO,
    SDRAM_CTL_SLEEP,            // TODO: verify this value
    SDRAM_CTL_WAKE,             // TODO: verify this value
    SDRAM_CTL_PAUSE,
    SDRAM_CTL_CONFIG,
    SDRAM_CTL_ACTIVE_PAUSE      // TODO: verify this value
};

typedef struct {
    uint address : 14;
    uint : 2;
    uint bank : 2;
    uint cmd : 2;
    uint chip : 2;
    uint : 10;
} sdram_direct_command_t;

enum sdram_direct_command {
    // Codes from SARK (sark_hw.c, pl340_init)
    SDRAM_DIRECT_PRECHARGE = 0,
    SDRAM_DIRECT_AUTOREFRESH = 1,
    SDRAM_DIRECT_MODEREG = 2,
    SDRAM_DIRECT_NOP = 3,
};

typedef struct {
    uint column : 3;
    uint row : 3;
    uint auto_precharge_position : 1;
    uint power_down_delay : 6;
    uint auto_power_down : 1;
    uint stop_clock : 1;
    uint burst : 3;
    uint qos : 3;
    uint active : 2;
    uint : 9;
} sdram_ram_config_t;

typedef struct {
    uint period : 15;
    uint : 17;
} sdram_refresh_t;

typedef struct {
    // See datasheet for meanings
    uint cas_latency;
    uint t_dqss;
    uint t_mrd;
    uint t_ras;
    uint t_rc;
    uint t_rcd;
    uint t_rfc;
    uint t_rp;
    uint t_rrd;
    uint t_wr;
    uint t_wtr;
    uint t_xp;
    uint t_xsr;
    uint t_esr;
} sdram_timing_config_t;

//! SDRAM control registers
typedef struct {
    const sdram_status_t status;
    sdram_command_t command;
    sdram_direct_command_t direct;
    sdram_ram_config_t mem_config;
    sdram_refresh_t refresh;
    sdram_timing_config_t timing_config; // 14 words
} sdram_controller_t;

typedef struct {
    uint enable : 1;
    uint minimum : 1;
    uint maximum : 8;
    uint : 22;
} sdram_qos_t;

typedef struct {
    uint mask : 8;
    uint match : 8;
    uint orientation : 1;
    uint : 15;
} sdram_chip_t;

enum {
    SDRAM_QOS_MAX = 15,
    SDRAM_CHIP_MAX = 3
};

typedef struct {
    uint meter : 7;
    uint : 1;
    uint s0 : 1;
    uint c0 : 1;
    uint s1 : 1;
    uint c1 : 1;
    uint s2 : 1;
    uint c2 : 1;
    uint s3 : 1;
    uint c3 : 1;
    uint decing : 1;
    uint incing : 1;
    uint locked : 1;
    uint : 1;
    uint R : 1;
    uint M : 1;
    uint L : 1;
    uint : 9;
} sdram_dll_status_t;

typedef struct {
    uint s0 : 2;
    uint s1 : 2;
    uint s2 : 2;
    uint s3 : 2;
    uint s4 : 2;
    uint s5 : 2;
    uint : 4;
    uint test_decing : 1;
    uint test_incing : 1;
    uint enable_force_inc_dec : 1;
    uint test_5 : 1;
    uint R : 1;
    uint M : 1;
    uint L : 1;
    uint enable_force_lmr : 1;
    uint enable : 1;
    uint : 7;
} sdram_dll_user_config0_t;

typedef union {
    struct {
        uint tune_0 : 4;
        uint tune_1 : 4;
        uint tune_2 : 4;
        uint tune_3 : 4;
        uint tune_4 : 4;
        uint tune_5 : 4;
        uint : 8;
    };
    uint word;
} sdram_dll_user_config1_t;

//! SDRAM timing control registers
typedef struct {
    const sdram_dll_status_t status;
    sdram_dll_user_config0_t config0;
    sdram_dll_user_config1_t config1;
} sdram_dll_t;

ASSERT_WORD_SIZED(sdram_status_t);
ASSERT_WORD_SIZED(sdram_command_t);
ASSERT_WORD_SIZED(sdram_direct_command_t);
ASSERT_WORD_SIZED(sdram_ram_config_t);
ASSERT_WORD_SIZED(sdram_refresh_t);
ASSERT_WORD_SIZED(sdram_qos_t);
ASSERT_WORD_SIZED(sdram_chip_t);
ASSERT_WORD_SIZED(sdram_dll_status_t);
ASSERT_WORD_SIZED(sdram_dll_user_config0_t);
ASSERT_WORD_SIZED(sdram_dll_user_config1_t);

//! \}

// ---------------------------------------------------------------------
//! \name 14. System Controller
//! \{

typedef struct {
    uint select : 18;
    uint : 2;
    uint security_code : 12; // NB: see documentation!
} sc_magic_proc_map_t;

typedef struct {
    uint reset_code : 3;
    uint : 29;
} sc_reset_code_t;

typedef struct {
    uint monitor_id : 5;
    uint : 3;
    uint arbitrate_request : 1;
    uint : 7;
    uint reset_on_watchdog : 1;
    uint : 3;
    uint security_code : 12; // NB: see documentation!
} sc_monitor_id_t;

typedef struct {
    uint boot_area_map : 1;
    uint : 14;
    uint jtag_on_chip : 1;
    uint test : 1;
    uint ethermux : 1;
    uint clk32 : 1;
    uint jtag_tdo : 1;
    uint jtag_rtck : 1;
    uint : 11;
} sc_misc_control_t;

typedef union {
    struct {
        uint : 16;
        uint ethernet_receive : 4;
        uint ethernet_transmit : 4;
        uint jtag : 4;
        uint : 1;
        uint sdram : 3;
    };
    uint gpio;
} sc_io_t;

typedef struct {
    uint input_multiplier : 6;
    uint : 2;
    uint output_divider : 6;
    uint : 2;
    uint freq_range : 2;
    uint power_up : 1;
    uint : 5;
    uint _test : 1;
    uint : 7;
} sc_pll_control_t;

enum frequency_range {
    FREQ_25_50,
    FREQ_50_100,
    FREQ_100_200,
    FREQ_200_400
};

typedef struct {
    uint pa : 2;
    uint adiv : 2;
    uint : 1;
    uint pb : 2;
    uint bdiv : 2;
    uint : 1;
    uint mem : 2;
    uint mdiv : 2;
    uint : 1;
    uint rtr : 2;
    uint rdiv : 2;
    uint : 1;
    uint sys : 2;
    uint sdiv : 2;
    uint : 7;
    uint invert_b : 1;
} sc_clock_mux_t;

typedef struct {
    uint status : 18;
    uint : 14;
} sc_sleep_status_t;

typedef struct {
    uint temperature : 24;
    uint sample_finished : 1;
    uint : 6;
    uint start : 1;
} sc_temperature_t;

typedef struct {
    uint : 31;
    uint bit : 1;
} sc_mutex_bit_t;

typedef struct {
    uint rx_disable : 6;
    uint : 2;
    uint tx_disable : 6;
    uint : 2;
    uint parity_control : 1;
    uint : 3;
    uint security_code : 12; // NB: see documentation!
} sc_link_disable_t;

//! System controller registers
typedef struct {
    const uint chip_id;
    sc_magic_proc_map_t processor_disable;
    sc_magic_proc_map_t set_cpu_irq;
    sc_magic_proc_map_t clear_cpu_irq;
    uint set_cpu_ok;
    uint clear_cpu_ok;
    sc_magic_proc_map_t cpu_reset_level;
    sc_magic_proc_map_t node_reset_level;
    sc_magic_proc_map_t subsystem_reset_level;
    sc_magic_proc_map_t cpu_reset_pulse;
    sc_magic_proc_map_t node_reset_pulse;
    sc_magic_proc_map_t subsystem_reset_pulse;
    const sc_reset_code_t reset_code;
    sc_monitor_id_t monitor_id;
    sc_misc_control_t misc_control;
    sc_io_t gpio_pull_up_down_enable; // NB: see documentation!
    sc_io_t io_port;                  // NB: see documentation!
    sc_io_t io_direction;
    sc_io_t io_set;
    sc_io_t io_clear;
    sc_pll_control_t pll1_freq_control;
    sc_pll_control_t pll2_freq_control;
    uint set_flags;
    uint reset_flags;
    sc_clock_mux_t clock_mux_control;
    const sc_sleep_status_t cpu_sleep;
    sc_temperature_t temperature[3];
    const uint _padding[3];
    const sc_mutex_bit_t monitor_arbiter[32];
    const sc_mutex_bit_t test_and_set[32];
    const sc_mutex_bit_t test_and_clear[32];
    sc_link_disable_t link_disable;
} system_controller_t;

enum {
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

//! \}

// ---------------------------------------------------------------------
//! \name 15. Ethernet MII Interface
//! \{

typedef struct {
    uint transmit : 1;
    uint receive : 1;
    uint loopback : 1;
    uint receive_error_filter : 1;
    uint receive_unicast: 1;
    uint receive_multicast : 1;
    uint receive_broadcast : 1;
    uint receive_promiscuous : 1;
    uint receive_vlan : 1;
    uint reset_drop_counter : 1;
    uint hardware_byte_reorder_disable : 1;
    uint : 21;
} ethernet_general_command_t;

typedef struct {
    uint transmit_active : 1;
    uint unread_counter : 6;
    uint : 9;
    uint drop_counter : 16;
} ethernet_general_status_t;

typedef struct {
    uint reset : 1; // Active low
    uint smi_input : 1;
    uint smi_output : 1;
    uint smi_out_enable : 1;
    uint smi_clock : 1; // Active rising
    uint irq_invert_disable : 1;
    uint : 26;
} ethernet_phy_control_t;

typedef struct {
    uint transmit : 1;
    uint : 3;
    uint receive : 1;
    uint : 27;
} ethernet_interrupt_clear_t;

typedef struct {
    uint ptr : 12;
    uint rollover : 1;
    uint : 19;
} ethernet_receive_pointer_t;

typedef struct {
    uint ptr : 6;
    uint rollover : 1;
    uint : 25;
} ethernet_receive_descriptor_pointer_t;

//! Ethernet controller registers
typedef struct {
    ethernet_general_command_t command;
    const ethernet_general_status_t status;
    uint transmit_length;
    uint transmit_command;
    uint receive_command;
    uint64 mac_address; // Low 48 bits only
    ethernet_phy_control_t phy_control;
    ethernet_interrupt_clear_t interrupt_clear;
    const ethernet_receive_pointer_t receive_read;
    const ethernet_receive_pointer_t receive_write;
    const ethernet_receive_descriptor_pointer_t receive_desc_read;
    const ethernet_receive_descriptor_pointer_t receive_desc_write;
} ethernet_controller_t;

//! \brief Ethernet received message descriptor.
//! \warning Cannot find description of rest of this structure; SCAMP only
//!     uses one field.
typedef struct {
    uint length : 11;
    uint : 21; // ???
} ethernet_receive_descriptor_t;

ASSERT_WORD_SIZED(ethernet_general_command_t);
ASSERT_WORD_SIZED(ethernet_general_status_t);
ASSERT_WORD_SIZED(ethernet_phy_control_t);
ASSERT_WORD_SIZED(ethernet_interrupt_clear_t);
ASSERT_WORD_SIZED(ethernet_receive_pointer_t);
ASSERT_WORD_SIZED(ethernet_receive_descriptor_pointer_t);
ASSERT_WORD_SIZED(ethernet_receive_descriptor_t);

//! \}

// ---------------------------------------------------------------------
//! \name 16. Watchdog timer
//! \{

typedef struct {
    uint interrupt_enable : 1;
    uint reset_enable : 1;
    uint : 30;
} watchdog_control_t;

typedef struct {
    uint interrupted : 1;
} watchdog_status_t;

typedef union {
    struct {
        uint lock : 1;
        uint magic : 31;
    };
    uint whole_value;
} watchdog_lock_t;

enum {
    WATCHDOG_LOCK_RESET = 0,
    WATCHDOG_LOCK_MAGIC = WD_CODE
};

//! Watchdog timer control registers
typedef struct {
    uint load;
    const uint value;
    watchdog_control_t control;
    uint interrupt_clear;
    const watchdog_status_t raw_status;
    const watchdog_status_t masked_status;
    const uint _padding[0x2fa]; // Lots of padding!
    watchdog_lock_t lock;
} watchdog_controller_t;

ASSERT_WORD_SIZED(watchdog_control_t);
ASSERT_WORD_SIZED(watchdog_status_t);
ASSERT_WORD_SIZED(watchdog_lock_t);

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

//! \name General layout
//! \{

//! VIC registers
static volatile vic_control_t *const vic_control =
        (vic_control_t *) VIC_BASE_UNBUF; // NB unbuffered!
//! VIC interrupt handlers. Array of 32 elements.
static volatile vic_interrupt_handler_t *const vic_interrupt_vector =
        (vic_interrupt_handler_t *) (VIC_BASE + 0x100);
//! VIC individual interrupt control. Array of 32 elements.
static volatile vic_vector_control_t *const vic_interrupt_control =
        (vic_vector_control_t *) (VIC_BASE + 0x200);

//! Timer 1 control registers
static volatile timer_controller_t *const timer1_control =
        (timer_controller_t *) TIMER1_BASE;
//! Timer 2 control registers
static volatile timer_controller_t *const timer2_control =
        (timer_controller_t *) TIMER2_BASE;

//! DMA control registers
static volatile dma_t *const dma_control = (dma_t *) DMA_BASE;

//! Communications controller registers
static volatile comms_ctl_t *const comms_control = (comms_ctl_t *) CC_BASE;

//! Router controller registers
static volatile router_t *const router_control = (router_t *) RTR_BASE;
//! Router diagnostic filters
static volatile router_diagnostic_filter_t *const router_diagnostic_filter =
        (router_diagnostic_filter_t *) (RTR_BASE + 0x200);
//! Router diagnostic counters
static volatile uint *const router_diagnostic_counter =
        (uint *) (RTR_BASE + 0x300);

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

//! System controller registers
static volatile system_controller_t *const system_control =
        (system_controller_t *) SYSCTL_BASE;

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
#endif // !__SPINN_EXTRA_H__

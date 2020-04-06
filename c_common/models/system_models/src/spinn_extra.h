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
//
// Extra definitions of things on SpiNNaker chips that aren't already mentioned
// in spinnaker.h, or where the description is miserable.
//
// ------------------------------------------------------------------------

#ifndef __SPINN_EXTRA_H__
#define __SPINN_EXTRA_H__

// ---------------------------------------------------------------------
// 1. Chip Organization

// No registers

// ---------------------------------------------------------------------
// 2. System Architecture

// No registers

// ---------------------------------------------------------------------
// 3. ARM968 Processing Subsystem

#include <spinnaker.h>
// No registers

// ---------------------------------------------------------------------
// 4. ARM 968

// No special registers here

// ---------------------------------------------------------------------
// 5. Vectored Interrupt Controller

typedef void (*vic_interrupt_handler_t) (void);

typedef union {
    struct {
        uint watchdog : 1;
        uint software : 1;
        uint comm_rx : 1;
        uint comm_tx : 1;
        uint timer1 : 1;
        uint timer2 : 1;
        uint cc_rx_ready : 1;
        uint cc_rx_parity_error : 1;
        uint cc_rx_framing_error : 1;
        uint cc_tx_full : 1;
        uint cc_tx_overflow : 1;
        uint cc_tx_empty : 1;
        uint dma_done : 1;
        uint dma_error : 1;
        uint dma_timeout : 1;
        uint router_diagnostic : 1;
        uint router_dump : 1;
        uint router_error : 1;
        uint cpu : 1;
        uint ethernet_tx : 1;
        uint ethernet_rx : 1;
        uint ethernet_phy : 1;
        uint slow_clock : 1;
        uint cc_tx_not_full : 1;
        uint cc_rx_mc : 1;
        uint cc_rx_p2p : 1;
        uint cc_rx_nn : 1;
        uint cc_rx_fr : 1;
        uint int0 : 1;
        uint int1 : 1;
        uint gpio8 : 1;
        uint gpio9 : 1;
    };
    uint value;
} vic_mask_t;

typedef struct {
    const vic_mask_t irq_status;
    const vic_mask_t fiq_status;
    const vic_mask_t raw_status;
    vic_mask_t int_select;
    vic_mask_t int_enable;
    vic_mask_t int_disable;
    vic_mask_t soft_int_enable;
    vic_mask_t soft_int_disable;
    bool protection;
    const uint _padding[3];
    vic_interrupt_handler_t vector_address;
    vic_interrupt_handler_t default_vector_address;
} vic_control_t;

typedef struct {
    uint source : 5;
    uint enable : 1;
    uint : 27;
} vic_vector_control_t;

// ---------------------------------------------------------------------
// 6. Counter/Timer

typedef struct {
    uint one_shot : 1;
    uint size : 1;
    uint pre_divide : 2;
    uint : 1;
    uint interrupt_enable : 1;
    uint periodic_mode : 1;
    uint enable : 1;
    uint : 24;
} timer_control_t;

enum timer_pre_divide {
    TIMER_PRE_DIVIDE_1 = 0,
    TIMER_PRE_DIVIDE_16 = 1,
    TIMER_PRE_DIVIDE_256 = 2
};

typedef struct {
    uint status : 1;
    uint : 31;
} timer_interrupt_status_t;

typedef struct {
    uint load_value;
    const uint current_value;
    timer_control_t control;
    uint interrupt_clear;
    const timer_interrupt_status_t raw_interrupt_status;
    const timer_interrupt_status_t masked_interrupt_status;
    uint background_load_value;
    uint _dummy;
} timer_controller_t;

// ---------------------------------------------------------------------
// 7. DMA Controller

typedef struct {
    uint _zeroes : 2;
    uint length_words : 15;
    uint : 2;
    uint direction : 1; // 0 = write to TCM, 1 = write to SDRAM
    uint crc : 1;
    uint burst : 3;
    uint width : 1; // 0 = word, 1 = double-word
    uint privilege : 1;
    uint transfer_id : 6;
} dma_description_t;

typedef struct {
    uint uncommit : 1;
    uint abort : 1;
    uint restart : 1;
    uint clear_done_int : 1;
    uint clear_timeout_int : 1;
    uint clear_write_buffer_int : 1;
    uint : 26;
} dma_control_t;

typedef struct {
    uint transferring : 1;
    uint paused : 1;
    uint queued : 1;
    uint write_buffer_full : 1;
    uint write_buffer_active : 1;
    uint : 5;
    uint transfer_done : 1;
    uint transfer2_done : 1;
    uint timeout : 1;
    uint crc_error : 1;
    uint tcm_error : 1;
    uint axi_error : 1;
    uint user_abort : 1;
    uint soft_reset : 1;
    uint : 2;
    uint write_buffer_error : 1;
    uint : 3;
    uint processor_id : 8;
} dma_status_t;

typedef struct {
    uint bridge_buffer_enable : 1;
    uint : 9;
    uint transfer_done_interrupt : 1;
    uint transfer2_done_interrupt : 1;
    uint timeout_interrupt : 1;
    uint crc_error_interrupt : 1;
    uint tcm_error_interrupt : 1;
    uint axi_error_interrupt : 1;
    uint user_abort_interrupt : 1;
    uint soft_reset_interrupt : 1;
    uint : 2;
    uint write_buffer_error_interrupt : 1;
    uint : 10;
    uint timer : 1;
} dma_global_control_t;

typedef struct {
    uint _zeroes : 5;
    uint value : 5;
    uint : 22;
} dma_timeout_t;

typedef struct {
    uint enable : 1;
    uint clear : 1;
    uint : 30;
} dma_stats_control_t;

typedef struct {
    const uint _unused1[1];
    void *sdram_address;
    void *tcm_address;
    dma_description_t description;
    dma_control_t control;
    const dma_status_t status;
    dma_global_control_t global_control;
    const uint crcc;
    const uint crcr;
    dma_timeout_t timeout;
    dma_stats_control_t statistics_control;
    const uint _unused2[5];
    const uint statistics[8];
    // TODO: current state
    // TODO: CRC polynomial
} dma_t;

// ---------------------------------------------------------------------
// 8. Communications controller

typedef union {
    struct {
        uchar parity : 1;
        uchar payload : 1;
        uchar timestamp : 2;
        uchar : 2;
        uchar type : 2;
    };
    struct {
        uchar : 4;
        uchar emergency_routing : 2;
        uchar : 2;
    } mc;
    struct {
        uchar : 4;
        uchar seq_code : 2;
        uchar : 2;
    } p2p;
    struct {
        uchar : 2;
        uchar route : 3;
        uchar mem_or_normal : 1;
        uchar : 2;
    } nn;
    struct {
        uchar : 4;
        uchar emergency_routing : 2;
        uchar : 2;
    } fr;
    uchar value;
} spinnaker_packet_control_byte_t;

enum {
    SPINNAKER_PACKET_TYPE_MC = 0,
    SPINNAKER_PACKET_TYPE_P2P = 1,
    SPINNAKER_PACKET_TYPE_NN = 2,
    SPINNAKER_PACKET_TYPE_FR = 3,
};

typedef struct {
    uint : 16;
    uint control_byte : 8;
    uint : 4;
    uint const not_full : 1;
    uint overrun : 1;
    uint full : 1;
    uint const empty : 1;
} comms_tx_control_t;

typedef struct {
    uint const multicast : 1;
    uint const point_to_point : 1;
    uint const nearest_neighbour : 1;
    uint const fixed_route : 1;
    uint : 12;
    uint const control_byte : 8;
    uint const route : 3;
    uint : 1;
    uint const error_free : 1;
    uint framing_error : 1;
    uint parity_error : 1;
    uint const received : 1;
} comms_rx_status_t;

typedef struct {
    uint p2p_source_id : 16;
    uint : 8;
    uint route : 3;
    uint : 5;
} comms_source_addr_t;

typedef struct {
    comms_tx_control_t tx_control;
    uint tx_data;
    uint tx_key;
    comms_rx_status_t rx_status;
    const uint rx_data;
    const uint rx_key;
    comms_source_addr_t source_addr;
    const uint _test;
} comms_ctl_t;

// ---------------------------------------------------------------------
// 9. Communications NoC

// No registers

// ---------------------------------------------------------------------
// 10. SpiNNaker Router

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
    uint emergency_wait_time : 8;
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
} diagnostic_counter_ctrl_t;

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

typedef struct {
    // r0
    router_control_t control;
    // r1
    const router_status_t status;
    struct {
        // r2
        router_packet_header_t header;
        // r3
        uint key;
        // r4
        uint payload;
        // r5
        const router_error_status_t status;
    } error;
    struct {
        // r6
        router_packet_header_t header;
        // r7
        uint key;
        // r8
        uint payload;
        // r9
        router_dump_outputs_t outputs;
        // r10
        const router_dump_status_t status;
    } dump;
    // r11
    diagnostic_counter_ctrl_t diagnostic_counter_control;
    // r12
    router_timing_counter_ctrl_t timing_counter_control;
    // r13
    uint cycle_count;
    // r14
    uint emergency_active_cycle_count;
    // r15
    uint unblocked_count;
    // r16-31
    uint delay_histogram[16];
    // r32
    router_diversion_t diversion;
    // r33
    router_fixed_route_routing_t fixed_route;
} router_t;

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

// ---------------------------------------------------------------------
// 11. Inter-chip transmit and receive interfaces

// No registers

// ---------------------------------------------------------------------
// 12. System NoC

// No registers

// ---------------------------------------------------------------------
// 13. SDRAM interface

// Do not use these structures without talking to Luis!

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
    uint r : 1;
    uint m : 1;
    uint l : 1;
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
    uint r : 1;
    uint m : 1;
    uint l : 1;
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

typedef struct {
    const sdram_dll_status_t status;
    sdram_dll_user_config0_t config0;
    sdram_dll_user_config1_t config1;
} sdram_dll_t;

// ---------------------------------------------------------------------
// 14. System Controller

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
    uint const test : 1;
    uint const ethermux : 1;
    uint const clk32 : 1;
    uint const jtag_tdo : 1;
    uint const jtag_rtck : 1;
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
    uint const temperature : 24;
    uint const sample_finished : 1;
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

// ---------------------------------------------------------------------
// 15. Ethernet MII Interface

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
    uint const smi_input : 1;
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
} receive_pointer_t;

typedef struct {
    uint ptr : 6;
    uint rollover : 1;
    uint : 25;
} receive_descriptor_pointer_t;

typedef struct {
    ethernet_general_command_t command;
    const ethernet_general_status_t status;
    uint transmit_length;
    uint transmit_command;
    uint receive_command;
    uint64 mac_address; // Low 48 bits only
    ethernet_phy_control_t phy_control;
    ethernet_interrupt_clear_t interrupt_clear;
    const receive_pointer_t receive_read;
    const receive_pointer_t receive_write;
    const receive_descriptor_pointer_t receive_desc_read;
    const receive_descriptor_pointer_t receive_desc_write;
} ethernet_controller_t;

// Cannot find description of rest of this structure; SCAMP only uses one field
typedef struct {
    uint length : 11;
    uint : 21; // ???
} ethernet_receive_descriptor_t;

// ---------------------------------------------------------------------
// 16. Watchdog timer

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

static volatile vic_control_t *const vic_control =
        (vic_control_t *) VIC_BASE_UNBUF; // NB unbuffered!
static volatile vic_interrupt_handler_t *const vic_interrupt_vectors =
        (vic_interrupt_handler_t *) (VIC_BASE + 0x100);
static volatile vic_vector_control_t *const vic_interrupt_control =
        (vic_vector_control_t *) (VIC_BASE + 0x200);

static volatile timer_controller_t *const timer1 =
        (timer_controller_t *) TIMER1_BASE;
static volatile timer_controller_t *const timer2 =
        (timer_controller_t *) TIMER2_BASE;

static volatile dma_t *const dma_controller = (dma_t *) DMA_BASE;

static volatile comms_ctl_t *const comms_control = (comms_ctl_t *) CC_BASE;

static volatile router_t *const router = (router_t *) RTR_BASE;
static volatile router_diagnostic_filter_t *const router_diagnostic_filter =
        (router_diagnostic_filter_t *) (RTR_BASE + 0x200);
static volatile uint *const router_diagnostic_counter =
        (uint *) (RTR_BASE + 0x300);

static volatile sdram_controller_t *const sdram_control =
        (sdram_controller_t *) PL340_BASE;
static volatile sdram_qos_t *const sdram_qos_control =
        (sdram_qos_t *) (PL340_BASE + 0x100);
static volatile sdram_chip_t *const sdram_chip_control =
        (sdram_chip_t *) (PL340_BASE + 0x200);
static volatile sdram_dll_t *const sdram_dll_control =
        (sdram_dll_t *) (PL340_BASE + 0x300);

static volatile system_controller_t *const system_control =
        (system_controller_t *) SYSCTL_BASE;

static volatile uchar *const ethernet_tx_buffer = (uchar *) ETH_TX_BASE;
static volatile uchar *const ethernet_rx_buffer = (uchar *) ETH_RX_BASE;
static volatile ethernet_receive_descriptor_t *const ethernet_desc_buffer =
        (ethernet_receive_descriptor_t *) ETH_RX_DESC_RAM;
static volatile ethernet_controller_t *const ethernet =
        (ethernet_controller_t *) ETH_REGS;

// ---------------------------------------------------------------------
#endif // !__SPINN_EXTRA_H__

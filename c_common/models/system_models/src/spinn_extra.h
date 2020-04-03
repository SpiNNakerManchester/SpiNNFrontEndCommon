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

#include <spinnaker.h>

// ---------------------------------------------------------------------

typedef void (*vic_interrupt_handler_t) (void);

typedef struct {
    const uint irq_status;
    const uint fiq_status;
    const uint raw_status;
    uint int_select;
    uint int_enable;
    uint int_disable;
    uint soft_int_enable;
    uint soft_int_disable;
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
} dma_t;

// ---------------------------------------------------------------------

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
    uint gpio_pull_up_down_enable;
    uint io_port;
    uint io_direction;
    uint io_set;
    uint io_clear;
    uint pll1_freq_control;
    uint pll2_freq_control;
    uint set_flags;
    uint reset_flags;
    uint clock_mux_control;
    const uint cpu_sleep;
    uint temperature[3];
    const uint _padding[3];
    const uint arbiter[32];
    const uint test_and_set[32];
    const uint test_and_clear[32];
    uint link_disable;
} system_controller_t;

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

static volatile comms_ctl_t *const comms_controller = (comms_ctl_t *) CC_BASE;

static volatile router_t *const router = (router_t *) RTR_BASE;
static volatile router_diagnostic_filter_t *const router_diagnostic_filter =
        (router_diagnostic_filter_t *) (RTR_BASE + 0x200);
static volatile uint *const router_diagnostic_counter =
        (uint *) (RTR_BASE + 0x300);

// memory controller explicitly not exposed; too dangerous!

static volatile system_controller_t *const system_controller =
        (system_controller_t *) SYSCTL_BASE;

// ---------------------------------------------------------------------
#endif // !__SPINN_EXTRA_H__

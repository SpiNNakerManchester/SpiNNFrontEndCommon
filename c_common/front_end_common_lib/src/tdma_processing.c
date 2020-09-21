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

/*! \file
 *  \brief implementation of tdma_processing.h
 */

#include <debug.h>
#include <stdbool.h>
#include <tdma_processing.h>
#include <spinnaker.h>

//! Spin1 API ticks - to know when the timer wraps
extern uint ticks;

//! The parameters
static tdma_parameters params;

//! The next expected time to send a spike
static uint32_t expected_time;

//! Number of times the core got behind its TDMA
static uint32_t n_behind_times = 0;

uint32_t tdma_processing_times_behind(void) {
    return n_behind_times;
}

bool tdma_processing_initialise(void **address) {
    // Get the parameters
    struct tdma_parameters *sdram_params = *address;
    spin1_memcpy(&params, sdram_params, sizeof(params));

    // Move on the pointer
    *address = &sdram_params[1];

    // Start expected time at the initial offset
    expected_time = params.initial_expected_time;

    return true;
}

void tdma_processing_reset_phase(void) {
    expected_time = params.initial_expected_time;
}

void tdma_processing_send_packet(
        uint32_t transmission_key, uint32_t payload,
        uint32_t with_payload, uint32_t timer_count) {
    uint32_t timer_value = tc[T1_COUNT];

    // Find the next valid phase to send in; might run out of phases, at
    // which point we will sent immediately.  We also should just send
    // if the timer has already expired completely as then we are really late!
    while ((ticks == timer_count) && (timer_value < expected_time)
            && (expected_time > params.min_expected_time)) {
        expected_time -= params.time_between_sends;
    }

    // Wait until the expected time to send; might already have passed in
    // which case we just skip this
    while ((ticks == timer_count) && (tc[T1_COUNT] > expected_time)) {
        // Do Nothing
    }

    // Send the spike
    log_debug("sending spike %d", transmission_key);
    while (!spin1_send_mc_packet(transmission_key, payload, with_payload)) {
        spin1_delay_us(1);
    }
}

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
 *  \brief Local TDMA (Time Division Multi Access) packet sending
 *  \details
 *      Provides functions for spending packets within a given time frame
 *      simulations, spreading them so they do not conflict with activity by
 *      other SpiNNaker cores.
 */

#ifndef _TDMA_PROCESSING_H_
#define _TDMA_PROCESSING_H_
#include <stdbool.h>
#include <spin1_api.h>
#include <spin1_api_params.h>
#include <spinn_extra.h>

//! The format of the TDMA processing state, and the config in SDRAM.
typedef struct tdma_parameters {
    //! The time at which the first message can be sent
    uint32_t initial_expected_time;
    //! The time at which the last message must be sent by
    uint32_t min_expected_time;
    //! The time between sending
    uint32_t time_between_sends;
} tdma_parameters;

//! The number of times the TDMA got behind
extern uint32_t n_tdma_behind_times;

//! The latest TIMER1 value of the TDMA
extern uint32_t tdma_latest_send;

//! The number of times the TDMA has to wait
extern uint32_t tdma_waits;

//! The expected time of the next send
extern uint32_t tdma_expected_time;

//! The TDMA parameters
extern tdma_parameters tdma_params;

//! \brief Get the number of times that the TDMA was behind.
//! \return the number of times the TDMA lagged
static inline uint32_t tdma_processing_times_behind(void) {
    return n_tdma_behind_times;
}

//! \brief Initialise the TDMA processing.
//! \param[in,out] address: pointer to the SDRAM address where this data is
//!     stored, updated after being read
//! \return whether we succeeded
bool tdma_processing_initialise(void **address);

//! \brief Reset the phase of the TDMA.
static inline void tdma_processing_reset_phase(void) {
    tdma_expected_time = tdma_params.initial_expected_time;
}

//! \brief Send a packet directly without queuing
//! \param[in] key The key of the packet to send
//! \param[in] payload The payload of the packet to send or ignored if none
//! \param[in] with_payload Indicate whether the payload should be used or ignored
static inline void send_packet(uint32_t key, uint32_t payload, uint32_t with_payload) {
    while (cc[CC_TCR] & TX_FULL_MASK) {
        spin1_delay_us(1);
    }
    cc[CC_TCR] = PKT_MC;
    if (with_payload) {
        cc[CC_TXDATA] = payload;
    }
    cc[CC_TXKEY]  = key;
}

//! \brief Send a packet according to the TDMA schedule.
//! \param[in] transmission_key: The key to send with
//! \param[in] payload: the payload to send
//! \param[in] with_payload: the marker about having a payload or not.
//!     Should be either ::PAYLOAD or ::NO_PAYLOAD from spin1_api.h
//! \param[in] timer_count: The expected timer tick
static inline void tdma_processing_send_packet(
        uint32_t transmission_key, uint32_t payload,
        uint32_t with_payload, uint32_t timer_count) {
    // Spin1 API ticks - to know when the timer wraps
    extern uint ticks;

    uint32_t timer_value = timer1_control->current_value;

    // Find the next valid phase to send in; might run out of phases, at
    // which point we will sent immediately.  We also should just send
    // if the timer has already expired completely as then we are really late!
    while ((ticks == timer_count) && (timer_value < tdma_expected_time)
            && (tdma_expected_time >= tdma_params.min_expected_time)) {
        tdma_expected_time -= tdma_params.time_between_sends;
    }

    n_tdma_behind_times += tdma_expected_time < tdma_params.min_expected_time;

    // Wait until the expected time to send; might already have passed in
    // which case we just skip this
    while ((ticks == timer_count) &&
            (timer1_control->current_value > tdma_expected_time)) {
        tdma_waits++;
    }

    // Send the spike
    uint32_t time = tc[T1_COUNT];
    if (time < tdma_latest_send) {
        tdma_latest_send = time;
    }
    send_packet(transmission_key, payload, with_payload);
}

#endif // _TDMA_PROCESSING_H_

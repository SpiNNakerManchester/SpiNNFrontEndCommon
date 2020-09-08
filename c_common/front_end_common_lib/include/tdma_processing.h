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
 *
 *  \brief local Time Division Multi Access Functions Header File
 *
 *    provides function for spending packets within a given time frame
 *    simulations.
 *
 */

#ifndef _TDMA_PROCESSING_H_
#define _TDMA_PROCESSING_H_
#include <stdbool.h>

//! stores the format of the TDMA processing state in SDRAM
typedef struct tdma_parameters {
    //! The time at which the first message can be sent
    uint32_t initial_expected_time;
    //! The time at which the last message must be sent by
    uint32_t min_expected_time;
    //! The time between sending
    uint32_t time_between_sends;
} tdma_parameters;

//! \brief Get the number of times that the TDMA was behind
//! \return the number of times the TDMA lagged
uint32_t tdma_processing_times_behind(void);

//! \brief init for the tdma processing
//! \param[in,out] address: pointer to the SDRAM address where this data is
//!                         stored, updated after being read
//! \return whether we succeeded
bool tdma_processing_initialise(void **address);

//! \brief resets the phase of the TDMA
void tdma_processing_reset_phase(void);

//! \brief sends a packet with the TDMA tie in
//! \param[in] transmission_key: The key to send with
//! \param[in] payload: the payload to send
//! \param[in] with_payload: the marker about having a payload or not.
//!            should be either PAYLOAD or NO_PAYLOAD from spin1_api.h
//! \param[in] timer_count: The expected timer tick
void tdma_processing_send_packet(
        uint32_t transmission_key, uint32_t payload,
        uint32_t with_payload, uint32_t timer_count);

#endif // _TDMA_PROCESSING_H_

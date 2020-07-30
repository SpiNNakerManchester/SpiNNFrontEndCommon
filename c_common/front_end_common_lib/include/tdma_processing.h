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

//! stores the format of the TDMA processing state in SDRAM
struct tdma_parameters {
    uint32_t core_slot;
    uint32_t time_between_spikes;
    uint32_t time_between_cores;
    uint32_t initial_offset;
} tdma_parameters;

//! \brief hands back the number of times the TDMA was behind
uint32_t tdma_processing_times_behind(void);

//! \brief init for the tdma processing
//! \param[in] address: the SDRAM address where this data is stored
//! \return: bool saying success or fail
bool tdma_processing_initialise(void **address);

//! \brief resets the phase of the TDMA
void tdma_processing_reset_phase(void);

//! \brief internal method for sending a spike with the TDMA tie in
//! \param[in] index: the atom index.
//! \param[in] phase: the current phase this vertex thinks its in.
//! \param[in] payload: the payload to send
//! \param[in] payload_marker: the marker about having a payload or not.
//!            should be either PAYLOAD or NO_PAYLOAD from spin1_api.h
//! \param[in] n_atoms: the number of atoms in this TDMA.
//! \param[in] timer_period:
//! \param[in] timer_count:
void tdma_processing_send_packet(
        uint32_t index, uint32_t transmission_key, uint32_t payload,
        uint32_t payload_marker, uint timer_period, uint timer_count,
        uint32_t n_atoms);

#endif // _TDMA_PROCESSING_H_

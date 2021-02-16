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
 *  \brief Implementation of tdma_processing.h
 */

#include <debug.h>
#include <stdbool.h>
#include <tdma_processing.h>

//! The parameters
tdma_parameters tdma_params;

//! The next expected time to send a spike
uint32_t tdma_expected_time;

//! Number of times the core got behind its TDMA
uint32_t n_tdma_behind_times = 0;

uint32_t max_retries = 0;
uint32_t max_retries_time = 0;

bool tdma_processing_initialise(void **address) {
    // Get the parameters
    struct tdma_parameters *sdram_params = *address;
    spin1_memcpy(&tdma_params, sdram_params, sizeof(tdma_params));

    // Move on the pointer
    *address = &sdram_params[1];

    // Start expected time at the initial offset
    tdma_expected_time = tdma_params.initial_expected_time;

    return true;
}

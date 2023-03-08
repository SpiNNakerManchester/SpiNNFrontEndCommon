/*
 * Copyright (c) 2017 The University of Manchester
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

//! The latest send time of the TDMA; note it is set to max integer initially
//! because the timer counts down (so later == smaller)
uint32_t tdma_latest_send = 0xFFFFFFFF;

//! The number of times the TDMA has to wait to send a packet
uint32_t tdma_waits = 0;

bool tdma_processing_initialise(void **address) {
    // Get the parameters
    struct tdma_parameters *sdram_params = *address;
    spin1_memcpy(&tdma_params, sdram_params, sizeof(tdma_params));

    // Move on the pointer
    *address = &sdram_params[1];

    // Start expected time at the initial offset
    tdma_expected_time = tdma_params.initial_expected_time;

    log_info("TDMA initial_expected_time=%u, min_expected_time=%u, time_between_sends=%u",
            tdma_params.initial_expected_time, tdma_params.min_expected_time,
            tdma_params.time_between_sends);

    return true;
}

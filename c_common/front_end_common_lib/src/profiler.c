/*
 * Copyright (c) 2016 The University of Manchester
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

//! \file
//!
//! \brief Implementation of profiler.h

#include <stdint.h>
#include <debug.h>
#include <profiler.h>
#include <spinnaker.h>

//---------------------------------------
// Globals
//---------------------------------------
struct profiler_state profiler_state;

//---------------------------------------
// Functions
//---------------------------------------
void profiler_init(uint32_t* data_region) {
    log_info("Reading profile setup from 0x%08x", data_region);
    profiler_state.samples_remaining = data_region[0];
    profiler_state.count = &data_region[0];
    profiler_state.output = &data_region[1];

    log_info("Initialising profiler with storage for %u samples starting at 0x%08x",
            profiler_state.samples_remaining, profiler_state.output);

    // If profiler is turned on, start timer 2 with no clock divider
    if (profiler_state.samples_remaining > 0) {
        tc[T2_CONTROL] = 0x82;
        tc[T2_LOAD] = 0;
    }
}

//---------------------------------------
void profiler_finalise(void) {
    uint32_t words_written = (profiler_state.output - profiler_state.count) - 1;
    *profiler_state.count = words_written;
    log_info("Profiler wrote %u bytes to 0x%08x",
            (words_written * 4) + 4, profiler_state.count);
}

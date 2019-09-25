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

#include <stdint.h>
#include <debug.h>
#include <profiler.h>

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

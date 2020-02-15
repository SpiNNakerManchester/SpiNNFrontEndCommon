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

#ifndef PROFILER_H
#define PROFILER_H

#define PROFILER_N_HEADER_WORDS 1

//---------------------------------------
// Declared functions
//---------------------------------------
// Initialised the profiler from a SDRAM region
void profiler_init(uint32_t* data_region);

// Finalises profiling - potentially slow process of writing profiler_count to
// SDRAM
void profiler_finalise(void);

struct profiler_state {
    uint32_t *count;
    uint32_t samples_remaining;
    uint32_t *output;
};

#ifdef PROFILER_ENABLED

#include <stdint.h>
#include <spin1_api.h>

//---------------------------------------
// Macros
//---------------------------------------
// Types of profiler event
#define PROFILER_ENTER          (1 << 31)
#define PROFILER_EXIT           0

//---------------------------------------
// Externals
//---------------------------------------
extern struct profiler_state profiler_state;

//---------------------------------------
// Inline functions
//---------------------------------------
static inline void profiler_write_entry(uint32_t tag) {
    if (profiler_samples_remaining > 0) {
        *profiler_state.output++ = tc[T2_COUNT];
        *profiler_state.output++ = tag;
        profiler_state.samples_remaining--;
    }
}

static inline void profiler_write_entry_disable_irq_fiq(uint32_t tag) {
    uint sr = spin1_irq_disable();
    spin1_fiq_disable();
    profiler_write_entry(tag);
    spin1_mode_restore(sr);
}

static inline void profiler_write_entry_disable_fiq(uint32_t tag) {
    uint sr = spin1_fiq_disable();
    profiler_write_entry(tag);
    spin1_mode_restore(sr);
}
#else // PROFILER_ENABLED

static inline void profiler_skip(void) { return; }

#define profiler_write_entry(tag) profiler_skip()
#define profiler_write_entry_disable_irq_fiq(tag) profiler_skip()
#define profiler_write_entry_disable_fiq(tag) profiler_skip()

#endif  // PROFILER_ENABLED

#endif  // PROFILER_H

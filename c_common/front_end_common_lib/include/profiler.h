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
//! \brief Support for code profiling.
//!
//! The profiler is known to have an impact on performance, and requires the
//! use of the secondary system timer for this core.

#ifndef PROFILER_H
#define PROFILER_H

//! Number of words in profile region not filled with actual profile data
#define PROFILER_N_HEADER_WORDS 1

//---------------------------------------
// Declared functions
//---------------------------------------

//! \brief Initialise the profiler from a SDRAM region.
//!
//! \param data_region: The pointer to the region, which must be laid out
//! according to the profiler_region structure.
void profiler_init(uint32_t* data_region);

//! \brief Finalises profiling.
//!
//! This includes the potentially slow process of writing to
//! profiler_region::count
void profiler_finalise(void);

//! \brief The layout of the profiler's DSG region.
struct profiler_region {
    //! \brief The number of samples taken
    uint32_t count;
    //! \brief The samples.
    //!
    //! Each sample is the timestamp (taken from a free-running timer) at the
    //! point a sample was taken, and a tag identifying what the sample point
    //! was. (Two words. Not formed into a structure for historical reasons.)
    uint32_t samples[];
};

//! \brief The internal state of the profiler
struct profiler_state {
    //! Points to where the profiling data starts being stored.
    uint32_t *count;
    //! How many samples can be written before space is exhausted.
    uint32_t samples_remaining;
    //! Points to where the next sample will be written.
    uint32_t *output;
};

#ifdef PROFILER_ENABLED

#include <stdint.h>
#include <spin1_api.h>

//---------------------------------------
// Macros
//---------------------------------------

//! \brief Types of profiler event
enum profiler_event {
    PROFILER_ENTER = 1 << 31,
    PROFILER_EXIT = 0
};

//---------------------------------------
// Externals
//---------------------------------------

//! \brief The concrete profiler state
extern struct profiler_state profiler_state;

//---------------------------------------
// Inline functions
//---------------------------------------

//! \brief Write a profiler entry.
//! \param[in] tag: Value that identifies the location being profiled.
//!
//! Requires two words of profiler storage to record an entry, one for the
//! high-resolution timestamp and one for the tag.
static inline void profiler_write_entry(uint32_t tag) {
    if (profiler_state.samples_remaining > 0) {
        *profiler_state.output++ = tc[T2_COUNT];
        *profiler_state.output++ = tag;
        profiler_state.samples_remaining--;
    }
}

//! \brief Write an entry with all interrupts disabled.
//! \param[in] tag: Value that identifies the location being profiled.
//!
//! See profiler_write_entry().
static inline void profiler_write_entry_disable_irq_fiq(uint32_t tag) {
    uint sr = spin1_irq_disable();
    spin1_fiq_disable();
    profiler_write_entry(tag);
    spin1_mode_restore(sr);
}

//! \brief Write an entry with just fast interrupts disabled.
//! \param[in] tag: Value that identifies the location being profiled.
//!
//! See profiler_write_entry().
static inline void profiler_write_entry_disable_fiq(uint32_t tag) {
    uint sr = spin1_fiq_disable();
    profiler_write_entry(tag);
    spin1_mode_restore(sr);
}
#else // PROFILER_ENABLED

static inline void __profiler_skip(void) { return; }

#define profiler_write_entry(tag) __profiler_skip()
#define profiler_write_entry_disable_irq_fiq(tag) __profiler_skip()
#define profiler_write_entry_disable_fiq(tag) __profiler_skip()

#endif  // PROFILER_ENABLED

#endif  // PROFILER_H

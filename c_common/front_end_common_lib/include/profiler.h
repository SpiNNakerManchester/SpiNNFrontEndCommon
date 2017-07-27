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
void profiler_finalise();

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
extern uint32_t *profiler_count;
extern uint32_t profiler_samples_remaining;
extern uint32_t *profiler_output;

//---------------------------------------
// Inline functions
//---------------------------------------
static inline void profiler_write_entry(uint32_t tag) {
    if (profiler_samples_remaining > 0) {
        *profiler_output++ = tc[T2_COUNT];
        *profiler_output++ = tag;
        profiler_samples_remaining--;
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

static inline void profiler_skip (void) { return; }

#define profiler_write_entry(tag) profiler_skip()
#define profiler_write_entry_disable_irq_fiq(tag) profiler_skip()
#define profiler_write_entry_disable_fiq(tag) profiler_skip()

#endif  // PROFILER_ENABLED

#endif  // PROFILER_H

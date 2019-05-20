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
#include "profile_tags.h"

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

extern uint32_t spike_pro_count;
extern uint32_t timer_pro_count_start;
//extern uint32_t spike_enter;
//---------------------------------------
// Inline functions
//---------------------------------------
static inline void profiler_write_entry(uint32_t tag) {
    if (profiler_samples_remaining > 0) {

        if (tag == (PROFILER_EXIT | PROFILER_TIMER)){
            //todo: need to store indices of the spike processing profile entries that prempt each timer profile.
            *profiler_output++ = timer_pro_count_start;
            *profiler_output++ = (PROFILER_ENTER|PROFILER_PROCESS_FIXED_SYNAPSES);
            *profiler_output++ = spike_pro_count;
            *profiler_output++ = (PROFILER_EXIT|PROFILER_PROCESS_FIXED_SYNAPSES);
        }

        if( tag == (PROFILER_ENTER | PROFILER_TIMER)){
            timer_pro_count_start = spike_pro_count;
        }
        else if(tag == (PROFILER_EXIT | PROFILER_INCOMING_SPIKE)){
            spike_pro_count++;
        }

        *profiler_output++ = tc[T2_COUNT];
        *profiler_output++ = tag;
        profiler_samples_remaining--;
    }
    else{
        io_printf(IO_BUF,"run out of profile samples!");
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

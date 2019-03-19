// Note: profiler.h is NOT imported here on purpose due to the optional nature
// of the profiler
#include <stdint.h>
#include <debug.h>

//---------------------------------------
// Types
//---------------------------------------

typedef struct profiler_region_t {
    uint32_t count;
    uint32_t data[];
} profiler_region_t;

//---------------------------------------
// Globals
//---------------------------------------
uint32_t *profiler_count = NULL;
uint32_t profiler_samples_remaining = 0;
uint32_t *profiler_output = NULL;

//---------------------------------------
// Functions
//---------------------------------------
void profiler_init(address_t data_region) {
    profiler_region_t *region = (profiler_region_t *) data_region;
    log_info("Reading profile setup from 0x%08x", region);
    profiler_samples_remaining = region->count;
    profiler_count = &region->count;
    profiler_output = region->data;

    log_info("Initialising profiler with storage for %u samples starting "
            "at 0x%08x", profiler_samples_remaining, profiler_output);

    // If profiler is turned on, start timer 2 with no clock divider
    if (profiler_samples_remaining > 0) {
        tc[T2_CONTROL] = 0x82;
        tc[T2_LOAD] = 0;
    }
}

//---------------------------------------
void profiler_finalise() {
    uint32_t words_written = (profiler_output - profiler_count) - 1;
    *profiler_count = words_written;
    log_info("Profiler wrote %u bytes to 0x%08x",
            (words_written + 1) * sizeof(uint32_t), profiler_count);
}

// Note: profiler.h is NOT imported here on purpose due to the optional nature
// of the profiler
#include <stdint.h>
#include <debug.h>

//---------------------------------------
// Globals
//---------------------------------------
uint32_t *profiler_count = NULL;
uint32_t profiler_samples_remaining = 0;
uint32_t *profiler_output = NULL;

//---------------------------------------
// Functions
//---------------------------------------
void profiler_init(uint32_t* address, uint32_t* data_region) {
    profiler_samples_remaining = address[0];
    profiler_count = &data_region[0];
    profiler_output = &data_region[1];

    log_info(
        "Initialising profiler with storage for %u samples",
        profiler_samples_remaining);

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
    log_info(
        "Profiler wrote %u bytes to %08x.",
        (words_written * 4) + 4, profiler_count);
}

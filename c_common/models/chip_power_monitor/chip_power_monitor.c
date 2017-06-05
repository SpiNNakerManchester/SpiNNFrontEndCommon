#include <spin1_api.h>
#include <simulation.h>
#include <spinnaker.h>
#include <data_specification.h>

#define NUM_CORES 18

#define NUM_RANDOM_BITS 12

typedef enum {
    SYSTEM, PARAMS, PROVENANCE
} region;
typedef enum {
    SAMPLE_COUNT_LIMIT
} parameter_layout;

uint32_t core_counters[NUM_CORES];
uint32_t sample_count, sample_count_limit;
uint32_t recording_flags, simulation_ticks, infinite_run;

static uint32_t get_sample(void)
{
    return sc[SC_SLEEP] & ((1<<NUM_CORES) - 1);
}

// Length of busy loop used to break up chance periodicities in sampling
static uint32_t get_random_busy(void)
{
    return (spin1_rand() >> 4) & ((1 << NUM_RANDOM_BITS) - 1);
}

static void record_aggregate_sample(void)
{
    recording_record(0, core_counters, sizeof core_counters);
}

static void reset_core_counters(void)
{
    int i;
    for (i=0 ; i<NUM_CORES ; i++) {
	core_counters[i] = 0;
    }
    sample_count = 0;
}

static void sample_in_slot(uint unused0, uint unused1)
{
    unit32_t sc = ++sample_count;
    uint32_t offset = get_random_busy();
    while (offset --> 0) {
	// Do nothing
    }

    uint32_t sample = get_sample();

    int i, j;
    for (i=0, j=1 ; i<NUM_CORES ; i++, j<<=1) {
	if (sample & j) {
	    core_counters[i]++;
	}
    }

    if (sc >= sample_count_limit) {
	record_aggregate_sample();
	reset_core_counters();
    }
}

bool read_parameters(address_t address)
{
    sample_count_limit = address[SAMPLE_COUNT_LIMIT];
    //TODO anything else that needs to be read here?
    return true;
}

static bool initialize(uint32_t *timer)
{
    address_t address = data_specification_get_data_address();
    if (!simulation_initialise(
            data_specification_get_region(SYSTEM, address),
            APPLICATION_NAME_HASH, timer, &simulation_ticks,
            &infinite_run, 1)) {
        return false;
    }
    if (!read_parameters(
            data_specification_get_region(PARAMS, address))) {
        return false;
    }
    address_t recording_region =
	    data_specification_get_region(PROVENANCE, address);
    bool success = recording_initialize(recording_region, &recording_flags);
    return true;
}

void c_main(void)
{
    uint32_t timer = 0;
    if (!initialize(&timer)) {
	log_error("failed to initialise");
	rt_error(RTE_SWERR);
    }

    reset_core_counters();

    spin1_set_timer_tick(timer);
    spin1_callback_on(TIMER_TICK, sample_in_slot, 0);
    simulation_run();
}

#include <spin1_api.h>
#include <simulation.h>
#include <spinnaker.h>

#define NUM_CORES 18

uint32_t core_counters[NUM_CORES];
uint32_t sample_count, sample_count_limit;

static uint32_t get_sample(void)
{
    return sc[SC_SLEEP] & ((1<<NUM_CORES) - 1);
}

static uint32_t get_random_busy(void)
{
    // TODO Actually get a random value instead of value chosen by XKCD
    return 4;
}

static void record_aggregate_sample(void)
{
    // TODO Store values to the area that will be read later
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
    for (i=0,j=1 ; i<NUM_CORES ; i++,j<<=1) {
	if (sample & j) {
	    core_counters[i]++;
	}
    }

    if (sc >= sample_count_limit) {
	record_aggregate_sample();
	reset_core_counters();
    }
}

static bool initialize(uint32_t *timer)
{
    //TODO Do the needful
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
    spin1_callback_on(TIMER_TICK, sample_in_slot, 2);
    simulation_run();
}

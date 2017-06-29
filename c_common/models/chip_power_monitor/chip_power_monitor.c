#include <spin1_api.h>
#include <simulation.h>
#include <spinnaker.h>
#include <recording.h>
#include <debug.h>
#include <data_specification.h>

#define NUM_CORES 18

#define NUM_RANDOM_BITS 12

typedef enum {
    SYSTEM = 0, CONFIG = 1, RECORDING = 2
} region;

typedef enum {
    SAMPLE_COUNT_LIMIT = 0, SAMPLE_FREQUENCY = 1
} parameter_layout;

static uint32_t RECORDING_REGION_ID = 0;

//! values for the priority for each callback
typedef enum callback_priorities{
    SDP = 1, TIMER = 0, DMA=2
} callback_priorities;

static uint32_t simulation_ticks = 0;
static uint32_t infinite_run = 0;
static uint32_t time;
static uint32_t timer = 0;

uint32_t core_counters[NUM_CORES];
uint32_t sample_count;
uint32_t sample_count_limit;
uint32_t recording_flags;
uint32_t sample_frequency;

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
    recording_record(
        RECORDING_REGION_ID, core_counters, sizeof(core_counters));
}

static void reset_core_counters(void)
{
    int i;
    for (i=0 ; i<NUM_CORES ; i++) {
	    core_counters[i] = 0;
    }
    sample_count = 0;
}

//! \brief the function to call when resuming a simulation
//! return None
void resume_callback() {
    // change simulation ticks to be a number related to sampling frequency
    simulation_ticks = (simulation_ticks * timer) / sample_frequency;
}

static void sample_in_slot(uint unused0, uint unused1)
{
    use(unused0);
    use(unused1);
    time += 1;

    // handle the situation when the first time update is sent
    if (time == 0){
        simulation_ticks = (simulation_ticks * timer) / sample_frequency;
    }
    // check if the simulation has run to completion
    if ((infinite_run != TRUE) && (time >= simulation_ticks)) {

        recording_finalise();
        simulation_handle_pause_resume(resume_callback);

        // Subtract 1 from the time so this tick gets done again on the next
        // run
        time -= 1;
    }

    uint32_t sc = ++sample_count;
    uint32_t offset = get_random_busy();
    while (offset --> 0) {
	    // Do nothing
    }

    uint32_t sample = get_sample();

    int i, j;
    for (i=0, j=1 ; i<NUM_CORES ; i++, j<<=1) {
        if (!(sample & j)) {
            core_counters[i]++;
        }
    }

    if (sc >= sample_count_limit) {
        record_aggregate_sample();
        reset_core_counters();
    }

    recording_do_timestep_update(time);

}

bool read_parameters(address_t address)
{
    sample_count_limit = address[SAMPLE_COUNT_LIMIT];
    sample_frequency = address[SAMPLE_FREQUENCY];
    log_info("count limit %d", sample_count_limit);
    log_info("sample frequency %d", sample_frequency);
    //TODO anything else that needs to be read here?
    return true;
}

static bool initialize(uint32_t *timer)
{
    address_t address = data_specification_get_data_address();
    if (!simulation_initialise(
            data_specification_get_region(SYSTEM, address),
            APPLICATION_NAME_HASH, timer, &simulation_ticks,
            &infinite_run, SDP, DMA)) {
        return false;
    }
    if (!read_parameters(
            data_specification_get_region(CONFIG, address))) {
        return false;
    }

    // change simulation ticks to be a number related to sampling frequency
    simulation_ticks = (simulation_ticks * *timer) / sample_frequency;
    log_info("total_sim_ticks = %d", simulation_ticks);

    address_t recording_region =
	    data_specification_get_region(RECORDING, address);
    bool success = recording_initialize(recording_region, &recording_flags);
    return success;
}

void c_main(void)
{
    if (!initialize(&timer)) {
        log_error("failed to initialise");
        rt_error(RTE_SWERR);
    }

    reset_core_counters();

    spin1_set_timer_tick(sample_frequency);
    spin1_callback_on(TIMER_TICK, sample_in_slot, TIMER);
    time = UINT32_MAX;
    simulation_run();
}

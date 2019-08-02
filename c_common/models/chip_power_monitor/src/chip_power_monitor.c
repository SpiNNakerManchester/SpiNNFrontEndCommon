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

#include <spin1_api.h>
#include <simulation.h>
#include <spinnaker.h>
#include <recording.h>
#include <debug.h>
#include <data_specification.h>

#define NUM_CORES 18

#define NUM_RANDOM_BITS 12

typedef enum {
    SYSTEM = 0,
    CONFIG = 1,
    RECORDING = 2
} region;

struct sample_params {
    uint32_t count_limit;
    uint32_t frequency;
};

static uint32_t RECORDING_REGION_ID = 0;

//! values for the priority for each callback
typedef enum callback_priorities{
    TIMER = 0,
    SDP = 1,
    DMA = 2
} callback_priorities;

static uint32_t simulation_ticks = 0;
static uint32_t infinite_run = 0;
static uint32_t time;
static uint32_t timer = 0;

static uint32_t core_counters[NUM_CORES];
static uint32_t sample_count;
static uint32_t sample_count_limit;
static uint32_t recording_flags;
static uint32_t sample_frequency;

//! \brief Read which cores on the chip are asleep right now.
static uint32_t get_sample(void) {
    return sc[SC_SLEEP] & ((1 << NUM_CORES) - 1);
}

// Length of busy loop used to break up chance periodicities in sampling
static uint32_t get_random_busy(void) {
    return (spin1_rand() >> 4) & ((1 << NUM_RANDOM_BITS) - 1);
}

static void record_aggregate_sample(void) {
    recording_record(
            RECORDING_REGION_ID, core_counters, sizeof(core_counters));
}

static void reset_core_counters(void) {
    for (uint32_t i = 0 ; i < NUM_CORES ; i++) {
        core_counters[i] = 0;
    }
    sample_count = 0;
}

//! \brief the function to call when resuming a simulation
//! \return None
static void resume_callback(void) {
    // change simulation ticks to be a number related to sampling frequency
    if (time == UINT32_MAX) {
        log_info("resume_skipped as time still zero");
    } else {
        simulation_ticks = (simulation_ticks * timer) / sample_frequency;
        log_info("total_sim_ticks = %d", simulation_ticks);
        recording_reset();
        log_info("resume_callback");
    }
}

static void count_core_states(void) {
    uint32_t sample = get_sample();

    for (uint32_t i = 0, j = 1 ; i < NUM_CORES ; i++, j <<= 1) {
        if (!(sample & j)) {
            core_counters[i]++;
        }
    }
}

//! \brief Called to actually record a sample.
static void sample_in_slot(uint unused0, uint unused1) {
    use(unused0);
    use(unused1);
    time++;

    // handle the situation when the first time update is sent
    if (time == 0){
        simulation_ticks = (simulation_ticks * timer) / sample_frequency;
        log_info("total_sim_ticks = %d", simulation_ticks);
    }
    // check if the simulation has run to completion
    if ((infinite_run != TRUE) && (time >= simulation_ticks)) {
        simulation_handle_pause_resume(resume_callback);

        recording_finalise();

        // Subtract 1 from the time so this tick gets done again on the next
        // run
        time--;

        simulation_ready_to_read();
    }

    uint32_t sc = ++sample_count;
    uint32_t offset = get_random_busy();
    while (offset --> 0) {
        // Do nothing; FIXME how to be sure to delay a random amount of time
    }

    count_core_states();
    if (sc >= sample_count_limit) {
        record_aggregate_sample();
        reset_core_counters();
    }

    recording_do_timestep_update(time);
}

static bool read_parameters(struct sample_params *sample_params) {
    sample_count_limit = sample_params->count_limit;
    sample_frequency = sample_params->frequency;
    log_info("count limit %d", sample_count_limit);
    log_info("sample frequency %d", sample_frequency);
    return true;
}

static bool initialize(uint32_t *timer) {
    data_specification_metadata_t *ds_regions =
            data_specification_get_data_address();
    if (!data_specification_read_header(ds_regions)) {
        return false;
    }
    if (!simulation_initialise(
            data_specification_get_region(SYSTEM, ds_regions),
            APPLICATION_NAME_HASH, timer, &simulation_ticks,
            &infinite_run, &time, SDP, DMA)) {
        return false;
    }
    if (!read_parameters(
            data_specification_get_region(CONFIG, ds_regions))) {
        return false;
    }

    // change simulation ticks to be a number related to sampling frequency
    simulation_ticks = (simulation_ticks * *timer) / sample_frequency;
    log_info("total_sim_ticks = %d", simulation_ticks);

    return recording_initialize(
            data_specification_get_region(RECORDING, ds_regions),
            &recording_flags);
}

void c_main(void) {
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

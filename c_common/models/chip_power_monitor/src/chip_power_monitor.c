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

//! The number of bits of randomness used to break up sampling periodicity
//! errors.
#define NUM_RANDOM_BITS 12

//! The IDs of each DSG region used.
enum {
    SYSTEM = 0,  //!< The system data region ID
    CONFIG = 1,  //!< The configuration region ID
    RECORDING = 2//!< The recorded data region ID
};

//! Describes the format of the configuration region.
struct sample_params {
    //! The number of samples to aggregate per recording entry.
    uint32_t count_limit;
    //! The fundamental sampling frequency
    uint32_t frequency;
};

//! \brief The recording channel we use.
//!
//! Only one recording channel is used by this application.
static const uint32_t RECORDING_CHANNEL_ID = 0;

//! values for the priority for each callback
enum {
    TIMER = 0, //!< The timer callback is highest priority
    SDP = 1,   //!< Responding to communications from host is next highest
    DMA = 2    //!< DMA processing is lowest priority
};

//! The main simulation tick.
static uint32_t simulation_ticks = 0;
//! Whether we are running "forever".
static uint32_t infinite_run = 0;
//! Our internal notion of time.
static uint32_t time;
//! The main simulation time period.
static uint32_t timer = 0;

//! Where we aggregate the sample activity counts.
static uint32_t core_counters[NUM_CPUS];
//! How many samples have we done so far within this aggregate step?
static uint32_t sample_count;
//! The number of samples to aggregate per recording entry.
static uint32_t sample_count_limit;
//! General recording flags. (Unused by this code.)
static uint32_t recording_flags;
//! The frequency with which we sample the execution state of all cores.
static uint32_t sample_frequency;

//! \brief Read which cores on the chip are asleep right now.
//! \return A word (with 18 relevant bits in the low bits of the word) where a
//! bit is set when a core is asleep and waiting for events, and clear when
//! the core is active.
//!
//! Note that this accesses into the SpiNNaker System Controller hardware (see
//! Data Sheet, section 14, register 25).
static uint32_t get_sample(void) {
    return sc[SC_SLEEP] & ((1 << NUM_CPUS) - 1);
}

//! \brief Computes a random value used to break up chance periodicities in
//! sampling.
//! \return The number of times a busy loop must run.
static uint32_t get_random_busy(void) {
    return (spin1_rand() >> 4) & ((1 << NUM_RANDOM_BITS) - 1);
}

//! \brief Synchronously records the current contents of the core_counters to
//! the recording region.
static void record_aggregate_sample(void) {
    recording_record(
            RECORDING_CHANNEL_ID, core_counters, sizeof(core_counters));
}

//! \brief Resets the state of the core_counters and the sample_count variables
//! to zero.
static void reset_core_counters(void) {
    for (uint32_t i = 0 ; i < NUM_CPUS ; i++) {
        core_counters[i] = 0;
    }
    sample_count = 0;
}

//! \brief The function to call when resuming a simulation.
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

//! \brief Accumulate a count of how active each core on the current chip is.
//! The counter for the core is incremented if the core is active.
//!
//! Uses get_sample() to obtain the state of the cores.
static void count_core_states(void) {
    uint32_t sample = get_sample();

    for (uint32_t i = 0, j = 1 ; i < NUM_CPUS ; i++, j <<= 1) {
        if (!(sample & j)) {
            core_counters[i]++;
        }
    }
}

//! \brief Called to actually record a sample.
//! \param unused0 unused
//! \param unused1 unused
static void sample_in_slot(uint unused0, uint unused1) {
    use(unused0);
    use(unused1);
    time++;

    // handle the situation when the first time update is sent
    if (time == 0) {
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

    uint32_t count = ++sample_count;
    uint32_t offset = get_random_busy();
    while (offset --> 0) {
        // Do nothing; FIXME how to be sure to delay a random amount of time
    }

    count_core_states();
    if (count >= sample_count_limit) {
        record_aggregate_sample();
        reset_core_counters();
    }

    recording_do_timestep_update(time);
}

//! \brief Reads the configuration of the application out of the configuration
//! region.
//! \param[in] sample_params Pointer to the configuration region.
//! \return True if the read was successful. (Does not currently fail.)
static bool read_parameters(struct sample_params *sample_params) {
    sample_count_limit = sample_params->count_limit;
    sample_frequency = sample_params->frequency;
    log_info("count limit %d", sample_count_limit);
    log_info("sample frequency %d", sample_frequency);
    return true;
}

//! \brief Initialises the program.
//! \return True if initialisation succeeded, false if it failed.
static bool initialize(void) {
    data_specification_metadata_t *ds_regions =
            data_specification_get_data_address();
    if (!data_specification_read_header(ds_regions)) {
        return false;
    }
    if (!simulation_initialise(
            data_specification_get_region(SYSTEM, ds_regions),
            APPLICATION_NAME_HASH, &timer, &simulation_ticks,
            &infinite_run, &time, SDP, DMA)) {
        return false;
    }
    if (!read_parameters(
            data_specification_get_region(CONFIG, ds_regions))) {
        return false;
    }

    // change simulation ticks to be a number related to sampling frequency
    simulation_ticks = (simulation_ticks * timer) / sample_frequency;
    log_info("total_sim_ticks = %d", simulation_ticks);

    void *recording_region =
            data_specification_get_region(RECORDING, ds_regions);
    return recording_initialize(&recording_region, &recording_flags);
}

//! \brief The application entry point.
//!
//! Initialises the application state, installs all required callbacks, and
//! runs the "simulation" loop until told to terminate.
void c_main(void) {
    if (!initialize()) {
        log_error("failed to initialise");
        rt_error(RTE_SWERR);
    }

    reset_core_counters();

    spin1_set_timer_tick(sample_frequency);
    spin1_callback_on(TIMER_TICK, sample_in_slot, TIMER);
    time = UINT32_MAX;
    simulation_run();
}

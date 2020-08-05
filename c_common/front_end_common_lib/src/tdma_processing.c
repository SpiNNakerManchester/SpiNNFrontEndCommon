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

/*! \file
 *
 *  \brief local Time Division Multi Access Functions Header File
 *
 *    provides function for spending packets within a given time frame
 *    simulations.
 *
 */

#include <debug.h>
#include <stdbool.h>
#include <tdma_processing.h>

//! which phase in the TDMA we're in
static uint32_t phase;

//! The number of clock ticks between sending each spike
static uint32_t time_between_spikes;

//! The number of clock ticks between core index's
static uint32_t time_between_cores;

//! The next change in the time between spikes
static uint32_t core_slot;

//! The expected current clock tick of timer_1 when the next spike can be sent
static uint32_t expected_time;

//! the initial offset
static uint32_t initial_offset;

//! n times the core got behind its TDMA
static uint32_t n_behind_times = 0;

//! \brief hands back the number of times the TDMA was behind
uint32_t tdma_processing_times_behind(void) {
    return n_behind_times;
}

//! \brief init for the tdma processing
//! \param[in] address: the SDRAM address where this data is stored
//! \return: bool saying success or fail
bool tdma_processing_initialise(void **address) {
    // cast to struct
    struct tdma_parameters *params = (void *) *address;

    // bring over to dtcm
    time_between_spikes = params->time_between_spikes * sv->cpu_clk;
    time_between_cores = params->time_between_cores * sv->cpu_clk;
    core_slot = params->core_slot;
    initial_offset = params->initial_offset * sv->cpu_clk;

    log_info("\t time between spikes %u", time_between_spikes);
    log_info("\t time between core index's %u", time_between_cores);
    log_info("\t core slot %u", core_slot);
    log_info("\t initial offset %u", initial_offset);

    // update address pointer
    *address =  &params[1];

    return true;
}

//! \brief resets the phase of the TDMA
void tdma_processing_reset_phase(void) {
    phase = 0;
}

//! \brief internal method for sending a spike with the TDMA tie in
//! \param[in] index: the atom index.
//! \param[in] phase: the current phase this vertex thinks its in.
//! \param[in] payload: the payload to send
//! \param[in] payload_marker: the marker about having a payload or not.
//!            should be either PAYLOAD or NO_PAYLOAD from spin1_api.h
//! \param[in] transmission_key: the key to transmit with
//! \param[in] n_atoms: the number of atoms in this TDMA.
//! \param[in] timer_period:
//! \param[in] timer_count:
void tdma_processing_send_packet(
        uint32_t index, uint32_t transmission_key, uint32_t payload,
        uint32_t payload_marker, uint timer_period, uint timer_count,
        uint32_t n_atoms) {

    // Spin1 API ticks - to know when the timer wraps
    extern uint ticks;

    // if we're too early. select the next index to where we are and wait
    if (index > phase) {
        int tc1_count = tc[T1_COUNT];
        int how_much_time_has_passed = (sv->cpu_clk * timer_period) - tc1_count;
        bool found_phase_id = false;
        while (!found_phase_id) {
            int time_when_phase_started = time_between_spikes * phase;

            int time_when_phase_slot_started =
                time_when_phase_started + initial_offset +
                (time_between_cores * core_slot);

            if (time_when_phase_slot_started < how_much_time_has_passed) {
                log_debug("up phase id");
                phase += 1;
            }
            else{
                found_phase_id = true;
                log_debug("phase id %d", phase);
            }
            if (phase > n_atoms) {
                log_info(
                    "missed the whole TDMA. go NOW! for atom %d on tick %d",
                    index, ticks);
                n_behind_times += 1;
                while (!spin1_send_mc_packet(
                        transmission_key, payload, payload_marker)) {
                    spin1_delay_us(1);
                }
                return;
            }
        }
    }

    // Set the next expected time to wait for between spike sending
    expected_time = (
        (sv->cpu_clk * timer_period) -
        ((phase * time_between_spikes) + (time_between_cores * core_slot) +
         initial_offset));

    // Wait until the expected time to send
    while ((ticks == timer_count) && (tc[T1_COUNT] > expected_time)) {
        // Do Nothing
    }

    // Send the spike
    log_debug("sending spike %d", transmission_key);
    while (!spin1_send_mc_packet(transmission_key, payload, payload_marker)) {
        spin1_delay_us(1);
    }

    phase += 1;

}

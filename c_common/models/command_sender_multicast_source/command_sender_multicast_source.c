#include <common-typedefs.h>
#include <data_specification.h>
#include <debug.h>
#include <simulation.h>
#include <string.h>
#include "../../front_end_common_lib/include/front_end_common_constants.h"

// Globals
static uint32_t time;
static uint32_t simulation_ticks;
static uint32_t *schedule;
static uint32_t schedule_size;
static uint32_t next_pos;

// Callbacks
void timer_callback(uint unused0, uint unused1) {
    use(unused0);
    use(unused1);
    time++;

    if ((next_pos >= schedule_size) && (simulation_ticks != UINT32_MAX)
            && (time >= simulation_ticks)) {
        log_info("Simulation complete.\n");
        spin1_exit(0);
        return;
    }

    if ((next_pos < schedule_size) && schedule[next_pos] == time) {
        uint32_t with_payload_count = schedule[++next_pos];
        log_debug("Sending %u packets with payloads at time %u",
                  with_payload_count, time);
        for (uint32_t i = 0; i < with_payload_count; i++) {
            uint32_t key = schedule[++next_pos];
            uint32_t payload = schedule[++next_pos];

            //check for delays and repeats
            uint32_t delay_and_repeat_data = schedule[++next_pos];
            if (delay_and_repeat_data != 0) {
                uint16_t repeat = delay_and_repeat_data >> 8;
                uint16_t delay = delay_and_repeat_data & 0x0000ffff;
                log_debug("Sending %u, %u at time %u with %u repeats and "
                          "%u delay ", key, payload, time, repeat, delay);
                for (uint16_t repeat_count = 0; repeat_count < repeat;
                        repeat_count++) {
                    spin1_send_mc_packet(key, payload, WITH_PAYLOAD);

                    // if the delay is 0, dont call delay
                    if (delay > 0) {
                        spin1_delay_us(delay);
                    }
                }
            } else {

                //if no repeats, then just sned the message
                spin1_send_mc_packet(key, payload, WITH_PAYLOAD);
            }
        }

        uint32_t without_payload_count = schedule[++next_pos];
        log_debug("Sending %u packets without payloads at time %u",
                  without_payload_count, time);
        for (uint32_t i = 0; i < without_payload_count; i++) {
            uint32_t key = schedule[++next_pos];
            log_debug("Sending %u", key);

            //check for delays and repeats
            uint32_t delay_and_repeat_data = schedule[++next_pos];
            if (delay_and_repeat_data != 0) {
                uint16_t repeat = delay_and_repeat_data >> 8;
                uint16_t delay = delay_and_repeat_data & 0x0000ffff;
                for (uint16_t repeat_count = 0; repeat_count < repeat;
                        repeat_count++) {
                    spin1_send_mc_packet(key, 0, NO_PAYLOAD);

                    // if the delay is 0, dont call delay
                    if (delay > 0) {
                        spin1_delay_us(delay);
                    }
                }
            } else {

                //if no repeats, then just sned the message
                spin1_send_mc_packet(key, 0, NO_PAYLOAD);
            }

        }
        ++next_pos;

        if (next_pos < schedule_size) {
            log_debug("Next packets will be sent at %u", schedule[next_pos]);
        } else {
            log_debug("End of Schedule");
        }
    }
}

bool read_parameters(address_t address) {
    schedule_size = address[0] >> 2;

    // Allocate the space for the schedule
    schedule = (uint32_t*) spin1_malloc(schedule_size * sizeof(uint32_t));
    if (schedule == NULL) {
        log_error("Could not allocate the schedule");
        return false;
    }
    memcpy(schedule, &address[1], schedule_size * sizeof(uint32_t));

    next_pos = 0;
    log_info("Schedule starts at time %d", schedule[0]);

    return (true);
}

bool initialize(uint32_t *timer_period) {

    // Get the address this core's DTCM data starts at from SRAM
    address_t address = data_specification_get_data_address();

    // Read the header
    if (!data_specification_read_header(address)) {
        return false;
    }

    // Get the timing details
    if (!simulation_read_header(
            data_specification_get_region(0, address),
            timer_period, &simulation_ticks)) {
        return false;
    }

    // Read the parameters
    read_parameters(data_specification_get_region(1, address));

    return true;
}

// Entry point
void c_main(void) {

    // Configure system
    uint32_t timer_period = 0;
    if (!initialize(&timer_period)) {
        return;
    }

    // Set timer_callback
    spin1_set_timer_tick(timer_period);

    // Register callbacks
    spin1_callback_on(TIMER_TICK, timer_callback, 2);

    log_info("Starting");

    // Start the time at "-1" so that the first tick will be 0
    time = UINT32_MAX;
    simulation_run();
}

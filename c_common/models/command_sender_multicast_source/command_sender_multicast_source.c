#include <common-typedefs.h>
#include <data_specification.h>
#include <debug.h>
#include <simulation.h>
#include <string.h>

// Globals
static uint32_t time;
static uint32_t simulation_ticks;
static uint32_t infinite_run;
static uint32_t *schedule;
static uint32_t schedule_size;
static uint32_t next_pos;

//! values for the priority for each callback
typedef enum callback_priorities{
    SDP = 0, TIMER = 2
} callback_priorities;

//! region identifiers
typedef enum region_identifiers{
    SYSTEM_REGION = 0, COMMANDS = 1, PROVENANCE_REGION = 2
} region_identifiers;

// Callbacks
void timer_callback(uint unused0, uint unused1) {
    use(unused0);
    use(unused1);
    time++;

    if ((next_pos >= schedule_size) && (infinite_run != TRUE) &&
            (time >= simulation_ticks)) {
        simulation_handle_pause_resume(NULL);
        return;
    }

    if ((next_pos < schedule_size) && schedule[next_pos] == time) {
        uint32_t with_payload_count = schedule[++next_pos];
        log_debug(
            "Sending %u packets with payloads at time %u",
            with_payload_count, time);
        for (uint32_t i = 0; i < with_payload_count; i++) {
            uint32_t key = schedule[++next_pos];
            uint32_t payload = schedule[++next_pos];

            //check for delays and repeats
            uint32_t delay_and_repeat_data = schedule[++next_pos];
            if (delay_and_repeat_data != 0) {
                uint32_t repeat = delay_and_repeat_data >> 16;
                uint32_t delay = delay_and_repeat_data & 0x0000ffff;
                log_debug(
                    "Sending %08x, %08x at time %u with %u repeats and "
                    "%u delay ", key, payload, time, repeat, delay);

                for (uint32_t repeat_count = 0; repeat_count < repeat;
                        repeat_count++) {
                    spin1_send_mc_packet(key, payload, WITH_PAYLOAD);

                    // if the delay is 0, don't call delay
                    if (delay > 0) {
                        spin1_delay_us(delay);
                    }
                }
            } else {
                log_debug("Sending %08x, %08x at time %u", key, payload, time);

                //if no repeats, then just send the message
                spin1_send_mc_packet(key, payload, WITH_PAYLOAD);
            }
        }

        uint32_t without_payload_count = schedule[++next_pos];
        log_debug(
            "Sending %u packets without payloads at time %u",
            without_payload_count, time);
        for (uint32_t i = 0; i < without_payload_count; i++) {
            uint32_t key = schedule[++next_pos];
            log_debug("Sending %08x", key);

            //check for delays and repeats
            uint32_t delay_and_repeat_data = schedule[++next_pos];
            if (delay_and_repeat_data != 0) {
                uint32_t repeat = delay_and_repeat_data >> 16;
                uint32_t delay = delay_and_repeat_data & 0x0000ffff;
                for (uint32_t repeat_count = 0; repeat_count < repeat;
                        repeat_count++) {
                    spin1_send_mc_packet(key, 0, NO_PAYLOAD);

                    // if the delay is 0, don't call delay
                    if (delay > 0) {
                        spin1_delay_us(delay);
                    }
                }
            } else {
                log_debug("Sending %08x at time %u", key, time);

                //if no repeats, then just send the message
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
    if (!simulation_read_timing_details(
            data_specification_get_region(SYSTEM_REGION, address),
            APPLICATION_NAME_HASH, timer_period)) {
        return false;
    }

    // Read the parameters
    read_parameters(data_specification_get_region(COMMANDS, address));

    return true;
}

// Entry point
void c_main(void) {

    // Configure system
    uint32_t timer_period = 0;
    if (!initialize(&timer_period)) {
        log_error("Error in initialisation - exiting!");
        rt_error(RTE_SWERR);
    }

    // Set timer_callback
    spin1_set_timer_tick(timer_period);

    // Register callbacks
    spin1_callback_on(TIMER_TICK, timer_callback, TIMER);
    simulation_register_simulation_sdp_callback(
        &simulation_ticks, &infinite_run, SDP);
    simulation_register_provenance_callback(NULL, PROVENANCE_REGION);

    // Start the time at "-1" so that the first tick will be 0
    time = UINT32_MAX;
    simulation_run();
}

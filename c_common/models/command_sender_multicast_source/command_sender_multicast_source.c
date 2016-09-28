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

//! address data
typedef enum address_data{
    SCHEDULE_SIZE = 0, START_OF_SCHEDULE = 1
} address_data;

//! time ID
typedef enum time_id{
    FIRST_TIME = 0
} time_id;

// Callbacks
void timer_callback(uint unused0, uint unused1) {
    use(unused0);
    use(unused1);
    time++;

    if ((next_pos * 4 >= schedule_size) || ((infinite_run != TRUE) &&
        (time >= simulation_ticks))) {
        simulation_handle_pause_resume(NULL);

        // Subtract 1 from the time so this tick gets done again on the next
        // run
        time -= 1;
        return;
    }

    if ((next_pos < schedule_size) && schedule[next_pos] == time) {
        next_pos = next_pos + 1;
        uint32_t command_count = schedule[next_pos];
        log_info("Sending %u packets at time %u", command_count, time);

        for (uint32_t i = 0; i < command_count; i++) {
            log_info("next pos before key = %u", next_pos);
            next_pos = next_pos + 1;
            uint32_t key = schedule[next_pos];
            log_info("next pos before has payload = %u", next_pos);
            next_pos = next_pos + 1;
            uint32_t has_payload = schedule[next_pos];
            uint32_t payload = 0;

            // read payload if needed
            if (has_payload == 0){
                log_info("next pos before payload= %u", next_pos);
                next_pos = next_pos + 1;
                payload = schedule[next_pos];
            }
            else{
                use(payload);
            }

            //check for delays and repeats
            log_info("next pos before delay and repeat = %u", next_pos);
            next_pos = next_pos + 1;
            uint32_t delay_and_repeat_data = schedule[next_pos];
            if (delay_and_repeat_data != 0) {
                uint32_t repeat = delay_and_repeat_data >> 16;
                uint32_t delay = delay_and_repeat_data & 0x0000ffff;

                for (uint32_t repeat_count = 0; repeat_count < repeat;
                        repeat_count++) {
                    if (has_payload == 0){
                        log_info(
                            "Sending %08x, %08x at time %u with %u repeats and "
                            "%u delay ", key, payload, time, repeat, delay);
                        spin1_send_mc_packet(key, payload, WITH_PAYLOAD);
                    }
                    else{
                        log_info(
                            "Sending %08x at time %u with %u repeats and "
                            "%u delay ", key, time, repeat, delay);
                        spin1_send_mc_packet(key, 0, NO_PAYLOAD);
                    }

                    // if the delay is 0, don't call delay
                    if (delay > 0) {
                        spin1_delay_us(delay);
                    }
                }
            } else {
                if (has_payload == 0){
                    log_info("Sending %08x, %08x at time %u",
                             key, payload, time);
                    //if no repeats, then just send the message
                    spin1_send_mc_packet(key, payload, WITH_PAYLOAD);
                }
                else{
                    log_info("Sending %08x at time %u", key, time);
                    spin1_send_mc_packet(key, 0, NO_PAYLOAD);
                }
            }
        }

        next_pos = next_pos + 1;
        log_info("next pos before scheudle check = %u", next_pos);

        if ((next_pos * 4) < schedule_size) {
            log_info("Next packets will be sent at %u", schedule[next_pos]);
            log_info("next pos = %u, schedule_size = %u", next_pos, schedule_size);
        } else {
            log_info("End of Schedule");
        }
    }
}

bool read_parameters(address_t address) {
    schedule_size = address[SCHEDULE_SIZE];
    log_info("schedule size = %u", schedule_size);

    // Allocate the space for the schedule
    schedule = (uint32_t*) spin1_malloc(schedule_size * sizeof(uint32_t));
    if (schedule == NULL) {
        log_error("Could not allocate the schedule");
        return false;
    }
    memcpy(schedule, &address[START_OF_SCHEDULE],
           schedule_size * sizeof(uint32_t));

    log_info("schedule stored in dtcm at %u", *schedule);

    next_pos = 0;
    log_info("Schedule starts at time %u", schedule[FIRST_TIME]);

    return (true);
}

bool initialize(uint32_t *timer_period) {

    // Get the address this core's DTCM data starts at from SRAM
    address_t address = data_specification_get_data_address();

    // Read the header
    if (!data_specification_read_header(address)) {
        return false;
    }

    // Get the timing details and set up the simulation interface
    if (!simulation_initialise(
            data_specification_get_region(SYSTEM_REGION, address),
            APPLICATION_NAME_HASH, timer_period, &simulation_ticks,
            &infinite_run, SDP, NULL,
            data_specification_get_region(PROVENANCE_REGION, address))) {
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

    // Start the time at "-1" so that the first tick will be 0
    time = UINT32_MAX;
    simulation_run();
}

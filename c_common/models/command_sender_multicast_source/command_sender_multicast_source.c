#include <common-typedefs.h>
#include <data_specification.h>
#include <debug.h>
#include <simulation.h>
#include <string.h>

// Globals
static uint32_t time;
static uint32_t simulation_ticks;
static uint32_t infinite_run;
static uint32_t *scheduled_commands;
static uint32_t *start_resume_commands;
static uint32_t *pause_stop_commands;
static uint32_t scheduled_commands_size;
static uint32_t start_resume_commands_size;
static uint32_t pause_stop_commands_size;


static uint32_t next_pos;

//! values for the priority for each callback
typedef enum callback_priorities{
    SDP = 0, TIMER = 2
} callback_priorities;

//! region identifiers
typedef enum region_identifiers{
    SYSTEM_REGION = 0, COMMANDS_WITH_ARBITRARY_TIMES = 1,
    COMMANDS_AT_START_RESUME = 2, COMMANDS_AT_STOP_PAUSE = 3,
    PROVENANCE_REGION = 4
} region_identifiers;

//! address data
typedef enum address_data{
    SCHEDULE_SIZE = 0, START_OF_SCHEDULE = 1
} address_data;

//! time ID
typedef enum time_id{
    FIRST_TIME = 0
} time_id;

//! n_commands enum
typedef enum n_commands_id{
    N_COMMANDS = 0
} n_commands_id;

uint32_t transmit_commands(
        uint32_t n_commands, address_t commands, uint32_t next_pos){

    for (uint32_t i = 0; i < n_commands; i++) {
        log_info("next pos before key = %u", next_pos);
        next_pos = next_pos + 1;
        uint32_t key = commands[next_pos];
        log_info("next pos before has payload = %u", next_pos);
        next_pos = next_pos + 1;
        uint32_t has_payload = commands[next_pos];
        uint32_t payload = 0;

        // read payload if needed
        if (has_payload == 0){
            log_info("next pos before payload= %u", next_pos);
            next_pos = next_pos + 1;
            payload = commands[next_pos];
        }
        else{
            use(payload);
        }

        //check for delays and repeats
        log_info("next pos before delay and repeat = %u", next_pos);
        next_pos = next_pos + 1;
        uint32_t delay_and_repeat_data = commands[next_pos];
        if (delay_and_repeat_data != 0) {
            uint32_t repeat = delay_and_repeat_data >> 16;
            uint32_t delay = delay_and_repeat_data & 0x0000ffff;

            for (uint32_t repeat_count = 0; repeat_count <= repeat;
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
    return next_pos;
}

void run_stop_pause_commands(){
    log_info("Transmit pause stop commands");
    transmit_commands(
        pause_stop_commands[N_COMMANDS], pause_stop_commands, 0);
}

void run_start_resume_commands(){
    log_info("Transmit start resume commands");
    transmit_commands(
        start_resume_commands[N_COMMANDS], start_resume_commands, 0);
}

bool read_scheduled_parameters(address_t address) {
    scheduled_commands_size = address[SCHEDULE_SIZE];
    log_info("schedule commands size = %u", scheduled_commands_size);

    // if no data, do not read it in
    if (scheduled_commands_size == 0){
        log_info("no schedule commands stored in dtcm");
        return true;
    }
    else {
        // Allocate the space for the scheduled_commands
        scheduled_commands =
        (uint32_t*) spin1_malloc(scheduled_commands_size * sizeof(uint32_t));

        if (scheduled_commands == NULL) {
            log_error("Could not allocate the scheduled_commands");
            return false;
        }

        memcpy(scheduled_commands, &address[START_OF_SCHEDULE],
               scheduled_commands_size * sizeof(uint32_t));

        log_info("schedule commands stored in dtcm at %u",
                 *scheduled_commands);

        next_pos = 0;
        log_info("Schedule commands starts at time %u",
                 scheduled_commands[FIRST_TIME]);

        return true;
    }
}

bool read_start_resume_commands(address_t address) {
    start_resume_commands_size = address[SCHEDULE_SIZE];

    if (start_resume_commands_size == 0){
        log_info("no start_resume commands stored in dtcm");
        return true;
    }
    else{
        log_info("start resume commands size = %u",
                 start_resume_commands_size);

        // Allocate the space for the start resume
        start_resume_commands = (uint32_t*) spin1_malloc(
            start_resume_commands_size * sizeof(uint32_t));

        if (start_resume_commands == NULL) {
            log_error("Could not allocate the start_resume_commands");
            return false;
        }
        memcpy(start_resume_commands, &address[START_OF_SCHEDULE],
               start_resume_commands_size * sizeof(uint32_t));

        log_info("start resume commands stored in dtcm at %u",
                 *start_resume_commands);

        next_pos = 0;
        log_info("there are %u commands in the start resume commands",
                 start_resume_commands[N_COMMANDS]);

        return (true);
    }
}

bool read_pause_stop_commands(address_t address) {
    pause_stop_commands_size = address[SCHEDULE_SIZE];

    if (pause_stop_commands_size == 0){
        log_info("no pause stop commands stored in dtcm");
        return true;
    }
    else{
        log_info("pause stop commands size = %u",
                 pause_stop_commands_size);

        // Allocate the space for the start resume
        pause_stop_commands = (uint32_t*) spin1_malloc(
            pause_stop_commands_size * sizeof(uint32_t));

        if (pause_stop_commands == NULL) {
            log_error("Could not allocate the pause_stop_commands");
            return false;
        }
        memcpy(pause_stop_commands, &address[START_OF_SCHEDULE],
               pause_stop_commands_size * sizeof(uint32_t));

        log_info("pause_stop_commands stored in dtcm at %u",
                 *pause_stop_commands);

        next_pos = 0;
        log_info("there are %u commands in the pause_stop_commands",
                 pause_stop_commands[N_COMMANDS]);

        return (true);
    }
}

// Callbacks
void timer_callback(uint unused0, uint unused1) {
    use(unused0);
    use(unused1);
    time++;

    if (time == 0){
        log_info("running first start resume commands");
        run_start_resume_commands();
    }

    if ((next_pos * 4 >= scheduled_commands_size) || ((infinite_run != TRUE) &&
        (time >= simulation_ticks))) {

        if ((infinite_run != TRUE) && (time >= simulation_ticks)){
            run_stop_pause_commands();
        }

        log_info("in pause resume mode");
        simulation_handle_pause_resume(run_start_resume_commands);

        // Subtract 1 from the time so this tick gets done again on the next
        // run
        time -= 1;
        return;
    }

    if ((next_pos * 4 < scheduled_commands_size) &&
            scheduled_commands[next_pos] == time) {
        log_info("starting arbitrary time transmission");
        next_pos = next_pos + 1;
        uint32_t command_count = scheduled_commands[next_pos];
        log_info("Sending %u packets at time %u", command_count, time);

        // transmit the commands for this block of data
        next_pos = transmit_commands(
            command_count, scheduled_commands, next_pos);

        next_pos = next_pos + 1;
        log_info("next pos before schedule check = %u", next_pos);

        if ((next_pos * 4) < scheduled_commands_size) {
            log_info("Next packets will be sent at %u",
                     scheduled_commands[next_pos]);
            log_info("next pos = %u, scheduled_commands_size = %u",
                     next_pos, scheduled_commands_size);
        } else {
            log_info("End of Schedule");
        }
    }
}

//! brief callback that executes the command sending of commands for exit.
void exit_callback_function(){
    run_stop_pause_commands();
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
            data_specification_get_region(PROVENANCE_REGION, address),
            exit_callback_function)) {
        return false;
    }

    // Read the parameters
    read_scheduled_parameters(data_specification_get_region(
        COMMANDS_WITH_ARBITRARY_TIMES, address));
    read_start_resume_commands(data_specification_get_region(
        COMMANDS_AT_START_RESUME, address));
    read_pause_stop_commands(data_specification_get_region(
        COMMANDS_AT_STOP_PAUSE, address));
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

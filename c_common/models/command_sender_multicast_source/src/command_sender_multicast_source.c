#include <common-typedefs.h>
#include <data_specification.h>
#include <debug.h>
#include <simulation.h>
#include <string.h>
#include <stdbool.h>

// Command structure
typedef struct command {
    uint32_t key;
    bool has_payload;
    uint32_t payload;
    uint32_t repeats;
    uint32_t delay;
} command;

typedef struct timed_command {
    uint32_t time;
    command command;
} timed_command;

// Globals
static uint32_t time;
static uint32_t simulation_ticks;
static uint32_t infinite_run;
static timed_command *timed_commands;
static command *start_resume_commands;
static command *pause_stop_commands;
static uint32_t n_timed_commands;
static uint32_t n_start_resume_commands;
static uint32_t n_pause_stop_commands;
static uint32_t next_timed_command;
static uint32_t expected_next_send;
static uint32_t time_between_sends;
static bool resume = true;

//! values for the priority for each callback
typedef enum callback_priorities{
    SDP = 0, TIMER = 2, DMA=1
} callback_priorities;

//! region identifiers
typedef enum region_identifiers{
    SYSTEM_REGION = 0, SETUP = 1, COMMANDS_WITH_ARBITRARY_TIMES = 2,
    COMMANDS_AT_START_RESUME = 3, COMMANDS_AT_STOP_PAUSE = 4,
    PROVENANCE_REGION = 5
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

static void transmit_command(command *command_to_send) {

    // Wait until the expected time to send
    while (tc[T1_COUNT] > expected_next_send) {

        // Do Nothing
    }
    expected_next_send -= time_between_sends;

    // check for repeats
    if (command_to_send->repeats != 0) {

        for (uint32_t repeat_count = 0;
                repeat_count <= command_to_send->repeats;
                repeat_count++) {
            if (command_to_send->has_payload) {
                log_debug(
                    "Sending %08x, %08x at time %u with %u repeats and "
                    "%u delay ", command_to_send->key, command_to_send->payload,
                    time, command_to_send->repeats, command_to_send->delay);
                spin1_send_mc_packet(
                    command_to_send->key, command_to_send->payload,
                    WITH_PAYLOAD);
            } else {
                log_debug(
                    "Sending %08x at time %u with %u repeats and "
                    "%u delay ", command_to_send->key, time,
                    command_to_send->repeats, command_to_send->delay);
                spin1_send_mc_packet(command_to_send->key, 0, NO_PAYLOAD);
            }

            // if the delay is 0, don't call delay
            if (command_to_send->delay > 0) {
                spin1_delay_us(command_to_send->delay);
            }
        }
    } else {
        if (command_to_send->has_payload) {
            log_debug(
                "Sending %08x, %08x at time %u",
                command_to_send->key, command_to_send->payload, time);

            //if no repeats, then just send the message
            spin1_send_mc_packet(
                command_to_send->key, command_to_send->payload, WITH_PAYLOAD);
        } else {
            log_debug("Sending %08x at time %u", command_to_send->key, time);
            spin1_send_mc_packet(command_to_send->key, 0, NO_PAYLOAD);
        }
    }
}

static void run_stop_pause_commands() {
    log_info("Transmit pause/stop commands");
    for (uint32_t i = 0; i < n_pause_stop_commands; i++) {
        transmit_command(&(pause_stop_commands[i]));
    }
}

static void run_start_resume_commands() {
    log_info("Transmit start/resume commands");
    for (uint32_t i = 0; i < n_start_resume_commands; i++) {
        transmit_command(&(start_resume_commands[i]));
    }
}

bool read_scheduled_parameters(address_t address) {
    n_timed_commands = address[SCHEDULE_SIZE];
    log_info("%d timed commands", n_timed_commands);

    // if no data, do not read it in
    if (n_timed_commands == 0) {
        return true;
    }

    // Allocate the space for the scheduled_commands
    timed_commands = (timed_command*) spin1_malloc(
        n_timed_commands * sizeof(timed_command));

    if (timed_commands == NULL) {
        log_error("Could not allocate the scheduled commands");
        return false;
    }

    memcpy(
        timed_commands, &address[START_OF_SCHEDULE],
        n_timed_commands * sizeof(timed_command));

    log_info(
        "Schedule commands starts at time %u", timed_commands[FIRST_TIME].time);

    return true;
}

bool read_start_resume_commands(address_t address) {
    n_start_resume_commands = address[SCHEDULE_SIZE];
    log_info("%u start/resume commands", n_start_resume_commands);

    if (n_start_resume_commands == 0) {
        return true;
    }

    // Allocate the space for the start resume
    start_resume_commands = (command*) spin1_malloc(
        n_start_resume_commands * sizeof(command));

    if (start_resume_commands == NULL) {
        log_error("Could not allocate the start/resume commands");
        return false;
    }
    memcpy(
        start_resume_commands, &address[START_OF_SCHEDULE],
        n_start_resume_commands * sizeof(command));

    return true;
}

bool read_pause_stop_commands(address_t address) {
    n_pause_stop_commands = address[SCHEDULE_SIZE];
    log_info("%u pause/stop commands", n_pause_stop_commands);

    if (n_pause_stop_commands == 0){
        return true;
    }

    // Allocate the space for the start resume
    pause_stop_commands = (command*) spin1_malloc(
        n_pause_stop_commands * sizeof(command));

    if (pause_stop_commands == NULL) {
        log_error("Could not allocate the pause/stop commands");
        return false;
    }
    memcpy(
        pause_stop_commands, &address[START_OF_SCHEDULE],
        n_pause_stop_commands * sizeof(command));

    return true;
}

void read_setup(address_t address) {
    time_between_sends = address[0] * sv->cpu_clk;
    log_info("Separating sends by %u clock cycles", time_between_sends);
}

// Callbacks
void timer_callback(uint unused0, uint unused1) {
    use(unused0);
    use(unused1);
    time++;

    // Set the next expected time to wait for between spike sending
    expected_next_send = tc[T1_COUNT] - time_between_sends;

    if (resume) {
        log_info("running first start resume commands");
        run_start_resume_commands();
        resume = false;
    }

    if (((infinite_run != TRUE) && (time >= simulation_ticks))) {
        run_stop_pause_commands();

        log_info("in pause resume mode");
        resume = true;
        simulation_handle_pause_resume(NULL);

        // Subtract 1 from the time so this tick gets done again on the next
        // run
        time -= 1;
        return;
    }

    while ((next_timed_command < n_timed_commands) &&
            (timed_commands[next_timed_command].time == time)) {
        transmit_command(&(timed_commands[next_timed_command].command));
        ++next_timed_command;
    }
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
            &infinite_run, SDP, DMA)) {
        return false;
    }
    simulation_set_provenance_data_address(
        data_specification_get_region(PROVENANCE_REGION, address));
    simulation_set_exit_function(run_stop_pause_commands);

    // Read the parameters
    read_setup(data_specification_get_region(SETUP, address));
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

#include <spin1_api.h>
#include <debug.h>
#include <bit_field.h>
#include <sdp_no_scp.h>
#include "common/platform.h"
#include "common/routing_table.h"
#include "common/sdp_formats.h"
#include "common/constants.h"

#include "common-typedefs.h"
#include "compressor_includes/aliases.h"
#include "compressor_includes/ordered_covering.h"
/*****************************************************************************/
/* SpiNNaker routing table minimisation with bitfield integration.
 *
 * Minimise a routing table loaded into SDRAM and load the minimised table into
 * the router using the specified application ID.
 *
 * the exit code is stored in the user1 register
 *
 * The memory address with tag "1" is expected contain the following struct
 * (entry_t is defined in `routing_table.h` but is described below).
*/

//! interrupt priorities
typedef enum interrupt_priority{
    TIMER_TICK_PRIORITY = -1, SDP_PRIORITY = 0, COMPRESSION_START_PRIORITY = 2
} interrupt_priority;

//! \brief the timer control logic.
volatile bool timer_for_compression_attempt = false;
int counter = 0;
int max_counter = 0;

//! \brief number of times a compression time slot has occurred
bool finish_compression_flag = false;

bool sent_force_ack = false;

//! \brief bool flag to say if i was forced to stop by the compressor control
bool finished_by_compressor_force = false;

//! bool flag pointer to allow minimise to report if it failed due to malloc
//! issues
bool failed_by_malloc = false;

//! control flag for running compression only when needed
bool compress_only_when_needed = false;

//! control flag for compressing as much as possible
bool compress_as_much_as_possible = false;

//! control flag if the routing tables are able to be stored in somewhere.
bool storable_routing_tables = false;

//! \brief the sdram location to write the compressed router table into
address_t sdram_loc_for_compressed_entries;

//! how many packets waiting for
uint32_t number_of_packets_waiting_for = 0;

//! \brief the control core id for sending responses to
uint32_t control_core_id = 1;

//! \brief sdp message to send acks to the control core with
sdp_msg_pure_data my_msg;

//! \brief sends a sdp message back to the control core
static void send_sdp_message_response(){
    my_msg.dest_port = (RANDOM_PORT << PORT_SHIFT) | control_core_id;
    // send sdp packet
    while (!spin1_send_sdp_msg((sdp_msg_t *) &my_msg, _SDP_TIMEOUT)) {
        log_info("failed to send. trying again");
        // Empty body
    }
}

//! \brief send a failed response due to a malloc issue
static inline void return_malloc_response_message(){
    // set message ack finished state to malloc fail
    my_msg.data[START_OF_SPECIFIC_MESSAGE_DATA] = FAILED_MALLOC;
    log_info("send fail malloc");
    // send message
    send_sdp_message_response();
}

//! \brief send a success response message
static inline void return_success_response_message(){
    // set message ack finished state to malloc fail
    my_msg.data[START_OF_SPECIFIC_MESSAGE_DATA] = SUCCESSFUL_COMPRESSION;

    // send message
    send_sdp_message_response();
    log_info("send success ack");
    sark_io_buf_reset();
}

//! \brief send a failed response due to the control forcing it to stop
static inline void return_failed_by_force_response_message(){
       // set message ack finished state to malloc fail
    my_msg.data[START_OF_SPECIFIC_MESSAGE_DATA] = FORCED_BY_COMPRESSOR_CONTROL;

    // send message
    log_info("send failed force");
    send_sdp_message_response();
    sark_io_buf_reset();
}

//! \brief sends a failed response due to running out of time
static inline void return_failed_by_time_response_message(){
       // set message ack finished state to malloc fail
    my_msg.data[START_OF_SPECIFIC_MESSAGE_DATA] = RAN_OUT_OF_TIME;
    log_info("send failed time");
    // send message
    send_sdp_message_response();
}

//! \brief send a failed response where finished compression but failed to
//! fit into allocated size.
static inline void return_failed_by_space_response_message(){
       // set message ack finished state to malloc fail
    my_msg.data[START_OF_SPECIFIC_MESSAGE_DATA] = FAILED_TO_COMPRESS;
    log_info("send failed space");
    // send message
    send_sdp_message_response();
}

//! \brief stores the compressed routing tables into the compressed sdram
//! location
//! \returns bool if was successful or now
static inline bool store_into_compressed_address(){
    if (routing_table_sdram_get_n_entries() > TARGET_LENGTH){
        log_error("not enough space in routing table");
        return false;
    }
    else{
        log_info("starting store of %d tables", n_tables);
        bool success = routing_table_sdram_store(
            sdram_loc_for_compressed_entries);
        log_info("finished store");
        if (!success){
            log_error("failed to store entries into sdram. ");
            return false;
        }
    }
    return true;
}

//! \brief starts the compression process
static inline void start_compression_process(uint unused0, uint unused1){
    // api requirement
    use(unused0);
    use(unused1);

    // reset fail state flags
    spin1_pause();
    log_info("in compression phase");
    failed_by_malloc = false;
    timer_for_compression_attempt = false;
    finished_by_compressor_force = false;

    // create aliases
    aliases_t aliases = aliases_init();

    // reset timer
    spin1_resume(SYNC_NOWAIT);

    // run compression
    bool success = oc_minimise(
        TARGET_LENGTH, &aliases, &failed_by_malloc,
        &finished_by_compressor_force, &timer_for_compression_attempt,
        &finish_compression_flag, compress_only_when_needed,
        compress_as_much_as_possible);

    spin1_pause();
    log_info("finished oc minimise with success %d", success);

    // check state
    if (success){
        success = store_into_compressed_address();
        if (success){
            return_success_response_message();
        }
        else{
            return_failed_by_space_response_message();
        }
        routing_table_reset();
    }
    else{  // if not a success, could be one of 4 states
        if (failed_by_malloc){  // malloc failed somewhere
            return_malloc_response_message();
        }
        else if (finished_by_compressor_force){  // control killed it
            if (!sent_force_ack){
                return_failed_by_force_response_message();
                sent_force_ack = true;
            }
            else{
                log_info("ignoring as already sent ack");
            }
        }
        else if (timer_for_compression_attempt){  // ran out of time
            return_failed_by_time_response_message();
        }
        else{  // after finishing compression, still could not fit into table.
            return_failed_by_space_response_message();
        }
    }
}

//! \brief takes a array of tables from a packet and puts them into the dtcm
//! store of routing tables based off a given offset
//! \param[in] n_tables_in_packet: the number of tables in packet to pull
//! \param[in] tables: the tables from the packet.
void store_info_table_store(int n_tables_in_packet, address_t tables[]){
    for(int rt_index = 0; rt_index < n_tables_in_packet; rt_index++){
        log_info("address of table is %x",  tables[rt_index]);
        routing_tables_store_routing_table((table_t*) tables[rt_index]);
        
        log_info("stored table with %d entries", tables[rt_index][0]);
    }
}

//! \brief the sdp control entrance.
//! \param[in] mailbox: the message
//! \param[in] port: don't care.
void _sdp_handler(uint mailbox, uint port) {
    use(port);

    log_info("received packet");
    // get data from the sdp message
    sdp_msg_pure_data *msg = (sdp_msg_pure_data *) mailbox;

    // record control core.
    control_core_id = (msg->srce_port & CPU_MASK);
    log_info("control core is %d", control_core_id);

    log_info("command code is %d", msg->data[COMMAND_CODE]);

    // get command code
    if (msg->srce_port >> PORT_SHIFT == RANDOM_PORT){
        if (msg->data[COMMAND_CODE] == START_DATA_STREAM){
            // update response tracker
            sent_force_ack = false;
            routing_table_reset();

            // process packet
            start_stream_sdp_packet_t* first_command_packet =
                (start_stream_sdp_packet_t*) &msg->data[
                    START_OF_SPECIFIC_MESSAGE_DATA];
    
            // location where to store the compressed (size
            sdram_loc_for_compressed_entries =
                first_command_packet->address_for_compressed;
    
            // set up fake heap
            log_info("setting up fake heap for sdram usage");
            platform_new_heap_creation(first_command_packet->fake_heap_data);
            log_info("finished setting up fake heap for sdram usage");
    
            // set up packet tracker
            number_of_packets_waiting_for =
                first_command_packet->n_sdp_packets_till_delivered;
    
            number_of_packets_waiting_for -= 1;

            log_info(
                "there are a total tables of %d",
                first_command_packet->total_n_tables);

            storable_routing_tables = routing_tables_init(
                first_command_packet->total_n_tables);
            if (!storable_routing_tables){
                log_error(
                    "failed to allocate memory for routing table.h state");
                sark_msg_free((sdp_msg_t*) msg);
                return_malloc_response_message();
            }
            else{
                // store this set into the store
                log_info("store routing table addresses into store");
                log_info(
                    "there are %d addresses in packet",
                    first_command_packet->n_tables_in_packet);
                for (int index = 0; index <
                        first_command_packet->n_tables_in_packet;
                        index++){
                    log_info(
                        "address is %x for %d",
                        first_command_packet->tables[index], index);
                }
                store_info_table_store(
                    first_command_packet->n_tables_in_packet,
                    first_command_packet->tables);

                // keep tracker updated
                log_info(
                    "finished storing start packet of routing table "
                    "address into store");

                // if no more packets to locate, then start compression process
                if (number_of_packets_waiting_for == 0){
                    spin1_schedule_callback(
                        start_compression_process, 0, 0,
                        COMPRESSION_START_PRIORITY);
                }
            }
            // free message
            sark_msg_free((sdp_msg_t*) msg);
        }
        else if (msg->data[COMMAND_CODE] == EXTRA_DATA_STREAM){
            if (!storable_routing_tables){
                log_error(
                    "ignoring extra routing table addresses packet, as"
                    " cant store them");
            }
            else{
                // start the storing of the data
                extra_stream_sdp_packet_t* extra_command_packet =
                    (extra_stream_sdp_packet_t*) &msg->data[
                        START_OF_SPECIFIC_MESSAGE_DATA];
    
                // store this set into the store
                log_info("store extra routing table addresses into store");
                store_info_table_store(
                    extra_command_packet->n_tables_in_packet,
                    extra_command_packet->tables);
                log_info(
                    "finished storing extra routing table address into store");

                // keep tracker updated
                number_of_packets_waiting_for -= 1;
    
                // if no more packets to locate, then start compression process
                if (number_of_packets_waiting_for == 0){
                    spin1_schedule_callback(
                        start_compression_process, 0, 0,
                        COMPRESSION_START_PRIORITY);
                }
            }
    
            // free message
            sark_msg_free((sdp_msg_t*) msg);
        }
        else if(msg->data[COMMAND_CODE] == COMPRESSION_RESPONSE){
            log_error("I really should not be receiving this!!! WTF");
            sark_msg_free((sdp_msg_t*) msg);
        }
        else if (msg->data[COMMAND_CODE] == STOP_COMPRESSION_ATTEMPT){
            log_info("been forced to stop by control");
            finished_by_compressor_force = true;
            sark_msg_free((sdp_msg_t*) msg);
        }
        else{
            log_error(
                "no idea what to do with message with command code %d Ignoring",
                msg->data[COMMAND_CODE]);
            sark_msg_free((sdp_msg_t*) msg);
        }
    }
    else{
        log_error(
            "no idea what to do with message. on port %d Ignoring",
            msg->srce_port >> PORT_SHIFT);
        sark_msg_free((sdp_msg_t*) msg);
    }
}

//! \brief timer interrupt for controlling time taken to try to compress table
//! \param[in] unused0: not used
//! \param[in] unused1: not used
void timer_callback(uint unused0, uint unused1) {
    use(unused0);
    use(unused1);
    counter ++;

    if (counter >= max_counter){
        finish_compression_flag = true;
        log_info("passed timer point");
        spin1_pause();
    }
}

//! \brief the callback for setting off the router compressor
static inline void initialise() {
    log_info("Setting up stuff to allow bitfield compressor to occur.");

    log_info("reading time_for_compression_attempt");
    vcpu_t *sark_virtual_processor_info = (vcpu_t*) SV_VCPU;
    uint32_t time_for_compression_attempt = sark_virtual_processor_info[
        spin1_get_core_id()].user1;
    log_info("user 1 = %d", time_for_compression_attempt);

    // bool from int conversion happening here
    uint32_t int_value =
        (uint32_t) sark_virtual_processor_info[spin1_get_core_id()].user2;
    log_info("user 2 = %d", int_value);
    if (int_value == 1){
        compress_only_when_needed = true;
    }

    int_value = sark_virtual_processor_info[spin1_get_core_id()].user3;
    log_info("user 3 = %d", int_value);
    if (int_value == 1){
        compress_as_much_as_possible = true;
    }

    max_counter = time_for_compression_attempt / 1000;

    spin1_set_timer_tick(1000);
    spin1_callback_on(TIMER_TICK, timer_callback, TIMER_TICK_PRIORITY);

    log_info("set up sdp interrupt");
    spin1_callback_on(SDP_PACKET_RX, _sdp_handler, SDP_PRIORITY);
    log_info("finished sdp interrupt");

    log_info("set up sdp message bits");
    my_msg.flags = REPLY_NOT_EXPECTED;
    my_msg.srce_addr = spin1_get_chip_id();
    my_msg.dest_addr = spin1_get_chip_id();
    my_msg.srce_port = (RANDOM_PORT << PORT_SHIFT) | spin1_get_core_id();
    my_msg.data[COMMAND_CODE] = COMPRESSION_RESPONSE;
    my_msg.length = LENGTH_OF_SDP_HEADER + (sizeof(response_sdp_packet_t));
    log_info("finished sdp message bits");
    log_info("my core id is %d", spin1_get_core_id());
    log_info(
        "srce_port = %d the core id is %d",
        my_msg.srce_port, my_msg.srce_port & CPU_MASK);
}

//! \brief the main entrance.
void c_main(void) {
    log_info("%u bytes of free DTCM", sark_heap_max(sark.heap, 0));

    initialise();

    // go
    spin1_start(SYNC_WAIT);
}

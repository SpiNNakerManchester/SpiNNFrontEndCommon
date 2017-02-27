#include <common-typedefs.h>
#include <circular_buffer.h>
#include <data_specification.h>
#include <debug.h>
#include <simulation.h>
#include <spin1_api.h>

// Globals
static sdp_msg_t g_event_message;
static uint16_t *sdp_msg_aer_header;
static uint16_t *sdp_msg_aer_key_prefix;
static void *sdp_msg_aer_payload_prefix;
static void *sdp_msg_aer_data;
static uint32_t time;
static uint32_t packets_sent;
static uint32_t buffer_index;
static uint16_t temp_header;
static uint8_t event_size;
static uint8_t header_len;
static uint32_t simulation_ticks = 0;
static uint32_t infinite_run = 0;
static circular_buffer without_payload_buffer;
static circular_buffer with_payload_buffer;
static bool processing_events = false;

//! Provenance data store
typedef struct provenance_data_struct {
    uint32_t number_of_over_flows_none_payload;
    uint32_t number_of_over_flows_payload;
} provenance_data_struct;

//! values for the priority for each callback
typedef enum callback_priorities{
    MC_PACKET = -1, SDP = 0, USER = 1, TIMER = 2
} callback_priorities;

//! struct holding the provenance data
provenance_data_struct provenance_data;

// P bit
static uint32_t apply_prefix;

// Prefix data
static uint32_t prefix;

// Type bits
static uint32_t packet_type;

// F bit (for the receiver)
static uint32_t prefix_type;

// Right payload shift (for the sender)
static uint32_t key_right_shift;

// T bit
static uint32_t payload_timestamp;

// D bit
static uint32_t payload_apply_prefix;

// Payload prefix data (for the receiver)
static uint32_t payload_prefix;

// Right payload shift (for the sender)
static uint32_t payload_right_shift;
static uint32_t sdp_tag;
static uint32_t sdp_dest;
static uint32_t packets_per_timestamp;

//! human readable definitions of each region in SDRAM
typedef enum regions_e {
    SYSTEM_REGION,
    CONFIGURATION_REGION,
    PROVENANCE_REGION
} regions_e;

//! Human readable definitions of each element in the configuration region in
//! SDRAM
typedef enum configuration_region_components_e {
    APPLY_PREFIX,
    PREFIX,
    PREFIX_TYPE,
    PACKET_TYPE,
    KEY_RIGHT_SHIFT,
    PAYLOAD_TIMESTAMP,
    PAYLOAD_APPLY_PREFIX,
    PAYLOAD_PREFIX,
    PAYLOAD_RIGHT_SHIFT,
    SDP_TAG,
    SDP_DEST,
    PACKETS_PER_TIMESTEP
} configuration_region_components_e;

void flush_events(void) {

    // Send the event message only if there is data
    if (buffer_index > 0) {
        uint8_t event_count;
        uint16_t bytes_to_clear = 0;

        if ((packets_per_timestamp == 0)
                || (packets_sent < packets_per_timestamp)) {

            // Get the event count depending on if there is a payload or not
            if (packet_type & 0x1) {
                event_count = buffer_index >> 1;
            } else {
                event_count = buffer_index;
            }

            // insert appropriate header
            sdp_msg_aer_header[0] = 0;
            sdp_msg_aer_header[0] |= temp_header;
            sdp_msg_aer_header[0] |= (event_count & 0xff);

            g_event_message.length = sizeof(sdp_hdr_t) + header_len
                                     + event_count * event_size;

#if LOG_LEVEL >= LOG_DEBUG
            log_debug("===========Packet============\n");
            uint8_t *print_ptr1 = (uint8_t *) &g_event_message;
            for (uint8_t i = 0; i < g_event_message.length + 8; i++) {
                log_debug("%02x ", print_ptr1[i]);
            }
#endif // LOG_LEVEL >= LOG_DEBUG

            if (payload_apply_prefix && payload_timestamp) {
                uint16_t *temp = (uint16_t *) sdp_msg_aer_payload_prefix;

                if (!(packet_type && 0x2)) {
                    temp[0] = (time & 0xFFFF);
                } else {
                    temp[0] = (time & 0xFFFF);
                    temp[1] = ((time >> 16) & 0xFFFF);
                }
            }

#if LOG_LEVEL >= LOG_DEBUG
            log_debug("===========Packet============\n");
            uint8_t *print_ptr2 = (uint8_t *) &sdp_msg_aer_data;
            for (uint8_t i = 0; i < buffer_index * event_size; i++) {
                log_debug("%02x ", print_ptr2[i]);
            }
#endif // LOG_LEVEL >= LOG_DEBUG

            spin1_send_sdp_msg(&g_event_message, 1);
            packets_sent++;
        }

        // reset packet content
        bytes_to_clear = buffer_index * event_size;
        uint16_t *temp = (uint16_t *) sdp_msg_aer_data;
        for (uint8_t i = 0; i < (bytes_to_clear >> 2); i++) {
            temp[i] = 0;
        }
    }

    // reset counter
    buffer_index = 0;
}

//! \brief function to store provenance data elements into SDRAM
void record_provenance_data(address_t provenance_region_address) {

    // Copy provenance data into SDRAM region
    memcpy(provenance_region_address, &provenance_data,
           sizeof(provenance_data));
}

// Callbacks
void timer_callback(uint unused0, uint unused1) {
    use(unused0);
    use(unused1);

    // flush the spike message and sent it over the Ethernet
    flush_events();

    // increase time variable to keep track of current timestep
    time++;
    log_debug("Timer tick %u", time);

    // check if the simulation has run to completion
    if ((infinite_run != TRUE) && (time >= simulation_ticks)) {
        simulation_handle_pause_resume(NULL);

        // Subtract 1 from the time so this tick gets done again on the next
        // run
        time -= 1;
    }
}

void flush_events_if_full(void) {
    uint8_t event_count;

    if (packet_type & 0x1) {
        event_count = buffer_index >> 1;
    } else {
        event_count = buffer_index;
    }

    if (((event_count + 1) * event_size) > 256) {
        flush_events();
    }
}

// process mc packet without payload
void process_incoming_event(uint key) {
    log_debug("Processing key %x", key);

    // process the received spike
    uint16_t *buf_pointer = (uint16_t *) sdp_msg_aer_data;
    if (!(packet_type & 0x2)) {

        // 16 bit packet
        buf_pointer[buffer_index] = (key >> key_right_shift) & 0xFFFF;
        buffer_index++;

        // if there is a payload to be added
        if ((packet_type & 0x1) && (!payload_timestamp)) {
            buf_pointer[buffer_index] = 0;
            buffer_index++;
        } else if ((packet_type & 0x1) && payload_timestamp) {
            buf_pointer[buffer_index] = (time & 0xFFFF);
            buffer_index++;
        }
    } else {

        // 32 bit packet
        uint16_t spike_index = buffer_index << 1;

        buf_pointer[spike_index] = (key & 0xFFFF);
        buf_pointer[spike_index + 1] = ((key >> 16) & 0xFFFF);
        buffer_index++;

        // if there is a payload to be added
        if ((packet_type & 0x1) && (!payload_timestamp)) {
            spike_index = buffer_index << 1;
            buf_pointer[spike_index] = 0;
            buf_pointer[spike_index + 1] = 0;
            buffer_index++;
        } else if ((packet_type & 0x1) && payload_timestamp) {
            spike_index = buffer_index << 1;
            buf_pointer[spike_index] = (time & 0xFFFF);
            buf_pointer[spike_index + 1] = ((time >> 16) & 0xFFFF);
            buffer_index++;
        }
    }

    // send packet if enough data is stored
    flush_events_if_full();
}

// processes mc packet with payload
void process_incoming_event_payload(uint key, uint payload) {
    log_debug("Processing key %x, payload %x", key, payload);

    // process the received spike
    uint16_t *buf_pointer = (uint16_t *) sdp_msg_aer_data;
    if (!(packet_type & 0x2)) {

        //16 bit packet
        buf_pointer[buffer_index] = (key >> key_right_shift) & 0xFFFF;
        buffer_index++;

        //if there is a payload to be added
        if ((packet_type & 0x1) && (!payload_timestamp)) {
            buf_pointer[buffer_index] = (payload >> payload_right_shift)
                                        & 0xFFFF;
            buffer_index++;
        } else if ((packet_type & 0x1) && payload_timestamp) {
            buf_pointer[buffer_index] = (time & 0xFFFF);
            buffer_index++;
        }
    } else {

        //32 bit packet
        uint16_t spike_index = buffer_index << 1;

        buf_pointer[spike_index] = (key & 0xFFFF);
        buf_pointer[spike_index + 1] = ((key >> 16) & 0xFFFF);
        buffer_index++;

        //if there is a payload to be added
        if ((packet_type & 0x1) && !payload_timestamp){
            spike_index = buffer_index << 1;
            buf_pointer[spike_index] = (payload & 0xFFFF);
            buf_pointer[spike_index + 1] = ((payload >> 16) & 0xFFFF);
            buffer_index++;
        } else if ((packet_type & 0x1) && payload_timestamp) {
            spike_index = buffer_index << 1;
            buf_pointer[spike_index] = (time & 0xFFFF);
            buf_pointer[spike_index + 1] = ((time >> 16) & 0xFFFF);
            buffer_index++;
        }
    }

    // send packet if enough data is stored
    flush_events_if_full();
}

void incoming_event_process_callback(uint unused0, uint unused1) {
    use(unused0);
    use(unused1);

    uint32_t key;
    do {
       if (circular_buffer_get_next(without_payload_buffer, &key)) {
           process_incoming_event(key);
       } else if (circular_buffer_get_next(with_payload_buffer, &key)) {
           uint32_t payload;
           circular_buffer_get_next(with_payload_buffer, &payload);
           process_incoming_event_payload(key, payload);
       } else {
           processing_events = false;
       }
    }
    while (processing_events);
}

void incoming_event_callback(uint key, uint unused) {
    use(unused);
    log_debug("Received key %x", key);
    if (circular_buffer_add(without_payload_buffer, key)) {
        if (!processing_events) {
            processing_events = true;
            spin1_trigger_user_event(0, 0);
        }
    } else {
        provenance_data.number_of_over_flows_none_payload += 1;
    }
}

void incoming_event_payload_callback(uint key, uint payload) {
    log_debug("Received key %x, payload %x", key, payload);
    if (circular_buffer_add(with_payload_buffer, key)) {
        circular_buffer_add(with_payload_buffer, payload);
        if (!processing_events) {
            processing_events = true;
            spin1_trigger_user_event(0, 0);
        }
    }
    else {
        provenance_data.number_of_over_flows_payload += 1;
    }
}

void read_parameters(address_t region_address) {

    // P bit
    apply_prefix = region_address[APPLY_PREFIX];

    // Prefix data
    prefix = region_address[PREFIX];

    // F bit (for the receiver)
    prefix_type = region_address[PREFIX_TYPE];

    // Type bits
    packet_type = region_address[PACKET_TYPE];

    // Right packet shift (for the sender)
    key_right_shift = region_address[KEY_RIGHT_SHIFT];

    // T bit
    payload_timestamp = region_address[PAYLOAD_TIMESTAMP];

    // D bit
    payload_apply_prefix = region_address[PAYLOAD_APPLY_PREFIX];

    // Payload prefix data (for the receiver)
    payload_prefix = region_address[PAYLOAD_PREFIX];

    // Right payload shift (for the sender)
    payload_right_shift = region_address[PAYLOAD_RIGHT_SHIFT];
    sdp_tag = region_address[SDP_TAG];
    sdp_dest = region_address[SDP_DEST];
    packets_per_timestamp = region_address[PACKETS_PER_TIMESTEP];

    log_info("apply_prefix: %d\n", apply_prefix);
    log_info("prefix: %08x\n", prefix);
    log_info("prefix_type: %d\n", prefix_type);
    log_info("packet_type: %d\n", packet_type);
    log_info("key_right_shift: %d\n", key_right_shift);
    log_info("payload_timestamp: %d\n", payload_timestamp);
    log_info("payload_apply_prefix: %d\n", payload_apply_prefix);
    log_info("payload_prefix: %08x\n", payload_prefix);
    log_info("payload_right_shift: %d\n", payload_right_shift);
    log_info("sdp_tag: %d\n", sdp_tag);
    log_info("sdp_dest: 0x%08x\n", sdp_dest);
    log_info("packets_per_timestamp: %d\n", packets_per_timestamp);
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
            &infinite_run, SDP, record_provenance_data,
            data_specification_get_region(PROVENANCE_REGION, address))) {
        return false;
    }

    // Fix simulation ticks to be one extra timer period to soak up last events
    if (infinite_run != TRUE) {
        simulation_ticks += 1;
    }

    // Read the parameters
    read_parameters(
        data_specification_get_region(CONFIGURATION_REGION, address));

    return true;
}

bool configure_sdp_msg(void) {
    log_info("configure_sdp_msg\n");

    void *temp_ptr;

    temp_header = 0;
    event_size = 0;

    // initialise SDP header
    g_event_message.tag = sdp_tag;

    // No reply required
    g_event_message.flags = 0x07;

    // Chip 0,0
    g_event_message.dest_addr = sdp_dest;

    // Dump through Ethernet
    g_event_message.dest_port = PORT_ETH;

    // Set up monitoring address and port
    g_event_message.srce_addr = spin1_get_chip_id();
    g_event_message.srce_port = (3 << PORT_SHIFT) | spin1_get_core_id();

    // check incompatible options
    if (payload_timestamp && payload_apply_prefix && (packet_type & 0x1)) {
        log_error("Timestamp can either be included as payload prefix or as"
                  "payload to each key, not both\n");
        return false;
    }
    if (payload_timestamp && !payload_apply_prefix && !(packet_type & 0x1)) {
        log_error("Timestamp can either be included as payload prefix or as"
                  "payload to each key, but current configuration does not"
                  "specify either of these\n");
        return false;
    }

    // initialise AER header
    // pointer to data space
    sdp_msg_aer_header = &g_event_message.cmd_rc;

    temp_header |= (apply_prefix << 15);
    temp_header |= (prefix_type << 14);
    temp_header |= (payload_apply_prefix << 13);
    temp_header |= (payload_timestamp << 12);
    temp_header |= (packet_type << 10);

    header_len = 2;
    temp_ptr = (void *) sdp_msg_aer_header[1];

    // pointers for AER packet header, prefix and data
    if (apply_prefix) {

        // pointer to key prefix
        sdp_msg_aer_key_prefix = (sdp_msg_aer_header + 1);
        temp_ptr = (void *) (sdp_msg_aer_header + 2);
        sdp_msg_aer_key_prefix[0] = (uint16_t) prefix;
        header_len += 2;
    } else {
        sdp_msg_aer_key_prefix = NULL;
        temp_ptr = (void *) (sdp_msg_aer_header + 1);
    }

    if (payload_apply_prefix) {
        sdp_msg_aer_payload_prefix = temp_ptr;
        uint16_t *a = (uint16_t *) sdp_msg_aer_payload_prefix;

        log_debug("temp_ptr: %08x\n", (uint32_t) temp_ptr);
        log_debug("a: %08x\n", (uint32_t) a);

        // pointer to payload prefix
        sdp_msg_aer_payload_prefix = temp_ptr;

        if (!(packet_type & 0x2)) {

            //16 bit payload prefix
            temp_ptr = (void *) (a + 1);
            header_len += 2;
            if (!payload_timestamp) {

                // add payload prefix as required - not a timestamp
                a[0] = payload_prefix;
            }
            log_debug("16 bit - temp_ptr: %08x\n", (uint32_t) temp_ptr);

        } else {

            //32 bit payload prefix
            temp_ptr = (void *) (a + 2);
            header_len += 4;
            if (!payload_timestamp) {

                // add payload prefix as required - not a timestamp
                a[0] = (payload_prefix & 0xFFFF);
                a[1] = ((payload_prefix >> 16) & 0xFFFF);
            }
            log_debug("32 bit - temp_ptr: %08x\n", (uint32_t) temp_ptr);
        }
    } else {
        sdp_msg_aer_payload_prefix = NULL;
    }

    // pointer to write data
    sdp_msg_aer_data = (void *) temp_ptr;

    switch (packet_type) {
    case 0:
        event_size = 2;
        break;

    case 1:
        event_size = 4;
        break;

    case 2:
        event_size = 4;
        break;

    case 3:
        event_size = 8;
        break;

    default:
        log_error("unknown packet type: %d\n", packet_type);
        return false;
    }

    log_debug("sdp_msg_aer_header: %08x\n", (uint32_t) sdp_msg_aer_header);
    log_debug("sdp_msg_aer_key_prefix: %08x\n",
              (uint32_t) sdp_msg_aer_key_prefix);
    log_debug("sdp_msg_aer_payload_prefix: %08x\n",
              (uint32_t) sdp_msg_aer_payload_prefix);
    log_debug("sdp_msg_aer_data: %08x\n", (uint32_t) sdp_msg_aer_data);

    packets_sent = 0;
    buffer_index = 0;

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

    // Configure SDP message
    if (!configure_sdp_msg()) {
         rt_error(RTE_SWERR);
    }

    // Set up circular buffers for multicast message reception
    without_payload_buffer = circular_buffer_initialize(256);
    with_payload_buffer = circular_buffer_initialize(512);

    // Set timer_callback
    spin1_set_timer_tick(timer_period);

    // Register callbacks
    spin1_callback_on(MC_PACKET_RECEIVED, incoming_event_callback, MC_PACKET);
    spin1_callback_on(
        MCPL_PACKET_RECEIVED, incoming_event_payload_callback, MC_PACKET);
    spin1_callback_on(
        USER_EVENT, incoming_event_process_callback, USER);
    spin1_callback_on(TIMER_TICK, timer_callback, TIMER);

    // Start the time at "-1" so that the first tick will be 0
    time = UINT32_MAX;
    simulation_run();
}

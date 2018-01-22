#include <common-typedefs.h>
#include <data_specification.h>
#include <debug.h>
#include <simulation.h>
#include <sark.h>
#include <string.h>
#include <buffered_eieio_defs.h>
#include "recording.h"

// Declare wfi function
extern void spin1_wfi();

#ifndef APPLICATION_NAME_HASH
#define APPLICATION_NAME_HASH 0
#error APPLICATION_NAME_HASH must be defined
#endif

//! The EIEIO message types

//! \brief human readable versions of the different priorities and usages.
typedef enum callback_priorities {
    SDP_CALLBACK = 1, TIMER = 2, DMA = 0
}callback_priorities;

typedef enum eieio_data_message_types {
    KEY_16_BIT, KEY_PAYLOAD_16_BIT, KEY_32_BIT, KEY_PAYLOAD_32_bIT
} eieio_data_message_types;

//! The EIEIO prefix types
typedef enum eieio_prefix_types {
    PREFIX_TYPE_LOWER_HALF_WORD, PREFIX_TYPE_UPPER_HALF_WORD
} eieio_prefix_types;

//! The parameter positions
typedef enum read_in_parameters{
    APPLY_PREFIX, PREFIX, PREFIX_TYPE, CHECK_KEYS, HAS_KEY, KEY_SPACE, MASK,
    BUFFER_REGION_SIZE, SPACE_BEFORE_DATA_REQUEST, RETURN_TAG_ID,
    RETURN_TAG_DEST, BUFFERED_IN_SDP_PORT
} read_in_parameters;

//! The memory regions
typedef enum memory_regions{
    SYSTEM,
    CONFIGURATION,
    RECORDING_REGION,
    BUFFER_REGION,
    PROVENANCE_REGION,
} memory_regions;

//! The provenance data items
typedef enum provenance_items {
    N_RECEIVED_PACKETS,
    N_SENT_PACKETS,
    INCORRECT_KEYS,
    INCORRECT_PACKETS,
    LATE_PACKETS
} provenance_items;

//! The number of regions that can be recorded
#define NUMBER_OF_REGIONS_TO_RECORD 1
#define SPIKE_HISTORY_CHANNEL 0

//! the minimum space required for a buffer to work
#define MIN_BUFFER_SPACE 10

//! the amount of ticks to wait between requests
#define TICKS_BETWEEN_REQUESTS 25

//! the maximum size of a packet
#define MAX_PACKET_SIZE 280

#pragma pack(1)

typedef struct {
    uint32_t length;
    uint32_t time;
    uint8_t data[MAX_PACKET_SIZE];
} recorded_packet_t;

typedef struct {
    uint16_t event;
    uint16_t payload;
} event16_t;

typedef struct {
    uint16_t eieio_header_command;
    uint16_t chip_id;
    uint8_t processor;
    uint8_t pad1;
    uint8_t region;
    uint8_t sequence;
    uint32_t space_available;
} req_packet_sdp_t;

// Globals
static uint32_t time;
static uint32_t simulation_ticks;
static uint32_t infinite_run;
static bool apply_prefix;
static bool check;
static uint32_t prefix;
static bool has_key;
static uint32_t key_space;
static uint32_t mask;
static uint32_t incorrect_keys;
static uint32_t incorrect_packets;
static uint32_t late_packets;
static uint32_t last_stop_notification_request;
static eieio_prefix_types prefix_type;
static uint32_t buffer_region_size;
static uint32_t space_before_data_request;
static uint32_t n_received_packets = 0;
static uint32_t n_send_packets = 0;

//! keeps track of which types of recording should be done to this model.
static uint32_t recording_flags = 0;

static uint8_t *buffer_region;
static uint8_t *end_of_buffer_region;
static uint8_t *write_pointer;
static uint8_t *read_pointer;

sdp_msg_t req;
req_packet_sdp_t *req_ptr;
static eieio_msg_t msg_from_sdram;
static bool msg_from_sdram_in_use;
static int msg_from_sdram_length;
static uint32_t next_buffer_time;
static uint8_t pkt_last_sequence_seen;
static bool send_packet_reqs;
static bool last_buffer_operation;
static uint8_t return_tag_id;
static uint32_t return_tag_dest;
static uint32_t buffered_in_sdp_port;
static uint32_t last_space;
static uint32_t last_request_tick;

static bool stopped = false;

static bool recording_in_progress = false;
static recorded_packet_t *recorded_packet;

static inline uint16_t calculate_eieio_packet_command_size(
        eieio_msg_t eieio_msg_ptr) {
    uint16_t data_hdr_value = eieio_msg_ptr[0];
    uint16_t command_number = data_hdr_value & ~0xC000;

    switch (command_number) {
    case DATABASE_CONFIRMATION:
    case EVENT_PADDING:
    case EVENT_STOP_COMMANDS:
    case STOP_SENDING_REQUESTS:
    case START_SENDING_REQUESTS:
        return 2;
    case SPINNAKER_REQUEST_BUFFERS:
        return 12;
    case HOST_SEND_SEQUENCED_DATA:

        // does not include the EIEIO packet payload
        return 4;
    case SPINNAKER_REQUEST_READ_DATA:
        return 16;
    case HOST_DATA_READ:
        return 8;
    default:
        return 0;
    }
    return 0;
}

static inline uint16_t calculate_eieio_packet_event_size(
        eieio_msg_t eieio_msg_ptr) {
    uint16_t data_hdr_value = eieio_msg_ptr[0];
    uint8_t pkt_type = (uint8_t)(data_hdr_value >> 10 & 0x3);
    bool pkt_apply_prefix = (bool)(data_hdr_value >> 15);
    bool pkt_payload_prefix_apply = (bool)(data_hdr_value >> 13 & 0x1);
    uint8_t event_count = data_hdr_value & 0xFF;
    uint16_t event_size, total_size;
    uint16_t header_size = 2;

    switch (pkt_type) {
    case KEY_16_BIT:
        event_size = 2;
        break;
    case KEY_PAYLOAD_16_BIT:
    case KEY_32_BIT:
        event_size = 4;
        break;
    case KEY_PAYLOAD_32_bIT:
        event_size = 8;
        break;
    }

    if (pkt_apply_prefix) {
        header_size += 2;
    }
    if (pkt_payload_prefix_apply) {
        if (pkt_type == 0 || pkt_type == 1) {
            header_size += 2;
        } else {
            header_size += 4;
        }
    }

    total_size = event_count * event_size + header_size;
    return total_size;
}

static inline uint16_t calculate_eieio_packet_size(eieio_msg_t eieio_msg_ptr) {
    uint16_t data_hdr_value = eieio_msg_ptr[0];
    uint8_t pkt_type = (data_hdr_value >> 14) & 0x03;

    if (pkt_type == 0x01) {
        return calculate_eieio_packet_command_size(eieio_msg_ptr);
    } else {
        return calculate_eieio_packet_event_size(eieio_msg_ptr);
    }
}

static inline void print_packet_bytes(
        eieio_msg_t eieio_msg_ptr, uint16_t length) {
    use(eieio_msg_ptr);
    use(length);
#if LOG_LEVEL >= LOG_DEBUG
    uint8_t *ptr = (uint8_t *) eieio_msg_ptr;

    log_debug("packet of %d bytes:", length);

    for (int i = 0; i < length; i++) {
        if ((i & 7) == 0) {
            io_printf(IO_BUF, "\n");
        }
        io_printf(IO_BUF, "%02x", ptr[i]);
    }
    io_printf(IO_BUF, "\n");
#endif
}

static inline void print_packet(eieio_msg_t eieio_msg_ptr) {
    use(eieio_msg_ptr);
#if LOG_LEVEL >= LOG_DEBUG
    uint32_t len = calculate_eieio_packet_size(eieio_msg_ptr);
    print_packet_bytes(eieio_msg_ptr, len);
#endif
}

static inline void signal_software_error(
        eieio_msg_t eieio_msg_ptr, uint16_t length) {
    use(eieio_msg_ptr);
    use(length);
#if LOG_LEVEL >= LOG_DEBUG
    print_packet_bytes(eieio_msg_ptr, length);
    rt_error(RTE_SWERR);
#endif
}

static inline uint32_t get_sdram_buffer_space_available() {
    if (read_pointer < write_pointer) {
        uint32_t final_space =
            (uint32_t) end_of_buffer_region - (uint32_t) write_pointer;
        uint32_t initial_space =
            (uint32_t) read_pointer - (uint32_t) buffer_region;
        return final_space + initial_space;
    } else if (write_pointer < read_pointer) {
        return (uint32_t) read_pointer - (uint32_t) write_pointer;
    } else if (last_buffer_operation == BUFFER_OPERATION_WRITE) {

        // If pointers are equal, buffer is full if last operation is write
        return 0;
    } else {

        // If pointers are equal, buffer is empty if last operation is read
        return buffer_region_size;
    }
}

static inline bool is_eieio_packet_in_buffer(void) {

    // If there is no buffering being done, there are no packets
    if (buffer_region_size == 0) {
        return false;
    }

    // There are packets as long as the buffer is not empty; the buffer is
    // empty if the pointers are equal and the last operation was read
    return !((write_pointer == read_pointer) &&
            (last_buffer_operation == BUFFER_OPERATION_READ));
}

static inline uint32_t extract_time_from_eieio_msg(eieio_msg_t eieio_msg_ptr) {
    uint16_t data_hdr_value = eieio_msg_ptr[0];
    bool pkt_has_timestamp = (bool) ((data_hdr_value >> 12) & 0x1);
    bool pkt_apply_prefix = (bool) ((data_hdr_value >> 15) & 0x1);
    bool pkt_mode = (bool) ((data_hdr_value >> 14) & 0x1);

    // If the packet is actually a command packet, return the current time
    if (!pkt_apply_prefix && pkt_mode) {
        return time;
    }

    // If the packet indicates that payloads are timestamps
    if (pkt_has_timestamp) {
        bool pkt_payload_prefix_apply = (bool) ((data_hdr_value >> 13) & 0x1);
        uint8_t pkt_type = (uint8_t) ((data_hdr_value >> 10) & 0x3);
        uint32_t payload_time = 0;
        bool got_payload_time = false;
        uint16_t *event_ptr = &eieio_msg_ptr[1];

        // If there is a payload prefix
        if (pkt_payload_prefix_apply) {

            // If there is a key prefix, the payload prefix is after that
            if (pkt_apply_prefix) {
                event_ptr += 1;
            }

            if (pkt_type & 0x2) {

                // 32 bit packet
                payload_time = (event_ptr[1] << 16) | event_ptr[0];
                event_ptr += 2;
            } else {

                // 16 bit packet
                payload_time = event_ptr[0];
                event_ptr += 1;
            }
            got_payload_time = true;
        }

        // If the packets have a payload
        if (pkt_type & 0x1) {
            if (pkt_type & 0x2) {

                // 32 bit packet
                payload_time |= (event_ptr[1] << 16) | event_ptr[0];
            } else {

                // 16 bit packet
                payload_time |= event_ptr[0];
            }
            got_payload_time = true;
        }

        // If no actual time was found, return the current time
        if (!got_payload_time) {
            return time;
        }
        return payload_time;
    }

    // This is not a timed packet, return the current time
    return time;
}

static inline bool add_eieio_packet_to_sdram(
        eieio_msg_t eieio_msg_ptr, uint32_t length) {
    uint8_t *msg_ptr = (uint8_t *) eieio_msg_ptr;

    log_debug("read_pointer = 0x%.8x, write_pointer= = 0x%.8x,"
              "last_buffer_operation == read = %d, packet length = %d",
              read_pointer,  write_pointer,
              last_buffer_operation == BUFFER_OPERATION_READ, length);
    if ((read_pointer < write_pointer) ||
            (read_pointer == write_pointer &&
                last_buffer_operation == BUFFER_OPERATION_READ)) {
        uint32_t final_space =
            (uint32_t) end_of_buffer_region - (uint32_t) write_pointer;

        if (final_space >= length) {
            log_debug("Packet fits in final space of %d", final_space);

            spin1_memcpy(write_pointer, msg_ptr, length);
            write_pointer += length;
            last_buffer_operation = BUFFER_OPERATION_WRITE;
            if (write_pointer >= end_of_buffer_region) {
                write_pointer = buffer_region;
            }
            return true;
        } else {

            uint32_t total_space =
                final_space +
                ((uint32_t) read_pointer - (uint32_t) buffer_region);
            if (total_space < length) {
                log_debug("Not enough space (%d bytes)", total_space);
                return false;
            }

            log_debug(
                "Copying first %d bytes to final space of %d", final_space);
            spin1_memcpy(write_pointer, msg_ptr, final_space);
            write_pointer = buffer_region;
            msg_ptr += final_space;

            uint32_t final_len = length - final_space;
            log_debug("Copying remaining %d bytes", final_len);
            spin1_memcpy(write_pointer, msg_ptr, final_len);
            write_pointer += final_len;
            last_buffer_operation = BUFFER_OPERATION_WRITE;
            if (write_pointer == end_of_buffer_region) {
                write_pointer = buffer_region;
            }
            return true;
        }
    } else if (write_pointer < read_pointer) {
        uint32_t middle_space =
            (uint32_t) read_pointer - (uint32_t) write_pointer;

        if (middle_space < length) {
            log_debug("Not enough space in middle (%d bytes)", middle_space);
            return false;
        } else {
            log_debug("Packet fits in middle space of %d", middle_space);
            spin1_memcpy(write_pointer, msg_ptr, length);
            write_pointer += length;
            last_buffer_operation = BUFFER_OPERATION_WRITE;
            if (write_pointer == end_of_buffer_region) {
                write_pointer = buffer_region;
            }
            return true;
        }
    }

    log_debug("Buffer already full");
    return false;
}

static inline void process_16_bit_packets(
        void* event_pointer, bool pkt_prefix_upper, uint32_t pkt_count,
        uint32_t pkt_key_prefix, uint32_t pkt_payload_prefix,
        bool pkt_has_payload, bool pkt_payload_is_timestamp) {

    log_debug("process_16_bit_packets");
    log_debug("event_pointer: %08x", (uint32_t) event_pointer);
    log_debug("count: %d", pkt_count);
    log_debug("pkt_prefix: %08x", pkt_key_prefix);
    log_debug("pkt_payload_prefix: %08x", pkt_payload_prefix);
    log_debug("payload on: %d", pkt_has_payload);
    log_debug("pkt_format: %d", pkt_prefix_upper);

    uint16_t *next_event = (uint16_t *) event_pointer;
    for (uint32_t i = 0; i < pkt_count; i++) {
        uint32_t key = (uint32_t) next_event[0];
        log_debug("Packet key = %d", key);
        next_event += 1;
        uint32_t payload = 0;
        if (pkt_has_payload) {
            payload = (uint32_t) next_event[0];
            next_event += 1;
        }

        if (!pkt_prefix_upper) {
            key <<= 16;
        }
        key |= pkt_key_prefix;
        payload |= pkt_payload_prefix;

        log_debug(
            "check before send packet: check=%d, key=0x%08x, mask=0x%08x,"
            " key_space=%d: %d", check, key, mask, key_space,
            (!check) || (check && ((key & mask) == key_space)));

        if (has_key) {
            if (!check || (check && ((key & mask) == key_space))) {
                n_send_packets += 1;
                if (pkt_has_payload && !pkt_payload_is_timestamp) {
                    log_debug(
                        "mc packet 16-bit key=%d, payload=%d", key, payload);
                    while (!spin1_send_mc_packet(key, payload, WITH_PAYLOAD)) {
                        spin1_delay_us(1);
                    }
                } else {
                    log_debug(
                        "mc packet 16-bit key=%d", key);
                    while (!spin1_send_mc_packet(key, 0, NO_PAYLOAD)) {
                        spin1_delay_us(1);
                    }
                }
            } else {
                incorrect_keys++;
            }
        }
    }
}

static inline void process_32_bit_packets(
        void* event_pointer, uint32_t pkt_count,
        uint32_t pkt_key_prefix, uint32_t pkt_payload_prefix,
        bool pkt_has_payload, bool pkt_payload_is_timestamp) {

    log_debug("process_32_bit_packets");
    log_debug("event_pointer: %08x", (uint32_t) event_pointer);
    log_debug("count: %d", pkt_count);
    log_debug("pkt_prefix: %08x", pkt_key_prefix);
    log_debug("pkt_payload_prefix: %08x", pkt_payload_prefix);
    log_debug("payload on: %d", pkt_has_payload);

    uint16_t *next_event = (uint16_t *) event_pointer;
    for (uint32_t i = 0; i < pkt_count; i++) {
        uint32_t key = (next_event[1] << 16) | next_event[0];
        log_debug("Packet key = 0x%08x", key);
        next_event += 2;
        uint32_t payload = 0;
        if (pkt_has_payload) {
            payload = (next_event[1] << 16) | next_event[0];
            next_event += 2;
        }

        key |= pkt_key_prefix;
        payload |= pkt_payload_prefix;

        log_debug("check before send packet: %d",
                  (!check) || (check && ((key & mask) == key_space)));

        if (has_key) {
            if (!check || (check && ((key & mask) == key_space))) {
                n_send_packets += 1;
                if (pkt_has_payload && !pkt_payload_is_timestamp) {
                    log_debug(
                        "mc packet 32-bit key=0x%08x , payload=0x%08x",
                        key, payload);
                    while (!spin1_send_mc_packet(key, payload, WITH_PAYLOAD)) {
                        spin1_delay_us(1);
                    }
                } else {
                    log_debug("mc packet 32-bit key=0x%08x", key);
                    while (!spin1_send_mc_packet(key, 0, NO_PAYLOAD)) {
                        spin1_delay_us(1);
                    }
                }
            } else {
                incorrect_keys++;
            }
        }
    }
}

void recording_done_callback() {
    recording_in_progress = false;
}

static inline void record_packet(eieio_msg_t eieio_msg_ptr, uint32_t length) {
    if (recording_flags > 0) {
        while (recording_in_progress) {
            spin1_wfi();
        }

        // Ensure that the recorded data size is a multiple of 4
        uint32_t recording_length = 4 * ((length + 3) / 4);
        log_debug(
            "recording a eieio message with length %u", recording_length);
        recording_in_progress = true;
        recorded_packet->length = recording_length;
        recorded_packet->time = time;
        spin1_memcpy(recorded_packet->data, eieio_msg_ptr, recording_length);

        // NOTE: recording_length could be bigger than the length of the valid
        // data in eieio_msg_ptr.  This is OK as the data pointed to by
        // eieio_msg_ptr is always big enough to have extra space in it.  The
        // bytes in this data will be random, but are also ignored by
        // whatever reads the data.
        recording_record_and_notify(
            SPIKE_HISTORY_CHANNEL, recorded_packet, recording_length + 8,
            recording_done_callback);
    }
}

static inline bool eieio_data_parse_packet(
        eieio_msg_t eieio_msg_ptr, uint32_t length) {
    log_debug("eieio_data_process_data_packet");
    print_packet_bytes(eieio_msg_ptr, length);

    uint16_t data_hdr_value = eieio_msg_ptr[0];
    void *event_pointer = (void *) &eieio_msg_ptr[1];

    if (data_hdr_value == 0) {

        // Count is 0, so no data
        return true;
    }

    log_debug("====================================");
    log_debug("eieio_msg_ptr: %08x", (uint32_t) eieio_msg_ptr);
    log_debug("event_pointer: %08x", (uint32_t) event_pointer);
    print_packet(eieio_msg_ptr);

    bool pkt_apply_prefix = (bool) ((data_hdr_value >> 15) & 0x1);
    bool pkt_prefix_upper = (bool) ((data_hdr_value >> 14) & 0x1);
    bool pkt_payload_apply_prefix = (bool) ((data_hdr_value >> 13) & 0x1);
    uint8_t pkt_type = (uint8_t) ((data_hdr_value >> 10) & 0x3);
    uint8_t pkt_count = (uint8_t) (data_hdr_value & 0xFF);
    bool pkt_has_payload = (bool) (pkt_type & 0x1);

    uint32_t pkt_key_prefix = 0;
    uint32_t pkt_payload_prefix = 0;
    bool pkt_payload_is_timestamp = (bool)((data_hdr_value >> 12) & 0x1);

    log_debug("data_hdr_value: %04x", data_hdr_value);
    log_debug("pkt_apply_prefix: %d", pkt_apply_prefix);
    log_debug("pkt_format: %d", pkt_prefix_upper);
    log_debug("pkt_payload_prefix: %d", pkt_payload_apply_prefix);
    log_debug("pkt_timestamp: %d", pkt_payload_is_timestamp);
    log_debug("pkt_type: %d", pkt_type);
    log_debug("pkt_count: %d", pkt_count);
    log_debug("payload_on: %d", pkt_has_payload);

    uint16_t *hdr_pointer = (uint16_t *) event_pointer;

    if (pkt_apply_prefix) {

        // Key prefix in the packet
        pkt_key_prefix = (uint32_t) hdr_pointer[0];
        hdr_pointer += 1;

        // If the prefix is in the upper part, shift the prefix
        if (pkt_prefix_upper) {
            pkt_key_prefix <<= 16;
        }
    } else if (!pkt_apply_prefix && apply_prefix) {

        // If there isn't a key prefix, but the config applies a prefix,
        // apply the prefix depending on the key_left_shift
        pkt_key_prefix = prefix;
        if (prefix_type == PREFIX_TYPE_UPPER_HALF_WORD) {
            pkt_prefix_upper = true;
        } else {
            pkt_prefix_upper = false;
        }
    }

    if (pkt_payload_apply_prefix) {

        if (!(pkt_type & 0x2)) {

            // If there is a payload prefix and the payload is 16-bit
            pkt_payload_prefix = (uint32_t) hdr_pointer[0];
            hdr_pointer += 1;
        } else {

            // If there is a payload prefix and the payload is 32-bit
            pkt_payload_prefix =
                (((uint32_t) hdr_pointer[1] << 16) |
                 (uint32_t) hdr_pointer[0]);
            hdr_pointer += 2;
        }
    }

    // Take the event pointer to start at the header pointer
    event_pointer = (void *) hdr_pointer;

    // If the packet has a payload that is a timestamp, but the timestamp
    // is not the current time, buffer it
    if (pkt_has_payload && pkt_payload_is_timestamp &&
            pkt_payload_prefix != time) {
        if (pkt_payload_prefix > time) {
            add_eieio_packet_to_sdram(eieio_msg_ptr, length);
            return true;
        }
        late_packets += 1;
        return false;
    }

    if (pkt_type <= 1) {
        process_16_bit_packets(
            event_pointer, pkt_prefix_upper, pkt_count, pkt_key_prefix,
            pkt_payload_prefix, pkt_has_payload, pkt_payload_is_timestamp);
        record_packet(eieio_msg_ptr, length);
        return true;
    } else {
        process_32_bit_packets(
            event_pointer, pkt_count, pkt_key_prefix,
            pkt_payload_prefix, pkt_has_payload, pkt_payload_is_timestamp);
        record_packet(eieio_msg_ptr, length);
        return false;
    }
}

static inline void eieio_command_parse_stop_requests(
        eieio_msg_t eieio_msg_ptr, uint16_t length) {
    use(eieio_msg_ptr);
    use(length);
    log_debug("Stopping packet requests - parse_stop_packet_reqs");
    send_packet_reqs = false;
    last_stop_notification_request = time;
}

static inline void eieio_command_parse_start_requests(
        eieio_msg_t eieio_msg_ptr, uint16_t length) {
    use(eieio_msg_ptr);
    use(length);
    log_debug("Starting packet requests - parse_start_packet_reqs");
    send_packet_reqs = true;
}

static inline void eieio_command_parse_sequenced_data(
        eieio_msg_t eieio_msg_ptr, uint16_t length) {
    uint16_t sequence_value_region_id = eieio_msg_ptr[1];
    uint16_t region_id = sequence_value_region_id & 0xFF;
    uint16_t sequence_value = (sequence_value_region_id >> 8) & 0xFF;
    uint8_t next_expected_sequence_no =
        (pkt_last_sequence_seen + 1) & MAX_SEQUENCE_NO;
    eieio_msg_t eieio_content_pkt = &eieio_msg_ptr[2];

    if (region_id != BUFFER_REGION) {
        log_debug("received sequenced eieio packet with invalid region id:"
                  " %d.", region_id);
        signal_software_error(eieio_msg_ptr, length);
        incorrect_packets++;
    }

    log_debug("Received packet sequence number: %d", sequence_value);

    if (sequence_value == next_expected_sequence_no) {

        // parse_event_pkt returns false in case there is an error and the
        // packet is dropped (i.e. as it was never received)
        log_debug("add_eieio_packet_to_sdram");
        bool ret_value = add_eieio_packet_to_sdram(eieio_content_pkt,
                                                   length - 4);
        log_debug("add_eieio_packet_to_sdram return value: %d", ret_value);

        if (ret_value) {
            pkt_last_sequence_seen = sequence_value;
            log_debug("Updating last sequence seen to %d",
                pkt_last_sequence_seen);
        } else {
            log_debug("unable to buffer sequenced data packet.");
            signal_software_error(eieio_msg_ptr, length);
            incorrect_packets++;
        }
    }
}

static inline bool eieio_commmand_parse_packet(eieio_msg_t eieio_msg_ptr,
                                               uint16_t length) {
    uint16_t data_hdr_value = eieio_msg_ptr[0];
    uint16_t pkt_command = data_hdr_value & (~0xC000);

    switch (pkt_command) {
    case HOST_SEND_SEQUENCED_DATA:
        log_debug("command: HOST_SEND_SEQUENCED_DATA");
        eieio_command_parse_sequenced_data(eieio_msg_ptr, length);
        break;

    case STOP_SENDING_REQUESTS:
        log_debug("command: STOP_SENDING_REQUESTS");
        eieio_command_parse_stop_requests(eieio_msg_ptr, length);
        break;

    case START_SENDING_REQUESTS:
        log_debug("command: START_SENDING_REQUESTS");
        eieio_command_parse_start_requests(eieio_msg_ptr, length);
        break;

    case EVENT_STOP_COMMANDS:
        log_debug("command: EVENT_STOP");
        stopped = true;
        write_pointer = read_pointer;
        break;

    default:
        return false;
        break;
    }
    return true;
}

static inline bool packet_handler_selector(eieio_msg_t eieio_msg_ptr,
                                           uint16_t length) {
    log_debug("packet_handler_selector");

    uint16_t data_hdr_value = eieio_msg_ptr[0];
    uint8_t pkt_type = (data_hdr_value >> 14) & 0x03;

    if (pkt_type == 0x01) {
        log_debug("parsing a command packet");
        return eieio_commmand_parse_packet(eieio_msg_ptr, length);
    } else {
        log_debug("parsing an event packet");
        return eieio_data_parse_packet(eieio_msg_ptr, length);
    }
}

void fetch_and_process_packet() {
    uint32_t last_len = 2;

    log_debug("in fetch_and_process_packet");
    msg_from_sdram_in_use = false;

    // If we are not buffering, there is nothing to do
    log_debug("buffer size is %d", buffer_region_size);
    if (buffer_region_size == 0) {
        return;
    }

    log_debug("dealing with SDRAM is set to %d", msg_from_sdram_in_use);
    log_debug(
        "has_eieio_packet_in_buffer set to %d",
        is_eieio_packet_in_buffer());
    while ((!msg_from_sdram_in_use) && is_eieio_packet_in_buffer() &&
            last_len > 0) {

        // If there is padding, move on 2 bytes
        uint16_t next_header = (uint16_t) *read_pointer;
        if (next_header == 0x4002) {
            read_pointer += 2;
            if (read_pointer >= end_of_buffer_region) {
                read_pointer = buffer_region;
            }
        } else {
            uint8_t *src_ptr = (uint8_t *) read_pointer;
            uint8_t *dst_ptr = (uint8_t *) msg_from_sdram;
            uint32_t len = calculate_eieio_packet_size(
                (eieio_msg_t) read_pointer);

            last_len = len;
            if (len > MAX_PACKET_SIZE) {
                log_error("Packet from SDRAM of %u bytes is too big!", len);
                rt_error(RTE_SWERR);
            }
            uint32_t final_space = (end_of_buffer_region - read_pointer);

            log_debug("packet with length %d, from address: %08x", len,
                      read_pointer);

            if (len > final_space) {

                // If the packet is split, get the bits
                log_debug("split packet");
                log_debug("1 - reading packet to %08x from %08x length: %d",
                          (uint32_t) dst_ptr, (uint32_t) src_ptr, final_space);
                spin1_memcpy(dst_ptr, src_ptr, final_space);

                uint32_t remaining_len = len - final_space;
                dst_ptr += final_space;
                src_ptr = buffer_region;
                log_debug("2 - reading packet to %08x from %08x length: %d",
                          (uint32_t) dst_ptr, (uint32_t) src_ptr,
                          remaining_len);

                spin1_memcpy(dst_ptr, src_ptr, remaining_len);
                read_pointer = buffer_region + remaining_len;
            } else {

                // If the packet is whole, get the packet
                log_debug("full packet");
                log_debug("1 - reading packet to %08x from %08x length: %d",
                          (uint32_t) dst_ptr, (uint32_t) src_ptr, len);

                spin1_memcpy(dst_ptr, src_ptr, len);
                read_pointer += len;
                if (read_pointer >= end_of_buffer_region) {
                    read_pointer = buffer_region;
                }
            }

            last_buffer_operation = BUFFER_OPERATION_READ;

            print_packet_bytes(msg_from_sdram, len);
            next_buffer_time = extract_time_from_eieio_msg(msg_from_sdram);
            log_debug("packet time: %d, current time: %d",
                      next_buffer_time, time);

            if (next_buffer_time <= time) {
                packet_handler_selector(msg_from_sdram, len);
            } else {
                msg_from_sdram_in_use = true;
                msg_from_sdram_length = len;
            }
        }
    }
}

void send_buffer_request_pkt(void) {
    uint32_t space = get_sdram_buffer_space_available();
    if ((space >= space_before_data_request) &&
            ((space != last_space) || (space == buffer_region_size))) {
        log_debug("sending request packet with space: %d and seq_no: %d at %u",
                  space, pkt_last_sequence_seen, time);

        last_space = space;
        req_ptr->sequence |= pkt_last_sequence_seen;
        req_ptr->space_available = space;
        spin1_send_sdp_msg(&req, 1);
        req_ptr->sequence &= 0;
        req_ptr->space_available = 0;
    }
}

bool read_parameters(address_t region_address) {

    // Get the configuration data
    apply_prefix = region_address[APPLY_PREFIX];
    prefix = region_address[PREFIX];
    prefix_type = (eieio_prefix_types) region_address[PREFIX_TYPE];
    check = region_address[CHECK_KEYS];
    has_key = region_address[HAS_KEY];
    key_space = region_address[KEY_SPACE];
    mask = region_address[MASK];
    buffer_region_size = region_address[BUFFER_REGION_SIZE];
    space_before_data_request = region_address[SPACE_BEFORE_DATA_REQUEST];
    return_tag_id = region_address[RETURN_TAG_ID];
    return_tag_dest = region_address[RETURN_TAG_DEST];
    buffered_in_sdp_port = region_address[BUFFERED_IN_SDP_PORT];

    // There is no point in sending requests until there is space for
    // at least one packet
    if (space_before_data_request < MIN_BUFFER_SPACE) {
        space_before_data_request = MIN_BUFFER_SPACE;
    }

    // Set the initial values
    incorrect_keys = 0;
    incorrect_packets = 0;
    msg_from_sdram_in_use = false;
    next_buffer_time = 0;
    pkt_last_sequence_seen = MAX_SEQUENCE_NO;
    send_packet_reqs = true;
    last_request_tick = 0;

    if (buffer_region_size != 0) {
        last_buffer_operation = BUFFER_OPERATION_WRITE;
    } else {
        last_buffer_operation = BUFFER_OPERATION_READ;
    }

    // allocate a buffer size of the maximum SDP payload size
    msg_from_sdram = (eieio_msg_t) spin1_malloc(MAX_PACKET_SIZE);
    recorded_packet = (recorded_packet_t *) spin1_malloc(
        sizeof(recorded_packet_t));

    req.length = 8 + sizeof(req_packet_sdp_t);
    req.flags = 0x7;
    req.tag = return_tag_id;
    req.dest_port = 0xFF;
    req.srce_port = (1 << 5) | spin1_get_core_id();
    req.dest_addr = return_tag_dest;
    req.srce_addr = spin1_get_chip_id();
    req_ptr = (req_packet_sdp_t*) &(req.cmd_rc);
    req_ptr->eieio_header_command = 1 << 14 | SPINNAKER_REQUEST_BUFFERS;
    req_ptr->chip_id = spin1_get_chip_id();
    req_ptr->processor = (spin1_get_core_id() << 3);
    req_ptr->pad1 = 0;
    req_ptr->region = BUFFER_REGION & 0x0F;

    log_info("apply_prefix: %d", apply_prefix);
    log_info("prefix: %d", prefix);
    log_info("prefix_type: %d", prefix_type);
    log_info("check: %d", check);
    log_info("key_space: 0x%08x", key_space);
    log_info("mask: 0x%08x", mask);
    log_info("space_before_read_request: %d", space_before_data_request);
    log_info("return_tag_id: %d", return_tag_id);
    log_info("return_tag_dest: 0x%08x", return_tag_dest);

    return true;
}

bool setup_buffer_region(address_t region_address) {
    buffer_region = (uint8_t *) region_address;
    read_pointer = buffer_region;
    write_pointer = buffer_region;
    end_of_buffer_region = buffer_region + buffer_region_size;

    log_info("buffer_region: 0x%.8x", buffer_region);
    log_info("buffer_region_size: %d", buffer_region_size);
    log_info("end_of_buffer_region: 0x%.8x", end_of_buffer_region);

    return true;
}

//! \brief Initialises the recording parts of the model
//! \return True if recording initialisation is successful, false otherwise
static bool initialise_recording(){
    address_t address = data_specification_get_data_address();
    address_t recording_region = data_specification_get_region(
            RECORDING_REGION, address);

    log_info("Recording starts at 0x%08x", recording_region);

    bool success = recording_initialize(recording_region, &recording_flags);
    log_info("Recording flags = 0x%08x", recording_flags);
    return success;
}

static void provenance_callback(address_t address) {
    address[N_RECEIVED_PACKETS] = n_received_packets;
    address[N_SENT_PACKETS] = n_send_packets;
    address[INCORRECT_KEYS] = incorrect_keys;
    address[INCORRECT_PACKETS] = incorrect_packets;
    address[LATE_PACKETS] = late_packets;
}

bool initialise(uint32_t *timer_period) {

    // Get the address this core's DTCM data starts at from SRAM
    address_t address = data_specification_get_data_address();

    // Read the header
    if (!data_specification_read_header(address)) {
        return false;
    }

    // Get the timing details and set up the simulation interface
    if (!simulation_initialise(
            data_specification_get_region(SYSTEM, address),
            APPLICATION_NAME_HASH, timer_period, &simulation_ticks,
            &infinite_run, SDP_CALLBACK, DMA)) {
        return false;
    }
    simulation_set_provenance_function(
        provenance_callback,
        data_specification_get_region(PROVENANCE_REGION, address));

    // Read the parameters
    if (!read_parameters(
            data_specification_get_region(CONFIGURATION, address))) {
        return false;
    }

    // set up recording data structures
    if (!initialise_recording()) {
         return false;
    }

    // Read the buffer region
    if (buffer_region_size > 0) {
        if (!setup_buffer_region(data_specification_get_region(
                BUFFER_REGION, address))) {
            return false;
        }
    }

    return true;
}

void resume_callback() {

    address_t address = data_specification_get_data_address();
    setup_buffer_region(data_specification_get_region(
        BUFFER_REGION, address));

    // set the code to start sending packet requests again
    send_packet_reqs = true;

    // magic state to allow the model to check for stuff in the SDRAM
    last_buffer_operation = BUFFER_OPERATION_WRITE;

    // have fallen out of a resume mode, set up the functions to start
    // resuming again
    recording_reset();

    stopped = false;
}

void timer_callback(uint unused0, uint unused1) {
    use(unused0);
    use(unused1);
    time++;

    log_debug("timer_callback, final time: %d, current time: %d,"
              "next packet buffer time: %d", simulation_ticks, time,
              next_buffer_time);

    if (stopped || ((infinite_run != TRUE) && (time >= simulation_ticks))) {

        // Wait for recording to finish
        while (recording_in_progress) {
            spin1_wfi();
        }

        // Enter pause and resume state to avoid another tick
        simulation_handle_pause_resume(resume_callback);

        // close recording channels
        if (recording_flags > 0) {
            recording_finalise();
        }

        log_debug("Last time of stop notification request: %d",
                  last_stop_notification_request);

        // Subtract 1 from the time so this tick gets done again on the next
        // run
        time = simulation_ticks - 1;

        return;
    }

    if (send_packet_reqs &&
            ((time - last_request_tick) >= TICKS_BETWEEN_REQUESTS)) {
        send_buffer_request_pkt();
        last_request_tick = time;
    }

    if (!msg_from_sdram_in_use) {
        fetch_and_process_packet();
    } else if (next_buffer_time < time) {
        late_packets += 1;
        fetch_and_process_packet();
    } else if (next_buffer_time == time) {
        eieio_data_parse_packet(msg_from_sdram, msg_from_sdram_length);
        fetch_and_process_packet();
    }

    if (recording_flags > 0) {
        recording_do_timestep_update(time);
    }
}

void sdp_packet_callback(uint mailbox, uint port) {
    use(port);
    sdp_msg_t *msg = (sdp_msg_t *) mailbox;
    uint16_t length = msg->length;
    eieio_msg_t eieio_msg_ptr = (eieio_msg_t) &(msg->cmd_rc);

    n_received_packets += 1;

    packet_handler_selector(eieio_msg_ptr, length - 8);

    // free the message to stop overload
    spin1_msg_free(msg);
}

// Entry point
void c_main(void) {

    // Configure system
    uint32_t timer_period = 0;
    if (!initialise(&timer_period)) {
        rt_error(RTE_SWERR);
        return;
    }

    // Set timer_callback
    spin1_set_timer_tick(timer_period);

    // Register callbacks
    simulation_sdp_callback_on(buffered_in_sdp_port, sdp_packet_callback);
    spin1_callback_on(TIMER_TICK, timer_callback, TIMER);

    // Start the time at "-1" so that the first tick will be 0
    time = UINT32_MAX;
    simulation_run();
}

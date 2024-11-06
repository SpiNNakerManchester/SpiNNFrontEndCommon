/*
 * Copyright (c) 2015 The University of Manchester
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

//! \file
//!
//! \brief The implementation of the Reverse IP tag Multicast Source.
//!
//! The purpose of this application is to inject SpiNNaker packets into the
//! on-chip network dynamically.

#include <common-typedefs.h>
#include <data_specification.h>
#include <debug.h>
#include <simulation.h>
#include <sark.h>
#include <eieio.h>
#include <buffered_eieio_defs.h>
#include "recording.h"
#include <wfi.h>

// ------------------------------------------------------------------------

#ifndef APPLICATION_NAME_HASH
#error APPLICATION_NAME_HASH must be defined
#endif

#ifndef __use
#define __use(x)    do { (void) (x); } while (0)
#endif

//! \brief human readable versions of the different priorities and usages.
enum interrupt_priorities {
    DMA = 0,
    SDP_CALLBACK = 1,
    TIMER = 2
};

//! The configuration parameters for the application
struct config {
    //! Whether to always apply a prefix
    uint32_t apply_prefix;
    //! The prefix to apply
    uint32_t prefix;
    //! The type of prefix that is supplied
    uint32_t prefix_type;
    //! Whether only packets with keys in the masked key space should be sent
    uint32_t check_keys;
    //! Whether a key is provided
    uint32_t has_key;
    //! The key space used for packet selection
    uint32_t key_space;
    //! The mask used for packet selection
    uint32_t mask;
    //! The size of the buffer region.
    uint32_t buffer_region_size;
    //! The point where we ask for the host to clear up space.
    uint32_t space_before_data_request;
    //! The SDP tag for sending messages to host
    uint32_t return_tag_id;
    //! The SDP destination for sending messages to host
    uint32_t return_tag_dest;
    //! The SDP port that we buffer messages in on.
    uint32_t buffered_in_sdp_port;
    //! \brief The timer offset to use for transmissions.
    //!
    //! Used to ensure we don't send all messages at the same time and overload
    //! SpiNNaker routers.
    uint32_t tx_offset;
};

//! The memory regions
enum region_ids {
    SYSTEM,
    CONFIGURATION,
    RECORDING_REGION,
    BUFFER_REGION,
    PROVENANCE_REGION,
};

//! The provenance data items
typedef struct ripmcs_provenance_t {
    uint32_t received_packets;  //!< How many EIEIO packets were received
    uint32_t sent_packets;      //!< How many MC packets were sent
    uint32_t incorrect_keys;    //!< Number of bad keys
    uint32_t incorrect_packets; //!< Number of bad packets (in non-debug mode)
    uint32_t late_packets;      //!< Number of packets dropped for being late
} ripmcs_provenance_t;

//! The number of regions that can be recorded
#define NUMBER_OF_REGIONS_TO_RECORD 1
//! The recording channel used to track the history of what spikes were sent
#define SPIKE_HISTORY_CHANNEL 0

//! the minimum space required for a buffer to work
#define MIN_BUFFER_SPACE 10

//! the amount of ticks to wait between requests
#define TICKS_BETWEEN_REQUESTS 25

//! the maximum size of a packet excluding header
#define MAX_PACKET_SIZE 272

#pragma pack(1)

//! \brief What information is recorded about a packet.
typedef struct {
    uint32_t length;               //!< The real length of recorded_packet_t::data
    uint32_t time;                 //!< The timestamp of this recording event
    uint8_t data[MAX_PACKET_SIZE]; //!< The content of the packet
} recorded_packet_t;

//! \brief An EIEIO request-for-more-space message
typedef struct {
    uint16_t eieio_header_command; //!< The command header
    uint16_t chip_id;              //!< What chip is making the request
    uint8_t processor;             //!< What core is making the request
    uint8_t _pad1;
    uint8_t region;                //!< What region is full
    uint8_t sequence;              //!< What sequence number we expect
    uint32_t space_available;      //!< How much space is available
} req_packet_sdp_t;

#pragma pack()

// ------------------------------------------------------------------------
// Globals

//! Current simulation time
static uint32_t time;

//! The time that the simulation is scheduled to stop at
static uint32_t simulation_ticks;

//! True if the simulation will "run forever" (until user interrupt).
static uint32_t infinite_run;

//! If a prefix should be applied
static bool apply_prefix;

//! Whether only packets with keys in the masked key space should be sent
static bool check_key_in_space;

//! The prefix to apply
static uint32_t prefix;

//! Whether a key is present; _nothing_ is sent if no key is present
static bool has_key;

//! Pattern of keys that must be matched when ::check_key_in_space is true
static uint32_t key_space;

//! Mask for keys to determine if the key matches the ::key_space
static uint32_t mask;

//! DEBUG: time of last stop notification
static uint32_t last_stop_notification_request;

//! How to apply the ::prefix
static eieio_prefix_types prefix_type;

//! Size of buffer in ::buffer_region
static uint32_t buffer_region_size;

//! Threshold at which we ask for buffers to be cleared
static uint32_t space_before_data_request;

//! The provenance information that we're collecting
static ripmcs_provenance_t provenance = {0};

//! Keeps track of which types of recording should be done to this model.
static uint32_t recording_flags = 0;

//! Points to the buffer used to store data being collected to transfer out.
static uint8_t *buffer_region;

//! Points to the end of the buffer (to first byte that must not be written)
static uint8_t *end_of_buffer_region;

//! Points to next byte to write in ::buffer_region
static uint8_t *write_pointer;

//! Points to next byte to read in ::buffer_region
static uint8_t *read_pointer;

//! An SDP message ready to send to host
static sdp_msg_t sdp_host_req;

//! Payload part of ::sdp_host_req
static req_packet_sdp_t *req_ptr;

//! DTCM buffer holding message copied from ::buffer_region
static eieio_msg_t msg_from_sdram;

//! Does ::msg_from_sdram currently contain a message being processed?
static bool msg_from_sdram_in_use;

//! Length of ::msg_from_sdram
static int msg_from_sdram_length;

//! Simulation time associated with message in ::msg_from_sdram
static uint32_t next_buffer_time;

//! Most recently seen message sequence number
static uint8_t pkt_last_sequence_seen;

//! Whether request packets should be sent.
static bool send_packet_reqs;

//! What the last operation done on ::buffer_region was
static buffered_operations last_buffer_operation;

//! The SDP tag for sending messages to host
static uint8_t return_tag_id;

//! The SDP destination for sending messages to host
static uint32_t return_tag_dest;

//! The SDP port that we buffer messages in on.
static uint32_t buffered_in_sdp_port;

//! \brief The timer offset to use for transmissions.
//!
//! Used to ensure we don't send all messages at the same time and overload
//! SpiNNaker routers.
static uint32_t tx_offset;

//! \brief Last value of result of get_sdram_buffer_space_available() in
//! send_buffer_request_pkt()
static uint32_t last_space;

//! \brief Last (sim) time we forced the buffers clear from timer_callback()
static uint32_t last_request_tick;

//! Whether this app has been asked to stop running
static bool stopped = false;

//! Buffer used for recording inbound packets
static recorded_packet_t *recorded_packet;

// ------------------------------------------------------------------------

//! \brief Extract a field from a bitfield value.
//! \param[in] value: the bitfield value
//! \param[in] shift: the index of the start of the LSB of the field
//! \param[in] mask: the mask for the value, once shifted to the bottom of the
//!                  word
//! \return The actual field value
#define BITS(value, shift, mask) \
    (((value) >> (shift)) & (mask))

//! \brief What is the size of a command message?
//! \param[in] eieio_msg_ptr Pointer to the message
//! \return The size of the command message, in bytes
static inline uint16_t calculate_eieio_packet_command_size(
        const eieio_msg_t eieio_msg_ptr) {
    uint16_t data_hdr_value = eieio_msg_ptr[0];
    uint16_t command_number = data_hdr_value & ~0xC000;

    switch (command_number) {
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

//! \brief What is the size of an event message?
//! \param[in] eieio_msg_ptr: Pointer to the message
//! \return The size of the event message, in bytes
static inline uint16_t calculate_eieio_packet_event_size(
        const eieio_msg_t eieio_msg_ptr) {
    uint16_t data_hdr_value = eieio_msg_ptr[0];
    bool pkt_apply_prefix = (bool) BITS(data_hdr_value, APPLY_PREFIX, 0x1);
    bool pkt_payload_prefix_apply = (bool)
            BITS(data_hdr_value, APPLY_PAYLOAD_PREFIX, 0x1);
    uint8_t pkt_type = (uint8_t) BITS(data_hdr_value, PACKET_TYPE, 0x3);
    uint8_t event_count = BITS(data_hdr_value, COUNT, 0xFF);
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

//! \brief What is the size of a message?
//! \param[in] eieio_msg_ptr: Pointer to the message
//! \return The size of the message, in bytes
static inline uint16_t calculate_eieio_packet_size(eieio_msg_t eieio_msg_ptr) {
    uint16_t data_hdr_value = eieio_msg_ptr[0];
    uint8_t pkt_class = BITS(data_hdr_value, PACKET_CLASS, 0x03);

    if (pkt_class == 0x01) {
        return calculate_eieio_packet_command_size(eieio_msg_ptr);
    } else {
        return calculate_eieio_packet_event_size(eieio_msg_ptr);
    }
}

//! \brief Dumps a message to IOBUF if debug messages are enabled
//! \param[in] eieio_msg_ptr: Pointer to the message to print
//! \param[in] length: Length of the message
static inline void print_packet_bytes(
        eieio_msg_t eieio_msg_ptr, uint16_t length) {
    __use(eieio_msg_ptr);
    __use(length);
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

//! \brief Dumps a message to IOBUF if debug messages are enabled
//!
//! Combines calculate_eieio_packet_size() and print_packet_bytes()
//!
//! \param[in] eieio_msg_ptr Pointer to the message to print
static inline void print_packet(const eieio_msg_t eieio_msg_ptr) {
    __use(eieio_msg_ptr);
#if LOG_LEVEL >= LOG_DEBUG
    uint32_t len = calculate_eieio_packet_size(eieio_msg_ptr);
    print_packet_bytes(eieio_msg_ptr, len);
#endif
}

//! \brief Flags up that bad input was received.
//!
//! This triggers an RTE, but only in debug mode.
//!
//! \param[in] eieio_msg_ptr: The bad message
//! \param[in] length: The length of the message
static inline void signal_software_error(
        const eieio_msg_t eieio_msg_ptr, uint16_t length) {
    __use(eieio_msg_ptr);
    __use(length);
#if LOG_LEVEL >= LOG_DEBUG
    print_packet_bytes(eieio_msg_ptr, length);
    rt_error(RTE_SWERR);
#endif
}

//! \brief Computes how much space is available in the buffer.
//! \return The number of available bytes.
static inline uint32_t get_sdram_buffer_space_available(void) {
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

//! \brief Whether we have a packet in the buffer.
//! \return True if the buffer is in use.
static inline bool is_eieio_packet_in_buffer(void) {
    // If there is no buffering being done, there are no packets
    if (buffer_region_size == 0) {
        return false;
    }

    // There are packets as long as the buffer is not empty; the buffer is
    // empty if the pointers are equal and the last operation was read
    return (write_pointer != read_pointer) ||
            (last_buffer_operation != BUFFER_OPERATION_READ);
}

//! \brief Get the time from a message.
//! \param[in] eieio_msg_ptr: The EIEIO message.
//! \return The timestamp from the message, or the current time if the message
//! did not have a timestamp.
static inline uint32_t extract_time_from_eieio_msg(
        const eieio_msg_t eieio_msg_ptr) {
    uint16_t data_hdr_value = eieio_msg_ptr[0];
    bool pkt_has_timestamp = (bool)
            BITS(data_hdr_value, PAYLOAD_IS_TIMESTAMP, 0x1);
    bool pkt_apply_prefix = (bool) BITS(data_hdr_value, APPLY_PREFIX, 0x1);
    bool pkt_class = (bool) BITS(data_hdr_value, PACKET_CLASS, 0x1);

    // If the packet is actually a command packet, return the current time
    if (!pkt_apply_prefix && pkt_class) {
        return time;
    }

    // If the packet indicates that payloads are timestamps
    if (pkt_has_timestamp) {
        bool pkt_payload_prefix_apply = (bool)
                BITS(data_hdr_value, APPLY_PAYLOAD_PREFIX, 0x1);
        uint8_t pkt_type = (uint8_t) BITS(data_hdr_value, PACKET_TYPE, 0x3);
        uint32_t payload_time = 0;
        bool got_payload_time = false;
        uint16_t *event_ptr = &eieio_msg_ptr[1];

        // If there is a payload prefix
        if (pkt_payload_prefix_apply) {
            // If there is a key prefix, the payload prefix is after that
            if (pkt_apply_prefix) {
                event_ptr++;
            }

            if (pkt_type & 0x2) {
                // 32 bit packet
                payload_time = (event_ptr[1] << 16) | event_ptr[0];
                event_ptr += 2;
            } else {
                // 16 bit packet
                payload_time = event_ptr[0];
                event_ptr++;
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

//! \brief Places a packet into the buffer.
//! \param[in] eieio_msg_ptr: The EIEIO message to store.
//! \param[in] length: The size of the message.
//! \return True if the packet was added, false if it was dropped due to the
//!         buffer being full.
static inline bool add_eieio_packet_to_sdram(
        const eieio_msg_t eieio_msg_ptr, uint32_t length) {
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
            uint32_t total_space = final_space +
                    ((uint32_t) read_pointer - (uint32_t) buffer_region);
            if (total_space < length) {
                log_debug("Not enough space (%d bytes)", total_space);
                return false;
            }

            log_debug("Copying first %d bytes to final space of %d",
                    length, final_space);
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
        }

        log_debug("Packet fits in middle space of %d", middle_space);
        spin1_memcpy(write_pointer, msg_ptr, length);
        write_pointer += length;
        last_buffer_operation = BUFFER_OPERATION_WRITE;
        if (write_pointer == end_of_buffer_region) {
            write_pointer = buffer_region;
        }
        return true;
    }

    log_debug("Buffer already full");
    return false;
}

//! \brief Handle an SDP message containing 16 bit events. The events are
//! converted into SpiNNaker multicast packets and sent.
//! \param[in] event_pointer: Where the events start
//! \param[in] pkt_prefix_upper: True if the prefix is an upper prefix.
//! \param[in] pkt_count: The number of events.
//! \param[in] pkt_key_prefix: The prefix for keys.
//! \param[in] pkt_payload_prefix: The prefix for payloads.
//! \param[in] pkt_has_payload: Whether there is a payload.
//! \param[in] pkt_payload_is_timestamp: Whether the payload is a timestamp.
static inline void process_16_bit_packets(
        const uint16_t* event_pointer, bool pkt_prefix_upper,
        uint32_t pkt_count,
        uint32_t pkt_key_prefix, uint32_t pkt_payload_prefix,
        bool pkt_has_payload, bool pkt_payload_is_timestamp) {
    log_debug("process_16_bit_packets");
    log_debug("event_pointer: %08x", (uint32_t) event_pointer);
    log_debug("count: %d", pkt_count);
    log_debug("pkt_prefix: %08x", pkt_key_prefix);
    log_debug("pkt_payload_prefix: %08x", pkt_payload_prefix);
    log_debug("payload on: %d", pkt_has_payload);
    log_debug("pkt_format: %d", pkt_prefix_upper);

    for (uint32_t i = 0; i < pkt_count; i++) {
        uint32_t key = (uint32_t) event_pointer[0];
        log_debug("Packet key = %d", key);
        event_pointer++;
        uint32_t payload = 0;
        if (pkt_has_payload) {
            payload = (uint32_t) event_pointer[0];
            event_pointer++;
        }

        if (!pkt_prefix_upper) {
            key <<= 16;
        }
        key |= pkt_key_prefix;
        payload |= pkt_payload_prefix;

        log_debug("check before send packet: check_key_in_space=%d, key=0x%08x,"
                " mask=0x%08x, key_space=%d: %d",
                check_key_in_space, key, mask, key_space,
                (!check_key_in_space || (key & mask) == key_space));

        if (has_key) {
            if (!check_key_in_space || (key & mask) == key_space) {
                provenance.sent_packets++;
                if (pkt_has_payload && !pkt_payload_is_timestamp) {
                    log_debug("mc packet 16-bit key=%d, payload=%d",
                            key, payload);
                    while (!spin1_send_mc_packet(key, payload, WITH_PAYLOAD)) {
                        spin1_delay_us(1);
                    }
                } else {
                    log_debug("mc packet 16-bit key=%d", key);
                    while (!spin1_send_mc_packet(key, 0, NO_PAYLOAD)) {
                        spin1_delay_us(1);
                    }
                }
            } else {
                provenance.incorrect_keys++;
            }
        }
    }
}

//! \brief Handle an SDP message containing 32 bit events. The events are
//! converted into SpiNNaker multicast packets and sent.
//! \param[in] event_pointer: Where the events start
//! \param[in] pkt_count: The number of events.
//! \param[in] pkt_key_prefix: The prefix for keys.
//! \param[in] pkt_payload_prefix: The prefix for payloads.
//! \param[in] pkt_has_payload: Whether there is a payload.
//! \param[in] pkt_payload_is_timestamp: Whether the payload is a timestamp.
static inline void process_32_bit_packets(
        const uint16_t* event_pointer, uint32_t pkt_count,
        uint32_t pkt_key_prefix, uint32_t pkt_payload_prefix,
        bool pkt_has_payload, bool pkt_payload_is_timestamp) {
    // Careful! event_pointer is not necessarily word aligned!
    log_debug("process_32_bit_packets");
    log_debug("event_pointer: %08x", (uint32_t) event_pointer);
    log_debug("count: %d", pkt_count);
    log_debug("pkt_prefix: %08x", pkt_key_prefix);
    log_debug("pkt_payload_prefix: %08x", pkt_payload_prefix);
    log_debug("payload on: %d", pkt_has_payload);

    for (uint32_t i = 0; i < pkt_count; i++) {
        uint32_t key = (event_pointer[1] << 16) | event_pointer[0];
        log_debug("Packet key = 0x%08x", key);
        event_pointer += 2;
        uint32_t payload = 0;
        if (pkt_has_payload) {
            payload = (event_pointer[1] << 16) | event_pointer[0];
            event_pointer += 2;
        }

        key |= pkt_key_prefix;
        payload |= pkt_payload_prefix;

        log_debug("check before send packet: %d",
                (!check_key_in_space || (key & mask) == key_space));

        if (has_key) {
            if (!check_key_in_space || (key & mask) == key_space) {
                provenance.sent_packets++;
                if (pkt_has_payload && !pkt_payload_is_timestamp) {
                    log_debug("mc packet 32-bit key=0x%08x, payload=0x%08x",
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
                provenance.incorrect_keys++;
            }
        }
    }
}

//! \brief Asynchronously record an EIEIO message.
//! \param[in] eieio_msg_ptr: The message to record.
//! \param[in] length: The length of the message.
static inline void record_packet(
        const eieio_msg_t eieio_msg_ptr, uint32_t length) {
    if (recording_flags > 0) {

        // Ensure that the recorded data size is a multiple of 4
        uint32_t recording_length = 4 * ((length + 3) / 4);
        log_debug("recording a EIEIO message with length %u",
                recording_length);
        recorded_packet->length = recording_length;
        recorded_packet->time = time;
        spin1_memcpy(recorded_packet->data, eieio_msg_ptr, recording_length);

        // NOTE: recording_length could be bigger than the length of the valid
        // data in eieio_msg_ptr.  This is OK as the data pointed to by
        // eieio_msg_ptr is always big enough to have extra space in it.  The
        // bytes in this data will be random, but are also ignored by
        // whatever reads the data.
        recording_record(SPIKE_HISTORY_CHANNEL, recorded_packet, recording_length + 8);
    }
}

//! \brief Parses an EIEIO message.
//!
//! This may cause the message to be saved for later, or may cause SpiNNaker
//! multicast messages to be sent at once.
//!
//! \param[in] eieio_msg_ptr: the message to handle
//! \param[in] length: the length of the message
//! \return True if the packet was successfully handled.
static inline bool eieio_data_parse_packet(
        const eieio_msg_t eieio_msg_ptr, uint32_t length) {
    log_debug("eieio_data_process_data_packet");
    print_packet_bytes(eieio_msg_ptr, length);

    uint16_t data_hdr_value = eieio_msg_ptr[0];
    const void *event_pointer = (const void *) &eieio_msg_ptr[1];

    if (data_hdr_value == 0) {
        // Count is 0, so no data
        return true;
    }

    log_debug("====================================");
    log_debug("eieio_msg_ptr: %08x", (uint32_t) eieio_msg_ptr);
    log_debug("event_pointer: %08x", (uint32_t) event_pointer);
    print_packet(eieio_msg_ptr);

    bool pkt_apply_prefix = (bool) BITS(data_hdr_value, APPLY_PREFIX, 0x1);
    bool pkt_prefix_upper = (bool) BITS(data_hdr_value, PREFIX_UPPER, 0x1);
    bool pkt_payload_apply_prefix = (bool)
            BITS(data_hdr_value, APPLY_PAYLOAD_PREFIX, 0x1);
    bool pkt_payload_is_timestamp = (bool)
            BITS(data_hdr_value, PAYLOAD_IS_TIMESTAMP, 0x1);
    uint8_t pkt_type = (uint8_t) BITS(data_hdr_value, PACKET_TYPE, 0x3);
    uint8_t pkt_count = (uint8_t) BITS(data_hdr_value, COUNT, 0xFF);
    bool pkt_has_payload = (bool) (pkt_type & 0x1);
    bool pkt_is_32bit = (bool) (pkt_type & 0x2);

    uint32_t pkt_key_prefix = 0;
    uint32_t pkt_payload_prefix = 0;

    log_debug("data_hdr_value: %04x", data_hdr_value);
    log_debug("pkt_apply_prefix: %d", pkt_apply_prefix);
    log_debug("pkt_format: %d", pkt_prefix_upper);
    log_debug("pkt_payload_prefix: %d", pkt_payload_apply_prefix);
    log_debug("pkt_timestamp: %d", pkt_payload_is_timestamp);
    log_debug("pkt_type: %d", pkt_type);
    log_debug("pkt_count: %d", pkt_count);
    log_debug("payload_on: %d", pkt_has_payload);

    const uint16_t *hdr_pointer = (const uint16_t *) event_pointer;

    if (pkt_apply_prefix) {
        // Key prefix in the packet
        pkt_key_prefix = (uint32_t) hdr_pointer[0];
        hdr_pointer++;

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
        if (!pkt_is_32bit) {
            // If there is a payload prefix and the payload is 16-bit
            pkt_payload_prefix = (uint32_t) hdr_pointer[0];
            hdr_pointer++;
        } else {
            // If there is a payload prefix and the payload is 32-bit
            pkt_payload_prefix =
                    ((uint32_t) hdr_pointer[1] << 16) | hdr_pointer[0];
            hdr_pointer += 2;
        }
    }

    // Take the event pointer to start at the header pointer
    event_pointer = (const void *) hdr_pointer;

    // If the packet has a payload that is a timestamp, but the timestamp
    // is not the current time, buffer it
    if (pkt_has_payload && pkt_payload_is_timestamp &&
            pkt_payload_prefix != time) {
        if (pkt_payload_prefix > time) {
            add_eieio_packet_to_sdram(eieio_msg_ptr, length);
            return true;
        }
        provenance.late_packets++;
        return false;
    }

    if (!pkt_is_32bit) {
        process_16_bit_packets(
                event_pointer, pkt_prefix_upper, pkt_count, pkt_key_prefix,
                pkt_payload_prefix, pkt_has_payload, pkt_payload_is_timestamp);
    } else {
        process_32_bit_packets(
                event_pointer, pkt_count, pkt_key_prefix,
                pkt_payload_prefix, pkt_has_payload, pkt_payload_is_timestamp);
    }
    record_packet(eieio_msg_ptr, length);
    return true;
}

//! \brief Handle the command to stop parsing requests.
//! \param[in] eieio_msg_ptr: The command message
//! \param[in] length: The length of the message
static inline void eieio_command_parse_stop_requests(
        UNUSED const eieio_msg_t eieio_msg_ptr, UNUSED uint16_t length) {
    log_debug("Stopping packet requests - parse_stop_packet_reqs");
    send_packet_reqs = false;
    last_stop_notification_request = time;
}

//! \brief Handle the command to start parsing requests.
//! \param[in] eieio_msg_ptr: The command message
//! \param[in] length: The length of the message
static inline void eieio_command_parse_start_requests(
        UNUSED const eieio_msg_t eieio_msg_ptr, UNUSED uint16_t length) {
    log_debug("Starting packet requests - parse_start_packet_reqs");
    send_packet_reqs = true;
}

//! \brief Handle the command to store a request for later processing.
//! \param[in] eieio_msg_ptr: The command message
//! \param[in] length: The length of the message
static inline void eieio_command_parse_sequenced_data(
        const eieio_msg_t eieio_msg_ptr, uint16_t length) {
    uint16_t sequence_value_region_id = eieio_msg_ptr[1];
    uint16_t region_id = BITS(sequence_value_region_id, 0, 0xFF);
    uint16_t sequence_value = BITS(sequence_value_region_id, 8, 0xFF);
    uint8_t next_expected_sequence_no =
            (pkt_last_sequence_seen + 1) & MAX_SEQUENCE_NO;
    eieio_msg_t eieio_content_pkt = &eieio_msg_ptr[2];

    if (region_id != BUFFER_REGION) {
        log_debug("received sequenced eieio packet with invalid region ID:"
                " %d.", region_id);
        signal_software_error(eieio_msg_ptr, length);
        provenance.incorrect_packets++;
    }

    log_debug("Received packet sequence number: %d", sequence_value);

    if (sequence_value == next_expected_sequence_no) {
        // parse_event_pkt returns false in case there is an error and the
        // packet is dropped (i.e. as it was never received)
        log_debug("add_eieio_packet_to_sdram");
        bool ret_value = add_eieio_packet_to_sdram(
                eieio_content_pkt, length - 4);
        log_debug("add_eieio_packet_to_sdram return value: %d", ret_value);

        if (ret_value) {
            pkt_last_sequence_seen = sequence_value;
            log_debug("Updating last sequence seen to %d",
                    pkt_last_sequence_seen);
        } else {
            log_debug("unable to buffer sequenced data packet.");
            signal_software_error(eieio_msg_ptr, length);
            provenance.incorrect_packets++;
        }
    }
}

//! \brief Handle a command message.
//! \param[in] eieio_msg_ptr: The command message
//! \param[in] length: The length of the message
//! \return True if the message was handled
static inline bool eieio_commmand_parse_packet(
        const eieio_msg_t eieio_msg_ptr, uint16_t length) {
    uint16_t data_hdr_value = eieio_msg_ptr[0];
    uint16_t pkt_command = BITS(data_hdr_value, PACKET_COMMAND, ~0xC000);

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
    }
    return true;
}

//! \brief Handle an EIEIO message, which can either be a command or an event
//! description message.
//! \param[in] eieio_msg_ptr: The message
//! \param[in] length: The length of the message
//! \return True if the message was handled.
static inline bool packet_handler_selector(
        const eieio_msg_t eieio_msg_ptr, uint16_t length) {
    log_debug("packet_handler_selector");

    uint16_t data_hdr_value = eieio_msg_ptr[0];
    uint8_t pkt_class = BITS(data_hdr_value, PACKET_CLASS, 0x03);

    if (pkt_class == 0x01) {
        log_debug("parsing a command packet");
        return eieio_commmand_parse_packet(eieio_msg_ptr, length);
    } else {
        log_debug("parsing an event packet");
        return eieio_data_parse_packet(eieio_msg_ptr, length);
    }
}

//! \brief Process a stored packet.
static void fetch_and_process_packet(void) {
    uint32_t last_len = 2;

    log_debug("in fetch_and_process_packet");
    msg_from_sdram_in_use = false;

    // If we are not buffering, there is nothing to do
    log_debug("buffer size is %d", buffer_region_size);
    if (buffer_region_size == 0) {
        return;
    }

    log_debug("dealing with SDRAM is set to %d", msg_from_sdram_in_use);
    log_debug("has_eieio_packet_in_buffer set to %d",
            is_eieio_packet_in_buffer());
    while (!msg_from_sdram_in_use && is_eieio_packet_in_buffer() &&
            (last_len > 0)) {
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
                log_error("Packet from SDRAM at 0x%08x of %u bytes is too big!",
                        src_ptr, len);
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
                        (uint32_t) dst_ptr, (uint32_t) src_ptr, remaining_len);

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

//! \brief Sends a message saying what our state is.
static void send_buffer_request_pkt(void) {
    uint32_t space = get_sdram_buffer_space_available();
    if ((space >= space_before_data_request) &&
            ((space != last_space) || (space == buffer_region_size))) {
        log_debug("sending request packet with space: %d and seq_no: %d at %u",
                space, pkt_last_sequence_seen, time);

        last_space = space;
        req_ptr->sequence |= pkt_last_sequence_seen;
        req_ptr->space_available = space;
        spin1_send_sdp_msg(&sdp_host_req, 1);
        req_ptr->sequence = 0;
        req_ptr->space_available = 0;
    }
}

//! \brief Reads our configuration region.
//! \param[in] config: The address of the configuration region.
//! \return True (always) if the data validates.
static bool read_parameters(struct config *config) {
    // Get the configuration data
    apply_prefix = config->apply_prefix;
    prefix = config->prefix;
    prefix_type = (eieio_prefix_types) config->prefix_type;
    check_key_in_space = config->check_keys;
    has_key = config->has_key;
    key_space = config->key_space;
    mask = config->mask;
    buffer_region_size = config->buffer_region_size;
    space_before_data_request = config->space_before_data_request;
    return_tag_id = config->return_tag_id;
    return_tag_dest = config->return_tag_dest;
    buffered_in_sdp_port = config->buffered_in_sdp_port;
    tx_offset = config->tx_offset;

    // There is no point in sending requests until there is space for
    // at least one packet
    if (space_before_data_request < MIN_BUFFER_SPACE) {
        space_before_data_request = MIN_BUFFER_SPACE;
    }

    // Set the initial values
    provenance.incorrect_keys = 0;
    provenance.incorrect_packets = 0;
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
    msg_from_sdram = spin1_malloc(MAX_PACKET_SIZE);
    recorded_packet = spin1_malloc(sizeof(recorded_packet_t));

    sdp_host_req.length = 8 + sizeof(req_packet_sdp_t);
    sdp_host_req.flags = 0x7;
    sdp_host_req.tag = return_tag_id;
    sdp_host_req.dest_port = 0xFF;
    sdp_host_req.srce_port = (1 << 5) | spin1_get_core_id();
    sdp_host_req.dest_addr = return_tag_dest;
    sdp_host_req.srce_addr = spin1_get_chip_id();
    req_ptr = (req_packet_sdp_t *) &sdp_host_req.cmd_rc;
    req_ptr->eieio_header_command = (1 << 14) | SPINNAKER_REQUEST_BUFFERS;
    req_ptr->chip_id = spin1_get_chip_id();
    req_ptr->processor = spin1_get_core_id() << 3;
    req_ptr->_pad1 = 0;
    req_ptr->region = BUFFER_REGION & 0x0F;

    log_info("apply_prefix: %d", apply_prefix);
    log_info("prefix: %d", prefix);
    log_info("prefix_type: %d", prefix_type);
    log_info("check_key_in_space: %d", check_key_in_space);
    log_info("key_space: 0x%08x", key_space);
    log_info("mask: 0x%08x", mask);
    log_info("space_before_read_request: %d", space_before_data_request);
    log_info("return_tag_id: %d", return_tag_id);
    log_info("return_tag_dest: 0x%08x", return_tag_dest);
    log_info("tx_offset: %d", tx_offset);

    return true;
}

//! \brief Initialises the buffer region.
//! \param[in] region_address: The location of the region.
//! \return True if we succeed.
static bool setup_buffer_region(uint8_t *region_address) {
    buffer_region = region_address;
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
static bool initialise_recording(void) {
    data_specification_metadata_t *ds_regions =
            data_specification_get_data_address();
    void *recording_region = data_specification_get_region(
            RECORDING_REGION, ds_regions);

    log_info("Recording starts at 0x%08x", recording_region);

    bool success = recording_initialize(&recording_region, &recording_flags);
    log_info("Recording flags = 0x%08x", recording_flags);
    return success;
}

//! \brief Writes our provenance data into the provenance region.
//! \param[in] address: Where to write
static void provenance_callback(address_t address) {
    ripmcs_provenance_t *prov = (void *) address;

    prov->received_packets = provenance.received_packets;
    prov->sent_packets = provenance.sent_packets;
    prov->incorrect_keys = provenance.incorrect_keys;
    prov->incorrect_packets = provenance.incorrect_packets;
    prov->late_packets = provenance.late_packets;
}

//! \brief Initialises the application
//! \param[out] timer_period: What to configure the timer with.
//! \return True if initialisation succeeded.
static bool initialise(uint32_t *timer_period) {
    // Get the address this core's DTCM data starts at from SRAM
    data_specification_metadata_t *ds_regions =
            data_specification_get_data_address();

    // Read the header
    if (!data_specification_read_header(ds_regions)) {
        return false;
    }

    // Get the timing details and set up the simulation interface
    if (!simulation_initialise(
            data_specification_get_region(SYSTEM, ds_regions),
            APPLICATION_NAME_HASH, timer_period, &simulation_ticks,
            &infinite_run, &time, SDP_CALLBACK, DMA)) {
        return false;
    }
    simulation_set_provenance_function(
            provenance_callback,
            data_specification_get_region(PROVENANCE_REGION, ds_regions));

    // Read the parameters
    if (!read_parameters(
            data_specification_get_region(CONFIGURATION, ds_regions))) {
        return false;
    }

    // set up recording data structures
    if (!initialise_recording()) {
         return false;
    }

    // Read the buffer region
    if (buffer_region_size > 0) {
        if (!setup_buffer_region(data_specification_get_region(
                BUFFER_REGION, ds_regions))) {
            return false;
        }
    }

    return true;
}

//! \brief Reinitialises the application after it was paused.
static void resume_callback(void) {
    data_specification_metadata_t *ds_regions =
            data_specification_get_data_address();
    setup_buffer_region(data_specification_get_region(
            BUFFER_REGION, ds_regions));

    // set the code to start sending packet requests again
    send_packet_reqs = true;

    // magic state to allow the model to check for stuff in the SDRAM
    last_buffer_operation = BUFFER_OPERATION_WRITE;

    // have fallen out of a resume mode, set up the functions to start
    // resuming again
    recording_reset();

    stopped = false;
}

//! \brief The fundamental operation loop for the application.
//! \param unused0 unused
//! \param unused1 unused
static void timer_callback(UNUSED uint unused0, UNUSED uint unused1) {
    time++;

    log_debug("timer_callback, final time: %d, current time: %d,"
            "next packet buffer time: %d",
            simulation_ticks, time, next_buffer_time);

    if (stopped || simulation_is_finished()) {
        // Enter pause and resume state to avoid another tick
        simulation_handle_pause_resume(resume_callback);

        // close recording channels
        if (recording_flags > 0) {
            recording_finalise();
        }

        log_debug("Last time of stop notification request: %d",
                last_stop_notification_request);

        simulation_ready_to_read();
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
        provenance.late_packets++;
        fetch_and_process_packet();
    } else if (next_buffer_time == time) {
        eieio_data_parse_packet(msg_from_sdram, msg_from_sdram_length);
        fetch_and_process_packet();
    }
}

//! \brief Handles an incoming SDP message.
//!
//! Delegates to packet_handler_selector()
//!
//! \param[in] mailbox: The address of the message.
//! \param port: The SDP port of the message. Ignored.
static void sdp_packet_callback(uint mailbox, UNUSED uint port) {
    sdp_msg_t *msg = (sdp_msg_t *) mailbox;
    uint16_t length = msg->length;
    eieio_msg_t eieio_msg_ptr = (eieio_msg_t) &msg->cmd_rc;

    provenance.received_packets++;

    packet_handler_selector(eieio_msg_ptr, length - 8);

    // free the message to stop overload
    spin1_msg_free(msg);
}

//! Entry point
void c_main(void) {
    // Configure system
    uint32_t timer_period = 0;
    if (!initialise(&timer_period)) {
        rt_error(RTE_SWERR);
        return;
    }

    // Set timer_callback
    spin1_set_timer_tick_and_phase(timer_period, tx_offset);

    // Register callbacks
    simulation_sdp_callback_on(buffered_in_sdp_port, sdp_packet_callback);
    spin1_callback_on(TIMER_TICK, timer_callback, TIMER);

    // Start the time at "-1" so that the first tick will be 0
    time = UINT32_MAX;
    simulation_run();
}

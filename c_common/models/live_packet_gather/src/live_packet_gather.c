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
//! \brief The implementation of the Live Packet Gatherer.
//!
//! The purpose of this application is to allow recorded information to be
//! streamed out of SpiNNaker in real time. It does not scale very well, as
//! SpiNNaker's aggregate internal state can change with a much higher
//! bandwidth than its external networking can handle.

#include <common-typedefs.h>
#include <circular_buffer.h>
#include <data_specification.h>
#include <debug.h>
#include <simulation.h>
#include <spin1_api.h>
#include <eieio.h>

//! Provenance data store
typedef struct lpg_provenance_data_t {
    //! Count of overflows when no payload was sent
    uint32_t number_of_overflows_no_payload;
    //! Count of overflows when a payload was sent
    uint32_t number_of_overflows_with_payload;
    //! Number of events gathered and recorded
    uint32_t number_of_gathered_events;
    //! Number of messages sent to host
    uint32_t number_of_sent_messages;
} lpg_provenance_data_t;

typedef struct key_translation_entry {
    // The key to check against after masking
    uint32_t key;
    // The mask to apply to the key
    uint32_t mask;
    // The atom identifier to add to the computed index
    uint32_t lo_atom;
} key_translation_entry;

//! \brief Definitions of each element in the configuration.
//!
//! This is copied from SDRAM into DTCM for speed.
struct lpg_config {
    //! P bit
    uint32_t apply_prefix;
    //! Prefix data
    uint32_t prefix;
    //! Type bits
    uint32_t prefix_type;
    //! F bit (for the receiver)
    uint32_t packet_type;
    //! Right payload shift (for the sender)
    uint32_t key_right_shift;
    //! T bit
    uint32_t payload_timestamp;
    //! D bit
    uint32_t payload_apply_prefix;
    //! Payload prefix data (for the receiver)
    uint32_t payload_prefix;
    //! Right payload shift (for the sender)
    uint32_t payload_right_shift;
    //! SDP tag to use when sending
    uint32_t sdp_tag;
    //! SDP destination to use when sending
    uint32_t sdp_dest;
    //! Maximum number of packets to send per timestep, or 0 for "send them all"
    uint32_t packets_per_timestamp;
    //! Mask to apply to non-translated keys
    uint32_t received_key_mask;
    //! Shift to apply to received and translated keys
    uint32_t translated_key_right_shift;
    //! The number of entries in the translation table
    uint32_t n_translation_entries;
    //! Translation table
    key_translation_entry translation_table[];
};

//! values for the priority for each callback
enum {
    MC_PACKET = -1, //!< Multicast packet interrupt uses FIQ (super high prio)
    SDP = 0,        //!< SDP interrupt is highest priority
    USER = 1,       //!< Interrupt for enqueued list of received packets
    DMA = 2,        //!< DMA complete interrupt is low priority
    TIMER = 3       //!< Timer interrupt is lowest priority
};

//! human readable definitions of each region in SDRAM
enum {
    SYSTEM_REGION,
    CONFIGURATION_REGION,
    PROVENANCE_REGION
};

//! EIEIO packet types
enum packet_types {
    NO_PAYLOAD_16,
    PAYLOAD_16,
    NO_PAYLOAD_32,
    PAYLOAD_32
};

// Globals
//! The SDP message that we will send.
static sdp_msg_t g_event_message;

//! The location of the EIEIO header in the message.
static uint16_t *sdp_msg_aer_header;

//! The location of the payload prefix in the message. `NULL` if no prefix.
static uint16_t *sdp_msg_aer_payload_prefix = NULL;

//! Pointer to outbound message data. _Might only be half-word aligned!_
static uint16_t *sdp_msg_aer_data;

//! Current simulation time
static uint32_t time;

//! The number of packets sent so far this timestamp
static uint32_t packets_sent;

//! Index into our buffer in ::sdp_msg_aer_data
static uint32_t buffer_index;

//! Part of the generic EIEIO header that is constant
static uint16_t eieio_constant_header;

//! The size of an individual event
static uint8_t event_size;

//! The length of the header, in bytes
static uint8_t sdp_msg_aer_header_len;

//! When we will run until
static uint32_t simulation_ticks = 0;

//! \brief TRUE if we're running without bound.
//! FALSE if we're only running for a limited period of time.
static uint32_t infinite_run = FALSE;

//! Circular buffer of incoming multicast packets that lack payloads
static circular_buffer without_payload_buffer;

//! Circular buffer of incoming multicast packets that have payloads
static circular_buffer with_payload_buffer;

//! Whether we are processing events (or discarding them).
static bool processing_events = false;

//! The provenance information that we are collecting.
static lpg_provenance_data_t provenance_data;

//! The configuration data of the application.
static struct lpg_config *config;

//! How to test if a bit flag is set
#define FLAG_IS_SET(flags, bit)		(((flags) & (bit)) != 0)

//! How to use just the low 8 bits of an integer value
#define CLAMP8(value)				((value) & 0xFF)

//! How to use just the low 16 bits of an integer value
#define CLAMP16(value)				((value) & 0xFFFF)

//! Does the packet type include a payload?
#define HAVE_PAYLOAD(pkt_type)		FLAG_IS_SET(pkt_type, 0x1)

//! Does the packet type include a double-width payload?
#define HAVE_WIDE_LOAD(pkt_type)	FLAG_IS_SET(pkt_type, 0x2)

//! The size of the circular buffers.
#define BUFFER_CAPACITY 256

//! \brief find a key translation entry
static inline bool find_translation_entry(uint32_t key, uint32_t *index) {
    if (!config->n_translation_entries) {
        return false;
    }

    uint32_t imin = 0;
    uint32_t imax = config->n_translation_entries;

    while (imin < imax) {
        uint32_t imid = (imax + imin) >> 1;
        key_translation_entry entry = config->translation_table[imid];
        if ((key & entry.mask) == entry.key) {
            *index = imid;
            return true;
        } else if (entry.key < key) {

            // Entry must be in upper part of the table
            imin = imid + 1;
        } else {
            // Entry must be in lower part of the table
            imax = imid;
        }
    }
    return false;
}

static inline uint32_t translated_key(uint32_t key) {
    uint32_t index = 0;

    // If there isn't an entry, don't translate
    if (!find_translation_entry(key, &index)) {
        return key & config->received_key_mask;
    }

    key_translation_entry entry = config->translation_table[index];

    // Pre-shift the key as requested
    uint32_t shifted_key = key & ~entry.mask;
    if (config->translated_key_right_shift) {
        shifted_key = shifted_key >> config->translated_key_right_shift;
    }
    return shifted_key + entry.lo_atom;
}

//! \brief Because _WHY OH WHY_ would you use aligned memory? At least with this
//! we don't get data aborts.
//! \param[out] base: Buffer to write in.
//!     _Only guaranteed to be half-word aligned._
//! \param[in] index: Offset in count of _words_ into the buffer.
//! \param[in] value: Value to write in (as little-endian).
static inline void write_word(void *base, uint32_t index, uint32_t value) {
    uint16_t *ary = base;
    uint32_t idx = index * 2;
    ary[idx++] = CLAMP16(value);
    ary[idx] = CLAMP16(value >> 16);
}

//! \brief Simple mirror of write_word() for true 16 bit values.
//! \param[in] base: place to write to
//! \param[in] index: location in base to write to
//! \param[in] value: the value to write to the base.
static inline void write_short(void *base, uint32_t index, uint32_t value) {
    uint16_t *ary = base;
    ary[index] = CLAMP16(value);
}

//! \brief Get how many events there are waiting to be sent
//! \return The number of events waiting
static inline uint8_t get_event_count(void) {
    uint8_t event_count = buffer_index;
    // If there are payloads, it takes two buffer values to encode them
    if (HAVE_PAYLOAD(config->packet_type)) {
        event_count >>= 1;
    }
    return event_count;
}

//! \brief Send buffered events to host via SDP AER message and clear internal
//!     buffers.
static void flush_events(void) {
    // Send the event message only if there is data
    if ((buffer_index > 0) && (
            (config->packets_per_timestamp == 0) ||
            (packets_sent < config->packets_per_timestamp))) {
        // Get the event count depending on if there is a payload or not
        uint8_t event_count = get_event_count();

        // insert appropriate header
        sdp_msg_aer_header[0] = eieio_constant_header | CLAMP8(event_count);

        g_event_message.length =
                sizeof(sdp_hdr_t) + sdp_msg_aer_header_len +
                event_count * event_size;

        // Add the timestamp if required
        if (sdp_msg_aer_payload_prefix && config->payload_timestamp) {
            if (!HAVE_WIDE_LOAD(config->packet_type)) {
                write_short(sdp_msg_aer_payload_prefix, 0, time);
            } else {
                write_word(sdp_msg_aer_payload_prefix, 0, time);
            }
        }

        spin1_send_sdp_msg(&g_event_message, 1);
        packets_sent++;
        provenance_data.number_of_sent_messages++;
    }

    // reset counter
    buffer_index = 0;
}

//! \brief Store provenance data elements into SDRAM
//! \param[out] provenance_region_address:
//!     Where the provenance data will be written
static void record_provenance_data(address_t provenance_region_address) {
    lpg_provenance_data_t *sdram = (void *) provenance_region_address;
    // Copy provenance data into SDRAM region
    *sdram = provenance_data;
}

// Callbacks
//! \brief Periodic timer callback
//!
//! Forces all events to be sent at least on the timer tick (calling
//! flush_events()) and handles pausing as required.
//!
//! \param unused0: unused
//! \param unused1: unused
static void timer_callback(UNUSED uint unused0, UNUSED uint unused1) {
    // flush the spike message and sent it over the Ethernet
    flush_events();

    // increase time variable to keep track of current timestep
    time++;
    log_debug("Timer tick %u", time);

    // Reset the count of packets sent in the current timestep
    packets_sent = 0;

    // check if the simulation has run to completion
    if (simulation_is_finished()) {
        simulation_handle_pause_resume(NULL);

        simulation_ready_to_read();
    }
}

//! \brief Flush events to the outside world if our internal buffers are now
//!     full.
//!
//! Calls flush_events() to do the flush.
static inline void flush_events_if_full(void) {
    if ((get_event_count() + 1) * event_size > BUFFER_CAPACITY) {
        flush_events();
    }
}

//! \brief Processes an incoming multicast packet without payload.
//! \param[in] key: The key of the packet.
static void process_incoming_event(uint key) {
    log_debug("Processing key %x", key);

    // process the received spike
    if (!HAVE_WIDE_LOAD(config->packet_type)) {
        // 16 bit packet
        write_short(sdp_msg_aer_data, buffer_index++,
                key >> config->key_right_shift);

        // if there is a payload to be added
        if (HAVE_PAYLOAD(config->packet_type) && !config->payload_timestamp) {
            write_short(sdp_msg_aer_data, buffer_index++, 0);
        } else if (HAVE_PAYLOAD(config->packet_type) && config->payload_timestamp) {
            write_short(sdp_msg_aer_data, buffer_index++, time);
        }
    } else {
        // 32 bit packet
        write_word(sdp_msg_aer_data, buffer_index++, key);

        // if there is a payload to be added
        if (HAVE_PAYLOAD(config->packet_type) && !config->payload_timestamp) {
            write_word(sdp_msg_aer_data, buffer_index++, 0);
        } else if (HAVE_PAYLOAD(config->packet_type) && config->payload_timestamp) {
            write_word(sdp_msg_aer_data, buffer_index++, time);
        }
    }
    provenance_data.number_of_gathered_events++;
}

//! \brief Processes an incoming multicast packet with payload.
//! \param[in] key: The key of the packet.
//! \param[in] payload: The payload word of the packet.
static void process_incoming_event_payload(uint key, uint payload) {
    log_debug("Processing key %x, payload %x", key, payload);

    // process the received spike
    if (!HAVE_WIDE_LOAD(config->packet_type)) {
        //16 bit packet
        write_short(sdp_msg_aer_data, buffer_index++,
                key >> config->key_right_shift);

        //if there is a payload to be added
        if (HAVE_PAYLOAD(config->packet_type) && !config->payload_timestamp) {
            write_short(sdp_msg_aer_data, buffer_index++,
                    payload >> config->payload_right_shift);
        } else if (HAVE_PAYLOAD(config->packet_type) && config->payload_timestamp) {
            write_short(sdp_msg_aer_data, buffer_index++, time);
        }
    } else {
        //32 bit packet
        write_word(sdp_msg_aer_data, buffer_index++, key);

        //if there is a payload to be added
        if (HAVE_PAYLOAD(config->packet_type) && !config->payload_timestamp) {
            write_word(sdp_msg_aer_data, buffer_index++, payload);
        } else if (HAVE_PAYLOAD(config->packet_type) && config->payload_timestamp) {
            write_word(sdp_msg_aer_data, buffer_index++, time);
        }
    }
    provenance_data.number_of_gathered_events++;
}

//! \brief Handler for processing incoming packets that have been locally queued
//!
//! Triggered by calling spin1_trigger_user_event() in incoming_event_callback()
//! and incoming_event_payload_callback(), which (being attached to the FIQ)
//! just enqueue messages for later handling. Delegates to
//! process_incoming_event() and process_incoming_event_payload() for actual
//! processing.
//!
//! Packets without payload are slightly higher priority than packets with
//! payload.
//!
//! Sends multiple SDP packets if required.
//!
//! \param unused0: Ignored
//! \param unused1: Ignored
static void incoming_event_process_callback(
        UNUSED uint unused0, UNUSED uint unused1) {
    do {
        uint32_t key, payload;

        if (circular_buffer_get_next(without_payload_buffer, &key)) {
            key = translated_key(key);
            process_incoming_event(key);
        } else if (circular_buffer_get_next(with_payload_buffer, &key)
                && circular_buffer_get_next(with_payload_buffer, &payload)) {
            key = translated_key(key);
            process_incoming_event_payload(key, payload);
        } else {
            processing_events = false;
            break;
        }

        // send packet if enough data is stored
        flush_events_if_full();
    } while (processing_events);
}

//! \brief FIQ handler for incoming packets without payload.
//!
//! Just enqueues them for later handling by incoming_event_process_callback(),
//! which will hand off to process_incoming_event().
//!
//! \param[in] key: The key of the incoming packet.
//! \param unused: unused
static void incoming_event_callback(uint key, UNUSED uint unused) {
    log_debug("Received key %x", key);

    if (circular_buffer_add(without_payload_buffer, key)) {
        if (!processing_events) {
            processing_events = true;
            spin1_trigger_user_event(0, 0);
        }
    } else {
        provenance_data.number_of_overflows_no_payload++;
    }
}

//! \brief FIQ handler for incoming packets with payload.
//!
//! Just enqueues them for later handling by incoming_event_process_callback(),
//! which will hand off to process_incoming_event_payload().
//!
//! \param[in] key: The key of the incoming packet.
//! \param[in] payload: The payload word of the incoming packet.
static void incoming_event_payload_callback(uint key, uint payload) {
    log_debug("Received key %x, payload %x", key, payload);

    if (circular_buffer_add(with_payload_buffer, key)) {
        circular_buffer_add(with_payload_buffer, payload);
        if (!processing_events) {
            processing_events = true;
            spin1_trigger_user_event(0, 0);
        }
    } else {
        provenance_data.number_of_overflows_with_payload++;
    }
}

//! \brief Copies the application configuration from DSG SDRAM to DTCM.
//!
//! Note that it's faster to copy by field than to use spin1_memcpy()!
//!
//! \param[in] sdram_config: Where to copy from
static bool read_parameters(struct lpg_config *sdram_config) {
    uint32_t n_bytes = sizeof(struct lpg_config) +
            (sdram_config->n_translation_entries * sizeof(key_translation_entry));
    config = spin1_malloc(n_bytes);
    if (config == NULL) {
        log_error("Could not allocate space for config!");
        return false;

    }
    spin1_memcpy(config, sdram_config, n_bytes);

    log_info("apply_prefix: %d", config->apply_prefix);
    log_info("prefix: %08x", config->prefix);
    log_info("prefix_type: %d", config->prefix_type);
    log_info("packet_type: %d", config->packet_type);
    log_info("key_right_shift: %d", config->key_right_shift);
    log_info("payload_timestamp: %d", config->payload_timestamp);
    log_info("payload_apply_prefix: %d", config->payload_apply_prefix);
    log_info("payload_prefix: %08x", config->payload_prefix);
    log_info("payload_right_shift: %d", config->payload_right_shift);
    log_info("sdp_tag: %d", config->sdp_tag);
    log_info("sdp_dest: 0x%04x", config->sdp_dest);
    log_info("packets_per_timestamp: %d", config->packets_per_timestamp);
    log_info("n_translation_entries: %d", config->n_translation_entries);
    for (uint32_t i = 0; i < config->n_translation_entries; i++) {
        key_translation_entry *entry = &config->translation_table[i];
        log_info("key = 0x%08x, mask = 0x%08x, lo_atom = 0x%08x",
                entry->key, entry->mask, entry->lo_atom);
    }

    return true;
}

//! \brief Initialise the application.
//! \param[out] timer_period: Value for programming the timer ticks.
//!     _A pointer to this variable is retained by the simulation framework._
//! \result True if initialisation succeeds.
static bool initialize(uint32_t *timer_period) {
    // Get the address this core's DTCM data starts at from SRAM
    data_specification_metadata_t *ds_regions =
            data_specification_get_data_address();

    // Read the header
    if (!data_specification_read_header(ds_regions)) {
        return false;
    }

    // Get the timing details and set up the simulation interface
    if (!simulation_initialise(
            data_specification_get_region(SYSTEM_REGION, ds_regions),
            APPLICATION_NAME_HASH, timer_period, &simulation_ticks,
            &infinite_run, &time, SDP, DMA)) {
        return false;
    }
    simulation_set_provenance_function(
            record_provenance_data,
            data_specification_get_region(PROVENANCE_REGION, ds_regions));

    // Fix simulation ticks to be one extra timer period to soak up last events
    if (infinite_run != TRUE) {
        simulation_ticks++;
    }

    // Read the parameters
    return read_parameters(
            data_specification_get_region(CONFIGURATION_REGION, ds_regions));
}

//! \brief Sets up the AER EIEIO data message.
//! \return bool where True was successful init and  false otherwise.
static bool configure_sdp_msg(void) {
    log_debug("configure_sdp_msg");

    switch (config->packet_type) {
    case NO_PAYLOAD_16:
        event_size = 2;
        break;
    case PAYLOAD_16:
        event_size = 4;
        break;
    case NO_PAYLOAD_32:
        event_size = 4;
        break;
    case PAYLOAD_32:
        event_size = 8;
        break;
    default:
        log_error("unknown packet type: %d", config->packet_type);
        return false;
    }

    // initialise SDP header
    g_event_message.tag = config->sdp_tag;
    // No reply required
    g_event_message.flags = 0x07;
    // Chip 0,0
    g_event_message.dest_addr = config->sdp_dest;
    // Dump through Ethernet
    g_event_message.dest_port = PORT_ETH;
    // Set up monitoring address and port
    g_event_message.srce_addr = spin1_get_chip_id();
    g_event_message.srce_port = (3 << PORT_SHIFT) | spin1_get_core_id();

    // check incompatible options
    if (config->payload_timestamp && config->payload_apply_prefix
            && HAVE_PAYLOAD(config->packet_type)) {
        log_error("Timestamp can either be included as payload prefix or as"
                "payload to each key, not both");
        return false;
    }
    if (config->payload_timestamp && !config->payload_apply_prefix
            && !HAVE_PAYLOAD(config->packet_type)) {
        log_error("Timestamp can either be included as payload prefix or as"
                "payload to each key, but current configuration does not"
                "specify either of these");
        return false;
    }

    // initialise AER header
    // pointer to data space
    sdp_msg_aer_header = &g_event_message.cmd_rc;

    eieio_constant_header = 0;
    eieio_constant_header |= config->apply_prefix << APPLY_PREFIX;
    eieio_constant_header |= config->prefix_type << PREFIX_UPPER;
    eieio_constant_header |= config->payload_apply_prefix << APPLY_PAYLOAD_PREFIX;
    eieio_constant_header |= config->payload_timestamp << PAYLOAD_IS_TIMESTAMP;
    eieio_constant_header |= config->packet_type << PACKET_TYPE;

    // pointers for AER packet header, prefix and data
    // Point to the half-word after main header half-word
    sdp_msg_aer_data = sdp_msg_aer_header + 1;
    if (config->apply_prefix) {
        // pointer to key prefix, so data is one half-word further ahead
        write_short(sdp_msg_aer_header, 1, config->prefix);
        sdp_msg_aer_data++;
    }

    if (config->payload_apply_prefix) {
        // pointer to payload prefix
        sdp_msg_aer_payload_prefix = sdp_msg_aer_data;

        if (!HAVE_WIDE_LOAD(config->packet_type)) {
            //16 bit payload prefix; advance data position by one half word
            sdp_msg_aer_data++;
            if (!config->payload_timestamp) {
                // add payload prefix as required - not a timestamp
                write_short(sdp_msg_aer_payload_prefix, 0, config->payload_prefix);
            }
        } else {
            //32 bit payload prefix; advance data position by two half words
            sdp_msg_aer_data += 2;
            if (!config->payload_timestamp) {
                // add payload prefix as required - not a timestamp
                write_word(sdp_msg_aer_payload_prefix, 0, config->payload_prefix);
            }
        }
    }

    // compute header length in bytes
    sdp_msg_aer_header_len =
            (sdp_msg_aer_data - sdp_msg_aer_header) * sizeof(uint16_t);

    log_debug("sdp_msg_aer_header: %08x", sdp_msg_aer_header);
    log_debug("sdp_msg_aer_payload_prefix: %08x", sdp_msg_aer_payload_prefix);
    log_debug("sdp_msg_aer_data: %08x", sdp_msg_aer_data);
    log_debug("sdp_msg_aer_header_len: %d", sdp_msg_aer_header_len);

    packets_sent = 0;
    buffer_index = 0;

    return true;
}

//! Entry point
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
    without_payload_buffer = circular_buffer_initialize(BUFFER_CAPACITY);
    with_payload_buffer = circular_buffer_initialize(BUFFER_CAPACITY * 2);

    // Set timer_callback
    spin1_set_timer_tick(timer_period);

    // Register callbacks
    spin1_callback_on(MC_PACKET_RECEIVED, incoming_event_callback, MC_PACKET);
    spin1_callback_on(
            MCPL_PACKET_RECEIVED, incoming_event_payload_callback, MC_PACKET);
    spin1_callback_on(USER_EVENT, incoming_event_process_callback, USER);
    spin1_callback_on(TIMER_TICK, timer_callback, TIMER);

    // Start the time at "-1" so that the first tick will be 0
    time = UINT32_MAX;
    simulation_run();
}

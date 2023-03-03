/*
 * Copyright (c) 2017-2019 The University of Manchester
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
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
    CONFIGURATION_REGION
};

//! The configuration data of the application.
static struct lpg_config *config;

//! Circular buffer of incoming multicast packets that lack payloads
static circular_buffer without_payload_buffer;

//! Circular buffer of incoming multicast packets that have payloads
static circular_buffer with_payload_buffer;

//! Whether we are processing events (or discarding them).
static bool processing_events = false;

//! Current simulation time
static uint32_t time;

//! When we will run until
static uint32_t simulation_ticks = 0;

//! \brief TRUE if we're running without bound.
//! FALSE if we're only running for a limited period of time.
static uint32_t infinite_run = FALSE;

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

// Callbacks
//! \brief Periodic timer callback
//!
//! Forces all events to be sent at least on the timer tick (calling
//! flush_events()) and handles pausing as required.
//!
//! \param unused0: unused
//! \param unused1: unused
static void timer_callback(UNUSED uint unused0, UNUSED uint unused1) {

    // increase time variable to keep track of current timestep
    time++;
    log_debug("Timer tick %u", time);

    // check if the simulation has run to completion
    if (simulation_is_finished()) {
        simulation_handle_pause_resume(NULL);

        // Subtract 1 from the time so this tick gets done again on the next
        // run
        time--;

        simulation_ready_to_read();
    }
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
            spin1_send_mc_packet(key, 0, 0);
        } else if (circular_buffer_get_next(with_payload_buffer, &key)
                && circular_buffer_get_next(with_payload_buffer, &payload)) {
            key = translated_key(key);
            spin1_send_mc_packet(key, payload, 1);
        } else {
            processing_events = false;
            break;
        }
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

    // Fix simulation ticks to be one extra timer period to soak up last events
    if (infinite_run != TRUE) {
        simulation_ticks++;
    }

    // Read the parameters
    return read_parameters(
            data_specification_get_region(CONFIGURATION_REGION, ds_regions));
}

//! Entry point
void c_main(void) {
    // Configure system
    uint32_t timer_period = 0;
    if (!initialize(&timer_period)) {
        log_error("Error in initialisation - exiting!");
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

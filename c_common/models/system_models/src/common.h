/*
 * Copyright (c) 2019-2020 The University of Manchester
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

/**
 * \file
 * \brief Common definitions for the non-SCAMP system binaries.
 */

#ifndef __COMMON_H__
#define __COMMON_H__
#include <common-typedefs.h>

//! Dropped packet re-injection internal control commands (RC of SCP message)
enum reinjector_command_codes {
    //! Set the router's wait1 timeout
    CMD_DPRI_SET_ROUTER_TIMEOUT = 0,
    //! Set the router's wait2 timeout
    CMD_DPRI_SET_ROUTER_EMERGENCY_TIMEOUT = 1,
    //! Set what packet types are reinjected
    CMD_DPRI_SET_PACKET_TYPES = 2,
    //! Get the status of the reinjector
    CMD_DPRI_GET_STATUS = 3,
    //! Reset the reinjection counters
    CMD_DPRI_RESET_COUNTERS = 4,
    //! Stop doing reinjection
    CMD_DPRI_EXIT = 5,
    //! Clear the reinjection queue
    CMD_DPRI_CLEAR = 6
};

//! \brief Human readable definitions of the offsets for multicast key elements
//! for reinjection.
//!
//! These act as commands sent to the target extra monitor core.
typedef enum {
    //! Set the router's wait1 timeout
    ROUTER_TIMEOUT_OFFSET = 0,
    //! Set the router's wait2 timeout
    ROUTER_EMERGENCY_TIMEOUT_OFFSET = 1,
    //! Clear the reinjection queue
    REINJECTOR_CLEAR_QUEUE_OFFSET = 2,
} reinjector_key_offsets;

//! Misc constants
enum {
    //! How many payload words are in an SDP packet.
    ITEMS_PER_DATA_PACKET = 68
};

// ------------------------------------------------------------------------
// structs used in system
// ------------------------------------------------------------------------

//! An SDP message with pure data, no SCP header
typedef struct sdp_msg_pure_data {  // SDP message (=292 bytes)
    struct sdp_msg *next;           //!< Next in free list
    uint16_t length;                //!< length
    uint16_t checksum;              //!< checksum (if used)

    // sdp_hdr_t
    // The length field measures from HERE...
    uint8_t flags;                  //!< SDP flag byte; first byte actually sent
    uint8_t tag;                    //!< SDP IPtag
    uint8_t dest_port;              //!< SDP destination port/CPU
    uint8_t srce_port;              //!< SDP source port/CPU
    uint16_t dest_addr;             //!< SDP destination address
    uint16_t srce_addr;             //!< SDP source address

    //! User data (272 bytes when no SCP header)
    uint32_t data[ITEMS_PER_DATA_PACKET];

    uint32_t _PAD;                  // Private padding
} sdp_msg_pure_data;

// ------------------------------------------------------------------------
// global variables for the reinjection mc interface
// ------------------------------------------------------------------------

//! the multicast key used for basic timeouts to all extra monitors
static uint reinject_timeout_mc_key;

//! the multicast key used for emergency timeouts to all extra monitors
static uint reinject_emergency_timeout_mc_key;

//! the multicast key used for clear reinjector queue to all extra monitors
static uint reinject_clear_mc_key;

//! \brief sets up the multicast keys for the reinjection multicast API
//! \param[in] base_mc_key: the base key for the api.
static void initialise_reinjection_mc_api(uint32_t base_mc_key) {
    // set the router timeout keys
    reinject_timeout_mc_key = base_mc_key + ROUTER_TIMEOUT_OFFSET;
    reinject_emergency_timeout_mc_key =
            base_mc_key + ROUTER_EMERGENCY_TIMEOUT_OFFSET;
    reinject_clear_mc_key = base_mc_key + REINJECTOR_CLEAR_QUEUE_OFFSET;
}

//! Number of bytes in an SDP header.
#define SDP_REPLY_HEADER_LEN 12

//! Flag for cap on transaction id
#define TRANSACTION_CAP 0xFFFFFFF

//! \brief Updates an SDP message so its content (a response to the message)
//!        goes back to where the message came from.
//! \param[in,out] msg: the SDP message to reflect
//! \param[in] body_length: the length of the response
static inline void reflect_sdp_message(sdp_msg_t *msg, uint body_length) {
    msg->length = SDP_REPLY_HEADER_LEN + body_length;
    uint dest_port = msg->dest_port;
    uint dest_addr = msg->dest_addr;

    msg->dest_port = msg->srce_port;
    msg->srce_port = dest_port;

    msg->dest_addr = msg->srce_addr;
    msg->srce_addr = dest_addr;
}

#endif  // __COMMON_H__

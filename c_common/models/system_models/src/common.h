/*
 * Copyright (c) 2019 The University of Manchester
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

/**
 * \file
 * \brief Common definitions for the non-SCAMP system binaries.
 */

#ifndef __COMMON_H__
#define __COMMON_H__
#include <common-typedefs.h>
#include <sdp_no_scp.h>

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

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

#ifndef __COMMON_H__
#define __COMMON_H__

// Dropped packet re-injection internal control commands (RC of SCP message)
enum reinjector_command_codes {
    CMD_DPRI_SET_ROUTER_TIMEOUT = 0,
    CMD_DPRI_SET_ROUTER_EMERGENCY_TIMEOUT = 1,
    CMD_DPRI_SET_PACKET_TYPES = 2,
    CMD_DPRI_GET_STATUS = 3,
    CMD_DPRI_RESET_COUNTERS = 4,
    CMD_DPRI_EXIT = 5,
    CMD_DPRI_CLEAR = 6
};

//! Human readable definitions of the offsets for multicast key elements for
//! reinjection. These act as commands sent to the target extra monitor core.
typedef enum {
    ROUTER_TIMEOUT_OFFSET = 0,
    ROUTER_EMERGENCY_TIMEOUT_OFFSET = 1,
    REINJECTOR_CLEAR_QUEUE_OFFSET = 2,
} reinjector_key_offsets;

// ------------------------------------------------------------------------
// global variables for the reinjection mc interface
// ------------------------------------------------------------------------

//! the mc key used for basic timeouts to all extra monitors
static uint reinjection_timeout_mc_key = 0;

//! the mc key used for emergency timeouts to all extra monitors
static uint reinjection_emergency_timeout_mc_key = 0;

//! the mc key used for clear reinjector queue to all extra monitors
static uint reinjection_clear_mc_key = 0;

//! \brief sets up the mc keys for the reinjection mc api
//! \param[in] base_mc_key: the base key for the api.
void initialise_reinjection_mc_api(uint32_t base_mc_key){
    // set the router timeout keys
    reinjection_timeout_mc_key = base_mc_key + ROUTER_TIMEOUT_OFFSET;
    reinjection_emergency_timeout_mc_key =
        base_mc_key + ROUTER_EMERGENCY_TIMEOUT_OFFSET;
    reinjection_clear_mc_key =
        base_mc_key + REINJECTOR_CLEAR_QUEUE_OFFSET;
}

#define SDP_REPLY_HEADER_LEN 12

//! does the setting of the msg to reflect back.
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
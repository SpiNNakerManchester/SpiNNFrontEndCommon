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

//! \file
//! \brief Describes a pure SDP message (without SCP payload)
#ifndef _SDP_NO_SCP_H_
#define _SDP_NO_SCP_H_

//! Miscellaneous sizes
enum {
    //! How many multicast packets are to be received per SDP packet
    ITEMS_PER_DATA_PACKET = 68,
    //! Extra length adjustment for the SDP header
    LENGTH_OF_SDP_HEADER = 8
};

//! An SDP message with purely data, no SCP header
typedef struct sdp_msg_pure_data {	// SDP message (=292 bytes)
    struct sdp_msg *next;   //!< Next in free list
    uint16_t length;        //!< Length (measured from \p flags field start)
    uint16_t checksum;      //!< Checksum (if used)

    // next part must match sdp_hdr_t
    uint8_t flags;          //!< SDP flag byte; first byte actually sent
    uint8_t tag;            //!< SDP IPtag
    uint8_t dest_port;      //!< SDP destination port/CPU
    uint8_t srce_port;      //!< SDP source port/CPU
    uint16_t dest_addr;     //!< SDP destination address
    uint16_t srce_addr;     //!< SDP source address

    //! User data (272 bytes when no SCP header)
    uint32_t data[ITEMS_PER_DATA_PACKET];

    uint32_t _PAD;          // Private padding
} sdp_msg_pure_data;

#endif // _SDP_NO_SCP_H_

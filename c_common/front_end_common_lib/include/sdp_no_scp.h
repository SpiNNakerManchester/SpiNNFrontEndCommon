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

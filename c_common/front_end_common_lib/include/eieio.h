/*
 * Copyright (c) 2019 The University of Manchester
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

#ifndef INCLUDE_FEC_EIEIO_H
#define INCLUDE_FEC_EIEIO_H

enum bit_offsets {
    APPLY_PREFIX = 15,
    PREFIX_UPPER = 14,
    APPLY_PAYLOAD_PREFIX = 13,
    PAYLOAD_IS_TIMESTAMP = 12,
    PACKET_TYPE = 10,
    COUNT = 0,
    PACKET_CLASS = 14,
    PACKET_COMMAND = 0
};

#if 0
// Bitfields go from LSB to MSB; SpiNNaker is little-endian, and making them all
// use uint16_t as a base type means that we know they'll all be in the same
// memory slot (which they will fit into).
//
// http://infocenter.arm.com/help/index.jsp?topic=/com.arm.doc.faqs/ka10202.html
// http://infocenter.arm.com/help/index.jsp?topic=/com.arm.doc.dui0491e/Babjddhe.html
//
// THIS IS NOT PORTABLE TO NON-SPINNAKER!
struct eieio_header_bitfields {
    uint16_t count : 8;
    uint16_t _padding : 2;
    uint16_t packet_type : 2;
    uint16_t payload_is_timestamp : 1;
    uint16_t apply_payload_prefix : 1;
    uint16_t prefix_upper : 1;
    uint16_t apply_prefix : 1;
};
#endif

#endif //INCLUDE_FEC_EIEIO_H

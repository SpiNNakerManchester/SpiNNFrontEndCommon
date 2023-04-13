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
//!
//! \brief EIEIO message header description

#ifndef INCLUDE_FEC_EIEIO_H
#define INCLUDE_FEC_EIEIO_H

#include <common-typedefs.h>

//! Offsets into the eieio_header_bitfields structure.
//!
//! These are bit offsets into a 16 bit unsigned integer.
enum eieio_bit_offsets {
    APPLY_PREFIX = 15,         //!< eieio_header_bitfields::apply_prefix
    PREFIX_UPPER = 14,         //!< eieio_header_bitfields::prefix_upper
    APPLY_PAYLOAD_PREFIX = 13, //!< eieio_header_bitfields::apply_payload_prefix
    PAYLOAD_IS_TIMESTAMP = 12, //!< eieio_header_bitfields::payload_is_timestamp
    PACKET_TYPE = 10,          //!< eieio_header_bitfields::packet_type
    COUNT = 0,                 //!< eieio_header_bitfields::count
    PACKET_CLASS = 14,         //!< eieio_header_bitfields::packet_class
    PACKET_COMMAND = 0         //!< eieio_header_bitfields::packet_command
};

//! Masks for the eieio_header_bitfields structure.
//!
//! These apply after the value has been shifted into the low bits by the
//! offset.
enum eieio_bit_masks {
    APPLY_PREFIX_MASK = 0x1,         //!< eieio_header_bitfields::apply_prefix
    PREFIX_UPPER_MASK = 0x1,         //!< eieio_header_bitfields::prefix_upper
    APPLY_PAYLOAD_PREFIX_MASK = 0x1, //!< eieio_header_bitfields::apply_payload_prefix
    PAYLOAD_IS_TIMESTAMP_MASK = 0x3, //!< eieio_header_bitfields::payload_is_timestamp
    PACKET_TYPE_MASK = 0x3,          //!< eieio_header_bitfields::packet_type
    COUNT_MASK = 0xFF,               //!< eieio_header_bitfields::count
    PACKET_CLASS_MASK = 0x3,         //!< eieio_header_bitfields::packet_class
    PACKET_COMMAND_MASK = 0x3FFF     //!< eieio_header_bitfields::packet_command
};

// Bitfields go from LSB to MSB; SpiNNaker is little-endian, and making them all
// use uint16_t as a base type means that we know they'll all be in the same
// memory slot (which they will fit into).
//
// https://infocenter.arm.com/help/index.jsp?topic=/com.arm.doc.faqs/ka10202.html
// https://infocenter.arm.com/help/index.jsp?topic=/com.arm.doc.dui0491e/Babjddhe.html
//
// THIS IS NOT PORTABLE TO NON-SPINNAKER!

//! \brief The header of an EIEIO packet.
union eieio_header_bitfields {
    struct {
        //! \brief The count
        uint16_t count : 8;
        // Padding
        uint16_t : 2;
        //! \brief The type of the packet (see eieio_data_message_types)
        uint16_t packet_type : 2;
        //! \brief Whether the payload is a timestamp
        uint16_t payload_is_timestamp : 1;
        //! \brief Whether to apply the current prefix to the payload
        uint16_t apply_payload_prefix : 1;
        //! \brief Whether the prefix is applied to the upper or lower half of the
        //! payload.
        uint16_t prefix_upper : 1;
        //! \brief Whether to apply the prefix
        uint16_t apply_prefix : 1;
    };
    struct {
        //! \brief What command is encoded in the packet.
        uint16_t packet_command : 14;
        //! \brief What is the class of the packet.
        uint16_t packet_class : 2;
    };
    uint16_t overall_value;
};

//! The EIEIO basic message types
typedef enum {
    //! Message is just a key, 16 bits long
    KEY_16_BIT,
    //! Message is a key and a payload, each 16 bits long
    KEY_PAYLOAD_16_BIT,
    //! Message is just a key, 32 bits long
    KEY_32_BIT,
    //! Message is a key and a payload, each 32 bits long
    KEY_PAYLOAD_32_bIT
} eieio_data_message_types;

//! The EIEIO prefix types
typedef enum {
    PREFIX_TYPE_LOWER_HALF_WORD,
    PREFIX_TYPE_UPPER_HALF_WORD
} eieio_prefix_types;

#endif //INCLUDE_FEC_EIEIO_H

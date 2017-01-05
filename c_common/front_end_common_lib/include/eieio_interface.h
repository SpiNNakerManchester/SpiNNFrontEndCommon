/*! \file
 *
 *  \brief EIEIO interface Header File
 *
 *  DESCRIPTION
 *    Specifies functions that can be used to read and write EIEIO data
 *    and command packets
 *
 */

#ifndef _EIEIO_INTERFACE_H_
#define _EIEIO_INTERFACE_H_

#include "common-typedefs.h"

//! eieio header struct
typedef struct eieio_header_struct {
    uint32_t apply_prefix; //! the p bit of the eieio header
    uint32_t prefix; //! prefix if needed (last 16 bits of header)
    uint32_t prefix_type; //! prefix type if data header (F bit)
    uint32_t packet_type; //! type of packet 16bit, payload, 32 bit payload. (type bits)
    uint32_t key_right_shift;
    uint32_t payload_as_timestamp; //! t bit, verifies if payloads are timestamps
    uint32_t payload_apply_prefix; //! D bit
    uint32_t payload_prefix; //! payload prefix
    uint32_t count; //! the number of elements in the header
    uint32_t tag; //! the tag bits of the eieio header
} eieio_header_struct;

//! \brief takes a memory address and translates the next 2 bytes into
eieio_header_struct eieio_interface_get_eieio_header(
    address_t header_start_address);

#endif

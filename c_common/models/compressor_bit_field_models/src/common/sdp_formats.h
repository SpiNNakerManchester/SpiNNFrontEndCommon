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

#ifndef __COMPRESSION_SDP_FORMATS_H__
#define __COMPRESSION_SDP_FORMATS_H__

#include <common-typedefs.h>

//! \brief the acceptable finish states
typedef enum finish_states {
    SUCCESSFUL_COMPRESSION = 30, FAILED_MALLOC = 31, FAILED_TO_COMPRESS = 32,
    RAN_OUT_OF_TIME = 33, FORCED_BY_COMPRESSOR_CONTROL = 34
} finish_states;

//! \brief the command codes in human readable form
typedef enum command_codes_for_sdp_packet {
    START_DATA_STREAM = 20,
    EXTRA_DATA_STREAM = 21,
    COMPRESSION_RESPONSE = 22,
    STOP_COMPRESSION_ATTEMPT = 23
} command_codes_for_sdp_packet;

//! \brief the elements in the sdp packet (control for setting off a minimise
//! attempt)
typedef struct start_stream_sdp_packet_t {
    table_t *address_for_compressed;
    heap_t *fake_heap_data;
    int n_sdp_packets_till_delivered;
    int total_n_tables;
    int n_tables_in_packet;
    table_t *tables [];
} start_stream_sdp_packet_t;

//! \brief the elements in the sdp packet when extension control for a minimise
//! attempt. Only used when x routing tables wont fit in first packet
typedef struct extra_stream_sdp_packet_t {
    int n_tables_in_packet;
    table_t *tables [];
} extra_stream_sdp_packet_t;

//! \brief the elements in the sdp packet when response to compression attempt.
typedef struct response_sdp_packet_t {
    uint32_t command_code;
    uint32_t response_code;
} response_sdp_packet_t;

//! \brief start message with command code encapsulated
typedef struct {
    uint32_t command;
    start_stream_sdp_packet_t msg;
} start_msg_t;

//! \brief extra message with command code encapsulated
typedef struct {
    uint32_t command;
    extra_stream_sdp_packet_t msg;
} extra_msg_t;

//! \brief all the types of SDP messages that we receive, as one
typedef union {
    command_codes_for_sdp_packet command;
    start_msg_t start;
    extra_msg_t extra;
    response_sdp_packet_t response;
} compressor_payload_t;

#endif  // __COMPRESSION_SDP_FORMATS_H__

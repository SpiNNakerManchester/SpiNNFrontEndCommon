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

#ifndef BUFFERED_EIEIO_DEFS_H
#define BUFFERED_EIEIO_DEFS_H

//! The different command message IDs
typedef enum eieio_command_messages {

    // Database handshake with visualiser
    DATABASE_CONFIRMATION = 1,

    // Fill in buffer area with padding
    EVENT_PADDING,

    // End of all buffers, stop execution
    EVENT_STOP_COMMANDS,

    // Stop complaining that there is SDRAM free space for buffers
    STOP_SENDING_REQUESTS,

    // Start complaining that there is SDRAM free space for buffers
    START_SENDING_REQUESTS,

    // SpiNNaker requesting new buffers for spike source population
    SPINNAKER_REQUEST_BUFFERS,

    // Buffers being sent from host to SpiNNaker
    HOST_SEND_SEQUENCED_DATA,

    // Buffers available to be read from a buffered out vertex
    SPINNAKER_REQUEST_READ_DATA,

    // Host confirming data being read form SpiNNaker memory
    HOST_DATA_READ,

    // Host confirming message received to read data
    HOST_DATA_READ_ACK = 12,
} eieio_command_messages;

//! The different buffer operations
typedef enum buffered_operations {
    BUFFER_OPERATION_READ,
    BUFFER_OPERATION_WRITE
} buffered_operations;

//! pointer to an EIEIO message
typedef uint16_t* eieio_msg_t;

// The maximum sequence number
#define MAX_SEQUENCE_NO 0xFF

#endif

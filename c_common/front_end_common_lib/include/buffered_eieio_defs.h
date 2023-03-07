/*
 * Copyright (c) 2015 The University of Manchester
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
//! \brief Definitions for the streaming-over-EIEIO buffering protocol.
//!
//! Note that this protocol is now mostly deprecated in favour of the
//! substantially-faster automatic pause-and-resume protocol.

#ifndef BUFFERED_EIEIO_DEFS_H
#define BUFFERED_EIEIO_DEFS_H

//! The different command message IDs
typedef enum eieio_command_messages {
    //! Fill in buffer area with padding
    EVENT_PADDING = 2,
    //! End of all buffers, stop execution
    EVENT_STOP_COMMANDS,
    //! Stop complaining that there is SDRAM free space for buffers
    STOP_SENDING_REQUESTS,
    //! Start complaining that there is SDRAM free space for buffers
    START_SENDING_REQUESTS,
    //! SpiNNaker requesting new buffers for spike source population
    SPINNAKER_REQUEST_BUFFERS,
    //! Buffers being sent from host to SpiNNaker
    HOST_SEND_SEQUENCED_DATA,
    //! Buffers available to be read from a buffered out vertex
    SPINNAKER_REQUEST_READ_DATA,
    //! Host confirming data being read form SpiNNaker memory
    HOST_DATA_READ,
    //! Host confirming message received to read data
    HOST_DATA_READ_ACK = 12,
} eieio_command_messages;

//! The different buffer operations
typedef enum buffered_operations {
    //! The last operation was a read
    BUFFER_OPERATION_READ,
    //! The last operation was a write
    BUFFER_OPERATION_WRITE
} buffered_operations;

//! pointer to an EIEIO message
typedef uint16_t* eieio_msg_t;

//! The maximum sequence number
#define MAX_SEQUENCE_NO 0xFF

#endif

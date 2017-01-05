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

    // Stop complaining that there is sdram free space for buffers
    STOP_SENDING_REQUESTS,

    // Start complaining that there is sdram free space for buffers
    START_SENDING_REQUESTS,

    // Spinnaker requesting new buffers for spike source population
    SPINNAKER_REQUEST_BUFFERS,

    // Buffers being sent from host to SpiNNaker
    HOST_SEND_SEQUENCED_DATA,

    // Buffers available to be read from a buffered out vertex
    SPINNAKER_REQUEST_READ_DATA,

    // Host confirming data being read form SpiNNaker memory
    HOST_DATA_READ
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

#ifndef BUFFERED_EIEIO_DEFS_H
#define BUFFERED_EIEIO_DEFS_H

//! human readable forms of the different command message ids.
typedef enum eieio_command_messages {
    DATABASE_CONFIRMATION = 1, // Database handshake with visualiser
    EVENT_PADDING, // Fill in buffer area with padding
    EVENT_STOP_COMMANDS,  // End of all buffers, stop execution
    STOP_SENDING_REQUESTS, // Stop complaining that there is sdram free space for buffers
    START_SENDING_REQUESTS, // Start complaining that there is sdram free space for buffers
    SPINNAKER_REQUEST_BUFFERS, // Spinnaker requesting new buffers for spike source population
    HOST_SEND_SEQUENCED_DATA, // Buffers being sent from host to SpiNNaker
    SPINNAKER_REQUEST_READ_DATA, // Buffers available to be read from a buffered out vertex
    HOST_DATA_READ, // Host confirming data being read form SpiNNaker memory
    HOST_REQUEST_FLUSH_DATA, // At the end of simulation the host requests to send all the remaining data
    FLUSH_DATA_COMPLETED // All the remaining data has been flushed to the host, no more data to be sent
}eieio_command_messages;

//! human readable forms of the different buffer operations
typedef enum buffered_operations{
    BUFFER_OPERATION_READ,
    BUFFER_OPERATION_WRITE
}buffered_operations;

#endif
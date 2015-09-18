#ifndef BUFFERED_EIEIO_DEFS_H
#define BUFFERED_EIEIO_DEFS_H

// Definitions
// EIEIO commands
#define DATABASE_CONFIRMATION       1   // Database handshake with visualiser
#define EVENT_PADDING               2   // Fill in buffer area with padding
#define EVENT_STOP                  3   // End of all buffers, stop execution
#define STOP_SENDING_REQUESTS       4   // Stop complaining that there is sdram free space for buffers
#define START_SENDING_REQUESTS      5   // Start complaining that there is sdram free space for buffers
#define SPINNAKER_REQUEST_BUFFERS   6   // Spinnaker requesting new buffers for spike source population
#define HOST_SEND_SEQUENCED_DATA    7   // Buffers being sent from host to SpiNNaker
#define SPINNAKER_REQUEST_READ_DATA 8   // Buffers available to be read from a buffered out vertex
#define HOST_DATA_READ              9   // Host confirming data being read form SpiNNaker memory
#define HOST_REQUEST_FLUSH_DATA     10  // At the end of simulation the host requests to send all the remaining data
#define FLUSH_DATA_COMPLETED        11  // All the remaining data has been flushed to the host, no more data to be sent

// Buffering operations
#define BUFFER_OPERATION_READ 0
#define BUFFER_OPERATION_WRITE 1

#endif
/*! \file
 *  \brief interface for recording data into "channels" on the SDRAM in a
 *         standard way, and storing buffers to be extracted during execution
 *
 *
 */

#ifndef _RECORDING_H_
#define _RECORDING_H_

#include <common-typedefs.h>
#include <spin1_api.h>
#include <buffered_eieio_defs.h>

#define RECORDING_DMA_COMPLETE_TAG_ID 15

typedef struct {
    uint16_t eieio_header_command;
    uint16_t chip_id;
} read_request_packet_header;

typedef struct {
    uint8_t processor_and_request;
    uint8_t sequence;
    uint8_t channel;
    uint8_t region;
    uint32_t start_address;
    uint32_t space_to_be_read;
} read_request_packet_data;

typedef struct {
    uint16_t eieio_header_command;
    uint8_t request;
    uint8_t sequence;
} host_data_read_packet_header;

typedef struct {
    uint16_t zero;
    uint8_t channel;
    uint8_t region;
    uint32_t space_read;
} host_data_read_packet_data;

//! \brief Determines if the given channel has space assigned for recording.
//! \param[in] recording_flags The flags as returned by recording_initialize
//! \param[in] channel The channel to check
//! \return True if the channel is enabled, false otherwise
inline bool recording_is_channel_enabled(
        uint32_t recording_flags, uint8_t channel) {
    return (recording_flags & (1 << channel)) != 0;
}

//! \brief records some data into a specific recording channel.
//! \param[in] channel the channel to store the data into.
//! \param[in] data the data to store into the channel.
//! \param[in] size_bytes the number of bytes that this data will take up.
//! \return boolean which is True if the data has been stored in the channel,
//!         False otherwise.
bool recording_record(
    uint8_t channel, void *data, uint32_t size_bytes);

//! \brief Finishes recording - should only be called if recording_flags is
//!        not 0
void recording_finalise();

//! \brief initialises the recording of data
//! \param[in] recording_data_address The start of the data about the recording
//!            Data is {
//!                // number of potential recording regions
//!                uint32_t n_regions;
//!
//!                // tag for live buffer control messages
//!                uint32_t buffering_output_tag;
//!
//!                // size of buffer before a read request is sent
//!                uint32_t buffer_size_before_request;
//!
//!                // minimum time between sending read requests
//!                uint32_t time_between_triggers;
//!
//!                // space that will hold the last sequence number once
//!                // recording is complete
//!                uint32_t last_sequence_number
//!
//!                // pointer to each region to be filled in (can be read
//!                // after recording is complete)
//!                uint32_t* pointer_to_address_of_region[n_regions]
//!
//!                // size of each region to be recorded
//!                uint32_t size_of_region[n_regions];
//!
//!            }
//! \param[out] recording_flags Output of flags which can be used to check if
//!            a channel is enabled for recording
//! \return True if the initialisation was successful, false otherwise
bool recording_initialize(
        address_t recording_data_address, uint32_t *recording_flags);

//! \brief resets recording to the state just after initialisation
void recording_reset();

//! \brief Call once per timestep to ensure buffering is done - should only
//!        be called if recording flags is not 0
void recording_do_timestep_update(uint32_t time);

#endif // _RECORDING_H_

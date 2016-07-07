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
//! \param[in] n_regions the number of regions to be recorded, one per type of
//!            data
//! \param[in] region_ids the ids of the regions to be recorded to
//! \param[in] recording_data The start of the data about the recording.
//!            Data is {uint32_t tag; uint32_t buffer_size_before_request;
//!                     uint32_t size_of_region[n_regions]}
//! \param[in] state_region The region in which to store the end of recording
//!            state information
//! \param[out] recording_flags Output of flags which can be used to check if
//!            a channel is enabled for recording
//! \return True if the initialisation was successful, false otherwise
bool recording_initialize(
        uint8_t n_regions, uint8_t *region_ids, uint32_t *recording_data,
        uint8_t state_region, uint32_t *recording_flags);

//! \brief Call once per timestep to ensure buffering is done - should only
//!        be called if recording flags is not 0
void recording_do_timestep_update(uint32_t time);

#endif // _RECORDING_H_

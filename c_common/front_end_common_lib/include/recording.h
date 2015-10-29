/*! \file
 *  \brief interface for recording data into "channels" on the SDRAM in a
 *  standard way for neural models.
 *
 *  \details
 *  the API is:
 *  - recording_read_region_sizes(region_start, recording_flags,
 *            spike_history_region_size, neuron_potential_region_size,
 *            neuron_gysn_region_size):
 *      Reads the size of the recording regions - pass 0s for the region
 *       size pointer when the value is not needed
 *  - recording_is_channel_enabled(recording_flags, channel):
 *      Determines if the given channel has been initialised yet.
 *  - recording_initialse_channel(output_region, channel, size_bytes)
 *      initialises a channel with the start, end, size and current position
 *       in SDRAM for the channel handed in.
 *  - recording_record(channel, data, size_bytes);
 *      records some data into a specific recording channel.
 *  -recording_finalise():
 *      updated the first word in the recording channel's memory region with
 *       the number of bytes that was actually written to SDRAM and then closes
 *       the channel so that future records fail.
 *
 */

#ifndef _RECORDING_H_
#define _RECORDING_H_

/*
 * TODO need to change the interface so that we add channels to recording which
 * then keeps it in a dynamic list so that models don't need to keep track of
 * the recording channels themselves.
 */


#include "common-typedefs.h"
#include "spin1_api.h"
#include <buffered_eieio_defs.h>

//! human readable forms of the different channels supported for neural models.
typedef enum recording_channel_e {
    e_recording_channel_spike_history,
    e_recording_channel_neuron_potential,
    e_recording_channel_neuron_gsyn,
    e_recording_channel_max,
} recording_channel_e;

typedef struct
{
    uint16_t eieio_header_command;
    uint16_t chip_id;
} read_request_packet_header;

typedef struct
{
    uint8_t processor_and_request;
    uint8_t sequence;
    uint8_t channel;
    uint8_t region;
    uint32_t start_address;
    uint32_t space_to_be_read;
} read_request_packet_data;

typedef struct
{
    uint16_t eieio_header_command;
    uint8_t request;
    uint8_t sequence;
} host_data_read_packet_header;

typedef struct
{
    uint16_t zero;
    uint8_t channel;
    uint8_t region;
    uint32_t space_read;
} host_data_read_packet_data;



//! max number of recordable channels supported by the neural models
#define RECORDING_POSITION_IN_REGION 3
#define MIN_BUFFERING_OUT_LIMIT 75

//! \brief Reads the size of the recording regions - pass 0s for the region
//!        size pointer when the value is not needed
//!
//! The region is expected to be formatted as:
//!      - 32-bit word with last 3-bits indicating if each of the 3 regions are
//!        in use
//!      - 32-bit word for the size of the spike history region
//!      - Optional 32-bit word for the size of the potential region (must be
//!        present if the gsyn region size is present).
//!      - Optional 32-bit word for the size of the gsyn region
//!
//! \param[in]  region_start A pointer to the start of the region (or to the
//!                          first 32-bit word if included as part of another
//!                          region
//! \param[out] recording_flags A pointer to an integer to receive the flags
//! \param[out] spike_history_region_size A pointer to an in integer to receive
//!                                       the size of the spike history region.
//! \param[out] neuron_potential_region_size A pointer to an in integer to
//!                                          receive the size of the neuron
//!                                          potential region.
//! \param[out] neuron_gsyn_region_size A pointer to an in integer to receive
//!                                     the size of the neuron gsyn region.
/*
void recording_read_region_sizes(
        address_t region_start, uint32_t* recording_flags,
        uint32_t* spike_history_region_size,
        uint32_t* neuron_potential_region_size,
        uint32_t* neuron_gysn_region_size);
*/

//! \brief Determines if the given channel has been initialised yet.
//! \param[in] recording_flags The flags as read by recording_read_region_sizes.
//! \param[in] channel The channel to check for already been initialised.
//! \return True if the channel has already been initialised, False otherwise.
inline bool recording_is_channel_enabled(uint32_t recording_flags,
        uint8_t channel) {
    return (recording_flags & (1 << channel)) != 0;
}

//! \brief initialises a channel with the start, end, size and current position
//! in SDRAM for the channel handed in.
//! \param[in] output_region the absolute memory address in SDRAM for the
//!recording region
//! \param[out] channel the channel to which we are initialising the
//! parameters of.
// \param[out] size_bytes the size of memory that the channel can put data into
//! \return boolean which is True if the channel was successfully initialised
//! or False otherwise.
/*
bool recording_initialise_channel(
        address_t output_region, recording_channel_e channel,
        uint32_t size_bytes);
*/

//! \brief records some data into a specific recording channel.
//! \param[in] channel the channel to store the data into.
//! \param[in] data the data to store into the channel.
//! \param[in] size_bytes the number of bytes that this data will take up.
//! \return boolean which is True if the data has been stored in the channel,
//! False otherwise.
bool recording_record(
        recording_channel_e channel, void *data, uint32_t size_bytes);

//! \brief updated the first word in the recording channel's memory region with
//! the number of bytes that was actually written to SDRAM and then closes the
//! channel so that future records fail.
//! \return nothing
void recording_finalise();

bool recording_initialize(uint8_t n_regions, uint8_t *region_ids,
                          uint32_t* region_sizes, uint8_t state_region,
                          uint8_t tag_id, uint32_t *recording_flags);

bool recording_write_memory(recording_channel_e channel, void *data, uint32_t size_bytes);
void recording_send_buffering_out_trigger_message(bool flush_all);
void recording_eieio_packet_handler(eieio_msg_t msg, uint length);
void recording_host_data_read(eieio_msg_t msg, uint length);
void recording_host_request_flush_data(eieio_msg_t msg, uint length);

#endif // _RECORDING_H_

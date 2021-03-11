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

/*! \file
 *  \brief interface for recording data into "channels" on the SDRAM in a
 *         standard way, and storing buffers to be extracted during execution
 */

#ifndef _RECORDING_H_
#define _RECORDING_H_

#include <stdbool.h>
#include <common-typedefs.h>
#include <spin1_api.h>
#include <buffered_eieio_defs.h>

//! \brief The type of channel indices.
typedef uint8_t channel_index_t;

//! \brief records some data into a specific recording channel.
//! \param[in] channel: the channel to store the data into.
//! \param[in] data: the data to store into the channel.
//! \param[in] size_bytes: the number of bytes that this data will take up.
//!            This may be any number of bytes, not just whole words.
//! \return True if the data has been stored in the channel,
//!         False otherwise.
bool recording_record(channel_index_t channel, const void *data, size_t size_bytes);

//! \brief Finishes recording.
//! \details should only be called if recording_flags is not 0
void recording_finalise(void);

//! \brief initialises the recording of data
//! \param[in,out] recording_data_address:
//!     The start of the data about the recording, updated to point to just
//!     after the data if return True. Data is:
//! ```
//! {
//!    // number of potential recording regions
//!    uint32_t n_regions;
//!
//!     // one of these for each region
//!     {
//!         // flag to indicate missing data
//!         uint32_t missing: 1;
//!
//!         // size of region to be recorded
//!         uint32_t size_of_region: 31;
//!
//!         // pointer region to be filled in (can be read after recording is
//!         // complete)
//!         uint8_t* pointer_to_address_of_region;
//!     }[n_regions]
//! }
//! ```
//! \param[out] recording_flags: Output of flags which can be used to check if
//!            a channel is enabled for recording
//! \return True if the initialisation was successful, false otherwise
bool recording_initialize(void **recording_data_address, uint32_t *recording_flags);

//! \brief resets recording to the state just after initialisation
void recording_reset(void);

#endif // _RECORDING_H_

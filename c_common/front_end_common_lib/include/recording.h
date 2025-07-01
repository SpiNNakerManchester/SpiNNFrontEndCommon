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

//! \brief determine if there is space in a specific recording channel.
//! \param[in] channel the channel to check.
//! \param[in] size_bytes the number of bytes that this data will take up.
//! \param[in] flag_missing if True, then the raise the missing data flag if
//!            there is not enough space in the channel
//! \return boolean which is True if there is enough space in the channel,
//!         False otherwise.
bool recording_is_space(channel_index_t channel, size_t size_bytes,
        bool flag_missing);

//! \brief records some data into a specific recording channel.
//! \param[in] channel the channel to store the data into.
//! \param[in] data the data to store into the channel.
//! \param[in] size_bytes the number of bytes that this data will take up.
//!            This may be any number of bytes, not just whole words.
//! \return boolean which is True if the data has been stored in the channel,
//!         False otherwise.
bool recording_record(channel_index_t channel, void *data, size_t size_bytes);

//! \brief Finishes recording - should only be called if recording_flags is
//!        not 0
void recording_finalise(void);

//! \brief initialises the recording of data
//! \param[in,out] recording_data_address The start of the data about the
//!                                       recording, updated to point to just
//!                                       after the data if return True.
//!                                       Data is:
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

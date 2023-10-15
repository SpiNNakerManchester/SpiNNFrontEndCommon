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
 *
 *  \brief implementation of recording.h
 *
 */

#include <recording.h>
#include <simulation.h>
#include <buffered_eieio_defs.h>
#include <sark.h>
#include <circular_buffer.h>
#include <spin1_api_params.h>
#include <debug.h>
#include <wfi.h>

//---------------------------------------
// Structures
//---------------------------------------
//! \brief Structure that defines a channel in memory.
//!
//! Channels are implemented using a circular buffer.
typedef struct recording_channel_t {
    uint8_t *start;             //!< The first byte of the buffer
    uint8_t *end;               //!< One byte past the end of the buffer
    uint8_t *write;             //!< Where to write to next
    uint32_t space: 31;         //!< The space remaining in the channel
    uint32_t missing: 1;        //!< Flag indicating if recording missed data
} recording_channel_t;

//! Data for an individual region
typedef struct recording_region_t {
    //! The size of the region to record into
    uint32_t space;
    //! The size of the region after recording
    uint32_t size:31;
    //! Flag indicating if any data is missing
    uint32_t missing: 1;
    //! Pointer to the recorded data
    uint8_t *data;
} recording_region_t;

//! header of general structure describing all recordings
typedef struct recording_regions_t {
    //! The number of recording regions
    uint32_t n_regions;
    //! Item for each region
    recording_region_t regions[];

} recording_regions_t;

//---------------------------------------
// Globals
//---------------------------------------

//! Array containing all possible channels
static recording_channel_t *channels;

//! The parameters of the recording
static recording_regions_t *regions;

//---------------------------------------
//! \brief checks that a channel has been initialised
//! \param[in] rec the channel data to check
//! \return True if the channel has been initialised or false otherwise
static inline bool has_been_initialised(recording_channel_t *rec) {
    return rec->start != NULL;
}

//----------------------------------------
//! \brief closes a channel
//! \param[in] rec: the channel to close
static inline void close_channel(recording_channel_t *rec) {
    rec->start = NULL;
}

//! \brief copy data in word-size chunks
//! \param[in] target where to write the data to
//! \param[in] source where to read the data from
//! \param[in] n_words the number of words to copy
static inline void copy_data(
        void *restrict target, const void *source, uint n_words) {
    uint *to = target;
    const uint *from = source;
    while (n_words-- > 0) {
        *to++ = *from++;
    }
}

bool recording_record(uint8_t channel, void *data, uint32_t size_bytes) {
    recording_channel_t *rec = &channels[channel];
    if (has_been_initialised(rec)) {

        if (rec->space >= size_bytes) {
            if ((((int) data & 0x3) != 0) || ((size_bytes & 0x3) != 0)) {
                spin1_memcpy(rec->write, data, size_bytes);
            } else {
                copy_data(rec->write, data, size_bytes >> 2);
            }
            rec->space -= size_bytes;
            rec->write += size_bytes;
            return true;
        }

        if (!rec->missing) {
            log_warning("WARNING: recording channel %u out of space", channel);
            rec->missing = 1;
        }
    }

    return false;
}

__attribute__((noreturn))
//! \brief Stop the program because of a bad recording request
//! \param[in] data: The address we were seeking to record from
//! \param[in] size: The amount of data we were seeking to record
void recording_bad_offset(void *data, uint32_t size) {
    log_error("DMA transfer of non-word data quantity in recording! "
            "(data=0x%08x, size=0x%x)", data, size);
    rt_error(RTE_SWERR);
}

void recording_finalise(void) {
    log_debug("Finalising recording channels");

    // Loop through channels
    for (uint32_t channel = 0; channel < regions->n_regions; channel++) {
        recording_channel_t *rec = &channels[channel];
        // If this channel's in use, copy things back to SDRAM
        if (has_been_initialised(rec)) {
            recording_region_t *reg = &regions->regions[channel];
            log_info("Recording channel %u, start=0x%08x, end=0x%08x, write=0x%08x, space=%u",
                    channel, rec->start, rec->end, rec->write, rec->space);
            reg->size = rec->write - rec->start;
            reg->missing = rec->missing;
            if (rec->missing) {
                log_info("Recording channel %u - has missing data", channel);
            }
            log_info("Recording channel %u wrote %u bytes", channel, reg->size);
            close_channel(rec);
        }
    }
}

bool recording_initialize(
        void **recording_data_address, uint32_t *recording_flags) {
    // Get the parameters
    regions = *recording_data_address;

    // Update the pointer to after the data
    uint32_t n_regions = regions->n_regions;
    *recording_data_address = &regions->regions[n_regions];

    // Set up the space for holding recording pointers and sizes
    channels = spin1_malloc(n_regions * sizeof(recording_channel_t));
    if (channels == NULL) {
        log_error("Not enough space to allocate recording channels");
        return false;
    }

    // Set up the recording flags
    if (recording_flags != NULL) {
        *recording_flags = 0;
    }

    /* Reserve the actual recording regions.
     *
     */
    for (uint32_t i = 0; i < n_regions; i++) {
        recording_region_t *region = &regions->regions[i];
        uint32_t space = region->space;
        if (space > 0) {
            region->data = sark_xalloc(
                    sv->sdram_heap, space, 0,
                    ALLOC_LOCK + ALLOC_ID + (sark_vec->app_id << 8));
            if (region->data == NULL) {
                log_error("Could not allocate recording region %u of %u bytes,"
                        " available was %u bytes", i, space,
                        sark_heap_max(sv->sdram_heap, 0));
                return false;
            }
//            log_info("Allocated %u bytes for recording channel %u at 0x%08x",
//                    space, i, region->data);
            if (recording_flags != NULL) {
                *recording_flags = (*recording_flags | (1 << i));
            }
        }
    }

    // Set up the channels and write the initial state data
    recording_reset();

    return true;
}

void recording_reset(void) {
    // Go through the regions and set up the data
    for (uint32_t i = 0; i < regions->n_regions; i++) {
        recording_region_t *region = &regions->regions[i];
        recording_channel_t *channel = &channels[i];
        uint32_t space = region->space;
        if (space > 0) {
            uint8_t *data = region->data;
            channel->start = data;
            channel->end = data + space;
            channel->space = space;
            channel->write = data;
            channel->missing = 0;

            log_info("Recording channel %u configured to use %u byte memory block"
                    " starting at 0x%08x", i, channel->space, channel->start);
        } else {
            close_channel(channel);
            log_info("Recording channel %u left uninitialised", i);
        }
    }
}

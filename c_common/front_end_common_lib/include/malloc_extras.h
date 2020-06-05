/*
 * Copyright (c) 2019-2020 The University of Manchester
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

//! \file
//! \brief Support for adding debugging information to dynamic allocation
#ifndef __MALLOC_EXTRAS_H__
#define __MALLOC_EXTRAS_H__

#include <sark.h>
#include <common-typedefs.h>
#include <debug.h>

//! debug flag to lock in safety features
#define SAFETY_FLAG     0xDEADBEEF
#define EXTRA_BYTES     64
#define MINUS_POINT     60
#define BYTE_TO_WORD    4
#define BUFFER_WORDS    15
#define MIN_SIZE_HEAP   32

//! The different states to report through `vcpu->user1`
typedef enum exit_states_for_user_one {
    //! Everything is fine
    EXITED_CLEANLY = 0,
    //! We went wrong
    EXIT_FAIL = 1,
    //! We ran out of space
    EXIT_MALLOC = 2,
    //! We hit an internal error
    EXIT_SWERR = 3,
    //! We detected a problem
    DETECTED_MALLOC_FAILURE = 4
} exit_states_for_user_one;

//! An SDRAM block outside the heap
typedef struct sdram_block {
    //! Base address of where the SDRAM block starts
    uchar *sdram_base_address;
    //! Size of block in bytes
    uint size;
} sdram_block;

//! Holds host-allocated SDRAM blocks outside the heap
typedef struct available_sdram_blocks {
    //! Number of blocks of SDRAM which can be utilised outside of alloc
    int n_blocks;
    //! VLA of SDRAM blocks
    sdram_block blocks[];
} available_sdram_blocks;

// ===========================================================================

//! \brief Turn off safety code if wanted
void malloc_extras_turn_off_safety(void);

//! \brief Turn on printing
//! \note Printing of allocations can take a lot of IOBUF space.
void malloc_extras_turn_on_print(void);

//! \brief Turn off printing
void malloc_extras_turn_off_print(void);

//! \brief Get the pointer to the stolen heap
//! \return the heap pointer.
heap_t *malloc_extras_get_stolen_heap(void);

#if 0
static inline void terminate(uint result_code) __attribute__((noreturn));
#endif

//! \brief Stops execution with a result code
//! \param[in] result_code: code to put in user 1
void malloc_extras_terminate(uint result_code);

//! \brief Checks a pointer for safety stuff
//! \param[in] ptr: the malloc pointer to check for memory overwrites
//! \return true if nothing is broken, false if there was detected overwrites.
bool malloc_extras_check(void *ptr);

//! \brief Checks all malloc()s with a given marker.
//! \param[in] marker: the numerical marker for this test, allowing easier
//!     tracking of where this check was called in the user application code
//! \internal probably should be a string marker, but meh
void malloc_extras_check_all_marked(int marker);

//! \brief Checks all malloc's for overwrites with no marker
//! \details Calls malloc_extras_check_all_marked(), but does not provide an
//!     easy marker to track back to the application user code.
void malloc_extras_check_all(void);

//! \brief Update heap
//! \param[in] heap_location: address where heap is located
bool malloc_extras_initialise_with_fake_heap(heap_t *heap_location);

//! \brief Builds a new heap based off stolen sdram blocks from cores
//!     synaptic matrices.
//! \details Needs to merge in the true SDRAM free heap, as otherwise it's
//!     impossible to free the block properly.
//! \param[in] sizes_region; the sdram address where the free regions exist
//! \return None
bool malloc_extras_initialise_and_build_fake_heap(
        available_sdram_blocks *sizes_region);

//! \brief Builds a new heap with no stolen SDRAM and sets up the malloc
//!     tracker.
//! \return true is a successful initialisation and false otherwise.
bool malloc_extras_initialise_no_fake_heap_data(void);

//! \brief Frees the sdram allocated from whatever heap it came from
//! \param[in] ptr: the address to free. could be DTCM or SDRAM
//! \param[in] marker: the numerical marker for this test, allowing easier
//!     tracking of where this check was called in the user application code
void malloc_extras_free_marked(void *ptr, int marker);

//! \brief Frees a pointer without any marker for application code
//! \param[in] ptr: the pointer to free.
void malloc_extras_free(void *ptr);

//! \brief Mallocs a number of bytes from SDRAM.
//! \details If safety turned on, it allocates more SDRAM to support buffers
//!     and size recordings.
//! \param[in] bytes: the number of bytes to allocate from SDRAM.
//! \return the pointer to the location in SDRAM to use in application code.
void *malloc_extras_sdram_malloc_wrapper(uint bytes);

//! \brief Allows a search of the 2 heaps available. (DTCM, stolen SDRAM)
//! \note Commented out as this can cause stack overflow issues quickly.
//!     If deemed safe, could be uncommented. That is the same to the
//!     `#define` below at the end of the file
//! \param[in] bytes: the number of bytes to allocate.
//! \return: the address of the block of memory to utilise.
void *malloc_extras_malloc(uint bytes);

//! \brief Locates the biggest block of available memory from the heaps
//! \return the biggest block size in the heaps.
uint malloc_extras_max_available_block_size(void);

#define MALLOC          malloc_extras_malloc
#define FREE            malloc_extras_free
#define FREE_MARKED     malloc_extras_free_marked
#define MALLOC_SDRAM    malloc_extras_sdram_malloc_wrapper

#endif  // __PLATFORM_H__

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

#ifndef __MALLOC_EXTRAS_H__
#define __MALLOC_EXTRAS_H__

#include <sark.h>
#include <common-typedefs.h>
#include <debug.h>

//! debug flag to lock in safety features
#define SAFETY_FLAG 0xDEADBEEF
#define EXTRA_BYTES 64
#define MINUS_POINT 60
#define BYTE_TO_WORD 4
#define BUFFER_WORDS 15
#define MIN_SIZE_HEAP 32

//! enum for the different states to report through the user1 address.
typedef enum exit_states_for_user_one {
    EXITED_CLEANLY = 0, EXIT_FAIL = 1, EXIT_MALLOC = 2, EXIT_SWERR = 3,
    DETECTED_MALLOC_FAILURE = 4
} exit_states_for_user_one;


//! a sdram block outside the heap
typedef struct sdram_block {
    // the base address of where the sdram block starts
    uchar *sdram_base_address;

    // size of block in bytes
    uint size;

} sdram_block;

//! the struct for holding host based sdram blocks outside the heap
typedef struct available_sdram_blocks {
    // the number of blocks of sdram which can be utilised outside of alloc
    int n_blocks;

    // VLA of sdram blocks
    sdram_block blocks [];
} available_sdram_blocks;

// ===========================================================================

//! \brief turn on printing
void malloc_extras_turn_on_print(void);

//! \brief turn off printing
void malloc_extras_turn_off_print(void);

//! \brief get the pointer to the stolen heap
//! \return the heap pointer.
heap_t* malloc_extras_get_stolen_heap(void);

//static inline void terminate(uint result_code) __attribute__((noreturn));
//! \brief stops a binary dead
//! \param[in] code to put in user 1
void malloc_extras_terminate(uint result_code);

//! \brief checks a pointer for safety stuff
bool malloc_extras_check(void *ptr);

//! \brief checks all malloc's with a given marker. to allow easier tracking
//! from application code (probably should be a string. but meh)
void malloc_extras_check_all_marked(int marker);

//! \brief checks all malloc's for overwrites with no marker
void malloc_extras_check_all(void);

//! \brief update heap
//! \param[in] heap_location: address where heap is location
bool malloc_extras_initialise_with_fake_heap(heap_t *heap_location);

//! \brief builds a new heap based off stolen sdram blocks from cores
//! synaptic matrix's. Needs to merge in the true sdram free heap, as
//! otherwise its impossible to free the block properly.
//! \param[in] sizes_region; the sdram address where the free regions exist
//! \return None
bool malloc_extras_initialise_and_build_fake_heap(
        available_sdram_blocks *sizes_region);

//! \brief builds a new heap with no stolen SDRAM and sets up the malloc
//! tracker.
//! \return bool where true is a successful initialisation and false otherwise.
bool malloc_extras_initialise_no_fake_heap_data(void);

//! \brief frees the sdram allocated from whatever heap it came from
//! \param[in] ptr: the address to free. could be DTCM or SDRAM
void malloc_extras_free_marked(void *ptr, int marker);

//! \brief frees a pointer without any marker for application code
//! \param[in] ptr: the pointer to free.
void malloc_extras_free(void *ptr);

void * malloc_extras_sdram_malloc_wrapper(uint bytes);

//! \brief allows a search of the 2 heaps available. (DTCM, stolen SDRAM)
//! NOTE: commented out as this can cause stack overflow issues quickly.
//! if deemed safe. could be uncommented out. which the same to the #define
//! below at the end of the file
//! \param[in] bytes: the number of bytes to allocate.
//! \return: the address of the block of memory to utilise.
void * malloc_extras_malloc(uint bytes);

//! \brief locates the biggest block of available memory from the heaps
//! \return the biggest block size in the heaps.
uint malloc_extras_max_available_block_size(void) ;

#define MALLOC malloc_extras_malloc
#define FREE   malloc_extras_free
#define FREE_MARKED malloc_extras_free_marked
#define MALLOC_SDRAM malloc_extras_sdram_malloc_wrapper

#endif  // __MALLOC_EXTRAS_H__

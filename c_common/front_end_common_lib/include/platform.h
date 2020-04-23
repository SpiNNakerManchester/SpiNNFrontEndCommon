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

#ifndef __PLATFORM_H__
#define __PLATFORM_H__

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
void platform_turn_on_print(void);

//! \brief turn off printing
void platform_turn_off_print(void);

//! \brief get the pointer to the stolen heap
//! \return the heap pointer.
heap_t* platform_get_stolen_heap(void);

//static inline void terminate(uint result_code) __attribute__((noreturn));
//! \brief stops a binary dead
//! \param[in] code to put in user 1
void terminate(uint result_code);

//! \brief checks a pointer for safety stuff
bool platform_check(void *ptr);

//! \brief checks all malloc's with a given marker. to allow easier tracking
//! from application code (probably should be a string. but meh)
void platform_check_all_marked(int marker);

//! \brief checks all malloc's for overwrites with no marker
void platform_check_all(void);


//! \brief cycles through the true heap and figures how many blocks there are
//! to steal.
//! \param[in] sdram_heap: the true sdram heap
//! \return the number of sdram blocks to utilise
int available_mallocs(heap_t *sdram_heap);

//! \brief builds a tracker for mallocs. for debug purposes
void build_malloc_tracker(void);

//! \brief update heap
//! \param[in] heap_location: address where heap is location
bool platform_new_heap_update(heap_t *heap_location);

//! \brief count how much space available given expected block costs
//! \param[in] sizes_region: the sdram loc where addresses to steal are located
uint free_space_available(available_sdram_blocks *sizes_region);

//! \brief steals all sdram spaces from true heap
//! \param[in] list_of_available_blocks: loc for stolen heap bits to go
bool add_heap_to_collection(sdram_block *list_of_available_blocks);

//! \brief builds the new heap struct over our stolen and proper claimed
//! sdram spaces.
void make_heap_structure(
        available_sdram_blocks *sizes_region, int n_mallocs,
        sdram_block *list_of_available_blocks);

//! \brief prints out the fake heap as if the spin1 alloc was operating over it
void print_free_sizes_in_heap(void);


//! \brief builds a new heap based off stolen sdram blocks from cores
//! synaptic matrix's. Needs to merge in the true sdram free heap, as
//! otherwise its impossible to free the block properly.
//! \param[in] sizes_region; the sdram address where the free regions exist
//! \return None
bool platform_new_heap_creation(
        available_sdram_blocks *sizes_region);

//! \brief frees the sdram allocated from whatever heap it came from
//! \param[in] ptr: the address to free. could be DTCM or SDRAM
void safe_x_free_marked(void *ptr, int marker);

void safe_x_free(void *ptr);

//! \brief doubles the size of the sdram malloc tracker
void build_bigger_size(void);

int find_free_malloc_index(void);

//! \brief allows a search of the SDRAM heap.
//! \param[in] bytes: the number of bytes to allocate.
//! \return: the address of the block of memory to utilise.
void * safe_sdram_malloc(uint bytes);

void * safe_sdram_malloc_wrapper(uint bytes);

//! \brief allows a search of the 2 heaps available. (DTCM, stolen SDRAM)
//! NOTE: commented out as this can cause stack overflow issues quickly.
//! if deemed safe. could be uncommented out. which the same to the #define
//! below at the end of the file
//! \param[in] bytes: the number of bytes to allocate.
//! \return: the address of the block of memory to utilise.
/*static void * safe_malloc(uint bytes) {

    if (safety) {
        bytes = bytes + EXTRA_BYTES;
    }

    // try DTCM
    int *p = sark_alloc(bytes, 1);

    if (p == NULL) {
       if(to_print) {
           log_info("went to sdram");
       }
       p = safe_sdram_malloc(bytes);
    }

    if (safety) {
        int n_words = (int) ((bytes - 4) / BYTE_TO_WORD);
        p[0] = n_words;
        p[n_words] = SAFETY_FLAG;
        int malloc_point_index = find_free_malloc_index();
        if (malloc_point_index == -1){
            log_error("cant track this malloc. failing");
            rt_error(RTE_SWERR);
        }

        malloc_points[malloc_point_index] = (void *)  &p[1];

        // only print if its currently set to print (saves iobuf)
        if(to_print) {
            log_info("index %d", malloc_point_index);
            log_info("address is %x", &p[1]);
        }
        return (void *) &p[1];
    }

    return (void *) p;
}*/

//! \brief locates the biggest block of available memory from the heaps
//! \return the biggest block size in the heaps.
uint platform_max_available_block_size(void) ;

/* this is commented out to stop utilising DTCM. if deemed safe, could be
 turned back on
#define MALLOC safe_malloc*/
#define MALLOC safe_sdram_malloc_wrapper
#define FREE   safe_x_free
#define FREE_MARKED safe_x_free_marked
#define MALLOC_SDRAM safe_sdram_malloc_wrapper

#endif  // __PLATFORM_H__

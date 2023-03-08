/*
 * Copyright (c) 2019 The University of Manchester
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

#include <sark.h>
#include <common-typedefs.h>
#include <debug.h>
#include <malloc_extras.h>

//! debug flag to lock in safety features
#define SAFETY_FLAG     0xDEADBEEF
//! amount of extra space _per allocation_ to add for the safety checker code
#define EXTRA_BYTES     64
//! offset used to compute location of the heap block metadata
#define MINUS_POINT     60
//! the number of bytes in a word
#define BYTE_TO_WORD    4
//! number of words to fill with debug canaries
#define BUFFER_WORDS    (MINUS_POINT / BYTE_TO_WORD)
//! minimum size of heap to steal from SARK
#define MIN_SIZE_HEAP   32

//============================================================================
// control flags

//! debug flag to lock in safety features
bool safety = true;

//! \brief flag to help with debugging
bool to_print = false;

//! \brief use DTCM at all?
//! \details ONLY TURN THIS ON IF YOU'RE SURE STACK OVERFLOWS WILL NOT HAPPEN
bool use_dtcm = true;

//============================================================================
// global variables

//! a extra heap, that exploits SDRAM which can be easily regenerated.
static heap_t *stolen_sdram_heap = NULL;

//! tracker for mallocs
void **malloc_points = NULL;

//! base line for the tracker array size. will grow with usage
int malloc_points_size = 4;

// ===========================================================================
// functions

void malloc_extras_turn_off_safety(void) {
    safety = false;
}

void malloc_extras_turn_on_print(void) {
    to_print = true;
}

void malloc_extras_turn_off_print(void) {
    to_print = false;
}

heap_t *malloc_extras_get_stolen_heap(void) {
    return stolen_sdram_heap;
}

#if 0
static inline void terminate(uint result_code) __attribute__((noreturn));
#endif
void malloc_extras_terminate(uint result_code) {
    vcpu_t *sark_virtual_processor_info = (vcpu_t *) SV_VCPU;
    uint core = spin1_get_core_id();
    sark_virtual_processor_info[core].user1 = result_code;

    if (result_code != EXITED_CLEANLY && result_code != EXIT_FAIL) {
        rt_error(RTE_SWERR);
    }
    spin1_exit(0);
}

bool malloc_extras_check(void *ptr) {
    // only check if safety is turned on. else its not possible to check.
    if (safety) {
        int *int_pointer = (int *) ptr;
        int_pointer = int_pointer - 1;
        int words = int_pointer[0];

        for (int buffer_index = 0; buffer_index < BUFFER_WORDS;
                buffer_index++) {
            uint32_t flag = int_pointer[words + buffer_index];
            if (flag != SAFETY_FLAG) {
                bool found = false;
                for (int index = 0; index < malloc_points_size; index ++) {
                    if ((malloc_points[index] != 0) &&
                            (malloc_points[index] == ptr)) {
                        found = true;
                    }
                }
                if (found) {
                    log_error("flag is actually %x for ptr %x", flag, ptr);
                } else {
                    log_error("Unexpected ptr %x", ptr);
                }
                return false;
             }
        }
        return true;
    }
    return true;
}

//! \brief allows the ability to read the size of a malloc.
//! \param[in] ptr: the pointer to get the size in words of.
//! \return returns the size of a given malloc in words.
int malloc_extras_malloc_size(void *ptr) {
    // only able to be figured out if safety turned on.
    if (safety) {
        // locate and return the len at the front of the malloc.
        int *int_pointer = (int *) ptr;
        int_pointer = int_pointer - 1;
        return int_pointer[0];
    }

    log_error("there is no way to measure size when the safety is off.");
    //Not know so return 0
    return 0;
}

//! \brief checks a given pointer with a marker
//! \param[in] ptr: the pointer marker for whats being checked.
//! \param[in] marker: the numerical marker for this test. allowing easier
//!     tracking of where this check was called in the user application code
//!     (probably should be a string. but meh)
void malloc_extras_check_marked(void *ptr, int marker) {
    // only check if safety turned on
    if (safety) {
        if (!malloc_extras_check(ptr)) {
            log_error("test failed with marker %d", marker);
            malloc_extras_terminate(DETECTED_MALLOC_FAILURE);
        }
    } else {
        log_error("check cannot operate with safety turned off.");
    }
}

void malloc_extras_check_all_marked(int marker) {
    // only check if safety turned on. else pointless.
    if (safety) {
        bool failed = false;
        for (int index = 0; index < malloc_points_size; index ++) {
            if (malloc_points[index] != 0 &&
                    !malloc_extras_check(malloc_points[index])) {
                log_error("the malloc with index %d has overran", index);
                log_error("this test is marked by marker %d", marker);
                failed = true;
            }
        }

        if (failed) {
            malloc_extras_terminate(DETECTED_MALLOC_FAILURE);
        }
    } else {
        log_error("cannot do checks with safety turned off");
    }
}

void malloc_extras_check_all(void) {
    malloc_extras_check_all_marked(-1);
}

//! \brief cycles through the true heap and figures how many blocks there are
//!     to steal.
//! \param[in] sdram_heap: the true SDRAM heap
//! \return the number of SDRAM blocks to utilise
static inline int find_n_available_mallocs(heap_t *sdram_heap) {
    int n_available_true_malloc = 0;
    block_t *free_blk = sdram_heap->free;

    // traverse blocks till none more available
    while (free_blk != NULL) {
        free_blk = free_blk->free;
        n_available_true_malloc += 1;
    }
    return n_available_true_malloc;
}

//! \brief builds a tracker for mallocs. for debug purposes
static void build_malloc_tracker(void) {
    // malloc tracker
    malloc_points = sark_xalloc(
            stolen_sdram_heap, malloc_points_size * sizeof(void*), 0,
            ALLOC_LOCK);
    if (malloc_points == NULL) {
        log_error("FAILED to allocate the tracker code!");
        rt_error(RTE_SWERR);
    }

    // set tracker.
    for (int index = 0; index < malloc_points_size; index ++) {
        malloc_points[index] = 0;
    }
}

//! \brief count how much space available given expected block costs
//! \param[in] sizes_region: the SDRAM loc where addresses to steal are located
//! \return size available given expected block costs
static inline uint find_free_space_available(
        available_sdram_blocks *sizes_region) {
    uint free = 0;
    for (int index = 0; index < sizes_region->n_blocks; index++) {
        free += sizes_region->blocks[index].size - sizeof(block_t);
    }
    return free;
}

//! \brief steals all SDRAM spaces from true heap
//! \param[in] list_of_available_blocks: location for stolen heap bits to go
//! \return true if successful. false otherwise
static inline bool add_heap_to_collection(
        sdram_block *list_of_available_blocks) {
    // go through true heap and allocate and add to end of list.
    int position = 0;

    // loop over the true heap and add accordingly.
    while (sv->sdram_heap->free != NULL) {
        block_t *next_blk = sv->sdram_heap->free->next;

        // get next size minus the size it'll need to put in when alloc'ing
        int size = ((uchar *) next_blk - (uchar *) sv->sdram_heap->free) -
                sizeof(block_t);

        // make life easier by saying blocks have to be bigger than the heap.
        // so all spaces can be used for heaps
        uchar *b_address = sark_xalloc(sv->sdram_heap, size, 0, ALLOC_LOCK);
        if (b_address == NULL) {
            log_error("failed to allocate %d", size);
            return false;
        }
        list_of_available_blocks[position].sdram_base_address = b_address;
        list_of_available_blocks[position].size = size;
        stolen_sdram_heap->free_bytes += size;
        position++;
    }
    return true;
}

//! \brief builds the new heap struct over our stolen and proper claimed
//!     SDRAM spaces.
//! \param[in] sizes_region: the struct that contains addresses and sizes that
//!     have already been allocated, but which we can use.
//! \param[in] n_mallocs: the number of mallocs expected to be done.
//! \param[in] list_of_available_blocks: the mallocs from the original heap.
static inline void make_heap_structure(
        available_sdram_blocks *sizes_region, int n_mallocs,
        sdram_block *list_of_available_blocks) {
    // generate position pointers
    int stolen_current_index = 0;
    int heap_current_index = 0;
    bool first = true;
    block_t *previous = NULL;
    block_t *previous_free = NULL;

    // generate heap pointers
    while (stolen_current_index < sizes_region->n_blocks ||
            heap_current_index < n_mallocs) {
        // build pointers to try to reduce code space
        int *to_process;
        sdram_block *to_process_blocks;

        // determine which tracker to utilise
        uint top_stolen = (uint) sizes_region->blocks[
                stolen_current_index].sdram_base_address;
        uint top_true = (uint) list_of_available_blocks[
                heap_current_index].sdram_base_address;

        // determine which one to utilise now
        if ((stolen_current_index < sizes_region->n_blocks) &&
                top_stolen < top_true) {
            to_process = &stolen_current_index;
            to_process_blocks = sizes_region->blocks;
        } else {
            to_process = &heap_current_index;
            to_process_blocks = list_of_available_blocks;
        }

        // if has not already set up the heap struct, set it up
        if (first) {
            // set flag to not need to do this again
            first = false;

            // set up stuff we can
            stolen_sdram_heap->free = (block_t *)
                    to_process_blocks[*to_process].sdram_base_address;

            stolen_sdram_heap->free->next = (block_t *) (
                    to_process_blocks[*to_process].sdram_base_address +
                    to_process_blocks[*to_process].size - sizeof(block_t));

            stolen_sdram_heap->free->free = NULL;
            stolen_sdram_heap->first = stolen_sdram_heap->free;

            // previous block in chain
            previous = stolen_sdram_heap->free->next;
            previous_free = stolen_sdram_heap->free;
        } else {
            // set up block in block
            block_t *free = (block_t *)
                    to_process_blocks[*to_process].sdram_base_address;
            free->free = NULL;

            // update next block
            free->next = (block_t *) (
                    to_process_blocks[*to_process].sdram_base_address +
                    to_process_blocks[*to_process].size - sizeof(block_t));
            free->next->free = NULL;
            free->next->next = NULL;

            // update previous links
            previous->next = free;
            previous->free = free;
            previous_free->free = free;

            // update previous pointers
            previous = free->next;
            previous_free = free;
        }
        // update pointers
        (*to_process)++;
    }

    // update last
    stolen_sdram_heap->last = previous;
    stolen_sdram_heap->last->free = NULL;
    stolen_sdram_heap->last->next = NULL;
}

//! prints out the fake heap as if the spin1 alloc was operating over it
static inline void print_free_sizes_in_heap(void) {
    block_t *free_blk = stolen_sdram_heap->free;
    uint total_size = 0;
    uint index = 0;

    // traverse blocks till none more available
    while (free_blk) {
        uint size = (uchar *) free_blk->next - (uchar *) free_blk;
        log_info("free block %d has address %x and size of %d",
                index, free_blk, size);

        total_size += size;
        free_blk = free_blk->free;
        index++;
    }

    log_info("total free size is %d", total_size);
}

//! \details sets up trackers for this core if asked.
//! \note DOES NOT REBUILD THE FAKE HEAP!
bool malloc_extras_initialise_with_fake_heap(
        heap_t *heap_location) {
    stolen_sdram_heap = heap_location;

    // if no real stolen SDRAM heap. point at the original SDRAM heap.
    if (stolen_sdram_heap == NULL) {
        stolen_sdram_heap = sv->sdram_heap;
    }

    // only build tracker if not already built and its expected
    if (malloc_points == NULL && safety) {
        build_malloc_tracker();
    }
    return true;
}

bool malloc_extras_initialise_and_build_fake_heap(
        available_sdram_blocks *sizes_region) {
    // hard set stolen sdram heap to the default heap. in case no fake heap
    stolen_sdram_heap = sv->sdram_heap;

    /* if planning to track all mallocs and frees to verify no
     overwrites/corruption. build the initial malloc tracker*/
    if (safety) {
        build_malloc_tracker();
    }

    // only build the fake heap if there's bits to build with
    if (sizes_region == NULL) {
        return true;
    }

    // allocate blocks store for figuring out block order
    uint n_mallocs = find_n_available_mallocs(sv->sdram_heap);
    sdram_block *list_of_available_blocks = sark_alloc(
            n_mallocs * sizeof(sdram_block), 1);

    // if fail to alloc dtcm blow up
    if (list_of_available_blocks == NULL) {
        return false;
    }

    // alloc space for a heap object (stealing from steal store if not by
    // normal means.
    stolen_sdram_heap =
            sark_xalloc(sv->sdram_heap, MIN_SIZE_HEAP, 0, ALLOC_LOCK);
    if (stolen_sdram_heap == NULL) {
        // check we can steal
        if (sizes_region->n_blocks == 0) {
            log_error("cant find space for the heap");
            return false;
        }

        // deallocate 32 bytes from first handed down to be the heap object
        stolen_sdram_heap = (heap_t *)
                sizes_region->blocks[0].sdram_base_address;
        sizes_region->blocks[0].sdram_base_address += MIN_SIZE_HEAP;
        sizes_region->blocks[0].size -= MIN_SIZE_HEAP;
    }

    // determine how much spare space there is.
    stolen_sdram_heap->free_bytes = find_free_space_available(sizes_region);

    // go through true heap and allocate and add to end of list.
    bool success = add_heap_to_collection(list_of_available_blocks);
    if (!success) {
        log_error("failed to add heap");
        return false;
    }

    // build the heap struct if there is a heap structure.
    make_heap_structure(sizes_region, n_mallocs, list_of_available_blocks);

    // free the allocated dtcm for the true alloc stuff.
    sark_free(list_of_available_blocks);

    // printer for sanity purposes
    if (to_print) {
        print_free_sizes_in_heap();
    }

    return true;
}

//! \brief builds a new heap with no stolen SDRAM and sets up the malloc
//!     tracker if required.
//! \return bool where true is a successful initialisation and false otherwise.
bool malloc_extras_initialise_no_fake_heap_data(void) {
    return malloc_extras_initialise_and_build_fake_heap(NULL);
}

void malloc_extras_free_marked(void *ptr, int marker) {
    // only print if its currently set to print (saves iobuf)
    if (to_print) {
        log_info("freeing %x", ptr);
    }

    // track if the pointer has been corrupted before trying to free it.
    // only possible if safety been turned on
    int *int_pointer = (int *) ptr;
    if (safety) {
        if (!malloc_extras_check(ptr)) {
            log_error("over ran whatever is being freed");
            log_error("marker is %d", marker);
            malloc_extras_terminate(DETECTED_MALLOC_FAILURE);
        }

        bool found = false;
        int index = 0;
        while (!found && index < malloc_points_size) {
            if (malloc_points[index] == ptr) {
                found = true;
                malloc_points[index] = 0;
            } else {
                index++;
            }
        }

        // if set to print and there was a free index, print it
        if (found && to_print) {
            log_info("freeing index %d", index);
        }

        // shift pointer if in safety
        int_pointer--;
    }

    // if safe to free, free from the correct heap based off position.
    if ((int) ptr >= DTCM_BASE && (int) ptr <= DTCM_TOP) {
        sark_xfree(sark.heap, int_pointer, ALLOC_LOCK);
    } else {
        sark_xfree(stolen_sdram_heap, int_pointer, ALLOC_LOCK);
    }
}

void malloc_extras_free(void *ptr) {
    malloc_extras_free_marked(ptr, -1);
}

//! \brief doubles the size of the SDRAM malloc tracker
static inline void build_bigger_size(void) {
    // make twice as big tracker
    int new_malloc_points_size = malloc_points_size * 2;

    // make new tracker
    void **temp_pointer = sark_xalloc(
            stolen_sdram_heap, new_malloc_points_size * sizeof(void*), 0,
            ALLOC_LOCK);

    // check for null
    if (temp_pointer == NULL) {
        log_error("failed to allocate space for next range.");
        rt_error(RTE_SWERR);
    }

    // init the new store
    for (int index = 0; index < new_malloc_points_size; index ++) {
        temp_pointer[index] = 0;
    }

    // move from old to new
    for (int index = 0; index < malloc_points_size; index ++) {
        temp_pointer[index] = malloc_points[index];
    }

    // free old and update pointers
    sark_xfree(stolen_sdram_heap, malloc_points, ALLOC_LOCK);
    malloc_points = temp_pointer;
    malloc_points_size = new_malloc_points_size;
}

//! \brief locates a new spot in the malloc tracker. may force a new
//!     allocation of malloc markers if full already.
//! \return the index in the current malloc tracker to put this new malloc
//!     pointer.
static inline int find_free_malloc_index(void) {
    int index;
    for (index = 0; index < malloc_points_size; index ++) {
        if (malloc_points[index] == 0) {
            return index;
        }
    }
    // full. rebuild twice as big
    build_bigger_size();
    return index + 1;
}

//! \brief allows a search of the SDRAM heap.
//! \param[in] bytes: the number of bytes to allocate.
//! \return the address of the block of memory to utilise.
static void *safe_sdram_malloc(uint bytes) {
    // try SDRAM stolen from the cores synaptic matrix areas.
    uint32_t *p = sark_xalloc(stolen_sdram_heap, bytes, 0, ALLOC_LOCK);

    if (p == NULL) {
        log_error("Failed to malloc %u bytes.\n", bytes);
    }

    return (void *) p;
}

//! \brief adds the len and buffers to a given malloc pointer.
//! \details Stores in the malloc tracker and prints index if required.
//! \param[in] p: The allocated buffer
//! \param[in] bytes: The size of the buffer in \p p
static void add_safety_len_and_padding(int *p, uint bytes) {
    // add len
    int n_words = (int) ((bytes - MINUS_POINT) / BYTE_TO_WORD);
    p[0] = n_words;

    // fill in buffer at end of malloc.
    for (int buffer_word = 0; buffer_word < BUFFER_WORDS; buffer_word++) {
        p[n_words + buffer_word] = SAFETY_FLAG;
    }

    // add malloc to the malloc tracker.
    int malloc_point_index = find_free_malloc_index();
    if (malloc_point_index == -1) {
        log_error("cant track this malloc. failing");
        rt_error(RTE_SWERR);
    }
    malloc_points[malloc_point_index] = (void *)  &p[1];

    // only print if its currently set to print (saves iobuf)
    if (to_print) {
        log_info("index %d", malloc_point_index);
        log_info("address is %x", &p[1]);
    }
}

void *malloc_extras_sdram_malloc_wrapper(uint bytes) {
    // if using safety. add the extra bytes needed for buffer and len.
    if (safety) {
        bytes = bytes + EXTRA_BYTES;
    }

    // malloc from SDRAM heap.
    int * p = safe_sdram_malloc(bytes);

    // if safety, add the len and buffers and return location for app code.
    if (safety) {
        add_safety_len_and_padding(p, bytes);

        // return the point were user code can use from.
        return (void *) &p[1];
    }

    // if no safety, the point is the point used by the application code.
    return (void *) p;
}

void *malloc_extras_malloc(uint bytes) {
    if (safety) {
        bytes = bytes + EXTRA_BYTES;
    }

    // try DTCM if allowed (not safe if overused, due to stack overflows)
    int *p = NULL;
    if (use_dtcm) {
        p = sark_alloc(bytes, 1);

        // if DTCM failed to malloc, go to SDRAM.
        if (p == NULL) {
           if (to_print) {
               log_info("went to SDRAM");
           }
           p = safe_sdram_malloc(bytes);
        }
    // only use SDRAM. (safer to avoid stack overflows)
    } else {
        if (to_print) {
            log_info("went to SDRAM without checking DTCM. as requested");
        }
        p = safe_sdram_malloc(bytes);
    }

    // if safety, add the len and buffers and return location for app code.
    if (safety) {
        add_safety_len_and_padding(p, bytes);

        // return the point were user code can use from.
        return (void *) &p[1];
    }

    // if no safety, the point is the point used by the application code.
    return (void *) p;
}

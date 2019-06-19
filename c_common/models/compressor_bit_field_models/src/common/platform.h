#ifndef __PLATFORM_H__
#define __PLATFORM_H__

#include <sark.h>
#include <common-typedefs.h>
#include <debug.h>


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

//! a extra heap, that exploits sdram which can be easily regenerated.
static heap_t *stolen_sdram_heap = NULL;

// ===========================================================================

#define MIN_SIZE_HEAP 32

// ===========================================================================

//! \brief cycles through the true heap and figures how many blocks there are
//! to steal.
//! \param[in] sdram_heap: the true sdram heap
//! \return the number of sdram blocks to utilise
static inline int available_mallocs(heap_t *sdram_heap){
    int n_available_true_malloc = 0;
    block_t *free_blk = sdram_heap->free;

    // traverse blocks till none more available
    while (free_blk != NULL) {
        free_blk = free_blk->free;
        n_available_true_malloc += 1;
    }
    return n_available_true_malloc;
}

//! \brief update heap
//! \param[in] heap_location: address where heap is location
static inline bool platform_new_heap_update(heap_t *heap_location){
    stolen_sdram_heap = heap_location;
    return true;
}

//! \brief count how much space available given expected block costs
//! \param[in] sizes_region: the sdram loc where addresses to steal are located
static inline uint free_space_available(available_sdram_blocks *sizes_region){
    uint free = 0;
    for (int index =0; index < sizes_region->n_blocks; index++){
        free += sizes_region->blocks[index].size - sizeof(block_t);
    }
    return free;
}

//! \brief steals all sdram spaces from true heap
//! \param[in] list_of_available_blocks: loc for stolen heap bits to go
static inline bool add_heap_to_collection(
        sdram_block *list_of_available_blocks){
    // go through true heap and allocate and add to end of list.
    int position = 0;

    // loop over the true heap and add accordingly.
    while (sv->sdram_heap->free != NULL){
        block_t *next_blk = sv->sdram_heap->free->next;

        // get next size minus the size it'll need to put in when alloc'ing
        int size =(
            (uchar*) next_blk - (uchar*) sv->sdram_heap->free) -
            sizeof(block_t);

        // make life easier by saying blocks have to be bigger than the heap.
        // so all spaces can be used for heaps
        uchar* block_address =
            sark_xalloc(sv->sdram_heap, size, 0, ALLOC_LOCK);
        if (block_address == NULL){
            log_error("failed to allocate %d", size);
            return false;
        }
        list_of_available_blocks[position].sdram_base_address =
            block_address;
        list_of_available_blocks[position].size = size;
        stolen_sdram_heap->free_bytes += size;
        position += 1;
    }
    return true;
}

//! \brief builds the new heap struct over our stolen and proper claimed
//! sdram spaces.
static inline void make_heap_structure(
        available_sdram_blocks *sizes_region, int n_mallocs,
        sdram_block *list_of_available_blocks){

    // generate position pointers
    int stolen_current_index = 0;
    int heap_current_index = 0;
    bool first = true;
    block_t *previous = NULL;
    block_t *previous_free = NULL;

    // generate heap pointers
    while (stolen_current_index < sizes_region->n_blocks ||
            heap_current_index < n_mallocs){
        if (previous != NULL){
            log_debug("previous is now %x", previous);
            log_debug("root free next is %x", stolen_sdram_heap->free->next);
        }

        // build pointers to try to reduce code space
        int * to_process;
        sdram_block *to_process_blocks;

        // determine which tracker to utilise
        uint top_stolen = (uint) sizes_region->blocks[
                stolen_current_index].sdram_base_address;
        uint top_true = (uint) list_of_available_blocks[
                    heap_current_index].sdram_base_address;

        // determine which one to utilise now
        if (((stolen_current_index < sizes_region->n_blocks) &&
                top_stolen < top_true)){
            log_debug("stolen");
            to_process = &stolen_current_index;
            to_process_blocks = sizes_region->blocks;
        }
        else{
            log_debug("true");
            to_process = &heap_current_index;
            to_process_blocks = list_of_available_blocks;
        }

        log_debug(
            "address %x with size %u",
            to_process_blocks[*to_process].sdram_base_address,
            to_process_blocks[*to_process].size);

        // if has not already set up the heap struct, set it up
        if (first){
            // set flag to not need to do this again
            first = false;

            // set up stuff we can
            stolen_sdram_heap->free =
                (block_t*) to_process_blocks[*to_process].sdram_base_address;
            log_debug("set root to %x", stolen_sdram_heap->free);

            stolen_sdram_heap->free->next =
                (block_t*) (
                    to_process_blocks[*to_process].sdram_base_address
                    + to_process_blocks[*to_process].size
                    - sizeof(block_t));

            log_debug(
                "free -> next is %x with size %u",
                stolen_sdram_heap->free->next,
                (uchar*) stolen_sdram_heap->free->next -
                (uchar*) stolen_sdram_heap->free);

            stolen_sdram_heap->free->free = NULL;
            stolen_sdram_heap->first = stolen_sdram_heap->free;

            // previous block in chain
            previous = stolen_sdram_heap->free->next;
            previous_free = stolen_sdram_heap->free;
        } else {
            // set up block in block
            block_t *free = (block_t*) (
                to_process_blocks[*to_process].sdram_base_address);
            free->free = NULL;
            free->next = NULL;

            // update next block
            free->next =
                (block_t*) (
                    to_process_blocks[*to_process].sdram_base_address
                    + to_process_blocks[*to_process].size
                    - sizeof(block_t));
            free->next->free = NULL;
            free->next->next = NULL;

            // update previous links
            previous->next = free;
            previous->free = free;
            previous_free->free = free;

            // update previous pointers
            previous = free->next;
            previous_free = free;

            log_debug(
                "next free is %x and -> next is %x and its next is %x "
                "and its free is %x with size %u",
                free, free->next, free->next->next, free->next->free,
                (uchar*) free->next - (uchar*) free);
        }
        // update pointers
        *to_process += 1;
    }

    // update last
    stolen_sdram_heap->last = previous;
    stolen_sdram_heap->last->free = NULL;
    stolen_sdram_heap->last->next = NULL;
}

//! \brief prints out the fake heap as if the spin1 alloc was operating over it
void print_free_sizes_in_heap(void){
    block_t *free_blk = stolen_sdram_heap->free;
    uint total_size = 0;
    uint index = 0;

    // traverse blocks till none more available
    while (free_blk) {
        uint size = (uchar*) free_blk->next - (uchar*) free_blk;
        log_debug(
            "free block %d has address %x and size of %d",
            index, free_blk, size);

        total_size += size;
        free_blk = free_blk->free;
        index += 1;
    }

    log_debug("total free size is %d", total_size);
}

//! \brief builds a new heap based off stolen sdram blocks from cores
//! synaptic matrix's. Needs to merge in the true sdram free heap, as
//! otherwise its impossible to free the block properly.
//! \param[in] sizes_region; the sdram address where the free regions exist
//! \return None
static inline bool platform_new_heap_creation(
        available_sdram_blocks *sizes_region) {
    // NOTE use if not trusting the heap
    //stolen_sdram_heap = sv->sdram_heap;
    // return true;

    // allocate blocks store for figuring out block order
    uint n_mallocs = available_mallocs(sv->sdram_heap);
    sdram_block *list_of_available_blocks = sark_alloc(
        n_mallocs * sizeof(sdram_block), 1);

    // if fail to alloc dtcm blow up
    if (list_of_available_blocks == NULL){
        return false;
    }

    // alloc space for a heap object (stealing from steal store if not by
    // normal means.
    stolen_sdram_heap =
        (heap_t*) sark_xalloc(sv->sdram_heap, MIN_SIZE_HEAP, 0, ALLOC_LOCK);
    if (stolen_sdram_heap == NULL){

        //check we can steal
        if (sizes_region->n_blocks == 0){
            log_error("cant find space for the heap");
            return false;
        }

        // deallocate 32 bytes from first handed down to be the heap object
        stolen_sdram_heap =
            (heap_t*) sizes_region->blocks[0].sdram_base_address;
        sizes_region->blocks[0].sdram_base_address += MIN_SIZE_HEAP;
        sizes_region->blocks[0].size -= MIN_SIZE_HEAP;
    }

    // determine how much spare space there is.
    stolen_sdram_heap->free_bytes = free_space_available(sizes_region);
    
    // go through true heap and allocate and add to end of list.
    bool success = add_heap_to_collection(list_of_available_blocks);
    if (!success){
        log_error("failed to add heap");
        return false;
    }

    // build the heap struct.
    make_heap_structure(sizes_region, n_mallocs, list_of_available_blocks);

    // free the allocated dtcm for the true alloc stuff.
    sark_free(list_of_available_blocks);

    // printer for sanity purposes
    print_free_sizes_in_heap();

    return true;
}

//! \brief allows a search of the SDRAM heap.
//! \param[in] bytes: the number of bytes to allocate.
//! \return: the address of the block of memory to utilise.
void * safe_sdram_malloc(uint bytes){
    // try SDRAM stolen from the cores synaptic matrix areas.
    //print_free_sizes_in_heap();
    void * p = sark_xalloc(stolen_sdram_heap, bytes, 0, ALLOC_LOCK);

    if (p == NULL) {
        log_error("Failed to malloc %u bytes.\n", bytes);
    }
    return p;
}

//! \brief allows a search of the 2 heaps available. (DTCM, stolen SDRAM)
//! \param[in] bytes: the number of bytes to allocate.
//! \return: the address of the block of memory to utilise.
static void * safe_malloc(uint bytes) {

    // try DTCM
    void *p = sark_alloc(bytes, 1);
    if (p != NULL) {
        return p;
    }
    return safe_sdram_malloc(bytes);
}

//! \brief locates the biggest block of available memory from the heaps
//! \return the biggest block size in the heaps.
static inline uint platform_max_available_block_size(void) {
    uint max_dtcm_block = sark_heap_max(sark.heap, ALLOC_LOCK);
    uint max_sdram_block = sark_heap_max(stolen_sdram_heap, ALLOC_LOCK);
    if (max_dtcm_block > max_sdram_block){
        return max_dtcm_block;
    } else {
        return max_sdram_block;
    }
}

//! \brief frees the sdram allocated from whatever heap it came from
//! \param[in] ptr: the address to free. could be DTCM or SDRAM
static void safe_x_free(void *ptr) {
    if ((int) ptr >= DTCM_BASE && (int) ptr <= DTCM_TOP) {
        sark_xfree(sark.heap, ptr, 0);
    } else {
        sark_xfree(stolen_sdram_heap, ptr, ALLOC_LOCK);
    }
}


#define MALLOC safe_malloc
#define FREE   safe_x_free
#define MALLOC_SDRAM safe_sdram_malloc


#endif  // __PLATFORM_H__

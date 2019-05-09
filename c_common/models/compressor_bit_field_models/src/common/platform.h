#ifndef __PLATFORM_H__
#define __PLATFORM_H__

#include <sark.h>
#include <common-typedefs.h>


//! a sdram block outside the heap
typedef struct sdram_block {
    // the base address of where the sdram block starts
    address_t sdram_base_address;

    // size of block in bytes
    int size;

} sdram_block;

//! the struct for holding host based sdram blocks outside the heap
typedef struct available_sdram_blocks {
    // the number of blocks of sdram which can be utilised outside of alloc
    int n_blocks;

    // VLA of sdram blocks
    sdram_block *blocks;
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
static inline bool platform_new_heap_update(address_t heap_location){
    //stolen_sdram_heap = sv->sdram_heap;
    //use(heap_location);
    stolen_sdram_heap = (heap_t*) heap_location;
    return true;
}

//! \brief count how much space available given expected block costs
static inline uint free_space_available(available_sdram_blocks *sizes_region){
    uint free = 0;
    for (int index =0; index < sizes_region->n_blocks; index++){
        free += sizes_region->blocks[index].size - sizeof(block_t);
    }
    return free;
}

//! \brief builds a new heap based off stolen sdram blocks from cores
//! synaptic matrix's. Needs to merge in the true sdram free heap, as
//! otherwise its impossible to free the block properly.
//! \param[in] sizes_region; the sdram address where the free regions exist
//! \return None
static inline bool platform_new_heap_creation(
        available_sdram_blocks *sizes_region) {
    // TODO hook removal here if we decide on this insanity
    //stolen_sdram_heap = sv->sdram_heap;
    //use(sizes_region);
    //return true;

    // allocate blocks store for figuring out block order
    int n_mallocs = available_mallocs(sv->sdram_heap);
    sdram_block *list_of_available_blocks = sark_alloc(
        n_mallocs * sizeof(sdram_block), 1);

    // if fail to alloc dtcm blow up
    if(list_of_available_blocks == NULL){
        return false;
    }

    // determine how much spare space there is.
    uint available_free_bytes = free_space_available(sizes_region);
    // adjust for fact we're allocating a heap in here somewhere
    available_free_bytes -= sizeof(heap_t);

    // go through true heap and allocate and add to end of list.
    int position = 0;

    // loop over the true heap and add accordingly.
    while(sv->sdram_heap->free != NULL){
        block_t *next_blk = sv->sdram_heap->free->next;

        // get next size minus the size it'll need to put in when alloc'ing
        int size = (next_blk - sv->sdram_heap->free) - sizeof(block_t);

        // make life easier by saying blocks have to be bigger than the heap.
        // so all spaces can be used for heaps
        if (size >= MIN_SIZE_HEAP){
            address_t block_address = sark_alloc(size, 1);
            list_of_available_blocks[position].sdram_base_address =
                block_address;
            list_of_available_blocks[position].size = size;
            available_free_bytes += size;
            position += 1;
        }
    }

    // generate position pointers
    int stolen_current_index = 0;
    int heap_current_index = 0;
    bool has_set_up_heap_struct = false;
    block_t *previous = NULL;

    // generate heap pointers
    while(stolen_current_index < sizes_region->n_blocks &&
            heap_current_index < n_mallocs){

        // build pointers to try to reduce code space
        int * to_process;
        sdram_block *to_process_blocks;

        // cast the two lists to figure next one
        uint top_stolen =
            (uint) sizes_region->blocks[
                stolen_current_index].sdram_base_address;
        uint top_true =
            (uint) list_of_available_blocks[
                heap_current_index].sdram_base_address;

        // determine which tracker to utilise
        if (top_stolen < top_true){
            to_process = &stolen_current_index;
            to_process_blocks = sizes_region->blocks;
        }
        else{
            to_process = &heap_current_index;
            to_process_blocks = list_of_available_blocks;
        }

        // if has not already set up the heap struct, set it up
        if (!has_set_up_heap_struct){
            // build new heap
            stolen_sdram_heap =
                (heap_t*) to_process_blocks[*to_process].sdram_base_address;

            // deallocate 32 bytes for the heap object
            to_process_blocks[*to_process].sdram_base_address += MIN_SIZE_HEAP;
            to_process_blocks[*to_process].size -= MIN_SIZE_HEAP;

            // set up stuff we can
            stolen_sdram_heap->free_bytes = available_free_bytes;
            stolen_sdram_heap->free =
                (block_t*) to_process_blocks[*to_process].sdram_base_address;
            stolen_sdram_heap->first = stolen_sdram_heap->free;

            // previous block in chain
            previous = stolen_sdram_heap->free;

            // set flag to not need to do this again
            has_set_up_heap_struct = true;
        }

        // set up block in block
        block_t *next = (block_t*) (
            to_process_blocks[*to_process].sdram_base_address +
            to_process_blocks[*to_process].size - sizeof(block_t));



        // update previous
        previous->next = next;
        previous->free =
            (block_t*) to_process_blocks[*to_process].sdram_base_address;
        previous = next;

        // update pointers
        *to_process += 1;

    }

    // free the allocated dtcm for the true alloc stuff.
    sark_free(list_of_available_blocks);

    return true;
}



//! \brief allows a search of the SDRAM heap.
//! \param[in] bytes: the number of bytes to allocate.
//! \return: the address of the block of memory to utilise.
static void * safe_sdram_malloc(uint bytes){
    // try SDRAM stolen from the cores synaptic matrix areas.
    void * p = sark_xalloc(stolen_sdram_heap, bytes, 0, ALLOC_LOCK);

    if (p == NULL) {
        //log_error("Failed to malloc %u bytes.\n", bytes);
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
    //return MAX(max_dtcm_block, max_sdram_block);
    if (max_dtcm_block > max_sdram_block){
        return max_dtcm_block;
    } else {
        return max_sdram_block;
    }
}

//! \brief frees the sdram allocated from whatever heap it came from
//! \param[in] ptr: the address to free. could be DTCM or SDRAM
static inline void safe_x_free(void *ptr) {
    if ((int) ptr >= DTCM_BASE && (int) ptr <= DTCM_TOP) {
        sark_xfree(sark.heap, ptr, 0);
    } else {
        sark_xfree(stolen_sdram_heap, ptr, ALLOC_LOCK);
    }
}

#ifdef PROFILED
    void profile_init();
    void *profiled_malloc(uint bytes);
    void profiled_free(void * ptr);

    #define MALLOC profiled_malloc
    #define FREE   profiled_free
#else
    #define MALLOC safe_malloc
    #define FREE   safe_x_free
    #define MALLOC_SDRAM safe_sdram_malloc
#endif

#endif  // __PLATFORM_H__

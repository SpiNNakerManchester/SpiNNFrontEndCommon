#ifndef __PLATFORM_H__
#define __PLATFORM_H__

#include <sark.h>
#include <common-typedefs.h>

//! a extra heap, that exploits sdram which can be easily regenerated.
static heap_t *stolen_sdram_heap = NULL;

//! \brief builds a new heap based off stolen sdram blocks from cores
//! synaptic matrix's. Needs to merge in the true sdram free heap, as
//! otherwise its impossible to free the block properly.
//! \param[in] sizes_region; the sdram address where the free regions exist
//! \return None
static inline void platform_new_heap_creation(address_t sizes_region) {
    // TODO hook removal here if we decide on this insanity
    stolen_sdram_heap = sv->sdram_heap;
    use(sizes_region);
}

//! \brief allows a search of the SDRAM heap.
//! \param[in] bytes: the number of bytes to allocate.
//! \return: the address of the block of memory to utilise.
static inline void * safe_sdram_malloc(uint bytes){
    // try SDRAM stolen from the cores synaptic matrix areas.
    void * p = sark_xalloc(stolen_sdram_heap, bytes, 0, ALLOC_LOCK);

    if (p == NULL) {
        //log_error("Failed to malloc %u bytes.\n", bytes);
    }
    return p;
}

//! \brief resets the heap so that it looks like it was before
static inline void platform_kill_fake_heap(void) {
    return;
}

//! \brief allows a search of the 2 heaps available. (DTCM, stolen SDRAM)
//! \param[in] bytes: the number of bytes to allocate.
//! \return: the address of the block of memory to utilise.
static inline void * safe_malloc(uint bytes) {

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

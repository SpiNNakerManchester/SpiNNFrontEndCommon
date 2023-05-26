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

//! \brief flag to help with debugging
bool to_print = false;

//! \brief use DTCM at all?
//! \details ONLY TURN THIS ON IF YOU'RE SURE STACK OVERFLOWS WILL NOT HAPPEN
bool use_dtcm = true;

//============================================================================

// ===========================================================================
// functions

void malloc_extras_turn_on_print(void) {
    to_print = true;
}

void malloc_extras_turn_off_print(void) {
    to_print = false;
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

void malloc_extras_free(void *ptr) {

    // if safe to free, free from the correct heap based off position.
    if ((int) ptr >= DTCM_BASE && (int) ptr <= DTCM_TOP) {
        if (to_print) {
            log_info("freeing 0x%08x from DTCM", ptr);
        }
        sark_xfree(sark.heap, ptr, ALLOC_LOCK);
    } else {
        if (to_print) {
            log_info("freeing 0x%08x from SDRAM", ptr);
        }
        sark_xfree(sv->sdram_heap, ptr, ALLOC_LOCK);
    }
}

void *malloc_extras_sdram_malloc(uint bytes) {

    // try SDRAM stolen from the cores synaptic matrix areas.
    void *p = sark_xalloc(sv->sdram_heap, bytes, 0, ALLOC_LOCK);

    if (p == NULL) {
        log_error("Failed to malloc %u bytes.\n", bytes);
    }
    if (to_print) {
        log_info("Allocated %u bytes from SDRAM at 0x%08x", bytes, p);
    }

    return p;
}

void *malloc_extras_malloc(uint bytes) {

    // try DTCM if allowed (not safe if overused, due to stack overflows)
    void *p = NULL;
    if (use_dtcm) {
        p = sark_alloc(bytes, 1);

        // if DTCM failed to malloc, go to SDRAM.
        if (p == NULL) {
           p = malloc_extras_sdram_malloc(bytes);
        } else if (to_print) {
            log_info("Allocated %u bytes from DTCM at 0x%08x", bytes, p);
        }
    // only use SDRAM. (safer to avoid stack overflows)
    } else {
        p = malloc_extras_sdram_malloc(bytes);
    }

    // if no safety, the point is the point used by the application code.
    return p;
}

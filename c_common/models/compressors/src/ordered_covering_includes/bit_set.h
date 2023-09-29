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

//! \file
//! \brief Sets of bits.
#ifndef __BIT_SET_H__
#define __BIT_SET_H__

// NOTE: THIS LOOKS AND ACTS LIKE A WRAPPER OVER WHAT SPINN_COMMON HAS ON
// BIT_FIELD.h. IS LEFT DUE TO THE AMOUNT THAT IS USED IN THE COMPRESSOR.
// DAMN WELL LOOKS LIKE A FILTER_INFO.h

#include <bit_field.h>
#include <stdint.h>
#include <malloc_extras.h>
#include "../common/constants.h"
#include <debug.h>

//! \brief wrapper over bitfield
typedef struct _bit_set_t {
    //! Keep track of members
    unsigned int count;

    //! Number of words in _data
    unsigned int n_words;

    //! Number of elements which may be in the set
    unsigned int n_elements;

    //! Pointer to data
    uint32_t *_data;
} bit_set_t;

//! \brief Empty a bitset entirely
//! \param[in] b: the bit set to clear bits
//! \return bool saying successfully cleared bit field
bool bit_set_clear(bit_set_t *b) {
    // Clear the data
    for (unsigned int i = 0; i < b->n_words; i++) {
        b->_data[i] = 0x0;
    }

    // Reset the count
    b->count = 0;
    return true;
}

//! \brief Create a new bitset
//! \param[in] b: the bitset to create
//! \param[in] length: the length of bits to make
//! \return whether the bitset was created
static inline bool bit_set_init(bit_set_t *b, unsigned int length) {
    // Malloc space for the data
    unsigned int n_words = length / BITS_IN_A_WORD;
    if (length % BITS_IN_A_WORD) {
        n_words++;
    }

    uint32_t *data = (uint32_t *) MALLOC(n_words * sizeof(uint32_t));
    if (data == NULL) {
        b->_data = NULL;
        b->n_elements = 0;
        b->n_words = 0;
        return false;
    }

    b->_data = data;
    b->n_words = n_words;
    b->n_elements = length;
    bit_set_clear(b);
    return true;
}

//! \brief Destroy a bitset
//! \param[in] b: the bitset to delete
static inline void bit_set_delete(bit_set_t *b) {
    // Free the storage
    FREE(b->_data);
    b->_data = NULL;
    b->n_elements = 0;
}

//! \brief Add an element to a bitset
//! \param[in] b: the bitset to add to
//! \param[in] i: the bit to set / add
//! \return whether the bit is added successfully
static inline bool bit_set_add(bit_set_t* b, unsigned int i) {
    if (b->n_elements <= i) {
        return false;
    }

    // Determine the word and bit
    unsigned int word = i / BITS_IN_A_WORD;
    unsigned int bit  = 1 << (i & 31);

    // Set the word and bit
    b->_data[word] |= bit;

    // Increment the count of set elements
    b->count++;
    return true;
}

//! \brief Test if an element is in a bitset
//! \param[in] b: the bitset to check
//! \param[in] i: the bit to check is set /added
//! \return whether the bit is set/added in the bitfield
static inline bool bit_set_contains(bit_set_t *b, unsigned int i) {
    if (b->n_elements <= i) {
        return false;
    }

    // Determine the word and bit
    unsigned int word = i / BITS_IN_A_WORD;
    uint32_t bit = 1 << (i & 31);
    return (bool) (b->_data[word] & bit);
}

//! \brief Remove an element from a bitset
//! \param[in] b: the bitset to remove/unset the bit from
//! \param[in] i: the bit to unset
//! \return whether unset succeeded
static inline bool bit_set_remove(bit_set_t *b, unsigned int i) {
    if (!bit_set_contains(b, i)) {
        return false;
    }
    // Determine the word and bit
    unsigned int word = i >> 5;
    unsigned int bit  = 1 << (i & 0x1f);

    // Decrement the count of set elements
    b->count--;

    // Unset the bit of the appropriate word
    b->_data[word] &= ~bit;
    return true;
}

//! \brief This function prints out an individual word of a bit_field,
//!     as a sequence of ones and zeros.
//! \param[in] e The word of a bit_field to be printed.
//! \param[in] offset: the offset in id
static inline void print_bit_field_entry_v2(uint32_t e, int offset) {
    for (counter_t i = 32 ; i > 0; i--) {
        log_debug("%d,%c", offset + i, ((e & 0x1) == 0) ? ' ' : '1');
        e >>= 1;
    }
}

//! \brief This function prints out an entire bit_field,
//!     as a sequence of ones and zeros.
//! \param[in] b The sequence of words representing a bit_field.
//! \param[in] s The size of the bit_field.
void print_bit_field_bits_v2(bit_field_t b, size_t s) {
    for (int i = s; i > 0; i--) {
	    print_bit_field_entry_v2(b[i], ((i - 1) * 32));
    }
}

//! \brief This function prints out an entire bit_field,
//!     as a sequence of ones and zeros.
//! \param[in] b The sequence of words representing a bit_field.
//! \param[in] s The size of the bit_field.
void print_bit_set_bits(bit_field_t b, int s) {
    for (int i = s; i > 0; i--) {
	    print_bit_field_entry_v2(b[i], ((i - 1) * BITS_IN_A_WORD));
    }
}

//! \brief prints a bit set
//! \param[in] b: the bitset to print
void print_bit_set(bit_set_t b) {
    print_bit_set_bits(b._data, b.n_words);
}

#endif  // __BIT_SET_H__

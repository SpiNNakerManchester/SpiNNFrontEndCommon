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

#ifndef __COMMON_HELPFUL_FUNCTIONS_H__
#define __COMMON_HELPFUL_FUNCTIONS_H__

#include <debug.h>

//! \brief This function prints out an individual word of a bit_field,
// as a sequence of ones and zeros.
//! \param[in] e The word of a bit_field to be printed.
//! \param[in] offset: the offset in id
static inline void print_bit_field_entry_v2(uint32_t e, int offset) {
    counter_t i = 32;

    for ( ; i > 0; i--) {
        log_debug("%d,%c", offset + i, ((e & 0x1) == 0) ? ' ' : '1');
        e >>= 1;
    }
}

//! \brief This function prints out an entire bit_field,
// as a sequence of ones and zeros.
//! \param[in] b The sequence of words representing a bit_field.
//! \param[in] s The size of the bit_field.
void print_bit_field_bits_v2(bit_field_t b, size_t s) {
    use(b);
    use(s);
    int i; //!< For indexing through the bit field

    for (i = s; i > 0; i--) {
	    print_bit_field_entry_v2(b[i], ((i - 1) * 32));
    }
}

#endif  // __COMMON_HELPFUL_FUNCTIONS_H__

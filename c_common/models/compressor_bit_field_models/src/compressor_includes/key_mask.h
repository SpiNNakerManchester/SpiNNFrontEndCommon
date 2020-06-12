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

//! \dir
//! \brief Support includes for the bitfield compressor
//! \file
//! \brief Operations on a ::key_mask_t
#ifndef __KEY_MASK_H__
#define __KEY_MASK_H__

#include <stdbool.h>
#include <stdint.h>
#include <debug.h>
#include "../common/compressor_sorter_structs.h"

//=============================================================================
//state for reduction in parameters being passed around

//! \brief Get a mask of the Xs in a key_mask
//! \param[in] km: the key mask to get as xs
//! \return a merged mask
static inline uint32_t key_mask_get_xs(key_mask_t km) {
    return ~km.key & ~km.mask;
}


//! \brief Get a count of the Xs in a key_mask
//! \param[in] km: the key mask struct to count
//! \return the number of bits set in the mask
static inline unsigned int key_mask_count_xs(key_mask_t km) {
    return __builtin_popcount(key_mask_get_xs(km));
}


//! \brief Determine if two key_masks would match any of the same keys
//! \param[in] a: key mask struct a
//! \param[in] b: key mask struct b
//! \return bool that says if these key masks intersect
static inline bool key_mask_intersect(key_mask_t a, key_mask_t b) {
    return (a.key & b.mask) == (b.key & a.mask);
}

//! \brief Generate a new key-mask which is a combination of two other key_masks
//! \details `c := a | b`
//! \param[in] a: the first key mask struct
//! \param[in] b: the second key mask struct
//! \return the merged key mask struct
static inline key_mask_t key_mask_merge(key_mask_t a, key_mask_t b) {
    uint32_t new_xs = ~(a.key ^ b.key);
    key_mask_t c;
    c.mask = a.mask & b.mask & new_xs;
    c.key = (a.key | b.key) & c.mask;

    return c;
}

#endif  // __KEY_MASK_H__

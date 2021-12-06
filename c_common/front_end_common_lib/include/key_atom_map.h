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

//! \file
//! \brief Data structures describing a key-to-atom mapping
#ifndef __KEY_ATOM_MAP_H__
#define __KEY_ATOM_MAP_H__

//! \brief A pair containing a multicast key and the number of contiguous
//!     atoms (neurons, etc.) to which it applies.
typedef struct key_atom_pair_t {
    //! Multicast key.
    uint32_t key;
    //! Number of atoms for the key.
    uint32_t n_atoms;
} key_atom_pair_t;

//! \brief A mapping from multicast keys to sections of a contiguous range of
//!     atoms (neurons, etc.)
typedef struct key_atom_data_t {
    //! How many key-atom maps are present?
    uint32_t n_pairs;
    //! The array of mappings.
    key_atom_pair_t pairs[];
} key_atom_data_t;

#endif  // __KEY_ATOM_MAP_H__

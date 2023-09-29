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
    //! Core shift
    uint32_t core_shift: 5;
    //! Number of atoms per core
    uint32_t n_atoms_per_core: 27;
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

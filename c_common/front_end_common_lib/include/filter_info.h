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
//! \brief Data structures used by code that needs to be aware of bitfield
//!     filtering
#ifndef __FILTER_INFO_H__
#define __FILTER_INFO_H__

#include <bit_field.h>

//! \brief Describes a single filter, which is a wrapper for bit_field_t
typedef struct filter_info_t {
    //! Bit field master population key
    uint32_t key;
    //! Flag to indicate if the filter has been merged
    uint32_t merged: 1;
    //! Flag to indicate if the filter is redundant
    uint32_t all_ones: 1;
    //! Number of atoms (=valid bits) in the bitfield
    uint32_t n_atoms: 30;
    //! The shift to apply to the core to add the core to the key (0-31)
    uint32_t core_shift: 5;
    //! The number of atoms per core (0 if not used)
    uint32_t n_atoms_per_core:27;
    //! The words of the bitfield
    bit_field_t data;
} filter_info_t;

//! \brief The contents of the bitfield region in SDRAM
typedef struct filter_region_t {
    //! Total number of filters
    uint32_t n_filters;
    //! The filters themselves, ordered by key
    filter_info_t filters[];
} filter_region_t;

//! \brief A core and an atom for counting
struct core_atom {
    uint32_t core;
    uint32_t atom;
};

//! \brief Move to the next atom, updating the core as needed
//! \param[in] filter The filter being examined
//! \param[in/out] core_atom The counter to update
static inline void next_core_atom(filter_info_t *filter, struct core_atom *core_atom) {
    core_atom->atom++;
    // If n_atoms_per_core is 0 (i.e. disabled) this will never match, so the
    // atom will be global
    if (core_atom->atom == filter->n_atoms_per_core) {
        core_atom->core++;
        core_atom->atom = 0;
    }
}

//! \brief Get the key for a given core-atom pair
//! \param[in] filter The filter to get the key from
//! \param[in] core_atom The core-atom pair to find the key of
//! \return The key
static inline uint32_t get_bf_key(filter_info_t *filter, struct core_atom *core_atom) {
    // Note if n_atoms_per_core is 0, core will be 0, and atom will just be the
    // global atom
    return filter->key + (core_atom->core << filter->core_shift) + core_atom->atom;
}

//! \brief Get the global atom from the core-atom data
//! \param[in] filter The filter to get the details from
//! \param[in] core_atom The core-atom pair to work out the global atom from
//! \return The global atom number
static inline uint32_t global_atom(filter_info_t *filter, struct core_atom *core_atom) {
    return (filter->n_atoms_per_core * core_atom->core) + core_atom->atom;
}

#endif  // __FILTER_INFO_H__

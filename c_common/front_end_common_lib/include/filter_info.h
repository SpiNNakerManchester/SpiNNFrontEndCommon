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

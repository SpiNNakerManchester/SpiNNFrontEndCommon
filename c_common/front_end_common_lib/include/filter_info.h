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
    uint32_t redundant: 1;
    //! Number of atoms (=valid bits) in the bitfield
    uint32_t n_atoms: 30;
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

#endif  // __FILTER_INFO_H__

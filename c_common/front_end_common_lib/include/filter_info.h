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

#ifndef __FILTER_INFO_H__

//! \brief the elements in a filter info (bitfield wrapper)
typedef struct filter_info_t{
    // bit field master pop key
    uint32_t key;
    // n words representing the bitfield
    uint32_t n_atoms;
    // the words of the bitfield
    bit_field_t data;
} filter_info_t;

//! \brief the elements in the bitfield region
typedef struct filter_region_t{
    // how many filters have been merged into routing tables
    int n_merged_filters;
    // total number of filters with redundant packets. (merged or not)
    int n_redundancy_filters;
    // total number of filters including with and without redundancy
    int n_filters;
    // the filters
    filter_info_t filters[];
} filter_region_t;

#define __FILTER_INFO_H__
#endif  // __FILTER_INFO_H__

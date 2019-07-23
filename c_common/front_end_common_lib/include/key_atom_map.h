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

#ifndef __KEY_ATOM_MAP_H__

//! \brief struct for key and atoms
typedef struct key_atom_pair_t{
    // key
    uint32_t key;
    // n atoms
    int n_atoms;
} key_atom_pair_t;

//! \brief key atom map struct
typedef struct key_atom_data_t{
    // how many key atom maps
    int n_pairs;
    // the list of maps
    key_atom_pair_t pairs[];
} key_atom_data_t;

#define __KEY_ATOM_MAP_H__
#endif  // __KEY_ATOM_MAP_H__

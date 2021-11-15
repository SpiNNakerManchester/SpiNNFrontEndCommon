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
//! \brief API for routing table minimisation

#ifndef __MINIMISE_H__
#define __MINIMISE_H__

//! \brief Apply the ordered covering algorithm to a routing table
//! \details Minimise the table until either the table is shorter than the
//!     target length or no more merges are possible.
//! \param[in] target_length: The length to reach
//! \param[out] failed_by_malloc: Flag stating that it failed due to malloc
//! \param[out] stop_compressing: Variable saying if the compressor should stop
//!    and return false; _set by interrupt_ DURING the run of this method!
//! \return Whether successful or not.
bool minimise_run(
        int target_length, bool *failed_by_malloc,
        volatile bool *stop_compressing);

//! \brief Whether this is a standalone compressor.
//! \details Mainly used to change logging
//! \return Whether this is a standalone compressor
bool standalone(void);

#endif  // __MINIMISE_H__

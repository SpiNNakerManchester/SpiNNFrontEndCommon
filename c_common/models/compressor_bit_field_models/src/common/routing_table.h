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
//! \brief Utilities for a single routing table
#ifndef __ROUTING_TABLE_H__
#define __ROUTING_TABLE_H__

//=============================================================================

//! \brief Gets a pointer to where this entry is stored
//! \details Will not check if there is an entry with this id but will RTE if
//!     the id is too large
//! \param[in] entry_id_to_find: Id of entry to find pointer to
//! \return pointer to the entry's location
entry_t* routing_table_get_entry(uint32_t entry_id_to_find);

//! \brief Get the number of entries in the routing table
//! \return number of appended entries.
int routing_table_get_n_entries(void);

//! \brief updates table stores accordingly.
//!
//! will RTE if this causes the total entries to become negative.
//! \param[in] size_to_remove: the amount of size to remove from the table sets
void routing_table_remove_from_size(int size_to_remove);

#endif  // __ROUTING_TABLE_H__

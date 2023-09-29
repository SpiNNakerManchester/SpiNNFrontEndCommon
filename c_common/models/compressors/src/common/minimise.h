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

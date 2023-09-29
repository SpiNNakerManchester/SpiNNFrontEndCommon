/*
 * Copyright (c) 2013 The University of Manchester
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

/*
 * common-typedefs.h
 *
 *
 *  SUMMARY
 *    Data type definitions for SpiNNaker Neuron-modelling
 *
 *  AUTHOR
 *    Dave Lester (david.r.lester@manchester.ac.uk)
 *
 *  COPYRIGHT
 *    Copyright (c) Dave Lester and The University of Manchester, 2013.
 *    All rights reserved.
 *    SpiNNaker Project
 *    Advanced Processor Technologies Group
 *    School of Computer Science
 *    The University of Manchester
 *    Manchester M13 9PL, UK
 *
 *  DESCRIPTION
 *
 *
 *  CREATION DATE
 *    10 December, 2013
 *
 *  HISTORY
 *
 *  DETAILS
 *    Created on       : 10 December 2013
 *    Version          : $Revision$
 *    Last modified on : $Date$
 *    Last modified by : $Author$
 *    $Id$
 *
 *    $Log$
 *
 */

//! \file
//!
//! \brief Data type definitions for SpiNNaker Neuron-modelling.

#ifndef __COMMON_TYPEDEFS_H__
#define __COMMON_TYPEDEFS_H__

#include <stdint.h>
#include <stdbool.h>
#include <stdfix.h>
#include "stdfix-full-iso.h"

// Pseudo-function Declarations

//! \brief This can be used to silence gcc's "-Wall -Wextra"
//! warnings about failure to use function arguments.
//!
//! Obviously you'll only be using this during debug, for unused
//! arguments of callback functions, or where conditional compilation
//! means that the accessor functions return a constant
//!
//! \param[in] x: The variable that is "used". Not safe with floating point!

#ifndef use
#define use(x) do {} while ((x)!=(x))
#endif


// Define int/uint helper macros to create the correct
// type names for int/uint of a particular size.
//
// This requires an extra level of macro call to "stringify"
// the result.

#define __int_helper(b) int ## b ## _t
#define __uint_helper(b) uint ## b ## _t
//! \brief Yields the name of a signed integer type of a particular width.
//! \param[in] b: The width of type; only 8, 16, 32 and 64 expected to work.
//! \return The type name
#define __int_t(b) __int_helper(b)
//! \brief Yields the name of an unsigned integer type of a particular width.
//! \param[in] b: The width of type; only 8, 16, 32 and 64 expected to work.
//! \return The type name
#define __uint_t(b) __uint_helper(b)

// Give meaningful names to the common types.
// (checking that they haven't already been declared.)

#ifndef __SIZE_T__
//! \brief An unsigned integer used for the size of objects.
typedef uint32_t size_t;
#define __SIZE_T__
#endif /*__SIZE_T__*/

#ifndef __INDEX_T__
//! \brief An unsigned integer used as an index.
typedef uint32_t index_t;
#define __INDEX_T__
#endif /*__INDEX_T__*/

#ifndef __COUNTER_T__
//! \brief An unsigned integer used as a counter or iterator.
typedef uint32_t counter_t;
#define __COUNTER_T__
#endif /*__COUNTER_T__*/

#ifndef __TIMER_T__
//! \brief An unsigned integer used to track the simulation time.
typedef uint32_t timer_t;
#define __TIMER_T__
#endif /*__TIMER_T__*/

#ifndef __ADDRESS_T__
//! \brief A generic pointer to a word.
typedef uint32_t* address_t;
#define __ADDRESS_T__
#endif /*__ADDRESS_T__*/

#endif /* __COMMON_TYPEDEFS_H__ */

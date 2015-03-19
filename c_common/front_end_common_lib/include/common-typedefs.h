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
 * *  DETAILS
 *    Created on       : 10 December 2013
 *    Version          : $Revision$
 *    Last modified on : $Date$
 *    Last modified by : $Author$
 *    $Id$
 *
 *    $Log$
 *
 */

#ifndef __COMMON_TYPEDEFS_H__
#define __COMMON_TYPEDEFS_H__

#include <stdint.h>
#include <stdbool.h>
#include <stdfix.h>
#include "stdfix-full-iso.h"

// Pseudo-function Declarations

// The following can be used to silence gcc's "-Wall -Wextra"
// warnings about failure to use function arguments.
//
// Obviously you'll only be using this during debug, for unused
// arguments of callback functions, or where conditional compilation
// means that the accessor functions return a constant

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
#define __int_t(b) __int_helper(b)
#define __uint_t(b) __uint_helper(b)

// Give meaningful names to the common types.
// (checking that they haven't already been declared.)

#ifndef __SIZE_T__
typedef uint32_t size_t;
#define __SIZE_T__
#endif /*__SIZE_T__*/

#ifndef __INDEX_T__
typedef uint32_t index_t;
#define __INDEX_T__
#endif /*__INDEX_T__*/

#ifndef __COUNTER_T__
typedef uint32_t counter_t;
#define __COUNTER_T__
#endif /*__COUNTER_T__*/

#ifndef __TIMER_T__
typedef uint32_t timer_t;
#define __TIMER_T__
#endif /*__TIMER_T__*/

#ifndef __ADDRESS_T__
typedef uint32_t* address_t;
#define __ADDRESS_T__
#endif /*__ADDRESS_T__*/

#endif /* __COMMON_TYPEDEFS_H__ */

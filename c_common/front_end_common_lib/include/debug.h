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

/*! \file
 *
 *  \brief SpiNNaker debug header file
 *
 *  \author
 *    Dave Lester (david.r.lester@manchester.ac.uk)
 *
 *  \copyright
 *    Copyright (c) Dave Lester and The University of Manchester, 2013.
 *    All rights reserved.
 *    SpiNNaker Project
 *    Advanced Processor Technologies Group
 *    School of Computer Science
 *    The University of Manchester
 *    Manchester M13 9PL, UK
 *
 *  \date 12 December, 2013
 *
 *  # ORIGINAL DETAILS
 *
 *      Created on       : 12 December 2013
 *      Version          : $Revision$
 *      Last modified on : $Date$
 *      Last modified by : $Author$
 *      $Id$
 *
 *  # DESCRIPTION
 *
 *  A header file that can be used to incorporate and control debug information.
 *  It is switched ON by default; to switch OFF, the code is compiled with
 *
 *      -DPRODUCTION_CODE
 *
 *  or
 *
 *      -DNDEBUG
 *
 *  By default it is used for SpiNNaker ARM code; it can also be used in
 *  host-side C, by compiling with -DDEBUG_ON_HOST
 *
 *  # EXAMPLES
 *
 *  To use, you must `hash-include' debug.h:
 *
 *  Logging errors, warnings and info:
 *
 *      log_error(17, "error");                    // not the most useful message..
 *      log_warning(0, "variable x = %8x", 0xFF);  // variable printing
 *      log_info("function f entered");            // trace
 *
 */

#ifndef __DEBUG_H__
#define __DEBUG_H__

#include <stdint.h>
#include "spin-print.h"
#include <assert.h>

//! \brief This function logs errors. Errors usually indicate a serious fault
//! in the program, and that it is about to terminate abnormally (RTE).
//!
//! Calls to this function are rewritten during the build process to be calls
//! to log_mini_error(); the rewrite also encodes the message so that it is
//! handled more efficiently by the binary deployed to SpiNNaker.
//!
//! \param[in] message: The user-defined part of the error message.
extern void log_error(const char *message, ...);

//! \brief This function logs warnings.
//!
//! Calls to this function are rewritten during the build process to be calls
//! to log_mini_warning(); the rewrite also encodes the message so that it is
//! handled more efficiently by the binary deployed to SpiNNaker.
//!
//! \param[in] message: The user-defined part of the error message.
extern void log_warning(const char *message, ...);

//! \brief This function logs informational messages. This is the lowest level
//!        of message normally printed.
//!
//! Calls to this function are rewritten during the build process to be calls
//! to log_mini_info(); the rewrite also encodes the message so that it is
//! handled more efficiently by the binary deployed to SpiNNaker.
//!
//! \param[in] message: The user-defined part of the error message.
extern void log_info(const char *message, ...);

//! \brief This function logs debugging messages. This level of message is
//! normally not printed except when the binary is built in debug mode
//!
//! Calls to this function are rewritten during the build process to be calls
//! to log_mini_debug(); the rewrite also encodes the message so that it is
//! handled more efficiently by the binary deployed to SpiNNaker.
//!
//! \param[in] message: The user-defined part of the error message.
extern void log_debug(const char *message, ...);

//! \brief Type-pun a float as a 32-bit unsigned integer.
//!
//! Defeats unwanted casting.
//!
//! \param[in] f The floating point number
//! \return The integer that is the bits of the float
static inline uint32_t float_to_int(float f) {
    union {
        float f;
        uint32_t i;
    } dat;

    dat.f = f;
    return dat.i;
}

typedef struct {
    uint32_t lower;
    uint32_t upper;
} __upper_lower_t;

//! \brief Type-pun the lower 32 bits of a double as a 32-bit unsigned integer.
//!
//! Defeats unwanted casting.
//!
//! \param[in] d The floating point number
//! \return The integer that is the lower bits of the double
static inline uint32_t double_to_lower(double d) {
    union {
        double d;
        __upper_lower_t ints;
    } dat;

    dat.d = d;
    return dat.ints.lower;
}

//! \brief Type-pun the higher 32 bits of a double as a 32-bit unsigned integer.
//!
//! Defeats unwanted casting.
//!
//! \param[in] d The floating point number
//! \return The integer that is the higher bits of the double
static inline uint32_t double_to_upper(double d) {
    union {
        double d;
        __upper_lower_t ints;
    } dat;

    dat.d = d;
    return dat.ints.upper;
}

//! \brief This macro prints a debug message if level is less than or equal
//!        to the LOG_LEVEL
//!
//! This is the actual logging implementation, though the core of it just
//! delegates to the IOBUF system.
//!
//! \param[in] level The level of the messsage
//! \param[in] message The user-defined part of the debug message.
#define __log_mini(level, message, ...) \
    do {                                                  \
	    if (level <= LOG_LEVEL) {                         \
	        uint _debug_cpsr = spin1_int_disable();       \
	        fprintf(stderr, message "\n", ##__VA_ARGS__); \
	        spin1_mode_restore(_debug_cpsr);              \
	    }                                                 \
    } while (0)

//! \brief This macro logs errors. Do not call directly!
//! \param[in] message The user-defined part of the error message.
#define log_mini_error(message, ...) \
    __log_mini(LOG_ERROR, message, ##__VA_ARGS__)

//! \brief This macro logs warnings. Do not call directly!
//! \param[in] message The user-defined part of the error message.
#define log_mini_warning(message, ...) \
    __log_mini(LOG_WARNING, message, ##__VA_ARGS__)

//! \brief This macro logs information. Do not call directly!
//! \param[in] message The user-defined part of the error message.
#define log_mini_info(message, ...) \
    __log_mini(LOG_INFO, message, ##__VA_ARGS__)

//! \brief This macro logs debug messages. Do not call directly!
//! \param[in] message The user-defined part of the error message.
#define log_mini_debug(message, ...) \
    __log_mini(LOG_DEBUG, message, ##__VA_ARGS__)

#endif /* __DEBUG_H__ */

/*
 * Copyright (c) 2013-2019 The University of Manchester
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
 *  DETAILS
 *    Created on       : 12 December 2013
 *    Version          : $Revision$
 *    Last modified on : $Date$
 *    Last modified by : $Author$
 *    $Id$
 *
 *  DESCRIPTION
 *    A header file that can be used to incorporate and control debug information.
 *    It is switched ON by default; to switch OFF, the code is compiled with
 *      -DPRODUCTION_CODE
 *    or
 *      -DNDEBUG
 *
 *    By default it is used for SpiNNaker ARM code; it can also be used in
 *    host-side C, by compiling with -DDEBUG_ON_HOST
 *
 *  EXAMPLES
 *
 *    To use, you must `hash-include' debug.h:
 *
 *    Logging errors, warnings and info:
 *
 *      log_error(17, "error");                    // not the most useful message..
 *      log_warning(0, "variable x = %8x", 0xFF);  // variable printing
 *      log_info("function f entered");            // trace
 *
 */

#ifndef __DEBUG_H__
#define __DEBUG_H__

#include "spin-print.h"
#include <assert.h>

//! \brief This macro prints a debug message if level is less than or equal
//!        to the LOG_LEVEL
//! \param[in] level The level of the messsage
//! \param[in] message The user-defined part of the debug message.
#define __log_mini(level, message, ...) \
    do {                                                  \
	    if (level <= LOG_LEVEL) {                         \
	        fprintf(stderr, message "\n", ##__VA_ARGS__); \
	    }                                                 \
    } while (0)

//! \brief This macro logs errors.
//! \param[in] message The user-defined part of the error message.
#define log_mini_error(message, ...) \
    __log_mini(LOG_ERROR, message, ##__VA_ARGS__)

//! \brief This macro logs warnings.
//! \param[in] message The user-defined part of the error message.
#define log_mini_warning(message, ...) \
    __log_mini(LOG_WARNING, message, ##__VA_ARGS__)

//! \brief This macro logs information.
//! \param[in] message The user-defined part of the error message.
#define log_mini_info(message, ...) \
    __log_mini(LOG_INFO, message, ##__VA_ARGS__)

//! \brief This macro logs debug messages.
//! \param[in] message The user-defined part of the error message.
#define log_mini_debug(message, ...) \
    __log_mini(LOG_DEBUG, message, ##__VA_ARGS__)

#endif /* __DEBUG_H__ */

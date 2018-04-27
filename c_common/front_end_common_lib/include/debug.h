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
 *    Assertions:
 *
 *      assert(0.0 < c && c < 1.0);                // assertion checking
 *
 *    Logging errors, warnings and info:
 *
 *      log_error(17, "error");                    // not the most useful message..
 *      log_warning(0, "variable x = %8x", 0xFF);  // variable printing
 *      log_info("function f entered");            // trace
 *
 *    Checking:
 *
 *      check(1==1, "1 !=1 !!!!!!");               // assertion with message
 *      xp = malloc(n); check_memory(xp);          // checks malloc is non-null
 *
 *    Sentinels:
 *
 *      switch(n) {
 *      ...
 *      default: sentinel("switch: out of range"); // used for control flow checks
 *      .... }
 *
 *    SpiNNaker memory checking:
 *
 *      If we are running on spinnaker hardware, we have the following
 *      additional checks available:
 *
 *      check_itcm(addr);
 *      check_dtcm(addr);
 *      check_sysram(addr);
 *      check_sdram(addr);
 *
 *    Controlling the volume of logging information:
 *
 *      -DNO_DEBUG_INFO            Switches OFF the [INFO] information
 *      -D'DEBUG_LOG(n)=(n>10)'    Switches OFF [ERROR]s with number less than or equal 10
 *      -D'DEBUG_WARN(n)=(n>5)'    Switches OFF [WARNING]s with number less than or equal 5
 *
 *    By default all information is printed.
 *
 *    There is no way to switch off [ASSERT]s except by using either of the
 *    compilation flags:
 *
 *      -DPRODUCTION_CODE or -DNDEBUG
 */

#ifndef __DEBUG_H__
#define __DEBUG_H__

#include "spin-print.h"

//! \brief This macro is intended to mimic the behaviour of 'C's exit
//! system call.
#define abort(n)	do { exit(n); } while (0)

//! \brief The log level for errors
#define LOG_ERROR 10

//! \brief The log level for warnings
#define LOG_WARNING 20

//! \brief The log level for information
#define LOG_INFO 30

//! \brief The log level for debugging
#define LOG_DEBUG 40

// Define the log level if not already defined
#ifndef LOG_LEVEL
#if defined(PRODUCTION_CODE) || defined(NDEBUG)
#define LOG_LEVEL LOG_INFO
#else // PRODUCTION_CODE
#define LOG_LEVEL LOG_DEBUG
#endif // PRODUCTION_CODE
#endif // LOG_LEVEL


//! \brief This macro prints a debug message if level is less than or equal
//!        to the LOG_LEVEL
//! \param[in] level The level of the messsage
//! \param[in] message The user-defined part of the debug message.
#define __log_mini(level, message, ...) \
    do {							\
	if (level <= LOG_LEVEL) {				\
	    fprintf(stderr, message "\n", ##__VA_ARGS__);	\
	} 							\
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

#if !(defined(PRODUCTION_CODE) || defined(NDEBUG))

//! \brief This macro prints out a check message to the log file.
//! \param[in] condition The condition being tested.
//! \param[in] message The message to be printed if the condition is false
#define check(condition, message, ...) \
    do {								\
        if (!(condition)) {						\
            __log(LOG_DEBUG, "[CHECK]    ", message, ##__VA_ARGS__);	\
        } 								\
    } while (0)

//! \brief This macro prints out a sentinel message to the log file and aborts
//! \param[in] message The message to be printed if execution reaches this point
#define sentinel(message, ...) \
    do {								\
	__log(LOG_DEBUG, "[SENTINEL] ", message, ##__VA_ARGS__);	\
	abort(0);							\
    } while (0)

//! \brief This macro performs an assertion check on a condition and aborts if
//!        the condition is not met
//! \param[in] assertion The condition being tested.
#define assert(assertion) \
    do {								\
        if (!(assertion)) {						\
            __log(LOG_DEBUG, "[ASSERT]   ", "assertion check fails!");	\
            abort(0);							\
        }								\
    } while (0)

//! \brief This macro performs an assertion check on a condition and aborts if
//!        the condition is not met
//! \param[in] assertion The condition being tested.
//! \param[in] message The message to be printed if the condition is false
#define assert_info(assertion, message, ...) \
    do {                                                                \
        if (!(assertion)) {                                             \
            __log(LOG_DEBUG, "[ASSERT]   ", message, ##__VA_ARGS__);    \
            abort(0);                                                   \
        }                                                               \
    } while (0)

#else  /* PRODUCTION_CODE */
#define check(a, s, ...)	skip()
#define sentinel(s, ...)	skip()
#define assert(a)		skip()
#define assert_info(a, m, ...)	skip()
#endif /* PRODUCTION_CODE */

//! \brief This function returns the unsigned integer associated with a
//! pointer address.
//! \param[in] ptr The pointer whose address is required.
//! \return The value as an unsigned integer.
static inline unsigned int __addr__(void* ptr)
{
    return (unsigned int) ptr;
}

//! \brief This macro tests whether a pointer returned by malloc is null.
//! \param[in] a The address returned by malloc.
#define check_memory(a)		check((a), "Out of memory")

#ifndef DEBUG_ON_HOST
//! \brief This macro tests whether a pointer's address lies in itcm.
//! \param[in] a The pointer.
#define check_itcm(a) \
    check((ITCM_BASE   <= __addr__(a) && __addr__(a) < ITCM_TOP),       \
          "%x is not in ITCM", (a))

//! \brief This macro tests whether a pointer's address lies in dtcm.
//! \param[in] a The pointer.
#define check_dtcm(a) \
    check((DTCM_BASE   <= __addr__(a) && __addr__(a) < DTCM_TOP),       \
          "%x is not in DTCM", (a))

//! \brief This macro tests whether a pointer's address lies in sysram.
//! \param[in] a The pointer.
#define check_sysram(a) \
    check((SYSRAM_BASE <= __addr__(a) && __addr__(a) < SYSRAM_TOP),     \
          "%x is not in sysRAM", (a))

//! \brief This macro tests whether a pointer's address lies in sdram.
//! \param[in] a The pointer.
#define check_sdram(a) \
    check((SDRAM_BASE  <= __addr__(a) && __addr__(a) < SDRAM_TOP),      \
          "%x is not in sdram", (a))

#else  /* DEBUG_ON_HOST */
#define check_itcm(a)		skip()
#define check_dtcm(a)		skip()
#define check_sysram(a)		skip()
#define check_sdram(a)		skip()
#endif /* DEBUG_ON_HOST */

#endif /* __DEBUG_H__ */

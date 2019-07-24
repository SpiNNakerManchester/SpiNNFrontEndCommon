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

#ifndef __CONSTANTS_H__
#define __CONSTANTS_H__

//! max length of the router table entries
#define TARGET_LENGTH 1023

//! \brief timeout on attempts to send sdp message
#define _SDP_TIMEOUT 100

//! random port as 0 is in use by scamp/sark
#define RANDOM_PORT 4

//! word to byte multiplier
#define WORD_TO_BYTE_MULTIPLIER 4

//! flag for not requiring a reply
#define REPLY_NOT_EXPECTED 0x07

//! bits in a word
#define BITS_IN_A_WORD 32

//! enum for the different states to report through the user1 address.
typedef enum exit_states_for_user_one {
    EXITED_CLEANLY = 0, EXIT_FAIL = 1, EXIT_MALLOC = 2, EXIT_SWERR = 3
} exit_states_for_user_one;

#endif  // __CONSTANTS_H__

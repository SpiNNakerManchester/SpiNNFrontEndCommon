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

//! \dir
//! \brief Common files for sorter and compressor
//! \file
//! \brief General constants
#ifndef __CONSTANTS_H__
#define __CONSTANTS_H__

//! max number of processors on chip used for app purposes
#define MAX_PROCESSORS  18

//! max length of the router table entries
#define TARGET_LENGTH   1023

//! \brief timeout on attempts to send sdp message
#define _SDP_TIMEOUT    100

//! random port as 0 is in use by scamp/sark
#define RANDOM_PORT     4

//! word to byte multiplier
#define WORD_TO_BYTE_MULTIPLIER 4

//! SDP flag for not requiring a reply
#define REPLY_NOT_EXPECTED      0x07

//! bits in a word
#define BITS_IN_A_WORD  32

//! flag saying there is no valid result for a given search (
//! locate processor, locate midpoint)
#define FAILED_TO_FIND  -1

//! \brief move for processor id in the circular queue
#define CORE_MOVE       16

//! \brief mask to get the finished state
#define FINISHED_STATE_MASK     0x0000FFFF

//! how many tables the uncompressed router table entries is
#define N_UNCOMPRESSED_TABLE    1

//! \brief number of bitfields that no bitfields run needs
#define NO_BIT_FIELDS   0

#endif  // __CONSTANTS_H__

# Copyright (c) 2017 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Constants used by the Data Structure Generator (DSG)
and the Specification Executor.
"""
import numpy

# MAGIC Numbers:
#: Data spec magic number.
#DSG_MAGIC_NUM = 0x5B7CA17E

#: Application data magic number.
APPDATA_MAGIC_NUM = 0xAD130AD6

#: Version of the file produced by the DSE.
DSE_VERSION = 0x00010000

# DSG Arrays and tables sizes:
#: Maximum number of registers in DSG virtual machine.
#MAX_REGISTERS = 16
#: Maximum number of memory regions in DSG virtual machine.
MAX_MEM_REGIONS = 32
#: Maximum number of structure slots in DSG virtual machine.
#MAX_STRUCT_SLOTS = 16
#: Maximum number of packing specification slots in DSG virtual machine.
#MAX_PACKSPEC_SLOTS = 16
#: Maximum number of functions in DSG virtual machine.
#MAX_CONSTRUCTORS = 16
#: Maximum number of parameter lists in DSG virtual machine.
#MAX_PARAM_LISTS = 16
#: Maximum number of random number generators in DSG virtual machine.
#MAX_RNGS = 16
#: Maximum number of random distributions in DSG virtual machine.
#MAX_RANDOM_DISTS = 16

# conversion from words to bytes
BYTES_PER_WORD = 4

#: Size of header of data spec pointer table produced by DSE, in bytes.
#: Note that the header consists of 2 uint32_t variables
#: (magic_number, version)
APP_PTR_TABLE_HEADER_BYTE_SIZE = 2 * BYTES_PER_WORD
#: Size of a region description in the pointer table.
#: Note that the description consists of a pointer and 2 uint32_t variables:
#: (pointer, checksum, n_words)
APP_PTR_TABLE_REGION_BYTE_SIZE = 3 * BYTES_PER_WORD
#: Size of data spec pointer table produced by DSE, in bytes.
APP_PTR_TABLE_BYTE_SIZE = (
    APP_PTR_TABLE_HEADER_BYTE_SIZE +
    (MAX_MEM_REGIONS * APP_PTR_TABLE_REGION_BYTE_SIZE))

# Constants used by DSG command encoding; not relevant outside
#LEN1 = 0
#LEN2 = 1
#LEN3 = 2

# Yes, this is naming for bit patterns
#NO_REGS = 0
#SRC1_ONLY = 2
#ALL_REGS = 7

# return values from functions of the data spec executor
#END_SPEC_EXECUTOR = -1

TABLE_TYPE = numpy.dtype(
    [("pointer", "<u4"), ("checksum", "<u4"), ("n_words", "<u4")])

